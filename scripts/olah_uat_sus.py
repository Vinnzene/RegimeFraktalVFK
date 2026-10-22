"""Olah hasil UAT dan SUS menjadi tabel Bab 4.11.3.

Protokol dan target: docs/uat_sus/PANDUAN_UAT_SUS.md (ditetapkan sebelum pengujian).

Jalankan:
    python scripts/olah_uat_sus.py \
        --form docs/uat_sus/data/respon_google_form.csv \
        --observasi docs/uat_sus/data/lembar_observasi_terisi.csv

Masukan:
- Ekspor CSV Google Form dari `docs/uat_sus/create_google_form.gs`. Kolom
  dikenali dari kode di awal judul pertanyaan (A2, SUS1..SUS10, SEQ01..SEQ05).
- Lembar observasi (`docs/uat_sus/lembar_observasi.csv`): satu baris per
  responden per tugas; status = berhasil | bantuan | gagal, jawaban_benar = ya | tidak.

Keluaran: <folder --form>/hasil_uat_sus.md
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

TASKS = ["TSK01", "TSK02", "TSK03", "TSK04", "TSK05"]
TASK_LABEL = {
    "TSK01": "Melihat kondisi pasar 1H dan keyakinan",
    "TSK02": "Membandingkan dengan 4H",
    "TSK03": "Membaca saran strategi dan buktinya",
    "TSK04": "Membaca riwayat regime pada grafik",
    "TSK05": "Mengaktifkan notifikasi Telegram",
}
TARGET_SUS = 68.0
TARGET_RATE = 0.80
STATUSES = ("berhasil", "bantuan", "gagal")


def column(df: pd.DataFrame, code: str) -> str:
    """Kolom yang judulnya diawali `code.`; error bila tidak tepat satu."""
    hits = [c for c in df.columns if re.match(rf"^\s*{re.escape(code)}\.", str(c))]
    if len(hits) != 1:
        raise SystemExit(f"kolom untuk kode {code} tidak ditemukan tepat satu: {hits}")
    return hits[0]


def sus_score(row: pd.Series, cols: List[str]) -> float:
    vals = [int(row[c]) for c in cols]
    if any(v < 1 or v > 5 for v in vals):
        raise SystemExit(f"nilai SUS di luar 1–5 pada responden {row.get('kode')}: {vals}")
    odd = sum(v - 1 for v in vals[0::2])
    even = sum(5 - v for v in vals[1::2])
    return (odd + even) * 2.5


def acceptability(score: float) -> str:
    """Bangor, Kortum, & Miller (2008): rentang penerimaan."""
    return "Not acceptable" if score < 50 else ("Marginal" if score <= 70 else "Acceptable")


def adjective(score: float) -> str:
    """Kategori kata sifat terdekat dari rata-rata Bangor dkk. (2009), batas = titik tengah antar-rata-rata."""
    means = [("Worst imaginable", 12.5), ("Awful", 20.3), ("Poor", 35.7), ("OK", 50.9),
             ("Good", 71.4), ("Excellent", 85.5), ("Best imaginable", 100.0)]
    return min(means, key=lambda m: abs(m[1] - score))[0]


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def pct(x: float) -> str:
    return "–" if math.isnan(x) else f"{x * 100:.0f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--form", required=True, type=Path)
    ap.add_argument("--observasi", required=True, type=Path)
    args = ap.parse_args()

    form = pd.read_csv(args.form)
    kode_col = column(form, "A2")
    form["kode"] = form[kode_col].astype(str).str.strip().str.upper()
    if form["kode"].duplicated().any():
        raise SystemExit(f"kode responden ganda di formulir: {form.loc[form['kode'].duplicated(), 'kode'].tolist()}")
    sus_cols = [column(form, f"SUS{i}") for i in range(1, 11)]
    form["sus"] = form.apply(lambda r: sus_score(r, sus_cols), axis=1)

    obs = pd.read_csv(args.observasi, dtype=str).fillna("")
    obs["kode_responden"] = obs["kode_responden"].str.strip().str.upper()
    obs["tugas"] = obs["tugas"].str.strip().str.upper()
    obs["status"] = obs["status"].str.strip().str.lower()
    obs = obs[obs["status"] != ""]
    bad = obs[~obs["status"].isin(STATUSES)]
    if len(bad):
        raise SystemExit(f"status tidak dikenal (harus berhasil/bantuan/gagal): {bad[['kode_responden', 'tugas', 'status']].values.tolist()}")

    missing_obs = sorted(set(form["kode"]) - set(obs["kode_responden"]))
    missing_form = sorted(set(obs["kode_responden"]) - set(form["kode"]))

    s = form["sus"]
    L = ["# Hasil UAT dan SUS", "",
         f"Sumber: `{args.form.as_posix()}` ({len(form)} responden) dan `{args.observasi.as_posix()}`.",
         "Protokol dan target: `docs/uat_sus/PANDUAN_UAT_SUS.md` (ditetapkan sebelum pengujian).", ""]
    if missing_obs or missing_form:
        L += [f"> Peringatan: kode tanpa observasi {missing_obs}; kode tanpa formulir {missing_form}.", ""]

    # Profil responden
    L += ["## Profil responden", ""]
    for code, title in (("A3", "Gaya trading"), ("A4", "Pengalaman")):
        counts = form[column(form, code)].value_counts()
        L.append(f"- **{title}:** " + "; ".join(f"{k} ({v})" for k, v in counts.items()))
    L.append("")

    # SUS
    L += ["## System Usability Scale", "",
          "| Responden | " + " | ".join(f"Q{i}" for i in range(1, 11)) + " | Skor SUS |",
          "|---|" + "---|" * 11]
    for _, r in form.sort_values("kode").iterrows():
        L.append(f"| {r['kode']} | " + " | ".join(str(int(r[c])) for c in sus_cols) + f" | {r['sus']:.1f} |")
    item_means = [form[c].astype(float).mean() for c in sus_cols]
    L.append("| **Rata-rata** | " + " | ".join(f"{m:.1f}" for m in item_means) + f" | **{s.mean():.1f}** |")
    L += ["",
          f"- Rata-rata {s.mean():.1f} (SD {s.std(ddof=1):.1f}), median {s.median():.1f}, rentang {s.min():.1f}–{s.max():.1f}.",
          f"- Rentang penerimaan (Bangor dkk., 2008): **{acceptability(s.mean())}**; kategori kata sifat terdekat (Bangor dkk., 2009): **{adjective(s.mean())}**.",
          f"- Target rata-rata ≥ {TARGET_SUS:.0f}: **{'tercapai' if s.mean() >= TARGET_SUS else 'tidak tercapai'}**.", ""]

    # UAT
    L += ["## User Acceptance Testing", "",
          "| Tugas | n | Berhasil | Dengan bantuan | Gagal | Berhasil tanpa bantuan [CI95 Wilson] | Jawaban benar | Median waktu (detik) | SEQ median (1–7) |",
          "|---|---|---|---|---|---|---|---|---|"]
    targets: Dict[str, Tuple[bool, bool]] = {}
    for t in TASKS:
        o = obs[obs["tugas"] == t]
        n = len(o)
        k = {st: int((o["status"] == st).sum()) for st in STATUSES}
        lo, hi = wilson(k["berhasil"], n)
        rate = k["berhasil"] / n if n else math.nan
        jb = o["jawaban_benar"].str.strip().str.lower()
        correct = (jb == "ya").sum() / (jb != "").sum() if (jb != "").sum() else math.nan
        waktu = pd.to_numeric(o["waktu_detik"], errors="coerce").median()
        seq = form[column(form, f"SEQ0{t[-1]}")].astype(float).median()
        targets[t] = (bool(rate >= TARGET_RATE) if n else False, bool(correct >= TARGET_RATE) if not math.isnan(correct) else False)
        L.append(f"| {t} {TASK_LABEL[t]} | {n} | {k['berhasil']} | {k['bantuan']} | {k['gagal']} | "
                 f"{pct(rate)} [{pct(lo)}, {pct(hi)}] | {pct(correct)} | {'–' if math.isnan(waktu) else f'{waktu:.0f}'} | {seq:.0f} |")
    L += ["", "## Ringkasan terhadap target", "",
          "| Ukuran | Target | Hasil |", "|---|---|---|",
          f"| Rata-rata SUS | ≥ {TARGET_SUS:.0f} | {s.mean():.1f} ({'tercapai' if s.mean() >= TARGET_SUS else 'tidak'}) |"]
    for t in TASKS:
        a, b = targets[t]
        L.append(f"| {t} berhasil tanpa bantuan / jawaban benar | ≥ 80% / ≥ 80% | {'tercapai' if a else 'tidak'} / {'tercapai' if b else 'tidak'} |")

    # Masukan terbuka
    L += ["", "## Masukan terbuka (apa adanya)", ""]
    for code, title in (("D1", "Paling berguna"), ("D2", "Paling membingungkan"), ("D3", "Saran")):
        col = column(form, code)
        L.append(f"**{title}**")
        for _, r in form.sort_values("kode").iterrows():
            v = str(r[col]).strip()
            if v and v.lower() != "nan":
                L.append(f"- {r['kode']}: {v}")
        L.append("")

    out = args.form.parent / "hasil_uat_sus.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"tersimpan: {out}")


if __name__ == "__main__":
    main()

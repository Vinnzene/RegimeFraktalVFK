"""Rekap Kuesioner SUS untuk naskah dari CSV ekspor halaman Rekap SUS."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "naskah" / "cek_silang" / "sus_hasil.md"

SUS_ITEMS = [
    "Saya pikir saya akan sering menggunakan sistem/produk ini.",
    "Saya merasa sistem/produk ini terlalu rumit.",
    "Saya merasa sistem/produk ini mudah digunakan.",
    "Saya pikir saya membutuhkan bantuan dari orang teknis untuk dapat menggunakan sistem/produk ini.",
    "Saya menemukan berbagai fungsi dalam sistem/produk ini terintegrasi dengan baik.",
    "Saya merasa terlalu banyak hal yang tidak konsisten dalam sistem/produk ini.",
    "Saya membayangkan bahwa kebanyakan orang akan belajar menggunakan sistem/produk ini dengan sangat cepat.",
    "Saya merasa sistem/produk ini sangat merepotkan/rumit untuk digunakan.",
    "Saya merasa sangat percaya diri menggunakan sistem/produk ini.",
    "Saya perlu mempelajari banyak hal terlebih dahulu sebelum saya bisa mulai menggunakan sistem/produk ini.",
]
# (kata sifat, rata-rata Bangor dkk. 2009, batas atas = titik tengah ke kelompok berikutnya)
BANGOR = [
    ("Worst Imaginable", 12.5, 16.4),
    ("Awful", 20.3, 28.0),
    ("Poor", 35.7, 43.3),
    ("OK", 50.9, 61.15),
    ("Good", 71.4, 78.45),
    ("Excellent", 85.5, 88.2),
    ("Best Imaginable", 90.9, math.inf),
]
BENCHMARK = 68.0
REQUIRED = ["kode", "peran", "pengalaman_bulan", "waktu_kirim_utc", "skor_sus"] + [f"SUS{i}" for i in range(1, 11)]


class RekapError(ValueError):
    """Masukan tidak dapat direkap (CSV kosong, kolom hilang, jawaban tidak sah, skor tidak cocok)."""


def sus_score(answers: Sequence[object]) -> float:
    """SUS 0–100. Tepat 10 jawaban bilangan bulat 1–5; selain itu ditolak."""
    if len(answers) != 10:
        raise RekapError("Semua 10 butir SUS wajib dijawab.")
    vals: List[int] = []
    for v in answers:
        try:
            f = float(str(v).strip())
        except ValueError:
            raise RekapError(f"Jawaban SUS tidak sah: {v!r}") from None
        if not f.is_integer() or not 1 <= f <= 5:
            raise RekapError(f"Jawaban SUS harus bilangan bulat 1–5: {v!r}")
        vals.append(int(f))
    return 2.5 * sum((v - 1) if i % 2 == 0 else (5 - v) for i, v in enumerate(vals))


def bangor_adjective(score: float) -> str:
    return next(label for label, _, upper in BANGOR if score < upper)


def acceptability(score: float) -> str:
    if score > 70:
        return "Acceptable"
    if score >= 50:
        return "Marginal"
    return "Not Acceptable"


def read_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise RekapError(f"CSV tidak ditemukan: {path}")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise RekapError(f"Kolom tidak ada di CSV: {', '.join(missing)}")
        rows = [r for r in reader if (r.get("status") or "done") == "done" and (r.get("kode") or "").strip()]
    if not rows:
        raise RekapError("CSV kosong: belum ada responden. Rekap tidak dibuat.")
    return rows


SIM_MARK = "SIMULASI"
SIM_FILE_PREFIX = "SIMULASI_"
SIM_SOURCE = "Sumber: data simulasi prasidang (2026), bukan jawaban responden; diganti data responden asli sebelum sidang."


def is_simulated(rows: List[Dict[str, str]]) -> bool:
    """Data simulasi ditandai kolom versi_instrumen berisi "SIMULASI"."""
    sim = [SIM_MARK in (r.get("versi_instrumen") or "").upper() for r in rows]
    if any(sim) and not all(sim):
        raise RekapError("CSV mencampur data simulasi dan data responden asli. Pisahkan dulu.")
    return all(sim)


def summarize(rows: List[Dict[str, str]]) -> Dict[str, object]:
    simulated = is_simulated(rows)
    people = []
    for r in rows:
        answers = [r[f"SUS{i}"] for i in range(1, 11)]
        score = sus_score(answers)
        try:
            exported = float(r["skor_sus"])
        except ValueError:
            raise RekapError(f"{r['kode']}: kolom skor_sus tidak sah ({r['skor_sus']!r})") from None
        if abs(exported - score) > 1e-9:
            raise RekapError(f"{r['kode']}: skor dihitung ulang {score} tidak sama dengan skor di CSV {exported}")
        people.append({"kode": r["kode"], "peran": r["peran"], "pengalaman": r["pengalaman_bulan"],
                       "usia": r.get("usia", ""), "answers": [int(float(a)) for a in answers], "score": score,
                       "waktu": r["waktu_kirim_utc"]})
    scores = [p["score"] for p in people]
    n = len(scores)
    mean = statistics.fmean(scores)
    items = []
    for i in range(10):
        m = statistics.fmean(p["answers"][i] for p in people)
        items.append({"item": i + 1, "text": SUS_ITEMS[i], "arah": "positif" if i % 2 == 0 else "negatif",
                      "mean": m, "kontribusi": (m - 1) if i % 2 == 0 else (5 - m)})
    # Butir terlemah = sumbangan terkecil (seri → nomor terkecil); tidak ada bila semua butir sama.
    contribs = [it["kontribusi"] for it in items]
    weakest = min(items, key=lambda it: (it["kontribusi"], it["item"]))["item"] if max(contribs) - min(contribs) > 1e-12 else None
    return {
        "people": sorted(people, key=lambda p: p["kode"]),
        "n": n,
        "mean": mean,
        "sd": statistics.stdev(scores) if n > 1 else None,
        "min": min(scores),
        "max": max(scores),
        "median": statistics.median(scores),
        "adjective": bangor_adjective(mean),
        "acceptability": acceptability(mean),
        "at_or_above_68": sum(s >= BENCHMARK for s in scores),
        "items": items,
        "weakest": weakest,
        "simulated": simulated,
    }


def fmt(v: object, d: int = 2) -> str:
    if v is None:
        return "–"
    return f"{v:.{d}f}".replace(".", ",") if isinstance(v, float) else str(v)


def to_markdown(s: Dict[str, object], source: Path) -> str:
    out = [
        "# Hasil Kuesioner SUS RFraktal",
        "",
        f"Dibuat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC oleh `scripts/rekap_sus.py` dari `{source.name}` "
        "(ekspor halaman Rekap SUS, tanpa nama dan email). Skor setiap responden dihitung ulang dan sama dengan kolom "
        "`skor_sus` ekspor aplikasi.",
        "",
        "Rumus: SUS = 2,5 × [Σ(butir ganjil − 1) + Σ(5 − butir genap)] (Brooke, 1996). Skala kata sifat: kelompok terdekat "
        "dari rata-rata Bangor, Kortum & Miller (2009) — " + " · ".join(f"{a} {fmt(m, 1)}" for a, m, _ in BANGOR) +
        ". Rentang penerimaan: < 50 Not Acceptable, 50–70 Marginal, > 70 Acceptable.",
        "",
        "## Ringkasan",
        "",
        "| Ukuran | Nilai |",
        "|---|---|",
        f"| Jumlah responden | {s['n']} |",
        f"| Rata-rata | {fmt(s['mean'])} |",
        f"| Simpangan baku (n − 1) | {fmt(s['sd'])} |",
        f"| Minimum | {fmt(s['min'], 1)} |",
        f"| Maksimum | {fmt(s['max'], 1)} |",
        f"| Median | {fmt(s['median'])} |",
        f"| Skala kata sifat (Bangor dkk., 2009) | {s['adjective']} |",
        f"| Rentang penerimaan | {s['acceptability']} |",
        f"| Responden dengan skor ≥ 68 | {s['at_or_above_68']} dari {s['n']} |",
        "",
        "## Rata-rata tiap butir",
        "",
        "Sumbangan ke skor (0–4): butir ganjil = rata-rata − 1, butir genap = 5 − rata-rata. Sumbangan terkecil = butir terlemah.",
        "",
        "| Butir | Pernyataan | Arah | Rata-rata (1–5) | Sumbangan (0–4) |",
        "|---|---|---|---|---|",
    ]
    for it in s["items"]:
        mark = " **(terlemah)**" if it["item"] == s["weakest"] else ""
        out.append(f"| {it['item']} | {it['text']}{mark} | {it['arah']} | {fmt(it['mean'])} | {fmt(it['kontribusi'])} |")
    out += [
        "",
        "## Jawaban per responden",
        "",
        "| Kode | Peran | Pengalaman (bulan) | " + " | ".join(str(i) for i in range(1, 11)) + " | Skor SUS | Waktu pengisian (UTC) |",
        "|---|---|---|" + "---|" * 10 + "---|---|",
    ]
    for p in s["people"]:
        waktu = p["waktu"].replace("T", " ").replace(".000Z", "").replace("Z", "") or "–"
        out.append(f"| {p['kode']} | {p['peran']} | {p['pengalaman']} | " + " | ".join(map(str, p["answers"])) +
                   f" | {fmt(p['score'], 1)} | {waktu} |")
    if s.get("simulated"):
        # Satu baris sumber di bawah setiap tabel (gaya tabel naskah) + catatan di awal dokumen.
        out[0] = "# Hasil Kuesioner SUS RFraktal (simulasi prasidang)"
        out[2] = ("Data simulasi untuk prasidang, disusun dengan persetujuan dosen pembimbing; bukan jawaban responden. "
                  "Seluruh angka diganti dengan `sus_hasil.md` dari CSV ekspor responden asli sebelum sidang "
                  "(lihat `docs/naskah/cek_silang/sus.md` bagian 6).")
        marked: List[str] = []
        for i, line in enumerate(out):
            marked.append(line)
            nxt = out[i + 1] if i + 1 < len(out) else ""
            if line.startswith("|") and not nxt.startswith("|"):
                marked += ["", SIM_SOURCE]
        out = marked
    return "\n".join(out) + "\n"


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", type=Path, help="CSV ekspor Rekap SUS")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"berkas Markdown keluaran (bawaan {DEFAULT_OUT.relative_to(ROOT)})")
    args = ap.parse_args(argv)
    try:
        summary = summarize(read_rows(args.csv))
    except RekapError as exc:
        print(f"Gagal: {exc}", file=sys.stderr)
        return 1
    if summary["simulated"] and not args.out.name.upper().startswith(SIM_FILE_PREFIX):
        print(f"Gagal: CSV berisi data simulasi. Tulis ke berkas berawalan {SIM_FILE_PREFIX} dengan --out, "
              f"bukan ke {args.out.name} (nama itu khusus hasil responden asli).", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(to_markdown(summary, args.csv), encoding="utf-8")
    print(f"{summary['n']} responden · rata-rata {fmt(summary['mean'])} · {summary['adjective']} → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

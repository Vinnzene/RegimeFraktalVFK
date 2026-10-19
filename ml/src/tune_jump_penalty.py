"""Pemilihan jump penalty λ untuk Statistical Jump Model.

Jalankan:
    python ml/src/tune_jump_penalty.py --timeframe 1h

λ mengatur keseimbangan antara kesetiaan pada data dan kestabilan label.
Terlalu kecil: label berkedip seperti metode ambang. Terlalu besar: seluruh
deret runtuh menjadi satu state dan label kehilangan daya beda.

Tiga kriteria dilaporkan agar pemilihan tidak bergantung satu angka saja:

1. **Durasi run** — berapa window regime bertahan sebelum berganti. Target
   wajar untuk data 1H dengan stride 4 bar adalah puluhan window, bukan 1-2.
2. **Keseimbangan kelas** — entropi distribusi. Nilai mendekati nol berarti
   satu kelas mendominasi dan sisanya hampir kosong.
3. **Kesesuaian dengan nilai eksponen** — apakah urutan rata-rata Hurst antar
   state tetap monoton. Bila tidak, penamaan regime kehilangan makna.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import ARTIFACTS_DIR, REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.jump_model import label_with_jump_model  # noqa: E402

# Urutan menaik menurut Hurst: state terendah = anti-persistent.
ORDERED_CLASSES = ["anti_persistent", "random_like", "persistent"]


def entropy(labels) -> float:
    """Entropi distribusi kelas, dinormalisasi ke [0, 1]."""
    n = len(labels)
    if n == 0:
        return 0.0
    counts = np.array(list(Counter(labels).values()), dtype=float)
    p = counts / counts.sum()
    h = -(p * np.log(p + 1e-12)).sum()
    return float(h / np.log(len(ORDERED_CLASSES)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid search jump penalty")
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument(
        "--penalties",
        type=float,
        nargs="+",
        default=[0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0],
    )
    args = parser.parse_args()

    cfg = get_config()
    repo = get_repository()
    df = repo.get_regime(args.symbol, args.timeframe)
    h = df["hurst"].to_numpy()
    a = df["dfa_alpha"].to_numpy()

    print(f"Timeframe {args.timeframe} — {len(df)} window")
    print(f"stride {int(df['stride_bars'].iloc[0])} bar, L={int(df['effective_window'].iloc[0])}")
    print()

    # Pembanding: labeling ambang yang dipakai sekarang.
    lama = df["regime"].tolist()
    sw_lama = sum(1 for x, y in zip(lama[:-1], lama[1:]) if x != y)
    runs_lama = []
    cur, ln = lama[0], 1
    for lab in lama[1:]:
        if lab == cur:
            ln += 1
        else:
            runs_lama.append(ln)
            cur, ln = lab, 1
    runs_lama.append(ln)
    print("Metode sekarang (ambang kuantil):")
    print(
        "  durasi rata-rata %.2f window | %d perpindahan | %d kelas terpakai"
        % (np.mean(runs_lama), sw_lama, len(set(lama)))
    )
    print()

    print(
        "%8s %10s %10s %9s %9s %8s %s"
        % ("lambda", "durasi", "median", "switch", "entropi", "monoton", "distribusi")
    )
    print("-" * 92)

    hasil: List[Dict[str, Any]] = []
    for lam in args.penalties:
        r = label_with_jump_model(h, a, ORDERED_CLASSES, jump_penalty=lam, seed=cfg.model.seed)
        labels = r["labels"]
        dist = Counter(labels)
        centers = np.array(r["centers"])
        monoton = bool(np.all(np.diff(centers[:, 0]) > 0))
        ent = entropy(labels)

        share = " ".join(
            f"{c[:4]}={100 * dist.get(c, 0) / len(labels):.0f}%" for c in ORDERED_CLASSES
        )
        print(
            "%8.1f %10.2f %10.1f %9d %9.3f %8s %s"
            % (lam, r["mean_run_length"], r["median_run_length"], r["n_switches"], ent,
               "ya" if monoton else "TIDAK", share)
        )

        hasil.append(
            {
                "jump_penalty": lam,
                "mean_run_length": r["mean_run_length"],
                "median_run_length": r["median_run_length"],
                "n_switches": r["n_switches"],
                "n_runs": r["n_runs"],
                "entropy": round(ent, 4),
                "monotonic": monoton,
                "distribution": {c: dist.get(c, 0) for c in ORDERED_CLASSES},
                "centers_hurst": [round(float(x), 4) for x in centers[:, 0]],
                "centers_dfa": [round(float(x), 4) for x in centers[:, 1]],
                "objective": round(float(r["objective"]), 2),
            }
        )

    # Pemilihan λ tidak boleh sekadar mengejar durasi terpanjang: menaikkan λ
    # selalu memperpanjang run, hingga akhirnya satu kelas menelan sisanya.
    # Dipakai tiga syarat sekaligus.
    #
    #   1. Urutan Hurst antar-state monoton — penamaan regime tetap bermakna.
    #   2. Entropi tinggi — distribusi kelas tidak timpang.
    #   3. Tidak ada kelas yang porsinya ekstrem.
    #
    # Di antara yang lolos, dipilih titik dengan penurunan switch per satuan λ
    # yang sudah melandai (siku kurva) — melewati titik itu, tambahan
    # kestabilan dibayar dengan hilangnya daya beda.
    def porsi_maks(x: dict) -> float:
        total = sum(x["distribution"].values()) or 1
        return max(x["distribution"].values()) / total

    layak = [
        x
        for x in hasil
        if x["monotonic"] and x["entropy"] >= 0.90 and porsi_maks(x) <= 0.60
    ]

    pilihan = None
    if layak:
        # Cari siku: rasio pengurangan switch terhadap kenaikan λ.
        best_score = -np.inf
        for i, x in enumerate(layak):
            if x["jump_penalty"] <= 0:
                continue
            prev = layak[i - 1] if i > 0 else hasil[0]
            drop = prev["n_switches"] - x["n_switches"]
            cost = max(x["jump_penalty"] - prev["jump_penalty"], 1e-9)
            # Manfaat marginal: berapa banyak switch hilang per satuan λ,
            # ditimbang durasi agar λ sangat kecil tidak menang otomatis.
            score = (drop / cost) * np.log1p(x["mean_run_length"])
            if score > best_score:
                best_score, pilihan = score, x

    print()
    if pilihan:
        base = float(np.mean(runs_lama))
        print(
            "Rekomendasi: lambda=%.1f  durasi %.2f window (ambang: %.2f, naik %.1fx)"
            % (
                pilihan["jump_penalty"],
                pilihan["mean_run_length"],
                base,
                pilihan["mean_run_length"] / base if base else 0,
            )
        )
        print(
            "  perpindahan %d (ambang: %d)  entropi %.3f  porsi kelas terbesar %.0f%%"
            % (pilihan["n_switches"], sw_lama, pilihan["entropy"], 100 * porsi_maks(pilihan))
        )
        print(
            "  Kriteria: monoton, entropi >= 0.90, tidak ada kelas > 60%, "
            "lalu titik siku kurva switch-vs-lambda."
        )
    else:
        print("Tidak ada lambda yang memenuhi kriteria; periksa rentang grid.")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / f"jump_penalty_tuning_{args.timeframe}.json"
    out.write_text(
        json.dumps(
            {
                "timeframe": args.timeframe,
                "config_hash": cfg.config_hash,
                "baseline_threshold": {
                    "mean_run_length": round(float(np.mean(runs_lama)), 2),
                    "n_switches": sw_lama,
                },
                "results": hasil,
                "recommended": pilihan,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nDisimpan: {out.name}")


if __name__ == "__main__":
    main()

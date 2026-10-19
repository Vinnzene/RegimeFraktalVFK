"""Langkah 7 — Validasi walk-forward + confusion matrix agregat.

Jalankan:
    python ml/src/walk_forward_study.py --timeframe 1h
    python ml/src/walk_forward_study.py --timeframe 1h --binary
    python ml/src/walk_forward_study.py --timeframe 1h --labeling jump

Model dilatih ULANG pada tiap fold, lalu seluruh prediksi digabung menjadi satu
confusion matrix. Ini menjawab pertanyaan yang tidak dapat dijawab split
tunggal: apakah performa bertahan sepanjang rentang data, atau hanya kebetulan
baik di satu periode.

Pengklasifikasi memakai ExtraTrees pada fitur struktural — bukan
Attention-BiLSTM — karena walk-forward memerlukan pelatihan ulang pada tiap
fold. Melatih jaringan saraf lima kali memakan waktu sangat lama, sementara
tujuan pengujian di sini adalah kestabilan LABELING dan FITUR lintas periode,
bukan mencari akurasi tertinggi mutlak.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, cast

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sklearn.ensemble import ExtraTreesClassifier  # noqa: E402

from app.core.config import ARTIFACTS_DIR, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.hurst_dfa import to_log_return  # noqa: E402
from app.services.jump_model import label_with_jump_model  # noqa: E402
from app.services.splitting import bars_to_rows  # noqa: E402
from app.services.structural_features import build_feature_matrix  # noqa: E402
from app.services.walk_forward import run_walk_forward  # noqa: E402

ORDERED_CLASSES = ["anti_persistent", "random_like", "persistent"]
BINARY_CLASSES = ["anti_persistent", "persistent"]


def make_fit_predict(seed: int):
    """Pengklasifikasi dilatih ulang pada tiap fold.

    Penskalaan dipasang dari data latih fold itu saja. Menghitungnya sekali di
    luar loop akan memakai statistik periode uji — kebocoran halus yang tidak
    memunculkan error apa pun.
    """

    def fit_predict(
        X_tr: np.ndarray, y_tr: Sequence[str], X_te: np.ndarray
    ) -> List[str]:
        mean = X_tr.mean(axis=0)
        std = X_tr.std(axis=0)
        std[std < 1e-12] = 1.0
        model = ExtraTreesClassifier(
            n_estimators=400, random_state=seed, n_jobs=-1, min_samples_leaf=2
        )
        model.fit((X_tr - mean) / std, list(y_tr))
        return [str(p) for p in model.predict((X_te - mean) / std)]

    return fit_predict


def main() -> None:
    parser = argparse.ArgumentParser(description="Validasi walk-forward")
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--splits", type=int, default=5)
    parser.add_argument("--binary", action="store_true")
    parser.add_argument(
        "--labeling",
        default="threshold",
        choices=["threshold", "jump"],
        help="threshold = ambang kuantil; jump = Statistical Jump Model",
    )
    parser.add_argument("--jump-penalty", type=float, default=0.5)
    parser.add_argument(
        "--scheme", default="both", choices=["expanding", "rolling", "both"]
    )
    args = parser.parse_args()

    cfg = get_config()
    repo = get_repository()
    df = repo.get_regime(args.symbol, args.timeframe)
    ohlcv = repo.get_ohlcv(args.symbol, args.timeframe)
    log_ret = to_log_return(ohlcv["close"].to_numpy())

    positions = df["index"].astype(int).tolist()
    window = int(df["effective_window"].iloc[0])
    stride = int(df["stride_bars"].iloc[0])

    print(f"[{args.timeframe}] {len(df)} window, L={window}, stride={stride} bar")
    print("Membangun fitur struktural...")
    t0 = time.time()
    X = build_feature_matrix(log_ret, positions, window=window, swt_level=cfg.analysis.J)
    print(f"  selesai {time.time() - t0:.0f}s, dim={X.shape[1]}")

    classes = BINARY_CLASSES if args.binary else ORDERED_CLASSES
    labels: List[str]
    if args.labeling == "jump":
        jm = label_with_jump_model(
            df["hurst"].astype(float).tolist(),
            df["dfa_alpha"].astype(float).tolist(),
            ORDERED_CLASSES,
            jump_penalty=args.jump_penalty,
            seed=cfg.model.seed,
        )
        labels = cast(List[str], jm["labels"])
        info_label = f"jump (lambda={args.jump_penalty}, durasi {jm['mean_run_length']})"
    else:
        labels = [str(x) for x in df["regime"].tolist()]
        info_label = "ambang kuantil"

    n_valid = sum(1 for l in labels if l in classes)
    print(f"Labeling : {info_label}")
    print(f"Kelas    : {classes}  ({n_valid} window berlabel)")

    # Purge dalam satuan BARIS window, bukan bar.
    purge_rows = bars_to_rows(cfg.analysis.L, stride)
    print(f"Purge    : {purge_rows} baris ({cfg.analysis.L} bar)")
    print()

    schemes = ["expanding", "rolling"] if args.scheme == "both" else [args.scheme]
    hasil: Dict[str, Any] = {}

    for scheme in schemes:
        print(f"--- skema {scheme} ---")
        t0 = time.time()
        res: Dict[str, Any] = run_walk_forward(
            X,
            labels,
            classes,
            make_fit_predict(cfg.model.seed),
            n_splits=args.splits,
            purge=purge_rows,
            scheme=scheme,
        )
        if not res.get("available"):
            print(f"  dilewati: {res.get('reason')}")
            continue

        agg = res["aggregate"]
        st = res["stability"]
        print(f"  {res['n_splits']} fold, {time.time() - t0:.0f}s")
        print("  %-6s %8s %8s %9s %9s" % ("fold", "n_train", "n_test", "akurasi", "macroF1"))
        for f in res["folds"]:
            print(
                "  %-6d %8d %8d %9.4f %9.4f"
                % (f["fold"], f["n_train"], f["n_test"], f["accuracy"], f["macro_f1"])
            )
        print(
            "  AGREGAT      akurasi=%.4f  BA=%.4f  macroF1=%.4f  (n=%d)"
            % (agg["accuracy"], agg["balanced_accuracy"], agg["macro_f1"], agg["n"])
        )
        print(
            "  kestabilan   akurasi %.4f +/- %.4f  (min %.4f, maks %.4f)"
            % (
                st["accuracy_mean"],
                st["accuracy_std"],
                st["accuracy_min"],
                st["accuracy_max"],
            )
        )
        print()
        for p in agg["per_class"]:
            print(
                "    %-18s P=%.3f R=%.3f F1=%.3f (n=%d)"
                % (p["regime"], p["precision"], p["recall"], p["f1"], p["support"])
            )
        print()
        hasil[scheme] = res

    mode = "binary" if args.binary else "multiclass"
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / f"walk_forward_{args.timeframe}_{mode}_{args.labeling}.json"
    out.write_text(
        json.dumps(
            {
                "timeframe": args.timeframe,
                "mode": mode,
                "labeling": args.labeling,
                "jump_penalty": args.jump_penalty if args.labeling == "jump" else None,
                "classes": classes,
                "config_hash": cfg.config_hash,
                "purge_rows": purge_rows,
                "n_windows": len(df),
                "schemes": hasil,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Disimpan: {out.name}")


if __name__ == "__main__":
    main()

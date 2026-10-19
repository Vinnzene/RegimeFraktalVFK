"""Analisis sensitivitas horizon prediksi.

Menjawab pertanyaan yang hampir pasti muncul saat sidang: apakah daya prediksi
model menurun seiring jauhnya horizon? Kalau ya, seberapa cepat?

Jalankan:
    python ml/src/horizon_study.py --timeframe 1h --horizons 125 250 500 1000

Setiap horizon dilatih dari awal dengan konfigurasi identik kecuali `h`, lalu
dibandingkan terhadap Baseline Persistence pada horizon yang sama. Membandingkan
lintas horizon tanpa baseline per-horizon akan menyesatkan: regime bertahan lebih
lama pada horizon pendek, sehingga tebakan naif pun otomatis lebih baik di sana.

Hasil disimpan ke ml/artifacts/horizon_study_<tf>.json dan dibaca oleh endpoint
/api/v1/model/horizon-study.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, cast

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.model_registry import (  # noqa: E402
    balanced_accuracy,
    matthews_corrcoef,
)
from dataset import build_dataset  # noqa: E402
from train import class_weights, persistence_baseline  # noqa: E402


def evaluate(model, X: np.ndarray, y: np.ndarray) -> Dict[str, object]:
    if len(X) == 0:
        return {"n": 0}
    probs = model.predict(X, batch_size=256, verbose=0)
    pred = [REGIME_CLASSES[i] for i in probs.argmax(axis=1)]
    true = [REGIME_CLASSES[i] for i in y.argmax(axis=1)]
    return {
        "n": len(X),
        "balanced_accuracy": balanced_accuracy(true, pred),
        "mcc": matthews_corrcoef(true, pred),
        "mean_max_prob": float(round(probs.max(axis=1).mean(), 4)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sensitivitas horizon prediksi")
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=[125, 250, 500, 1000],
        help="Daftar horizon dalam satuan BAR",
    )
    parser.add_argument(
        "--model",
        default="swt_attention_bilstm",
        choices=["swt_bilstm", "swt_attention_bilstm"],
    )
    parser.add_argument("--seq-len", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    import tensorflow as tf  # type: ignore

    from model_architecture import (
        build_swt_attention_bilstm,
        build_swt_bilstm,
        compile_model,
    )

    cfg = get_config()
    close = get_repository().get_ohlcv(args.symbol, args.timeframe)["close"].to_numpy()
    bars_per_day = 24 if args.timeframe == "1h" else 6

    results: List[Dict[str, Any]] = []
    for h in args.horizons:
        print(f"\n=== h = {h} bar (~{h / bars_per_day:.1f} hari) ===")
        tf.keras.utils.set_random_seed(cfg.model.seed)

        started = time.time()
        data = build_dataset(
            close, seq_len=args.seq_len, h_bars=h, with_structural=False
        )
        X_tr, _, y_tr = data["train"]  # type: ignore[misc]
        X_va, _, y_va = data["validation"]  # type: ignore[misc]
        X_te, _, y_te = data["test"]  # type: ignore[misc]

        if len(X_tr) == 0 or len(X_te) == 0:
            print("  dilewati: dataset kosong pada horizon ini")
            continue

        baseline = persistence_baseline(data["labels"], data["targets"])
        print(f"  train={X_tr.shape[0]} val={X_va.shape[0]} test={X_te.shape[0]}")
        print(f"  baseline BA={baseline.get('balanced_accuracy')}")

        builder = (
            build_swt_attention_bilstm
            if args.model == "swt_attention_bilstm"
            else build_swt_bilstm
        )
        model = compile_model(builder(input_shape=X_tr.shape[1:]))
        model.fit(
            X_tr,
            y_tr,
            validation_data=(X_va, y_va) if len(X_va) else None,
            epochs=args.epochs,
            batch_size=args.batch_size,
            class_weight=class_weights(y_tr),
            callbacks=[
                tf.keras.callbacks.EarlyStopping(
                    monitor="val_loss" if len(X_va) else "loss",
                    patience=8,
                    restore_best_weights=True,
                )
            ],
            verbose=0,
        )

        test_metrics = evaluate(model, X_te, y_te)
        # Selisih terhadap baseline pada horizon yang SAMA — ini angka yang
        # sebanding antar horizon, bukan BA mentahnya.
        lift = None
        if test_metrics.get("balanced_accuracy") is not None and baseline.get(
            "balanced_accuracy"
        ):
            lift = round(
                float(cast(Any, test_metrics)["balanced_accuracy"]) - float(cast(Any, baseline)["balanced_accuracy"]),
                4,
            )

        entry = {
            "h_bars": h,
            "h_days": round(h / bars_per_day, 2),
            "h_windows": data["h_windows"],
            "n_train": len(X_tr),
            "n_test": len(X_te),
            "test": test_metrics,
            "baseline": baseline,
            "lift_over_baseline": lift,
            "seconds": round(time.time() - started, 1),
        }
        results.append(entry)
        print(
            f"  test BA={test_metrics.get('balanced_accuracy')} "
            f"MCC={test_metrics.get('mcc')} lift={lift}"
        )

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / f"horizon_study_{args.timeframe}.json"
    out.write_text(
        json.dumps(
            {
                "timeframe": args.timeframe,
                "model": args.model,
                "config_hash": cfg.config_hash,
                "seq_len": args.seq_len,
                "bars_per_day": bars_per_day,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nRingkasan ({args.model}, {args.timeframe}):")
    print(f"{'h (bar)':>9} {'hari':>7} {'test BA':>9} {'baseline':>9} {'selisih':>9}")
    for r in results:
        print(
            "%9d %7.1f %9s %9s %9s"
            % (
                r["h_bars"],
                r["h_days"],
                r["test"].get("balanced_accuracy"),
                r["baseline"].get("balanced_accuracy"),
                r["lift_over_baseline"],
            )
        )
    print(f"\nDisimpan: {out}")


if __name__ == "__main__":
    main()

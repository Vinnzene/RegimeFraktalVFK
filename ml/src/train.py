"""Training offline. Backend TIDAK pernah menjalankan file ini saat request.

Jalankan:
    python ml/src/train.py --timeframe 1h --model swt_attention_bilstm

Artefak disimpan ke ml/artifacts/<model>_<tf>.keras beserta metadata berisi
config_hash, sehingga hasil di dashboard bisa ditelusuri ke konfigurasi yang
menghasilkannya.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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


def class_weights(y: np.ndarray) -> dict:
    """Bobot berbanding terbalik dengan frekuensi kelas.

    Distribusi regime tidak seimbang; tanpa bobot, model cenderung menebak
    kelas mayoritas dan balanced accuracy-nya runtuh.
    """
    counts = y.sum(axis=0)
    total = counts.sum()
    n_classes = len(counts)
    return {
        i: float(total / (n_classes * c)) if c > 0 else 1.0
        for i, c in enumerate(counts)
    }


def evaluate_split(model, X: np.ndarray, y: np.ndarray) -> dict:
    if len(X) == 0:
        return {"n": 0}
    probs = model.predict(X, verbose=0)
    pred = [REGIME_CLASSES[i] for i in probs.argmax(axis=1)]
    true = [REGIME_CLASSES[i] for i in y.argmax(axis=1)]
    return {
        "n": int(len(X)),
        "balanced_accuracy": balanced_accuracy(true, pred),
        "mcc": matthews_corrcoef(true, pred),
        "plain_accuracy": float(round(np.mean([t == p for t, p in zip(true, pred)]), 4)),
    }


def persistence_baseline(labels, targets) -> dict:
    """Ambang minimum: prediksi regime t+h dengan regime pada t."""
    pairs = [
        (t, p)
        for t, p in zip(targets, labels)
        if t in REGIME_CLASSES and p in REGIME_CLASSES
    ]
    if not pairs:
        return {"n": 0}
    true = [t for t, _ in pairs]
    pred = [p for _, p in pairs]
    return {
        "n": len(pairs),
        "balanced_accuracy": balanced_accuracy(true, pred),
        "mcc": matthews_corrcoef(true, pred),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Training model regime fraktal")
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument(
        "--model",
        default="swt_attention_bilstm",
        choices=["swt_bilstm", "swt_attention_bilstm", "both"],
    )
    parser.add_argument("--seq-len", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    import tensorflow as tf  # import lokal: backend tidak pernah butuh TF

    from model_architecture import (
        build_swt_attention_bilstm,
        build_swt_bilstm,
        compile_model,
    )

    cfg = get_config()
    tf.keras.utils.set_random_seed(cfg.model.seed)

    close = get_repository().get_ohlcv(args.symbol, args.timeframe)["close"].to_numpy()
    print(f"[{args.timeframe}] menyiapkan dataset dari {len(close)} bar...")
    data = build_dataset(close, seq_len=args.seq_len)

    # build_dataset mengembalikan (sekuens, fitur struktural, target). Skrip ini
    # memakai jalur sekuens saja — fitur struktural dipakai oleh
    # train_identification.py.
    X_tr, _, y_tr = data["train"]  # type: ignore[misc]
    X_va, _, y_va = data["validation"]  # type: ignore[misc]
    X_te, _, y_te = data["test"]  # type: ignore[misc]

    print(f"  train={X_tr.shape}  val={X_va.shape}  test={X_te.shape}")
    print(f"  h={cfg.model.h} bar = {data['h_windows']} window (stride {data['stride_bars']} bar)")
    if len(X_tr) == 0:
        raise SystemExit("Dataset training kosong. Periksa L, h, dan panjang data.")

    baseline = persistence_baseline(data["labels"], data["targets"])
    print(f"  Baseline Persistence: BA={baseline.get('balanced_accuracy')} MCC={baseline.get('mcc')}")

    targets = ["swt_bilstm", "swt_attention_bilstm"] if args.model == "both" else [args.model]
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    for model_key in targets:
        print(f"\n--- {model_key} ---")
        builder = (
            build_swt_attention_bilstm
            if model_key == "swt_attention_bilstm"
            else build_swt_bilstm
        )
        model = compile_model(builder(input_shape=X_tr.shape[1:]))

        history = model.fit(
            X_tr,
            y_tr,
            validation_data=(X_va, y_va) if len(X_va) else None,
            epochs=args.epochs,
            batch_size=args.batch_size,
            class_weight=class_weights(y_tr),
            callbacks=[
                tf.keras.callbacks.EarlyStopping(
                    monitor="val_loss" if len(X_va) else "loss",
                    patience=10,
                    restore_best_weights=True,
                ),
                tf.keras.callbacks.ReduceLROnPlateau(
                    monitor="val_loss" if len(X_va) else "loss",
                    factor=0.5,
                    patience=5,
                    min_lr=1e-5,
                ),
            ],
            verbose=2,
        )

        out = ARTIFACTS_DIR / f"{model_key}_{args.timeframe}.keras"
        model.save(out)

        metrics = {
            "validation": evaluate_split(model, X_va, y_va),
            "test": evaluate_split(model, X_te, y_te),
            "baseline_persistence": baseline,
        }
        print(f"  val : {metrics['validation']}")
        print(f"  test: {metrics['test']}")

        meta = {
            "model": model_key,
            "timeframe": args.timeframe,
            "config_hash": cfg.config_hash,
            "seq_len": args.seq_len,
            "h_bars": cfg.model.h,
            "h_windows": data["h_windows"],
            "stride_bars": data["stride_bars"],
            "effective_window": data["effective_window"],
            "threshold_mode": cfg.analysis.threshold_mode,
            # Scaler wajib ikut disimpan: inference harus memakai statistik yang
            # sama persis dengan training, dan statistik itu berasal dari subset
            # training saja.
            "scaler": data["scaler"],
            "n_train": int(len(X_tr)),
            "n_val": int(len(X_va)),
            "n_test": int(len(X_te)),
            "epochs_ran": len(history.history.get("loss", [])),
            "metrics": metrics,
            "history": {k: [float(x) for x in v] for k, v in history.history.items()},
        }
        (ARTIFACTS_DIR / f"{model_key}_{args.timeframe}.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        print(f"  artefak: {out.name}")


if __name__ == "__main__":
    main()

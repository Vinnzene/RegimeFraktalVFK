"""Training tugas IDENTIFIKASI regime.

Berbeda dari `train.py` yang memprediksi regime h bar ke depan, skrip ini
menjawab pertanyaan yang sesuai judul penelitian: *window ini regimenya apa?*

    python ml/src/train_identification.py --timeframe 1h
    python ml/src/train_identification.py --timeframe 1h --binary

Catatan metodologis penting
---------------------------
Hurst dan DFA TIDAK boleh menjadi fitur. Label regime dibentuk dari keduanya
lewat aturan ambang, sehingga memberikannya sebagai input membuat model sekadar
menghafal aturan if-else — label sirkular. Pengujian memberi balanced accuracy
~0.99 dengan cara itu, dan angka tersebut tidak membuktikan apa pun.

Fitur yang dipakai berkaitan dengan persistensi secara teoretis tetapi dihitung
berbeda: variance ratio, autokorelasi multi-lag, rasio energi antar-skala.

Mode biner (`--binary`) membandingkan hanya persistent lawan anti-persistent.
Kelas random_like dikeluarkan karena batasnya memang kabur secara definisi —
ia dinyatakan sebagai "tidak persisten dan tidak anti-persisten".
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
from train import class_weights  # noqa: E402

BINARY_CLASSES = ["persistent", "anti_persistent"]


def evaluate(model, inputs, y, classes) -> dict:
    if len(y) == 0:
        return {"n": 0}
    probs = model.predict(inputs, batch_size=256, verbose=0)
    pred = [classes[i] for i in probs.argmax(axis=1)]
    true = [classes[i] for i in y.argmax(axis=1)]

    recalls = []
    per_class = {}
    for idx, c in enumerate(classes):
        sel = [i for i, t in enumerate(true) if t == c]
        if sel:
            r = sum(1 for i in sel if pred[i] == c) / len(sel)
            recalls.append(r)
            per_class[c] = {"n": len(sel), "recall": round(r, 4)}

    return {
        "n": int(len(y)),
        "accuracy": float(round(np.mean([t == p for t, p in zip(true, pred)]), 4)),
        "balanced_accuracy": float(round(np.mean(recalls), 4)) if recalls else None,
        "mcc": matthews_corrcoef(true, pred),
        "mean_max_prob": float(round(probs.max(axis=1).mean(), 4)),
        "per_class": per_class,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Training identifikasi regime")
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument(
        "--binary",
        action="store_true",
        help="Hanya persistent vs anti_persistent (kelas random_like dikeluarkan)",
    )
    parser.add_argument("--seq-len", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    import tensorflow as tf

    from model_architecture import (
        build_hybrid_attention_bilstm,
        build_structural_mlp,
        compile_model,
    )

    cfg = get_config()
    tf.keras.utils.set_random_seed(cfg.model.seed)

    classes = BINARY_CLASSES if args.binary else list(REGIME_CLASSES)
    suffix = "binary" if args.binary else "multiclass"

    close = get_repository().get_ohlcv(args.symbol, args.timeframe)["close"].to_numpy()
    print(f"[{args.timeframe}] menyiapkan dataset identifikasi ({suffix})...")
    data = build_dataset(
        close, seq_len=args.seq_len, h_bars=0, classes=classes, with_structural=True
    )

    Xs_tr, Xf_tr, y_tr = data["train"]  # type: ignore[misc]
    Xs_va, Xf_va, y_va = data["validation"]  # type: ignore[misc]
    Xs_te, Xf_te, y_te = data["test"]  # type: ignore[misc]

    print(f"  train={len(y_tr)}  val={len(y_va)}  test={len(y_te)}")
    print(f"  kelas: {classes}")
    print(f"  fitur struktural: {Xf_tr.shape[1]} dimensi")
    if len(y_tr) == 0:
        raise SystemExit("Dataset kosong.")

    results = {}
    for model_key in ("structural_mlp", "hybrid_attention_bilstm"):
        print(f"\n--- {model_key} ---")
        if model_key == "structural_mlp":
            model = compile_model(build_structural_mlp(Xf_tr.shape[1], len(classes)))
            tr_in, va_in, te_in = Xf_tr, Xf_va, Xf_te
        else:
            model = compile_model(
                build_hybrid_attention_bilstm(Xs_tr.shape[1:], Xf_tr.shape[1], len(classes))
            )
            tr_in = [Xs_tr, Xf_tr]
            va_in = [Xs_va, Xf_va]
            te_in = [Xs_te, Xf_te]

        history = model.fit(
            tr_in,
            y_tr,
            validation_data=(va_in, y_va) if len(y_va) else None,
            epochs=args.epochs,
            batch_size=args.batch_size,
            class_weight=class_weights(y_tr),
            callbacks=[
                tf.keras.callbacks.EarlyStopping(
                    monitor="val_loss" if len(y_va) else "loss",
                    patience=12,
                    restore_best_weights=True,
                ),
                tf.keras.callbacks.ReduceLROnPlateau(
                    monitor="val_loss" if len(y_va) else "loss",
                    factor=0.5,
                    patience=6,
                    min_lr=1e-5,
                ),
            ],
            verbose=2,
        )

        metrics = {
            "validation": evaluate(model, va_in, y_va, classes),
            "test": evaluate(model, te_in, y_te, classes),
        }
        print(f"  val : acc={metrics['validation'].get('accuracy')} "
              f"BA={metrics['validation'].get('balanced_accuracy')}")
        print(f"  test: acc={metrics['test'].get('accuracy')} "
              f"BA={metrics['test'].get('balanced_accuracy')}")

        name = f"{model_key}_{suffix}_{args.timeframe}"
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        model.save(ARTIFACTS_DIR / f"{name}.keras")

        meta = {
            "model": model_key,
            "task": "identification",
            "mode": suffix,
            "classes": classes,
            "timeframe": args.timeframe,
            "config_hash": cfg.config_hash,
            "seq_len": args.seq_len,
            "stride_bars": data["stride_bars"],
            "effective_window": data["effective_window"],
            "scaler": data["scaler"],
            "feature_scaler": data["feature_scaler"],
            "feature_names": data["feature_names"],
            "n_train": int(len(y_tr)),
            "n_val": int(len(y_va)),
            "n_test": int(len(y_te)),
            "epochs_ran": len(history.history.get("loss", [])),
            "metrics": metrics,
            "history": {k: [float(x) for x in v] for k, v in history.history.items()},
            "catatan": (
                "Hurst dan DFA sengaja TIDAK dipakai sebagai fitur. Label dibentuk "
                "dari keduanya, sehingga memakainya sebagai input menghasilkan label "
                "sirkular dan angka akurasi yang tidak bermakna."
            ),
        }
        (ARTIFACTS_DIR / f"{name}.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        results[model_key] = metrics["test"]
        print(f"  artefak: {name}.keras")

    print("\n=== Ringkasan test ===")
    for k, m in results.items():
        print("  %-26s acc=%.4f  BA=%.4f  MCC=%.4f" % (
            k, m.get("accuracy", 0), m.get("balanced_accuracy", 0), m.get("mcc", 0)))


if __name__ == "__main__":
    main()

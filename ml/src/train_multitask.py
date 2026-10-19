"""Pretraining fBm + fine-tune multi-task — flow.md langkah 4 & 6.

    python ml/src/train_multitask.py --timeframe 1h
    python ml/src/train_multitask.py --timeframe 1h --no-pretrain   # ablasi
    python ml/src/train_multitask.py --timeframe 1h --lambda-reg 0.0  # ablasi

Dua langkah flow.md digabung dalam satu skrip karena saling bergantung:
pretraining hanya masuk akal bila arsitektur yang dilatih di data sintetis sama
persis dengan yang di-fine-tune, dan head regresi H adalah alasan utama
pretraining fBm berguna — di sana H diketahui persis.

Urutan kerja
------------
1. Bangkitkan fBm dengan H diketahui, latih model penuh di sana.
2. Muat bobot hasil langkah 1, lanjutkan training pada data BTC.
3. Laporkan kedua tahap, plus dua ablasi bawaan:
   - tanpa pretraining (`--no-pretrain`)
   - tanpa head regresi (`--lambda-reg 0`)

Dua ablasi itu yang membuktikan apakah langkah 4 dan langkah 6 benar-benar
berkontribusi, bukan sekadar menambah kerumitan. Hasil yang menunjukkan TIDAK
berkontribusi tetap dilaporkan apa adanya — seperti temuan order flow.

Catatan tentang scaler
----------------------
Scaler sintetis tidak dibawa ke tahap fine-tuning. Koefisien SWT fBm dan BTC
punya skala berbeda; memakai statistik fBm pada data riil akan menggeser
seluruh masukan. Yang dipindahkan hanya BOBOT, dan itu sah karena bentuk
masukan (seq_len, jumlah channel) identik.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

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
from synthetic import build_synthetic_dataset  # noqa: E402
from train import class_weights  # noqa: E402


def sample_weights_from(y_class: np.ndarray) -> np.ndarray:
    """Bobot per sampel, berbanding terbalik dengan frekuensi kelasnya.

    Model multi-output tidak menerima `class_weight` di Keras, sehingga
    penyeimbangan kelas dinyatakan sebagai sample_weight pada head klasifikasi
    saja. Head regresi tetap berbobot seragam: nilai H kontinu tidak punya
    kelas, dan memberinya bobot kelas akan membuat galat pada regime minoritas
    dihukum lebih keras tanpa alasan.
    """
    weights = class_weights(y_class)
    idx = np.asarray(y_class).argmax(axis=1)
    return np.asarray([weights[int(i)] for i in idx], dtype=float)


def evaluate(model, X, y_class, y_hurst, classes: List[str]) -> dict:
    """Metrik kedua head sekaligus.

    Head regresi dilaporkan bersama MAE baseline "selalu tebak rata-rata".
    Tanpa pembanding itu, MAE 0.05 tidak bisa dinilai: bisa saja sebaran H
    memang hanya selebar 0.05.
    """
    if len(y_class) == 0:
        return {"n": 0}

    outputs = model.predict(X, batch_size=256, verbose=0)
    probs, h_pred = (outputs[0], outputs[1]) if isinstance(outputs, list) else (outputs, None)

    pred = [classes[i] for i in np.asarray(probs).argmax(axis=1)]
    true = [classes[i] for i in np.asarray(y_class).argmax(axis=1)]

    out: Dict[str, Any] = {
        "n": len(y_class),
        "accuracy": float(round(np.mean([t == p for t, p in zip(true, pred)]), 4)),
        "balanced_accuracy": balanced_accuracy(true, pred),
        "mcc": matthews_corrcoef(true, pred),
        "mean_max_prob": float(round(np.asarray(probs).max(axis=1).mean(), 4)),
    }

    if h_pred is not None and y_hurst is not None and len(y_hurst):
        h_true = np.asarray(y_hurst, dtype=float).ravel()
        h_est = np.asarray(h_pred, dtype=float).ravel()
        baseline_mae = float(np.mean(np.abs(h_true - h_true.mean())))
        out["hurst_regression"] = {
            "mae": round(float(np.mean(np.abs(h_est - h_true))), 4),
            "mae_baseline_mean": round(baseline_mae, 4),
            "rmse": round(float(np.sqrt(np.mean((h_est - h_true) ** 2))), 4),
            "korelasi": round(float(np.corrcoef(h_est, h_true)[0, 1]), 4)
            if np.std(h_est) > 1e-9 and np.std(h_true) > 1e-9
            else None,
            "catatan": (
                "MAE hanya bermakna dibanding mae_baseline_mean (tebakan "
                "'selalu rata-rata'). Lebih besar dari baseline = head regresi "
                "tidak mempelajari apa pun."
            ),
        }
    return out


def pretrain_on_fbm(
    args,
    classes: List[str],
    seq_len: int,
    window: int,
    swt_level: int,
) -> tuple:
    """Tahap 1: latih pada fBm dengan H diketahui. Mengembalikan (model, laporan)."""
    import tensorflow as tf  # type: ignore

    from model_architecture import build_multitask_attention_bilstm, compile_multitask

    print("\n=== Tahap 1: pretraining fBm ===")
    synth = build_synthetic_dataset(
        seq_len=seq_len,
        window=window,
        swt_level=swt_level,
        n_series_per_h=args.synthetic_series,
        samples_per_series=args.synthetic_samples,
        classes=classes,
        with_structural=False,
        with_multifractal=False,
        seed=args.seed,
    )
    Xs_tr, _, yc_tr, yh_tr = synth["train"]  # type: ignore[misc]
    Xs_va, _, yc_va, yh_va = synth["validation"]  # type: ignore[misc]

    print(f"  deret fBm : {synth['n_series']}  sampel: {synth['n_samples']}")
    print(f"  distribusi: {synth['class_counts']}")
    print(f"  train={len(yc_tr)}  val={len(yc_va)}")

    if len(yc_tr) == 0:
        raise SystemExit("Dataset sintetis kosong.")

    model = compile_multitask(
        build_multitask_attention_bilstm(Xs_tr.shape[1:], n_classes=len(classes)),
        lambda_regression=args.lambda_reg,
    )
    history = model.fit(
        Xs_tr,
        # Target dan bobot ditulis sebagai LIST mengikuti urutan output model
        # (regime, lalu hurst). Pada Keras 3.9, sample_weight berbentuk dict
        # gagal dengan `KeyError: 0`, dan mencampur dict untuk y dengan list
        # untuk sample_weight ditolak karena strukturnya harus sepadan.
        [yc_tr, yh_tr],
        validation_data=(Xs_va, [yc_va, yh_va]) if len(yc_va) else None,
        epochs=args.pretrain_epochs,
        batch_size=args.batch_size,
        # Grid H tidak menghasilkan jumlah sampel yang sama per kelas: pita
        # netral di sekitar 0.5 lebih sempit daripada dua sisi lainnya.
        sample_weight=cast(Any, [sample_weights_from(yc_tr), np.ones(len(yh_tr), dtype=float)]),
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss" if len(yc_va) else "loss",
                patience=8,
                restore_best_weights=True,
            )
        ],
        verbose=2,
    )

    metrics = evaluate(model, Xs_va, yc_va, yh_va, classes)
    print(f"  val sintetis: acc={metrics.get('accuracy')} BA={metrics.get('balanced_accuracy')}")
    if "hurst_regression" in metrics:
        hr = metrics["hurst_regression"]
        print(f"  regresi H   : MAE={hr['mae']} (baseline {hr['mae_baseline_mean']})")

    report = {
        "n_series": synth["n_series"],
        "n_samples": synth["n_samples"],
        "class_counts": synth["class_counts"],
        "hurst_grid": synth["hurst_grid"],
        "epochs_ran": len(history.history.get("loss", [])),
        "validation": metrics,
    }
    return model, report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pretraining fBm + fine-tune multi-task (flow.md langkah 4 & 6)"
    )
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--seq-len", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--pretrain-epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--lambda-reg",
        type=float,
        default=0.3,
        help="Bobot MSE head regresi H. 0 = tanpa multi-task (ablasi langkah 6).",
    )
    parser.add_argument(
        "--no-pretrain",
        action="store_true",
        help="Lewati pretraining fBm (ablasi langkah 4).",
    )
    parser.add_argument("--synthetic-series", type=int, default=40)
    parser.add_argument("--synthetic-samples", type=int, default=8)
    parser.add_argument(
        "--binary",
        action="store_true",
        help="Hanya persistent vs anti_persistent.",
    )
    parser.add_argument(
        "--identification",
        action="store_true",
        help="Tugas identifikasi (h = 0), bukan prediksi h bar ke depan.",
    )
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    import tensorflow as tf  # type: ignore

    from model_architecture import build_multitask_attention_bilstm, compile_multitask

    cfg = get_config()
    if args.seed is None:
        args.seed = cfg.model.seed
    tf.keras.utils.set_random_seed(args.seed)

    classes = ["persistent", "anti_persistent"] if args.binary else list(REGIME_CLASSES)
    mode = "binary" if args.binary else "multiclass"
    task = "identification" if args.identification else "forecasting"

    # ---- Tahap 2: data BTC ----
    close = get_repository().get_ohlcv(args.symbol, args.timeframe)["close"].to_numpy()
    print(f"[{args.timeframe}] menyiapkan dataset {task} dari {len(close)} bar...")
    data = build_dataset(
        close,
        seq_len=args.seq_len,
        h_bars=0 if args.identification else None,
        classes=classes,
        with_structural=False,
        with_multifractal=False,
        return_hurst=True,
    )

    X_tr, _, yc_tr = data["train"]  # type: ignore[misc]
    X_va, _, yc_va = data["validation"]  # type: ignore[misc]
    X_te, _, yc_te = data["test"]  # type: ignore[misc]
    hurst_targets = data["hurst_targets"]  # type: ignore[index]
    yh_tr = hurst_targets["train"]  # type: ignore[index]
    yh_va = hurst_targets["validation"]  # type: ignore[index]
    yh_te = hurst_targets["test"]  # type: ignore[index]

    print(f"  train={len(yc_tr)}  val={len(yc_va)}  test={len(yc_te)}")
    print(f"  kelas: {classes}  lambda_reg={args.lambda_reg}")
    if len(yc_tr) == 0:
        raise SystemExit("Dataset training kosong. Periksa L, h, dan panjang data.")

    # ---- Tahap 1: pretraining ----
    pretrain_report: Optional[dict] = None
    model = None
    if not args.no_pretrain:
        try:
            model, pretrain_report = pretrain_on_fbm(
                args,
                classes,
                seq_len=args.seq_len,
                window=int(data["effective_window"]),  # type: ignore[arg-type]
                swt_level=cfg.analysis.J,
            )
        except (ValueError, SystemExit) as exc:
            # Pretraining gagal tidak boleh menggagalkan seluruh eksperimen;
            # yang penting statusnya tercatat, bukan hilang diam-diam.
            print(f"  pretraining dilewati: {exc}")
            pretrain_report = {"gagal": str(exc)[:200]}
            model = None

    if model is None:
        model = compile_multitask(
            build_multitask_attention_bilstm(X_tr.shape[1:], n_classes=len(classes)),
            lambda_regression=args.lambda_reg,
        )
    else:
        # Bobot dipertahankan, optimizer di-reset: momentum dari data sintetis
        # tidak berlaku untuk lanskap loss data riil. Learning rate diturunkan
        # agar fine-tuning tidak langsung menghapus apa yang sudah dipelajari.
        model = compile_multitask(
            model, lr=3e-4, lambda_regression=args.lambda_reg
        )

    print("\n=== Tahap 2: fine-tune pada BTC ===")
    history = model.fit(
        X_tr,
        [yc_tr, yh_tr],
        validation_data=(X_va, [yc_va, yh_va]) if len(yc_va) else None,
        epochs=args.epochs,
        batch_size=args.batch_size,
        # class_weight tidak dipakai di sini: Keras menolaknya pada model
        # multi-output. Penyeimbangan kelas dinyatakan sebagai sample_weight
        # yang hanya membebani head klasifikasi (urutan list mengikuti urutan
        # output: regime, lalu hurst).
        sample_weight=cast(Any, [sample_weights_from(yc_tr), np.ones(len(yh_tr), dtype=float)]),
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss" if len(yc_va) else "loss",
                patience=12,
                restore_best_weights=True,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss" if len(yc_va) else "loss",
                factor=0.5,
                patience=6,
                min_lr=1e-5,
            ),
        ],
        verbose=2,
    )

    metrics = {
        "validation": evaluate(model, X_va, yc_va, yh_va, classes),
        "test": evaluate(model, X_te, yc_te, yh_te, classes),
    }
    for split_name in ("validation", "test"):
        m = metrics[split_name]
        print(
            f"  {split_name:<11}: acc={m.get('accuracy')} "
            f"BA={m.get('balanced_accuracy')} MCC={m.get('mcc')}"
        )
        if "hurst_regression" in m:
            hr = m["hurst_regression"]
            print(
                f"               regresi H MAE={hr['mae']} "
                f"(baseline {hr['mae_baseline_mean']}) r={hr['korelasi']}"
            )

    suffix = "nopretrain" if args.no_pretrain else "pretrained"
    if args.lambda_reg == 0:
        suffix += "_noreg"
    name = f"multitask_attention_bilstm_{mode}_{suffix}_{args.timeframe}"

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    model.save(ARTIFACTS_DIR / f"{name}.keras")

    meta = {
        "model": "multitask_attention_bilstm",
        "task": task,
        "mode": mode,
        "classes": classes,
        "timeframe": args.timeframe,
        "config_hash": cfg.config_hash,
        "seq_len": args.seq_len,
        "h_bars": data["h_bars"],
        "h_windows": data["h_windows"],
        "stride_bars": data["stride_bars"],
        "effective_window": data["effective_window"],
        "scaler": data["scaler"],
        "lambda_regression": args.lambda_reg,
        "pretrained": not args.no_pretrain,
        "pretrain": pretrain_report,
        "n_train": len(yc_tr),
        "n_val": len(yc_va),
        "n_test": len(yc_te),
        "epochs_ran": len(history.history.get("loss", [])),
        "metrics": metrics,
        "history": {k: [float(x) for x in v] for k, v in history.history.items()},
        "catatan": (
            "Head regresi memakai H hasil estimasi R/S sebagai target pada data "
            "BTC — nilai itu sendiri mengandung galat, sehingga MAE di sini "
            "mengukur kesesuaian terhadap estimator, bukan terhadap H sejati. "
            "Pada tahap pretraining fBm, H memang diketahui persis."
        ),
    }
    (ARTIFACTS_DIR / f"{name}.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"\nartefak: {name}.keras")
    print(
        "Ablasi pembanding:\n"
        f"  python ml/src/train_multitask.py --timeframe {args.timeframe} --no-pretrain\n"
        f"  python ml/src/train_multitask.py --timeframe {args.timeframe} --lambda-reg 0"
    )


if __name__ == "__main__":
    main()

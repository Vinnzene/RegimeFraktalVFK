"""Latih dan simpan detektor resmi sistem + pembanding untuk uji generalisasi.

Jalankan (setelah `synthetic_benchmark.py --stage data`):
    python ml/src/train_detector.py

Sesuai praregistrasi Fase 1 adendum 3 dan generalisasi adendum 1:
- D-sintetis: model M-kripto terpilih Fase 1 (n = 500, ambang utama), yaitu
  Hybrid PS yang dilatih pada campuran S1–S4, dengan hyperparameter dan seed
  yang sama dengan benchmark.
- D-BTC: regresi logistik latih-BTC 1H (skenario B Fase 0), protokol
  train_only, fitur statistik yang sama dengan Bab 4.
- D-klasik: VR(2) dengan ambang terkalibrasi Fase 1.
- D-konsensus: R/S–DFA dengan ambang BTC train_only.

Keluaran:
    ml/artifacts/detector/hybrid_ps_sintetis.keras   (tidak di-commit; dibangun ulang dengan skrip ini)
    ml/artifacts/detector/dbtc_logreg.joblib         (tidak di-commit)
    ml/artifacts/detector_meta.json                  (di-commit)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, get_config  # noqa: E402
from synthetic_benchmark import TRAIN_SCENARIOS, balanced_accuracy, concat, labels_for, load  # noqa: E402
from synthetic_regimes import CLASSES, PRIMARY, SIGMA  # noqa: E402

OUT = ARTIFACTS_DIR / "detector"
N = 500


def train_synthetic_detector() -> dict:
    import tensorflow as tf  # type: ignore

    from app.services.feature_builder import apply_scaler, fit_scaler
    from model_architecture import build_hybrid_attention_bilstm, compile_model
    from train import class_weights

    tr = concat([load(s, N, "train") for s in TRAIN_SCENARIOS])
    va = concat([load(s, N, "validation") for s in TRAIN_SCENARIOS])
    y_tr, y_va = labels_for(tr["h"], PRIMARY), labels_for(va["h"], PRIMARY)
    onehot = lambda y: np.eye(3)[[CLASSES.index(c) for c in y]]  # noqa: E731

    mu, sd = tr["feat"].mean(axis=0), tr["feat"].std(axis=0)
    sd[sd < 1e-12] = 1.0
    ps_scaler = fit_scaler(tr["ps"])
    F = lambda d: (d["feat"] - mu) / sd  # noqa: E731
    S = lambda d: apply_scaler(d["ps"], ps_scaler)  # noqa: E731

    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(42)
    model = compile_model(build_hybrid_attention_bilstm((tr["ps"].shape[1], tr["ps"].shape[2]), tr["feat"].shape[1], 3))
    t0 = time.time()
    model.fit(
        [S(tr), F(tr)], onehot(y_tr), validation_data=([S(va), F(va)], onehot(y_va)),
        epochs=80, batch_size=64, class_weight=class_weights(onehot(y_tr)), shuffle=True, verbose=0,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
        ],
    )
    predict = lambda d: np.array(CLASSES)[model.predict([S(d), F(d)], batch_size=1024, verbose=0).argmax(axis=1)]  # noqa: E731
    test_ba = {}
    for s in ("S1", "S4", "S4k"):
        d = load(s, N, "test")
        test_ba[s] = round(balanced_accuracy(labels_for(d["h"], PRIMARY), predict(d)), 4)
    OUT.mkdir(parents=True, exist_ok=True)
    model.save(OUT / "hybrid_ps_sintetis.keras")
    print(f"D-sintetis dilatih {time.time() - t0:.0f}s, BA uji {test_ba}", flush=True)
    return {
        "file": "detector/hybrid_ps_sintetis.keras",
        "classes": list(CLASSES),
        "thresholds": list(PRIMARY),
        "window": N, "sub_window": 128, "seq_len": 32, "sigma_per_bar": SIGMA,
        "feature_mean": mu.round(8).tolist(), "feature_std": sd.round(8).tolist(),
        "ps_scaler": ps_scaler,
        "test_ba_reproduced": test_ba,
        "catatan": "Return tiap window dinormalisasi ke sigma_per_bar sebelum fitur dihitung, sama seperti data latih.",
    }


def train_btc_logreg() -> dict:
    import joblib
    from sklearn.linear_model import LogisticRegression

    from app.db.repository import get_repository
    from leakage_study import VARIANTS, build_base, make_split

    base = build_base("1h", 32, list(CLASSES))
    rows = make_split(base, VARIANTS["clean"], None, 42)
    F = np.hstack([base["F_struct"], base["F_mf"]])
    tr = rows["train"]
    mu, sd = F[tr].mean(axis=0), F[tr].std(axis=0)
    sd[sd < 1e-12] = 1.0
    y = base["y"][tr].argmax(axis=1)
    model = LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000, random_state=42)
    model.fit((F[tr] - mu) / sd, y)
    joblib.dump(model, OUT / "dbtc_logreg.joblib")
    times = get_repository().get_ohlcv("BTCUSDT", "1h")["time"].to_numpy()
    train_end_time = int(times[int(base["positions"][rows["validation"][-1]])])
    print(f"D-BTC dilatih pada {len(tr)} window, batas latih+validasi {train_end_time}", flush=True)
    return {
        "file": "detector/dbtc_logreg.joblib",
        "classes": list(CLASSES),
        "feature_mean": mu.round(8).tolist(), "feature_std": sd.round(8).tolist(),
        "btc_train_end_time": train_end_time,
        "btc_thresholds_train_only": base["thresholds"],
    }


def main() -> None:
    cfg = get_config()
    bench = json.loads((ARTIFACTS_DIR / "synthetic_benchmark.json").read_text(encoding="utf-8"))
    meta = {
        "config_hash": cfg.config_hash,
        "d_sintetis": train_synthetic_detector(),
        "d_btc": train_btc_logreg(),
        "d_klasik": {"estimator": "vr2", "thresholds": bench["utama"]["lengths"]["500"]["calibrated_thresholds"]["vr2"]},
    }
    meta["d_konsensus"] = {"thresholds": meta["d_btc"]["btc_thresholds_train_only"]}
    (ARTIFACTS_DIR / "detector_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("tersimpan: ml/artifacts/detector_meta.json")


if __name__ == "__main__":
    main()

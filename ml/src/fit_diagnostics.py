"""Diagnosis overfitting/underfitting model final: akurasi latih, validasi, dan uji.

Model tidak dilatih ulang. Fitur dibaca dari cache evaluasi, label dibangun ulang dengan aturan yang
sama, lalu dicocokkan dengan label validasi/uji yang tersimpan sebelum dipakai. Tidak ada cache yang ditulis.

Pemakaian: python ml/src/fit_diagnostics.py
Keluaran: ml/artifacts/fit_diagnostics.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, PROCESSED_DIR, REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.feature_builder import apply_scaler  # noqa: E402
from app.services.hurst_dfa import compute_rolling_er, to_log_return  # noqa: E402
from app.services.regime_labeling import label_series  # noqa: E402
from app.services.splitting import bars_to_rows, split_indices  # noqa: E402

REVIEW = ARTIFACTS_DIR / "review"
OUT = ARTIFACTS_DIR / "fit_diagnostics.json"
CLASSES = list(REGIME_CLASSES)
STRIDE = {"1h": 4, "4h": 2}


def metrics(y: np.ndarray, p: np.ndarray) -> Dict[str, Any]:
    """Akurasi, balanced accuracy, macro-F1, dan recall per kelas (y, p = indeks kelas)."""
    rec, f1 = {}, []
    for c, name in enumerate(CLASSES):
        tp = int(((p == c) & (y == c)).sum())
        n_true, n_pred = int((y == c).sum()), int((p == c).sum())
        r = tp / n_true if n_true else 0.0
        pr = tp / n_pred if n_pred else 0.0
        rec[name] = round(r, 4)
        f1.append(2 * pr * r / (pr + r) if pr + r else 0.0)
    return {
        "n": int(len(y)),
        "accuracy": round(float((p == y).mean()), 4),
        "balanced_accuracy": round(float(np.mean(list(rec.values()))), 4),
        "macro_f1": round(float(np.mean(f1)), 4),
        "recall": rec,
        "support": {name: int((y == c).sum()) for c, name in enumerate(CLASSES)},
        # Baris = label sebenarnya, kolom = prediksi; urutan mengikuti CLASSES.
        "confusion_matrix": [[int(((y == a) & (p == b)).sum()) for b in range(len(CLASSES))] for a in range(len(CLASSES))],
    }


def rebuild(tf: str) -> Dict[str, Any]:
    """Fitur dan label persis seperti `run_updated_evaluation.prepare_timeframe_data`, tanpa menulis cache."""
    cfg = get_config()
    stride, window = STRIDE[tf], cfg.analysis.L
    with np.load(PROCESSED_DIR / "cache" / f"updated_feat_{tf}_s{stride}_f56_ps14.npz") as z:
        positions = z["positions"].astype(int)
        PS, F = z["PS"], np.hstack([z["F_struct"], z["F_mf"]])
    if tf == "4h":
        reg = pd.read_parquet(PROCESSED_DIR / "cache" / "regime_btcusdt_4h_s2.parquet")
    else:
        reg = get_repository().get_regime("BTCUSDT", tf)
    reg = reg[reg["index"].astype(int).isin(set(positions.tolist()))].sort_values("index").reset_index(drop=True)
    if not np.array_equal(reg["index"].to_numpy(dtype=int), positions):
        raise SystemExit(f"[{tf}] posisi jendela regime tidak sama dengan cache fitur")
    reg = reg[["index", "hurst", "dfa_alpha"]].copy()
    log_ret = to_log_return(get_repository().get_ohlcv("BTCUSDT", tf)["close"].to_numpy(dtype=float))
    for k, v in compute_rolling_er(log_ret, positions.tolist(), window=window).items():
        reg[k] = v
    sp = split_indices(len(positions), cfg.split.ratios, bars_to_rows(window, stride))
    train_mask = np.zeros(len(positions), dtype=bool)
    train_mask[: sp["train"][1]] = True
    lab_df = label_series(
        reg, cfg.analysis.hurst_threshold, cfg.analysis.dfa_threshold, mode="quantile", quantiles=(1 / 3, 2 / 3),
        threshold_source="train_only", train_mask=train_mask, soft_consensus=True,
    )
    lab = lab_df["regime"].tolist()
    y = np.array([CLASSES.index(v) if v in CLASSES else -1 for v in lab])
    rows = {k: np.array([i for i in range(*sp[k]) if y[i] >= 0], dtype=int) for k in ("train", "validation", "test")}
    thr = {
        "hurst": [float(lab_df["hurst_lower"].iloc[0]), float(lab_df["hurst_upper"].iloc[0])],
        "dfa": [float(lab_df["dfa_lower"].iloc[0]), float(lab_df["dfa_upper"].iloc[0])],
    }
    return {"PS": PS, "F": F, "y": y, "rows": rows, "split": sp, "thresholds": thr,
            "hurst": reg["hurst"].to_numpy(dtype=float), "dfa": reg["dfa_alpha"].to_numpy(dtype=float)}


def predict(models: List[Any], sc: Dict[str, Any], PS: np.ndarray, F: np.ndarray) -> np.ndarray:
    """Softmax per seed (n_seed, n, 3), skala sama dengan `ai_detector.predict_proba`."""
    f32 = np.float32
    S = apply_scaler(np.asarray(PS, dtype=f32), sc["ps_scaler"])
    Fs = (np.asarray(F, dtype=f32) - np.asarray(sc["f_mean"], dtype=f32)) / np.asarray(sc["f_std"], dtype=f32)
    return np.stack([m.predict([S, Fs], batch_size=1024, verbose=0) for m in models])


def run(tf: str) -> Dict[str, Any]:
    import tensorflow as tf_  # type: ignore
    from model_architecture import AttentionPooling  # noqa: PLC0415

    t0 = time.time()
    d = rebuild(tf)
    raw = np.load(REVIEW / "raw" / f"{tf}_normal.npz")
    # Bukti replikasi: baris dan label validasi/uji harus sama persis dengan evaluasi asli.
    for k, rk in (("validation", "val"), ("test", "test")):
        if not np.array_equal(d["rows"][k], raw[f"bt__rows_{rk}"]):
            raise SystemExit(f"[{tf}] baris {k} berbeda dari evaluasi")
        y_raw = raw[f"bt__y_{rk}"]
        y_raw = y_raw.argmax(1) if y_raw.ndim == 2 else y_raw
        if not np.array_equal(d["y"][d["rows"][k]], y_raw):
            raise SystemExit(f"[{tf}] label {k} berbeda dari evaluasi")

    sc = json.loads((REVIEW / "models" / f"hybrid_ps_updated_{tf}_scaler.json").read_text(encoding="utf-8"))
    models = [tf_.keras.models.load_model(REVIEW / "models" / f, custom_objects={"AttentionPooling": AttentionPooling}, compile=False)
              for f in sc["files"]]
    out: Dict[str, Any] = {"seeds": sc["seeds"], "n_windows": int(len(d["y"])), "splits": {}}
    for k in ("train", "validation", "test"):
        r = d["rows"][k]
        P = predict(models, sc, d["PS"][r], d["F"][r])
        ens = metrics(d["y"][r], P.mean(0).argmax(1))
        ens["per_seed_accuracy"] = [round(float((P[i].argmax(1) == d["y"][r]).mean()), 4) for i in range(len(P))]
        ens["mean_confidence"] = round(float(P.mean(0).max(1).mean()), 4)
        out["splits"][k] = ens
    if tf == "4h":
        ex_path = PROCESSED_DIR / "cache" / "updated_extra_4h_eth_bnb_train.npz"
        if ex_path.exists():
            with np.load(ex_path) as z:
                P = predict(models, sc, z["PS"], z["F_all"])
                out["splits"]["train_extra_eth_bnb"] = metrics(z["y"].argmax(1), P.mean(0).argmax(1))
    meta = json.loads((REVIEW / "raw" / f"{tf}_normal.json").read_text(encoding="utf-8"))
    out["epochs_per_seed"] = meta.get("bt", {}).get("hybrid_ps", {}).get("epochs")
    out["test_matches_paper"] = out["splits"]["test"]["accuracy"] == round(float(sc["test_acc_ensemble_reproduced"]), 4)
    out["seconds"] = round(time.time() - t0, 1)
    return out


def learning_curve() -> Dict[str, Any]:
    """Akurasi walk-forward terhadap jumlah data latih (dari robustness_tests.json)."""
    rob = json.loads((ARTIFACTS_DIR / "robustness_tests.json").read_text(encoding="utf-8"))
    res = {}
    for tf, v in rob["timeframes"].items():
        wf = v.get("walk_forward") or {}
        res[tf] = {
            "folds": [{k: f[k] for k in ("fold", "n_train", "n_test", "pct", "balanced_pct", "mlp_pct")} for f in wf.get("folds", [])],
            "pooled_pct_ensemble": wf.get("pooled", {}).get("pooled_pct_ensemble"),
            "backtest_pct": wf.get("backtest_pct"),
        }
    return res


def main() -> None:
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ml/src/fit_diagnostics.py",
        "note": "Model final (3 seed, ensemble) tidak dilatih ulang; latih = jendela BTC berlabel pada bagian latih.",
        "timeframes": {tf: run(tf) for tf in ("1h", "4h")},
        "learning_curve": learning_curve(),
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    for tf, v in out["timeframes"].items():
        s = v["splits"]
        print(tf, {k: (s[k]["accuracy"], s[k]["balanced_accuracy"]) for k in s}, "uji cocok naskah:", v["test_matches_paper"])
    print("tersimpan:", OUT)


if __name__ == "__main__":
    main()

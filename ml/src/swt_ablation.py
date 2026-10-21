"""Ablasi fitur energi SWT pada detektor resmi (praregistrasi Fase 1 adendum 4).

Jalankan (setelah `synthetic_benchmark.py --stage data`):
    python ml/src/swt_ablation.py

A0 = detektor resmi (50 fitur struktural + sekuens PS).
A1 = sama, tanpa 12 fitur rasio energi SWT (38 fitur).
Konfigurasi latih sama dengan `train_detector.py`; tiap varian dilatih 3 seed.

Keluaran: ml/artifacts/swt_ablation.{json,md}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.services.structural_features import feature_names  # noqa: E402
from synthetic_benchmark import TRAIN_SCENARIOS, balanced_accuracy, concat, labels_for, load  # noqa: E402
from synthetic_regimes import CLASSES, PRIMARY  # noqa: E402

N = 500
SEEDS = (42, 43, 44)
TEST_SETS = ("S1", "S2", "S3", "S4", "S4k")
B = 2000
SWT_COLS = [i for i, name in enumerate(feature_names()) if name.startswith("swt_energy_")]
VARIANTS = {"A0": [], "A1": SWT_COLS}
VARIANT_LABEL = {"A0": "Detektor resmi (50 fitur)", "A1": "Tanpa energi SWT (38 fitur)"}


def train_and_predict(drop: List[int], seed: int, tests: Dict[str, Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
    import tensorflow as tf  # type: ignore

    from app.services.feature_builder import apply_scaler, fit_scaler
    from model_architecture import build_hybrid_attention_bilstm, compile_model
    from train import class_weights

    tr = concat([load(s, N, "train") for s in TRAIN_SCENARIOS])
    va = concat([load(s, N, "validation") for s in TRAIN_SCENARIOS])
    keep = np.setdiff1d(np.arange(tr["feat"].shape[1]), drop)
    onehot = lambda y: np.eye(3)[[CLASSES.index(c) for c in y]]  # noqa: E731
    y_tr, y_va = onehot(labels_for(tr["h"], PRIMARY)), onehot(labels_for(va["h"], PRIMARY))

    mu, sd = tr["feat"][:, keep].mean(axis=0), tr["feat"][:, keep].std(axis=0)
    sd[sd < 1e-12] = 1.0
    ps_scaler = fit_scaler(tr["ps"])
    F = lambda d: (d["feat"][:, keep] - mu) / sd  # noqa: E731
    S = lambda d: apply_scaler(d["ps"], ps_scaler)  # noqa: E731

    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(seed)
    model = compile_model(build_hybrid_attention_bilstm((tr["ps"].shape[1], tr["ps"].shape[2]), len(keep), 3))
    model.fit(
        [S(tr), F(tr)], y_tr, validation_data=([S(va), F(va)], y_va),
        epochs=80, batch_size=64, class_weight=class_weights(y_tr), shuffle=True, verbose=0,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
        ],
    )
    return {s: model.predict([S(d), F(d)], batch_size=1024, verbose=0) for s, d in tests.items()}


def ba_from_proba(y: np.ndarray, proba: np.ndarray) -> float:
    return balanced_accuracy(y, np.array(CLASSES)[proba.argmax(axis=1)])


def main() -> None:
    assert len(SWT_COLS) == 12, SWT_COLS
    tests = {s: load(s, N, "test") for s in TEST_SETS}
    y_test = {s: labels_for(d["h"], PRIMARY) for s, d in tests.items()}

    proba: Dict[str, Dict[str, List[np.ndarray]]] = {v: {s: [] for s in TEST_SETS} for v in VARIANTS}
    per_seed: Dict[str, Dict[str, List[float]]] = {v: {s: [] for s in TEST_SETS} for v in VARIANTS}
    for v, drop in VARIANTS.items():
        for seed in SEEDS:
            t0 = time.time()
            out = train_and_predict(drop, seed, tests)
            for s in TEST_SETS:
                proba[v][s].append(out[s])
                per_seed[v][s].append(ba_from_proba(y_test[s], out[s]))
            print(f"{v} seed {seed}: {time.time() - t0:.0f}s, BA S4 {per_seed[v]['S4'][-1]:.4f}", flush=True)

    ens = {v: {s: np.mean(proba[v][s], axis=0) for s in TEST_SETS} for v in VARIANTS}
    pred = {v: np.array(CLASSES)[ens[v]["S4"].argmax(axis=1)] for v in VARIANTS}
    y = y_test["S4"]
    rng = np.random.default_rng(2026)
    deltas = []
    for _ in range(B):
        idx = rng.integers(0, len(y), len(y))
        deltas.append(balanced_accuracy(y[idx], pred["A0"][idx]) - balanced_accuracy(y[idx], pred["A1"][idx]))
    delta = balanced_accuracy(y, pred["A0"]) - balanced_accuracy(y, pred["A1"])
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    if lo > 0:
        verdict = "Fitur SWT menyumbang akurasi"
    elif hi < 0:
        verdict = "Fitur SWT menurunkan akurasi"
    else:
        verdict = "Kontribusi fitur SWT tidak terdeteksi"

    result = {
        "swt_columns": [feature_names()[i] for i in SWT_COLS],
        "seeds": list(SEEDS),
        "ba_per_seed": per_seed,
        "ba_ensemble": {v: {s: round(ba_from_proba(y_test[s], ens[v][s]), 4) for s in TEST_SETS} for v in VARIANTS},
        "s_swt": {"delta_ba_s4": round(delta, 4), "ci95": [round(float(lo), 4), round(float(hi), 4)], "keputusan": verdict},
    }
    (ARTIFACTS_DIR / "swt_ablation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Ablasi fitur energi SWT pada detektor resmi",
        "",
        "Praregistrasi: `docs/praregistrasi_fase1_sintetis.md` adendum 4. Skrip: `ml/src/swt_ablation.py`.",
        "",
        "## Balanced accuracy uji (rata-rata ± simpangan baku 3 seed)",
        "",
        "| Varian | " + " | ".join(TEST_SETS) + " |",
        "|---|" + "---|" * len(TEST_SETS),
    ]
    for v in VARIANTS:
        cells = [f"{np.mean(per_seed[v][s]):.3f} ± {np.std(per_seed[v][s]):.3f}" for s in TEST_SETS]
        lines.append(f"| {VARIANT_LABEL[v]} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Hipotesis S-SWT (set uji S4, probabilitas rata-rata 3 seed)",
        "",
        "| ΔBA (A0 − A1) | CI95 | Keputusan |",
        "|---|---|---|",
        f"| {delta:+.4f} | [{lo:+.4f}, {hi:+.4f}] | **{verdict}** |",
        "",
    ]
    (ARTIFACTS_DIR / "swt_ablation.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

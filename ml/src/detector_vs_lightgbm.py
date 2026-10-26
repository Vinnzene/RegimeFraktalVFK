"""Uji formal detektor resmi vs LightGBM pada data sintetis (Fase 1 adendum 6).

    python ml/src/detector_vs_lightgbm.py

Detektor resmi dimuat apa adanya; LightGBM dilatih ulang persis seperti
synthetic_benchmark.train_models. Deret uji saling independen, sehingga uji
McNemar per deret sah, berdampingan dengan bootstrap berpasangan ΔBA.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR  # noqa: E402
from synthetic_benchmark import (  # noqa: E402
    TRAIN_SCENARIOS,
    balanced_accuracy,
    bootstrap_diff,
    concat,
    labels_for,
    load,
)
from synthetic_regimes import CLASSES, PRIMARY  # noqa: E402

N = 500
MAIN = "S4"
DESCRIPTIVE = ("S1", "S4k")


def mcnemar_exact(correct_a: np.ndarray, correct_b: np.ndarray) -> dict:
    """McNemar eksak dua sisi: binomial atas pasangan yang berbeda hasil."""
    a_only = int(np.sum(correct_a & ~correct_b))
    b_only = int(np.sum(~correct_a & correct_b))
    p = binomtest(a_only, a_only + b_only, 0.5).pvalue if a_only + b_only else 1.0
    return {"detector_only_correct": a_only, "lightgbm_only_correct": b_only, "p_two_sided": float(p)}


def main() -> None:
    import tensorflow as tf  # type: ignore

    from app.services.feature_builder import apply_scaler
    from ml_layers import AttentionPooling
    from tabular_baselines import fit_tabular

    meta = json.loads((ARTIFACTS_DIR / "detector_meta.json").read_text(encoding="utf-8"))["d_sintetis"]
    model = tf.keras.models.load_model(ARTIFACTS_DIR / meta["file"], custom_objects={"AttentionPooling": AttentionPooling})
    mu_d, sd_d = np.array(meta["feature_mean"]), np.array(meta["feature_std"])
    detector = lambda d: np.array(CLASSES)[  # noqa: E731
        model.predict([apply_scaler(d["ps"], meta["ps_scaler"]), (d["feat"] - mu_d) / sd_d], batch_size=1024, verbose=0).argmax(axis=1)
    ]

    # LightGBM: prosedur benchmark (normalisasi dari data latih, seed 42).
    tr = concat([load(s, N, "train") for s in TRAIN_SCENARIOS])
    va = concat([load(s, N, "validation") for s in TRAIN_SCENARIOS])
    mu, sd = tr["feat"].mean(axis=0), tr["feat"].std(axis=0)
    sd[sd < 1e-12] = 1.0
    onehot = lambda y: np.eye(3)[[CLASSES.index(c) for c in y]]  # noqa: E731
    scale = lambda d: (d["feat"] - mu) / sd  # noqa: E731
    proba = fit_tabular("lightgbm", scale(tr), onehot(labels_for(tr["h"], PRIMARY)), scale(va), onehot(labels_for(va["h"], PRIMARY)), 42)
    lightgbm = lambda d: np.array(CLASSES)[proba(scale(d)).argmax(axis=1)]  # noqa: E731

    out = {"adendum": "praregistrasi_fase1_sintetis.md adendum 6", "n": N, "thresholds": list(PRIMARY), "scenarios": {}}
    for s in (MAIN, *DESCRIPTIVE):
        d = load(s, N, "test")
        y = labels_for(d["h"], PRIMARY)
        p_det, p_lgb = detector(d), lightgbm(d)
        boot = bootstrap_diff(y, p_det, y, p_lgb, paired=True)
        mc = mcnemar_exact(p_det == y, p_lgb == y)
        out["scenarios"][s] = {
            "n_series": int(len(y)),
            "ba_detector": round(balanced_accuracy(y, p_det), 4),
            "ba_lightgbm": round(balanced_accuracy(y, p_lgb), 4),
            "bootstrap": boot,
            "mcnemar": mc,
        }
        print(s, out["scenarios"][s], flush=True)

    m = out["scenarios"][MAIN]
    proven = m["bootstrap"]["ci95"][0] > 0 and m["mcnemar"]["p_two_sided"] < 0.05
    out["decision"] = "TERBUKTI: detektor lebih akurat daripada LightGBM pada S4" if proven else "SETARA: selisih tidak melampaui variasi sampling"

    (ARTIFACTS_DIR / "detector_vs_lightgbm.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    fmt = lambda v: f"{v:.3f}".replace(".", ",")  # noqa: E731
    lines = [
        "# Uji formal detektor resmi vs LightGBM (Fase 1 adendum 6)", "",
        "Analisis tambahan setelah benchmark dibaca; ditulis dan di-commit sebelum dijalankan.",
        f"Data uji sintetis n = {N}, deret independen, ambang 0,47/0,53. Utama: {MAIN}.", "",
        "| Skenario | BA detektor | BA LightGBM | ΔBA [CI95] | p bootstrap (1 sisi) | Hanya detektor benar | Hanya LightGBM benar | p McNemar |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s, r in out["scenarios"].items():
        b, mc = r["bootstrap"], r["mcnemar"]
        lines.append(
            f"| {s}{' (utama)' if s == MAIN else ''} | {fmt(r['ba_detector'])} | {fmt(r['ba_lightgbm'])} | "
            f"{b['diff']:+.3f} [{b['ci95'][0]:+.3f}; {b['ci95'][1]:+.3f}] | {b['p_raw']:.4f} | "
            f"{mc['detector_only_correct']} | {mc['lightgbm_only_correct']} | {mc['p_two_sided']:.4f} |".replace(".", ",")
        )
    lines += ["", f"**Keputusan:** {out['decision']}."]
    (ARTIFACTS_DIR / "detector_vs_lightgbm.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out["decision"])


if __name__ == "__main__":
    main()

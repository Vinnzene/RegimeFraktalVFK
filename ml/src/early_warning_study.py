"""Peringatan dini dua kecepatan — praregistrasi docs/praregistrasi_peringatan_dini.md.

Jalankan (setelah `regime_change_study.py` dan `fast_detection_study.py`, yang
membuat cache deret panjang dan data latih):
    python ml/src/early_warning_study.py

D0 (detektor resmi) menentukan label; A (jendela 500, dilatih juga pada
pergantian regime) hanya memberi peringatan bila mengonfirmasi kelas yang
berbeda dari keadaan D0.

Keluaran:
    ml/artifacts/early_warning_study.{json,md}
    ml/artifacts/detector/early_warning_s{seed}.keras (tidak di-commit)
    ml/artifacts/detector/early_warning_meta.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.services import ai_detector  # noqa: E402
from fast_detection_study import STATIONARY, concat, dataset, long_series  # noqa: E402
from regime_change_study import K, N_SERIES, confirmed_events  # noqa: E402
from synthetic_benchmark import labels_for  # noqa: E402
from synthetic_regimes import CLASSES, PRIMARY  # noqa: E402

SEEDS = (42, 43, 44)
B = 2000
OUT = ARTIFACTS_DIR / "detector"


# ------------------------------------------------------------------ model A


def train_a(seed: int, meta: Dict[str, Any]):
    import tensorflow as tf  # type: ignore

    from app.services.feature_builder import apply_scaler, fit_scaler
    from model_architecture import build_hybrid_attention_bilstm, compile_model
    from train import class_weights

    scen = STATIONARY + ("S5",)
    tr = concat([dataset(s, "train", 500, meta) for s in scen])
    va = concat([dataset(s, "validation", 500, meta) for s in scen])
    mu, sd = tr["feat"].mean(axis=0), tr["feat"].std(axis=0)
    sd[sd < 1e-12] = 1.0
    sc = fit_scaler(tr["ps"])
    onehot = lambda h: np.eye(3)[[CLASSES.index(c) for c in labels_for(h, PRIMARY)]]  # noqa: E731
    X = lambda d: [apply_scaler(d["ps"], sc), (d["feat"] - mu) / sd]  # noqa: E731

    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(seed)
    model = compile_model(build_hybrid_attention_bilstm(tr["ps"].shape[1:], tr["feat"].shape[1], 3))
    model.fit(
        X(tr), onehot(tr["h"]), validation_data=(X(va), onehot(va["h"])),
        epochs=80, batch_size=64, class_weight=class_weights(onehot(tr["h"])), shuffle=True, verbose=0,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
        ],
    )
    OUT.mkdir(parents=True, exist_ok=True)
    model.save(OUT / f"early_warning_s{seed}.keras")
    scaler = {"file": f"detector/early_warning_s{seed}.keras", "feature_mean": mu.round(8).tolist(),
              "feature_std": sd.round(8).tolist(), "ps_scaler": sc}
    return (lambda d: model.predict(X(d), batch_size=1024, verbose=0)), scaler


# ------------------------------------------------------------------ peringatan


def states(labels: np.ndarray) -> List[Optional[str]]:
    """Keadaan terkonfirmasi (K jendela berturut-turut) di setiap titik deteksi."""
    out, state, run_cls, run = [], None, None, 0
    for lab in labels:
        if lab in CLASSES:
            run = run + 1 if lab == run_cls else 1
            run_cls = lab
        else:
            run_cls, run = None, 0
        if run >= K:
            state = run_cls
        out.append(state)
    return out


def warnings(d0: np.ndarray, a: np.ndarray, pos: np.ndarray) -> List[Tuple[int, str]]:
    """(bar, kelas) setiap peringatan: keadaan A ≠ keadaan D0, sekali per pasangan keadaan."""
    s0, sa = states(d0), states(a)
    out, warned, prev = [], False, (None, None)
    for t, x0, xa in zip(pos, s0, sa):
        if (x0, xa) != prev:
            warned = False
            prev = (x0, xa)
        if xa is not None and x0 is not None and xa != x0 and not warned:
            out.append((int(t), str(xa)))
            warned = True
    return out


def series_stats(d0: np.ndarray, a: np.ndarray, pos: np.ndarray, segs: np.ndarray) -> Dict[str, Any]:
    warns = warnings(d0, a, pos)
    confirms = confirmed_events(d0, pos)
    seg_of = lambda t: next(str(s[2]) for s in segs if int(s[0]) <= t < int(s[1]))  # noqa: E731
    leads = []
    for j in range(1, len(segs)):
        c, end, k = int(segs[j][0]), int(segs[j][1]), str(segs[j][2])
        td = next((t for t, cls in confirms if cls == k and c <= t < end), None)
        if td is None:
            continue
        tw = next((t for t, cls in warns if cls == k and c <= t < td), None)
        leads.append(td - tw if tw is not None else 0)
    correct = sum(1 for t, cls in warns if cls == seg_of(t))
    return {"leads": leads, "warnings": len(warns), "correct": correct,
            "bars": int(pos[-1] - pos[0])}


def pooled(ms: List[Dict[str, Any]]) -> Dict[str, float]:
    leads = [x for m in ms for x in m["leads"]]
    w = sum(m["warnings"] for m in ms)
    c = sum(m["correct"] for m in ms)
    return {
        "median_lead": float(np.median(leads)) if leads else float("nan"),
        "mean_lead": float(np.mean(leads)) if leads else float("nan"),
        "share_warned": float(np.mean([x > 0 for x in leads])) if leads else float("nan"),
        "precision": c / w if w else float("nan"),
        "false_per_1000": 1000 * (w - c) / sum(m["bars"] for m in ms),
        "warnings_per_1000": 1000 * w / sum(m["bars"] for m in ms),
        "n_changes": len(leads),
    }


def main() -> None:
    meta = ai_detector.meta()
    t0 = time.time()
    longs = [long_series(i, 500, meta) for i in range(N_SERIES)]
    d0_probs = [ai_detector.predict_proba(d["feat"], d["ps"], meta) for d in longs]

    a_probs: List[List[np.ndarray]] = []
    scalers = []
    for seed in SEEDS:
        ts = time.time()
        pred, sc = train_a(seed, meta)
        a_probs.append([pred(d) for d in longs])
        scalers.append(sc)
        print(f"  A seed {seed}: {time.time() - ts:.0f}s", flush=True)
    (OUT / "early_warning_meta.json").write_text(json.dumps({
        "classes": list(CLASSES), "thresholds": list(PRIMARY), "window": 500, "sub_window": 128, "seq_len": 32,
        "sigma_per_bar": meta["sigma_per_bar"], "models": scalers,
        "catatan": "Model A (latih pergantian). Hanya untuk peringatan dini bila lolos praregistrasi_peringatan_dini §5.",
    }), encoding="utf-8")

    per = []
    for i, d in enumerate(longs):
        lab0 = np.array(CLASSES)[d0_probs[i].argmax(axis=1)]
        laba = np.array(CLASSES)[np.mean([p[i] for p in a_probs], axis=0).argmax(axis=1)]
        per.append(series_stats(lab0, laba, d["pos"], d["segs"]))
    point = pooled(per)

    rng = np.random.default_rng(2026)
    boot = [pooled([per[j] for j in rng.integers(0, N_SERIES, N_SERIES)])["median_lead"] for _ in range(B)]
    ci = [float(np.nanpercentile(boot, 2.5)), float(np.nanpercentile(boot, 97.5))]
    h1 = ci[0] > 0
    install = h1 and point["precision"] >= 0.70 and point["false_per_1000"] <= 1.0

    out = {
        "preregistration": "docs/praregistrasi_peringatan_dini.md",
        "pooled": {k: round(v, 4) for k, v in point.items()},
        "dini_h1": {"ci95_median_lead": [round(x, 1) for x in ci], "keputusan": "TERBUKTI" if h1 else "TIDAK TERBUKTI"},
        "pasang_di_sistem": install, "seconds": round(time.time() - t0),
    }
    p = point
    md = "\n".join([
        "# Peringatan dini dua kecepatan", "",
        "Praregistrasi: `docs/praregistrasi_peringatan_dini.md`. Skrip: `ml/src/early_warning_study.py`.", "",
        f"40 deret S4 × 20.000 bar; {p['n_changes']} pergantian yang dikonfirmasi D0; K = 3.", "",
        "| Ukuran | Nilai |", "|---|---|",
        f"| Median waktu yang dihemat (lead) | {p['median_lead']:.0f} bar |",
        f"| Rata-rata lead | {p['mean_lead']:.0f} bar |",
        f"| Pergantian yang didahului peringatan benar | {p['share_warned'] * 100:.1f}% |",
        f"| Ketepatan peringatan | {p['precision'] * 100:.1f}% |",
        f"| Peringatan per 1.000 bar | {p['warnings_per_1000']:.2f} |",
        f"| Peringatan salah per 1.000 bar | {p['false_per_1000']:.2f} |", "",
        f"**DINI-H1** (median lead > 0): CI95 [{ci[0]:.0f}, {ci[1]:.0f}] bar → **{out['dini_h1']['keputusan']}**", "",
        "**Keputusan pemasangan (§5: H1 terbukti, ketepatan ≥ 70%, salah ≤ 1,0 / 1.000 bar):** "
        + ("dipasang di sistem sebagai peringatan dini." if install else "tidak dipasang; dilaporkan sebagai temuan."), "",
    ])
    path = ARTIFACTS_DIR / "early_warning_study.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()

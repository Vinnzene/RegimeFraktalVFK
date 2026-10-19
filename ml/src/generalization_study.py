"""Uji generalisasi lintas aset (praregistrasi generalisasi + adendum 1–2).

Jalankan (setelah `fetch_assets.py` dan `train_detector.py`):
    python ml/src/generalization_study.py --stage features   # fitur per window (paralel, di-cache)
    python ml/src/generalization_study.py --stage run        # deteksi, VR maju, bootstrap, G1–G4

Empat detektor: D-sintetis (utama, latih sintetis), D-BTC (regresi logistik
latih-BTC), D-klasik (VR(2) terkalibrasi Fase 1), D-konsensus (R/S–DFA, ambang
BTC train_only). Ukuran: Δ = rata-rata log VR(4) maju setelah label
persistent − setelah label anti-persistent. Detektor yang benar: Δ > 0.

Keluaran:
    ml/artifacts/generalization_cache/*.npz   (tidak di-commit)
    ml/artifacts/generalization.{json,md}
    ml/artifacts/figures/fig_generalization.png
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, PROCESSED_DIR  # noqa: E402
from synthetic_benchmark import classify  # noqa: E402
from synthetic_regimes import CLASSES, SIGMA  # noqa: E402

CACHE = ARTIFACTS_DIR / "generalization_cache"
L = 500
STRIDE = 4
HORIZON = {"1h": 200, "1d": 60}
B = 2000
DETECTORS = ("D-sintetis", "D-BTC", "D-klasik", "D-konsensus")

ASSETS: List[Dict[str, str]] = [
    *({"symbol": s, "group": "kripto", "tf": "1h"} for s in
      ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT")),
    {"symbol": "PAXGUSDT", "group": "emas", "tf": "1h"},
    {"symbol": "GCF", "group": "emas", "tf": "1d"},
    *({"symbol": s, "group": "saham_idx", "tf": "1d"} for s in
      ("JKSE", "BBCAJK", "BBRIJK", "BMRIJK", "BBNIJK", "TLKMJK", "ASIIJK", "ANTMJK", "UNVRJK", "ICBPJK", "ADROJK")),
]


# ------------------------------------------------------------------ fitur


def _window_features(w: np.ndarray) -> Dict[str, Any]:
    from app.services.hurst_dfa import dfa_alpha, hurst_rs
    from app.services.multifractal import build_feature_matrix as build_mf
    from app.services.persistence_sequence import build_persistence_sequences
    from app.services.structural_features import build_feature_matrix, variance_ratio

    sd = w.std()
    wn = w * (SIGMA / sd) if sd > 0 else w
    t = len(wn) - 1
    vr2 = variance_ratio(wn, 2)
    return {
        "feat": np.concatenate([build_feature_matrix(wn, [t], L, 4)[0], build_mf(wn, [t], L)[0]]),
        "ps": build_persistence_sequences(wn, [t], L, 128, 32)[0].astype(np.float32),
        "est": np.array([hurst_rs(wn), dfa_alpha(wn), 0.5 * (1 + np.log2(vr2)) if vr2 > 0 else np.nan]),
    }


def build_features(jobs: int) -> None:
    from joblib import Parallel, delayed

    from app.services.structural_features import variance_ratio

    CACHE.mkdir(parents=True, exist_ok=True)
    for a in ASSETS:
        path = CACHE / f"{a['symbol']}_{a['tf']}.npz"
        if path.exists():
            continue
        t0 = time.time()
        df = pd.read_parquet(PROCESSED_DIR / f"ohlcv_{a['symbol'].lower()}_{a['tf']}.parquet")
        df = df[df["close"] > 0].reset_index(drop=True)
        r = np.diff(np.log(df["close"].to_numpy(dtype=float)))
        m = HORIZON[a["tf"]]
        pos = np.arange(L - 1, len(r) - 1 - m, STRIDE)
        rows = Parallel(n_jobs=jobs, batch_size=32)(delayed(_window_features)(r[t - L + 1 : t + 1]) for t in pos)
        fwd = np.array([variance_ratio(r[t + 1 : t + 1 + m], 4) for t in pos])
        np.savez_compressed(
            path,
            time=df["time"].to_numpy()[pos + 1],
            feat=np.nan_to_num(np.stack([x["feat"] for x in rows])),
            ps=np.stack([x["ps"] for x in rows]),
            est=np.stack([x["est"] for x in rows]),
            fwd_log_vr=np.log(np.clip(fwd, 1e-9, None)),
        )
        print(f"{path.name}: {len(pos)} titik, {time.time() - t0:.0f}s", flush=True)


# ------------------------------------------------------------------ deteksi


def detect(meta: Dict[str, Any], d: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    import joblib
    import tensorflow as tf  # type: ignore

    from app.services.feature_builder import apply_scaler
    import model_architecture  # noqa: F401  (mendaftarkan AttentionPooling)

    ds, db = meta["d_sintetis"], meta["d_btc"]
    global _MODEL, _LOGREG
    if "_MODEL" not in globals():
        _MODEL = tf.keras.models.load_model(ARTIFACTS_DIR / ds["file"])
        _LOGREG = joblib.load(ARTIFACTS_DIR / db["file"])
    cls = np.array(CLASSES)
    F_s = (d["feat"] - np.array(ds["feature_mean"])) / np.array(ds["feature_std"])
    S = apply_scaler(d["ps"], ds["ps_scaler"])
    F_b = (d["feat"] - np.array(db["feature_mean"])) / np.array(db["feature_std"])
    thr = meta["d_konsensus"]["thresholds"]
    rs, dfa = classify(d["est"][:, 0], *thr["hurst"]), classify(d["est"][:, 1], *thr["dfa"])
    return {
        "D-sintetis": cls[_MODEL.predict([S, F_s], batch_size=1024, verbose=0).argmax(axis=1)],
        "D-BTC": cls[_LOGREG.predict(F_b)],
        "D-klasik": classify(d["est"][:, 2], *meta["d_klasik"]["thresholds"]),
        "D-konsensus": np.where(rs == dfa, rs, "uncertain"),
    }


def delta(labels: np.ndarray, fwd: np.ndarray) -> float:
    p, a = fwd[labels == "persistent"], fwd[labels == "anti_persistent"]
    return float(p.mean() - a.mean()) if len(p) and len(a) else math.nan


def analyse(a: Dict[str, str], meta: Dict[str, Any]) -> Dict[str, Any]:
    with np.load(CACHE / f"{a['symbol']}_{a['tf']}.npz") as z:
        d = {k: z[k] for k in z.files}
    preds = detect(meta, d)
    fwd = d["fwd_log_vr"]
    n = len(fwd)
    valid = {k: np.ones(n, bool) for k in DETECTORS}
    if a["symbol"] == "BTCUSDT":
        valid["D-BTC"] = d["time"] > meta["d_btc"]["btc_train_end_time"]

    block = math.ceil((L + HORIZON[a["tf"]]) / STRIDE)
    rng = np.random.default_rng(42)
    n_blocks = math.ceil(n / block)
    boot = {k: np.full(B, np.nan) for k in DETECTORS}
    for b in range(B):
        starts = rng.integers(0, max(1, n - block + 1), n_blocks)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]
        for k in DETECTORS:
            sel = idx[valid[k][idx]]
            boot[k][b] = delta(preds[k][sel], fwd[sel])

    def ci(x: np.ndarray) -> Dict[str, Any]:
        ok = x[np.isfinite(x)]
        if len(ok) < B * 0.5:
            return {"ci95": None, "dropped": round(1 - len(ok) / B, 3)}
        return {"ci95": [round(float(np.quantile(ok, 0.025)), 4), round(float(np.quantile(ok, 0.975)), 4)],
                "dropped": round(1 - len(ok) / B, 3)}

    out: Dict[str, Any] = {**a, "n_points": n, "block": block, "detectors": {}, "vs_D_sintetis": {}}
    for k in DETECTORS:
        lab = preds[k][valid[k]]
        out["detectors"][k] = {
            "delta": round(delta(lab, fwd[valid[k]]), 4),
            **ci(boot[k]),
            "n": int(valid[k].sum()),
            "share": {c: round(float(np.mean(lab == c)), 3) for c in (*CLASSES, "uncertain") if np.any(lab == c)},
        }
    for k in DETECTORS[1:]:
        out["vs_D_sintetis"][k] = {"diff": round(out["detectors"]["D-sintetis"]["delta"] - out["detectors"][k]["delta"], 4),
                                   **ci(boot["D-sintetis"] - boot[k])}
    return out


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    pos = lambda c: c is not None and c[0] > 0  # noqa: E731
    neg = lambda c: c is not None and c[1] < 0  # noqa: E731
    groups: Dict[str, Any] = {}
    for g in ("kripto", "emas", "saham_idx"):
        rs = [r for r in results if r["group"] == g]
        ok = sum(pos(r["detectors"]["D-sintetis"]["ci95"]) for r in rs)
        groups[g] = {"assets": len(rs), "g1_pass": ok, "generalizes": ok >= math.ceil(2 * len(rs) / 3)}
    comp = {}
    for k, name in (("D-BTC", "G2"), ("D-konsensus", "G3"), ("D-klasik", "G4")):
        comp[name] = {
            "vs": k,
            "d_sintetis_better": sum(pos(r["vs_D_sintetis"][k]["ci95"]) for r in results),
            "d_sintetis_worse": sum(neg(r["vs_D_sintetis"][k]["ci95"]) for r in results),
            "assets": len(results),
        }
    return {"groups": groups, "comparisons": comp}


def to_markdown(out: Dict[str, Any]) -> str:
    s = out["summary"]
    lines = ["# Uji generalisasi lintas aset", "",
             "Praregistrasi: `docs/praregistrasi_generalisasi_aset.md` + adendum. Δ = log VR(4) maju (persistent − anti-persistent); benar bila Δ > 0.", "",
             "## Ringkasan", "", "| Kelompok | Aset | G1 lolos (CI95 Δ D-sintetis > 0) | Tergeneralisasi (≥ 2/3) |", "|---|---|---|---|"]
    for g, v in s["groups"].items():
        lines.append(f"| {g} | {v['assets']} | {v['g1_pass']} | **{'YA' if v['generalizes'] else 'TIDAK'}** |")
    lines += ["", "| Uji | D-sintetis vs | Lebih baik (CI > 0) | Lebih buruk (CI < 0) | Aset |", "|---|---|---|---|---|"]
    for name, v in s["comparisons"].items():
        lines.append(f"| {name} | {v['vs']} | {v['d_sintetis_better']} | {v['d_sintetis_worse']} | {v['assets']} |")
    lines += ["", "## Per aset", "", "| Aset | Kelompok | TF | Titik | " + " | ".join(f"Δ {k} [CI95]" for k in DETECTORS) + " |",
              "|---|---|---|---|" + "---|" * len(DETECTORS)]
    for r in out["assets"]:
        cells = []
        for k in DETECTORS:
            v = r["detectors"][k]
            ci = f"[{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]" if v["ci95"] else "[n/a]"
            cells.append(f"{v['delta']:+.3f} {ci}")
        lines.append(f"| {r['symbol']} | {r['group']} | {r['tf']} | {r['n_points']} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def figure(out: Dict[str, Any]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    res = out["assets"]
    labels = [r["symbol"].replace("USDT", "").replace("JK", "") for r in res]
    colors = {"D-sintetis": "#ff7a1a", "D-BTC": "#4a9eff", "D-klasik": "#8b949e", "D-konsensus": "#b07cf5"}
    fig, ax = plt.subplots(figsize=(14, 4.6))
    x = np.arange(len(res))
    w = 0.2
    for i, k in enumerate(DETECTORS):
        vals = [r["detectors"][k]["delta"] for r in res]
        errs = [[v - (r["detectors"][k]["ci95"] or [v, v])[0] for v, r in zip(vals, res)],
                [(r["detectors"][k]["ci95"] or [v, v])[1] - v for v, r in zip(vals, res)]]
        ax.bar(x + (i - 1.5) * w, vals, w, yerr=errs, color=colors[k], label=k, capsize=1.5, error_kw={"lw": 0.6})
    ax.axhline(0, color="#444", lw=0.8)
    ax.set_xticks(x, labels, rotation=45, ha="right")
    ax.set_ylabel("Δ log VR(4) maju")
    ax.set_title("Pemisahan perilaku masa depan: persistent − anti-persistent (lebih tinggi = lebih baik)")
    ax.legend(ncol=4, fontsize=9)
    fig.tight_layout()
    (ARTIFACTS_DIR / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(ARTIFACTS_DIR / "figures" / "fig_generalization.png", dpi=150)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", choices=["features", "run"], required=True)
    p.add_argument("--jobs", type=int, default=12)
    args = p.parse_args()
    if args.stage == "features":
        build_features(args.jobs)
        return
    meta = json.loads((ARTIFACTS_DIR / "detector_meta.json").read_text(encoding="utf-8"))
    results = []
    for a in ASSETS:
        t0 = time.time()
        results.append(analyse(a, meta))
        print(f"{a['symbol']:10s} {time.time() - t0:.0f}s", flush=True)
    out = {"preregistration": "docs/praregistrasi_generalisasi_aset.md", "horizon_bars": HORIZON,
           "assets": results, "summary": summarize(results)}
    (ARTIFACTS_DIR / "generalization.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = to_markdown(out)
    (ARTIFACTS_DIR / "generalization.md").write_text(md, encoding="utf-8")
    figure(out)
    print(md)


if __name__ == "__main__":
    main()

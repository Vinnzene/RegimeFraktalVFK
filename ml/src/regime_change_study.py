"""Deteksi pergantian regime (§8) dan kurva abstain — praregistrasi Fase 1 adendum 5.

Jalankan (setelah `synthetic_benchmark.py --stage data` dan `train_detector.py`):
    python ml/src/regime_change_study.py

B. Abstain: kurva cakupan vs BA tercakup; τ dipilih di validasi campuran S1–S4.
A. Pergantian regime: 40 deret S4 × 20.000 bar dengan 8–12 titik ganti,
   detektor bergulir (jendela 500, langkah 4), konfirmasi K = 3.

Keluaran: ml/artifacts/regime_change_study.{json,md}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, PROCESSED_DIR  # noqa: E402
from app.services import ai_detector  # noqa: E402
from synthetic_benchmark import TRAIN_SCENARIOS, balanced_accuracy, classify, concat, consensus, labels_for, load  # noqa: E402
from synthetic_regimes import CLASSES, PRIMARY, SIGMA, CryptoParams, crypto_noise, fgn, sample_h  # noqa: E402

N_SERIES = 40
LENGTH = 20_000
MIN_SEG = 1_000
L = 500
STRIDE = 4
K = 3
B = 2000
TAUS = [round(0.40 + 0.05 * i, 2) for i in range(12)]
CACHE = ARTIFACTS_DIR / "regime_change_cache"
METHODS = ("D-sintetis", "Konsensus naif", "Konsensus terkalibrasi", "VR(2) terkalibrasi", "D-sintetis + abstain")


# ------------------------------------------------------------------ B. abstain


def proba_of(d: Dict[str, np.ndarray], m: Dict[str, Any]) -> np.ndarray:
    return ai_detector.predict_proba(d["feat"], d["ps"], m)


def coverage_curve(y: np.ndarray, p: np.ndarray) -> List[Dict[str, float]]:
    pred = np.array(CLASSES)[p.argmax(axis=1)]
    conf = p.max(axis=1)
    rows = []
    for tau in TAUS:
        keep = conf >= tau
        rows.append({
            "tau": tau, "coverage": round(float(keep.mean()), 4),
            "ba_covered": round(balanced_accuracy(y[keep], pred[keep]), 4) if keep.sum() >= 30 else float("nan"),
        })
    return rows


def abstain_study(m: Dict[str, Any]) -> Dict[str, Any]:
    va = concat([load(s, L, "validation") for s in TRAIN_SCENARIOS])
    curve_val = coverage_curve(labels_for(va["h"], PRIMARY), proba_of(va, m))
    ok = [r for r in curve_val if r["ba_covered"] >= 0.90]
    if ok:
        tau, rule = ok[0]["tau"], "τ terkecil dengan BA tercakup validasi ≥ 0,90"
    else:
        cand = [r for r in curve_val if r["coverage"] >= 0.20 and np.isfinite(r["ba_covered"])]
        tau, rule = max(cand, key=lambda r: r["ba_covered"])["tau"], "BA tercakup tertinggi dengan cakupan ≥ 20% (tidak ada yang ≥ 0,90)"
    tests = {}
    for s in ("S4", "S4k"):
        d = load(s, L, "test")
        tests[s] = coverage_curve(labels_for(d["h"], PRIMARY), proba_of(d, m))
    btc = {}
    for tf in ("1h", "4h"):
        path = PROCESSED_DIR / "cache" / f"ai_regime_btcusdt_{tf}.npz"
        if path.exists():
            with np.load(path) as z:
                btc[tf] = round(float((z["proba"].max(axis=1) < tau).mean()), 4)
    return {"tau": tau, "rule": rule, "validation": curve_val, "test": tests, "btc_uncertain_share": btc}


# ------------------------------------------------------------------ A. data deret panjang


def make_long(i: int) -> Tuple[np.ndarray, List[Tuple[int, int, str]]]:
    rng = np.random.default_rng(np.random.SeedSequence([8000, i]))
    n_cp = int(rng.integers(8, 13))
    # Titik ganti dengan panjang segmen minimum: sebar sisa panjang secara acak.
    slack = LENGTH - MIN_SEG * (n_cp + 1)
    extra = np.diff(np.concatenate([[0], np.sort(rng.integers(0, slack + 1, n_cp)), [slack]]))
    bounds = np.concatenate([[0], np.cumsum(MIN_SEG + extra)])
    segs: List[Tuple[int, int, str]] = []
    cls = str(rng.choice(CLASSES))
    parts = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        if segs:
            cls = str(rng.choice([c for c in CLASSES if c != segs[-1][2]]))
        parts.append(fgn(int(b - a), sample_h(cls, rng, PRIMARY), rng))
        segs.append((int(a), int(b), cls))
    r = crypto_noise(np.concatenate(parts), CryptoParams(), rng, heavy=True, sv=True, jump=True)
    return SIGMA * r / r.std(), segs


def featurize_series(i: int, m: Dict[str, Any]) -> Dict[str, Any]:
    path = CACHE / f"series_{i}.npz"
    if path.exists():
        with np.load(path, allow_pickle=True) as z:
            return {k: z[k] for k in z.files}
    from app.services.hurst_dfa import dfa_alpha, hurst_rs
    from app.services.structural_features import variance_ratio

    r, segs = make_long(i)
    pos = np.arange(L - 1, len(r), STRIDE)
    feat, ps, est = [], [], []
    for t in pos:
        w = r[t - L + 1 : t + 1]
        f = ai_detector.window_features(w, m)
        feat.append(f["feat"])
        ps.append(f["ps"])
        vr2 = variance_ratio(w, 2)
        est.append([hurst_rs(w), dfa_alpha(w), 0.5 * (1 + np.log2(vr2)) if vr2 > 0 else np.nan])
    out = {
        "pos": pos, "feat": np.nan_to_num(np.stack(feat)), "ps": np.stack(ps).astype(np.float32),
        "est": np.array(est), "segs": np.array(segs, dtype=object),
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **out)
    return out


# ------------------------------------------------------------------ A. konfirmasi & metrik


def confirmed_events(labels: np.ndarray, pos: np.ndarray) -> List[Tuple[int, str]]:
    """(bar akhir jendela, kelas baru) untuk tiap pergantian terkonfirmasi K jendela."""
    events, state, run_cls, run = [], None, None, 0
    for lab, t in zip(labels, pos):
        if lab in CLASSES:
            run = run + 1 if lab == run_cls else 1
            run_cls = lab
        else:
            run_cls, run = None, 0
        if run >= K and run_cls != state:
            if state is not None:
                events.append((int(t), str(run_cls)))
            state = run_cls
    return events


def series_metrics(events: List[Tuple[int, str]], segs: np.ndarray, n_bars: int) -> Dict[str, Any]:
    delays, missed = [], 0
    for j in range(1, len(segs)):
        c, end, k = int(segs[j][0]), int(segs[j][1]), str(segs[j][2])
        hit = [t for t, cls in events if cls == k and c <= t < end]
        if hit:
            delays.append(hit[0] - c)
        else:
            missed += 1
    seg_of = lambda t: next(str(s[2]) for s in segs if int(s[0]) <= t < int(s[1]))  # noqa: E731
    fa = sum(1 for t, cls in events if cls != seg_of(t))
    return {"delays": delays, "missed": missed, "changes": len(segs) - 1, "false_alarms": fa, "bars": n_bars}


def pooled(ms: List[Dict[str, Any]]) -> Dict[str, float]:
    d = [x for m in ms for x in m["delays"]]
    return {
        "median_delay": float(np.median(d)) if d else float("nan"),
        "fa_per_1000": 1000 * sum(m["false_alarms"] for m in ms) / sum(m["bars"] for m in ms),
        "missed_share": sum(m["missed"] for m in ms) / sum(m["changes"] for m in ms),
    }


def change_study(m: Dict[str, Any], tau: float) -> Dict[str, Any]:
    from joblib import Parallel, delayed

    t0 = time.time()
    data = Parallel(n_jobs=-1)(delayed(featurize_series)(i, m) for i in range(N_SERIES))
    print(f"  fitur {N_SERIES} deret {time.time() - t0:.0f}s", flush=True)
    cal = json.loads((ARTIFACTS_DIR / "synthetic_benchmark.json").read_text(encoding="utf-8"))["utama"]["lengths"]["500"]["calibrated_thresholds"]
    per: Dict[str, List[Dict[str, Any]]] = {k: [] for k in METHODS}
    for d in data:
        p = proba_of(d, m)
        pred = np.array(CLASSES)[p.argmax(axis=1)]
        rs, dfa, vr2 = d["est"][:, 0], d["est"][:, 1], d["est"][:, 2]
        labels = {
            "D-sintetis": pred,
            "Konsensus naif": consensus(rs, dfa, PRIMARY, PRIMARY),
            "Konsensus terkalibrasi": consensus(rs, dfa, tuple(cal["rs"]), tuple(cal["dfa"])),
            "VR(2) terkalibrasi": classify(vr2, *cal["vr2"]),
            "D-sintetis + abstain": np.where(p.max(axis=1) >= tau, pred, "uncertain"),
        }
        n_bars = int(d["pos"][-1] - d["pos"][0])
        for k, lab in labels.items():
            per[k].append(series_metrics(confirmed_events(lab, d["pos"]), d["segs"], n_bars))

    point = {k: {kk: round(v, 4) for kk, v in pooled(ms).items()} for k, ms in per.items()}

    rng = np.random.default_rng(2026)
    diff = {"median_delay": [], "fa_per_1000": [], "missed_share": []}
    for _ in range(B):
        idx = rng.integers(0, N_SERIES, N_SERIES)
        a = pooled([per["D-sintetis"][i] for i in idx])
        b = pooled([per["Konsensus naif"][i] for i in idx])
        for key in diff:
            diff[key].append(a[key] - b[key])
    ci = {k: [round(float(np.nanpercentile(v, 2.5)), 4), round(float(np.nanpercentile(v, 97.5)), 4)] for k, v in diff.items()}
    h5 = ci["median_delay"][1] < 0 and ci["fa_per_1000"][0] <= 0
    return {
        "n_series": N_SERIES, "length": LENGTH, "changes": sum(x["changes"] for x in per["D-sintetis"]),
        "pooled": point, "h5_ci95_diff": ci, "h5": "TERBUKTI" if h5 else "TIDAK TERBUKTI",
    }


# ------------------------------------------------------------------ laporan


def to_md(o: Dict[str, Any]) -> str:
    a, b = o["change"], o["abstain"]
    L_ = ["# Deteksi pergantian regime dan abstain (Fase 1 adendum 5)", "",
          "Praregistrasi: `docs/praregistrasi_fase1_sintetis.md` §8 + adendum 5. Skrip: `ml/src/regime_change_study.py`.", "",
          f"## A. Pergantian regime ({a['n_series']} deret S4 × {a['length']} bar, {a['changes']} titik ganti, konfirmasi K = {K})", "",
          "| Metode | Median keterlambatan (bar) | Salah alarm / 1.000 bar | Pergantian terlewat |",
          "|---|---|---|---|"]
    for k, v in a["pooled"].items():
        L_.append(f"| {k} | {v['median_delay']:.0f} | {v['fa_per_1000']:.2f} | {v['missed_share'] * 100:.1f}% |")
    c = a["h5_ci95_diff"]
    L_ += ["", "Selisih D-sintetis − konsensus naif, CI95 bootstrap per deret:",
           f"median keterlambatan {c['median_delay']}, salah alarm/1.000 bar {c['fa_per_1000']}, terlewat {c['missed_share']}.", "",
           f"**H5: {a['h5']}**", "",
           "## B. Abstain berdasarkan keyakinan", "",
           f"τ terpilih = **{b['tau']}** ({b['rule']}).", "",
           "| τ | Cakupan val | BA tercakup val | Cakupan uji S4 | BA tercakup uji S4 | Cakupan S4k | BA tercakup S4k |",
           "|---|---|---|---|---|---|---|"]
    for v, s4, s4k in zip(b["validation"], b["test"]["S4"], b["test"]["S4k"]):
        mark = " ←" if v["tau"] == b["tau"] else ""
        L_.append(f"| {v['tau']:.2f}{mark} | {v['coverage']:.3f} | {v['ba_covered']:.3f} | {s4['coverage']:.3f} | {s4['ba_covered']:.3f} | "
                  f"{s4k['coverage']:.3f} | {s4k['ba_covered']:.3f} |")
    L_ += ["", "Proporsi jendela BTC yang akan berlabel tidak pasti pada τ terpilih: " +
           ", ".join(f"{tf.upper()} {v * 100:.1f}%" for tf, v in b["btc_uncertain_share"].items()), ""]
    return "\n".join(L_)


def main() -> None:
    m = ai_detector.meta()
    print("B. abstain...", flush=True)
    ab = abstain_study(m)
    print(f"  τ = {ab['tau']} ({ab['rule']})", flush=True)
    print("A. pergantian regime...", flush=True)
    ch = change_study(m, ab["tau"])
    out = {"abstain": ab, "change": ch}
    path = ARTIFACTS_DIR / "regime_change_study.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(to_md(out), encoding="utf-8")
    print(to_md(out))


if __name__ == "__main__":
    main()

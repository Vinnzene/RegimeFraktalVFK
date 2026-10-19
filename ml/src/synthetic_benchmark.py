"""Benchmark Fase 1: identifikasi regime pada data sintetis berkarakter kripto.

Rancangan, hipotesis, dan kriteria: docs/praregistrasi_fase1_sintetis.md
(dikunci) beserta adendumnya. Skrip ini hanya menjalankannya.

Jalankan:
    python ml/src/synthetic_benchmark.py --stage data   # bangkitkan deret + fitur (paralel, di-cache)
    python ml/src/synthetic_benchmark.py --stage run    # latih, evaluasi, uji H1-H4

Keluaran:
    ml/artifacts/synthetic_cache/*.npz          cache fitur (tidak di-commit)
    ml/artifacts/synthetic_benchmark.{json,md}  hasil
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR  # noqa: E402
from synthetic_regimes import CLASSES, PRIMARY, SENSITIVITY, label, make_series, sample_h  # noqa: E402

CACHE = ARTIFACTS_DIR / "synthetic_cache"
LENGTHS = (500, 256, 128)
TRAIN_SCENARIOS = ("S1", "S2", "S3", "S4")
TEST_SCENARIOS = ("S1", "S2", "S3", "S4", "S5", "S4k")
N_SPLIT = {"train": 12_000, "validation": 3_000, "test": 3_000}
SEED_BASE = {"train": 1000, "validation": 2000, "test": 3000}
ESTIMATORS = ("rs", "dfa", "lo", "vr2", "vr_slope")
ESTIMATOR_LABEL = {
    "rs": "R/S", "dfa": "DFA-1", "lo": "R/S Lo", "vr2": "VR(2)", "vr_slope": "Kemiringan VR", "consensus": "Konsensus R/S–DFA",
}
VR_QS = (2, 3, 4, 6, 8, 12, 16, 24, 32, 48)
PS_WINDOW = 500  # definisi PS (sub-window 128, 32 langkah) hanya sah untuk n = 500
B = 2000


# ------------------------------------------------------------------ data


def _featurize(scenario: str, n: int, split: str, idx: int) -> Dict[str, Any]:
    from app.services.hurst_dfa import dfa_alpha, hurst_lo, hurst_rs
    from app.services.multifractal import build_feature_matrix as build_mf
    from app.services.persistence_sequence import build_persistence_sequences
    from app.services.structural_features import build_feature_matrix, variance_ratio

    s_idx = TEST_SCENARIOS.index(scenario)
    rng = np.random.default_rng(np.random.SeedSequence([SEED_BASE[split], s_idx, n, idx]))
    cls = CLASSES[idx % 3]
    h = sample_h(cls, rng, PRIMARY)
    r, info = make_series(scenario, n, h, rng)
    t = n - 1
    feats = np.concatenate([build_feature_matrix(r, [t], n, 4)[0], build_mf(r, [t], n)[0]])
    vrs = np.array([variance_ratio(r, q) for q in VR_QS])
    ok = np.isfinite(vrs) & (vrs > 0)
    slope = np.polyfit(np.log(np.array(VR_QS)[ok]), np.log(vrs[ok]), 1)[0] if ok.sum() >= 3 else np.nan
    est = np.array([
        hurst_rs(r), dfa_alpha(r), hurst_lo(r),
        0.5 * (1 + np.log2(vrs[0])) if vrs[0] > 0 else np.nan,
        0.5 * (1 + slope),
    ])
    out: Dict[str, Any] = {"h": h, "feat": feats, "est": est}
    if n == PS_WINDOW:
        out["ps"] = build_persistence_sequences(r, [t], n, 128, 32)[0]
    return out


def build_cache(n_jobs: int) -> None:
    from joblib import Parallel, delayed

    CACHE.mkdir(parents=True, exist_ok=True)
    for n in LENGTHS:
        for scenario in TEST_SCENARIOS:
            splits = ("train", "validation", "test") if scenario in TRAIN_SCENARIOS else ("test",)
            for split in splits:
                path = CACHE / f"{scenario}_n{n}_{split}.npz"
                if path.exists():
                    continue
                t0 = time.time()
                rows = Parallel(n_jobs=n_jobs, batch_size=64)(
                    delayed(_featurize)(scenario, n, split, i) for i in range(N_SPLIT[split])
                )
                arrays = {
                    "h": np.array([r["h"] for r in rows]),
                    "feat": np.nan_to_num(np.stack([r["feat"] for r in rows])),
                    "est": np.stack([r["est"] for r in rows]),
                }
                if n == PS_WINDOW:
                    arrays["ps"] = np.stack([r["ps"] for r in rows]).astype(np.float32)
                np.savez_compressed(path, **arrays)
                print(f"{path.name}: {len(rows)} deret, {time.time() - t0:.0f}s", flush=True)


def load(scenario: str, n: int, split: str) -> Dict[str, np.ndarray]:
    with np.load(CACHE / f"{scenario}_n{n}_{split}.npz") as z:
        return {k: z[k] for k in z.files}


# ------------------------------------------------------------------ metrik


def labels_for(h: np.ndarray, thresholds: Tuple[float, float]) -> np.ndarray:
    return np.array([label(float(x), thresholds) for x in h])


def balanced_accuracy(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean([np.mean(p[y == c] == c) for c in CLASSES if np.any(y == c)]))


def metrics(y: np.ndarray, p: np.ndarray) -> Dict[str, Any]:
    from sklearn.metrics import f1_score

    return {
        "balanced_accuracy": round(balanced_accuracy(y, p), 4),
        "macro_f1": round(float(f1_score(y, p, labels=list(CLASSES), average="macro", zero_division=0)), 4),
        "recall": {c: round(float(np.mean(p[y == c] == c)), 4) for c in CLASSES if np.any(y == c)},
        "confusion": [[int(np.sum((y == a) & (p == b))) for b in (*CLASSES, "uncertain")] for a in CLASSES],
    }


def classify(values: np.ndarray, lo: float, hi: float) -> np.ndarray:
    out = np.where(values < lo, "anti_persistent", np.where(values > hi, "persistent", "random_like"))
    return np.where(np.isfinite(values), out, "uncertain")


def calibrate(values: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Dua ambang yang memaksimalkan BA pada validasi (grid persentil 1–99)."""
    finite = values[np.isfinite(values)]
    cand = np.unique(np.quantile(finite, np.linspace(0.01, 0.99, 99)))
    best, best_ba = (float(cand[0]), float(cand[-1])), -1.0
    for lo, hi in combinations(cand, 2):
        ba = balanced_accuracy(y, classify(values, lo, hi))
        if ba > best_ba:
            best, best_ba = (float(lo), float(hi)), ba
    return best


def consensus(rs: np.ndarray, dfa: np.ndarray, t_rs: Tuple[float, float], t_dfa: Tuple[float, float]) -> np.ndarray:
    a, b = classify(rs, *t_rs), classify(dfa, *t_dfa)
    return np.where(a == b, a, "uncertain")


def bootstrap_diff(
    y_a: np.ndarray, p_a: np.ndarray, y_b: np.ndarray, p_b: np.ndarray, paired: bool, seed: int = 42,
) -> Dict[str, Any]:
    """BA(a) - BA(b) dengan CI95 bootstrap dan p satu sisi (H0: selisih <= 0)."""
    rng = np.random.default_rng(seed)
    diffs = np.empty(B)
    for i in range(B):
        ia = rng.integers(0, len(y_a), len(y_a))
        ib = ia if paired else rng.integers(0, len(y_b), len(y_b))
        diffs[i] = balanced_accuracy(y_a[ia], p_a[ia]) - balanced_accuracy(y_b[ib], p_b[ib])
    return {
        "diff": round(balanced_accuracy(y_a, p_a) - balanced_accuracy(y_b, p_b), 4),
        "ci95": [round(float(np.quantile(diffs, 0.025)), 4), round(float(np.quantile(diffs, 0.975)), 4)],
        "p_raw": float(np.mean(diffs <= 0)),
    }


def holm(ps: Sequence[float]) -> List[float]:
    order = np.argsort(ps)
    adj = np.empty(len(ps))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return [round(float(x), 4) for x in adj]


# ------------------------------------------------------------------ model


def train_models(
    n: int, regime: str, tr: Dict[str, np.ndarray], va: Dict[str, np.ndarray], y_tr: np.ndarray, y_va: np.ndarray,
) -> Dict[str, Callable[[Dict[str, np.ndarray]], np.ndarray]]:
    """Latih semua model untuk satu rezim; kembalikan prediktor per model."""
    import tensorflow as tf  # type: ignore

    from app.services.feature_builder import apply_scaler, fit_scaler
    from model_architecture import build_hybrid_attention_bilstm, build_structural_mlp, compile_model
    from tabular_baselines import fit_tabular
    from train import class_weights

    mu, sd = tr["feat"].mean(axis=0), tr["feat"].std(axis=0)
    sd[sd < 1e-12] = 1.0
    scale_f = lambda d: (d["feat"] - mu) / sd  # noqa: E731
    onehot = lambda y: np.eye(3)[[CLASSES.index(c) for c in y]]  # noqa: E731
    Ytr, Yva = onehot(y_tr), onehot(y_va)
    Ftr, Fva = scale_f(tr), scale_f(va)
    predictors: Dict[str, Callable[[Dict[str, np.ndarray]], np.ndarray]] = {}

    for key in ("logreg", "lightgbm"):
        t0 = time.time()
        proba = fit_tabular(key, Ftr, Ytr, Fva, Yva, 42)
        predictors[key] = lambda d, f=proba: np.array(CLASSES)[f(scale_f(d)).argmax(axis=1)]
        print(f"    [{regime} n={n}] {key} {time.time() - t0:.0f}s", flush=True)

    callbacks = lambda: [  # noqa: E731
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
    ]

    t0 = time.time()
    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(42)
    mlp = compile_model(build_structural_mlp(Ftr.shape[1], 3))
    mlp.fit(Ftr, Ytr, validation_data=(Fva, Yva), epochs=80, batch_size=64,
            class_weight=class_weights(Ytr), shuffle=True, callbacks=callbacks(), verbose=0)
    predictors["structural_mlp"] = lambda d, m=mlp: np.array(CLASSES)[
        m.predict(scale_f(d), batch_size=1024, verbose=0).argmax(axis=1)]
    print(f"    [{regime} n={n}] MLP {time.time() - t0:.0f}s", flush=True)

    if n == PS_WINDOW:
        t0 = time.time()
        scaler = fit_scaler(tr["ps"])
        Str, Sva = apply_scaler(tr["ps"], scaler), apply_scaler(va["ps"], scaler)
        tf.keras.utils.set_random_seed(42)
        hyb = compile_model(build_hybrid_attention_bilstm((Str.shape[1], Str.shape[2]), Ftr.shape[1], 3))
        hyb.fit([Str, Ftr], Ytr, validation_data=([Sva, Fva], Yva), epochs=80, batch_size=64,
                class_weight=class_weights(Ytr), shuffle=True, callbacks=callbacks(), verbose=0)
        predictors["hybrid_ps"] = lambda d, m=hyb, s=scaler: np.array(CLASSES)[
            m.predict([apply_scaler(d["ps"], s), scale_f(d)], batch_size=1024, verbose=0).argmax(axis=1)]
        print(f"    [{regime} n={n}] Hybrid PS {time.time() - t0:.0f}s", flush=True)
    return predictors


# ------------------------------------------------------------------ jalannya


def concat(parts: Sequence[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def run_config(thresholds: Tuple[float, float], tag: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"thresholds": list(thresholds), "lengths": {}}
    for n in LENGTHS:
        print(f"\n=== {tag} n={n} ===", flush=True)
        tr = {s: load(s, n, "train") for s in TRAIN_SCENARIOS}
        va = {s: load(s, n, "validation") for s in TRAIN_SCENARIOS}
        te = {s: load(s, n, "test") for s in TEST_SCENARIOS}
        y = lambda d: labels_for(d["h"], thresholds)  # noqa: E731
        va_mix = concat(list(va.values()))
        y_va_mix = y(va_mix)

        # Estimator klasik: naif (ambang absolut) dan terkalibrasi (validasi campuran S1–S4).
        cal = {e: calibrate(va_mix["est"][:, i], y_va_mix) for i, e in enumerate(ESTIMATORS)}
        classical: Dict[str, Callable[[Dict[str, np.ndarray]], np.ndarray]] = {}
        for i, e in enumerate(ESTIMATORS):
            classical[f"{e}_naive"] = lambda d, i=i: classify(d["est"][:, i], *thresholds)
            classical[f"{e}_cal"] = lambda d, i=i, t=cal[e]: classify(d["est"][:, i], *t)
        classical["consensus_naive"] = lambda d: consensus(d["est"][:, 0], d["est"][:, 1], thresholds, thresholds)
        classical["consensus_cal"] = lambda d: consensus(d["est"][:, 0], d["est"][:, 1], cal["rs"], cal["dfa"])
        cal_keys = [k for k in classical if k.endswith("_cal")]
        best_classical = max(cal_keys, key=lambda k: balanced_accuracy(y_va_mix, classical[k](va_mix)))

        # Model: M-fBm (latih S1) dan M-kripto (latih S1–S4). Seleksi dengan BA validasi campuran.
        regimes = {
            "fbm": (tr["S1"], va["S1"]),
            "kripto": (concat(list(tr.values())), va_mix),
        }
        models: Dict[str, Dict[str, Callable]] = {}
        selected: Dict[str, str] = {}
        val_ba: Dict[str, Dict[str, float]] = {}
        for regime, (d_tr, d_va) in regimes.items():
            models[regime] = train_models(n, regime, d_tr, d_va, y(d_tr), y(d_va))
            val_ba[regime] = {k: round(balanced_accuracy(y_va_mix, f(va_mix)), 4) for k, f in models[regime].items()}
            selected[regime] = max(val_ba[regime], key=lambda k: val_ba[regime][k])
            print(f"  {regime}: BA validasi {val_ba[regime]} -> {selected[regime]}", flush=True)

        # Evaluasi semua metode pada set uji tiap skenario (dipakai sekali).
        preds: Dict[str, Dict[str, np.ndarray]] = {s: {} for s in TEST_SCENARIOS}
        table: Dict[str, Dict[str, Any]] = {s: {} for s in TEST_SCENARIOS}
        for s, d in te.items():
            ys = y(d)
            for k, f in classical.items():
                preds[s][k] = f(d)
            for regime in models:
                for k, f in models[regime].items():
                    preds[s][f"{regime}:{k}"] = f(d)
            preds[s]["best_classical"] = preds[s][best_classical]
            preds[s]["M-fBm"] = preds[s][f"fbm:{selected['fbm']}"]
            preds[s]["M-kripto"] = preds[s][f"kripto:{selected['kripto']}"]
            table[s] = {k: metrics(ys, p) for k, p in preds[s].items()}

        # Bias/RMSE estimasi H (deskriptif).
        h_error = {
            s: {e: {"bias": round(float(np.nanmean(d["est"][:, i] - d["h"])), 4),
                    "rmse": round(float(np.sqrt(np.nanmean((d["est"][:, i] - d["h"]) ** 2))), 4)}
                for i, e in enumerate(ESTIMATORS)}
            for s, d in te.items()
        }

        result["lengths"][str(n)] = {
            "calibrated_thresholds": {e: [round(a, 4) for a in t] for e, t in cal.items()},
            "best_classical": best_classical,
            "selected_models": selected,
            "validation_ba": val_ba,
            "test": table,
            "h_error": h_error,
            "_preds": preds,
            "_y": {s: y(d) for s, d in te.items()},
        }
    return result


def hypotheses(res: Dict[str, Any]) -> Dict[str, Any]:
    L = res["lengths"]
    p500, y500 = L["500"]["_preds"], L["500"]["_y"]
    tests = {
        "H1": bootstrap_diff(y500["S1"], p500["S1"]["best_classical"], y500["S4"], p500["S4"]["best_classical"], paired=False),
        "H2": bootstrap_diff(y500["S4"], p500["S4"]["M-kripto"], y500["S4"], p500["S4"]["best_classical"], paired=True),
        "H3": bootstrap_diff(y500["S4"], p500["S4"]["M-kripto"], y500["S4"], p500["S4"]["M-fBm"], paired=True),
    }
    adj = holm([tests[h]["p_raw"] for h in ("H1", "H2", "H3")])
    for h, a in zip(("H1", "H2", "H3"), adj):
        t = tests[h]
        t["p_holm"] = a
        t["verdict"] = "TERBUKTI" if t["ci95"][0] > 0 and a < 0.05 else ("BERLAWANAN" if t["ci95"][1] < 0 else "TIDAK TERBUKTI")
    # Eksploratif, tanpa Holm.
    p128, y128 = L["128"]["_preds"], L["128"]["_y"]
    h2_128 = bootstrap_diff(y128["S4"], p128["S4"]["M-kripto"], y128["S4"], p128["S4"]["best_classical"], paired=True)
    tests["H4"] = {"H2_n128": h2_128, "H2_n500": tests["H2"]["diff"],
                   "selisih": round(h2_128["diff"] - tests["H2"]["diff"], 4), "catatan": "eksploratif"}
    for h in ("H2", "H3"):
        t = bootstrap_diff(y500["S4k"], p500["S4k"]["M-kripto"], y500["S4k"],
                           p500["S4k"]["best_classical" if h == "H2" else "M-fBm"], paired=True)
        t["catatan"] = "eksploratif S4k (adendum 1), tanpa Holm"
        tests[f"{h}_S4k"] = t
    return tests


def strip_private(res: Dict[str, Any]) -> Dict[str, Any]:
    return {**res, "lengths": {n: {k: v for k, v in d.items() if not k.startswith("_")} for n, d in res["lengths"].items()}}


def fmt_p(p: float) -> str:
    """p bootstrap tidak pernah tepat 0; batas resolusinya 1/B."""
    return f"< {1 / B:.4f}" if p <= 0 else f"{p:.4f}"


def to_markdown(out: Dict[str, Any]) -> str:
    lines = ["# Benchmark Fase 1: identifikasi regime pada data sintetis", "",
             "Praregistrasi: `docs/praregistrasi_fase1_sintetis.md` (dikunci) + adendum.", ""]
    for cfg_name in ("utama", "sensitivitas"):
        res = out[cfg_name]
        lines += [f"## Ambang {cfg_name}: {res['thresholds'][0]} / {res['thresholds'][1]}", "",
                  "| H | Selisih BA | CI95 | p mentah | p Holm | Keputusan |", "|---|---|---|---|---|---|"]
        for h in ("H1", "H2", "H3"):
            t = res["hypotheses"][h]
            lines.append(f"| {h} | {t['diff']:+.3f} | [{t['ci95'][0]:+.3f}, {t['ci95'][1]:+.3f}] | "
                         f"{fmt_p(t['p_raw'])} | {fmt_p(t['p_holm'])} | **{t['verdict']}** |")
        h4 = res["hypotheses"]["H4"]
        lines += ["", f"H4 (eksploratif): selisih H2 pada n=128 {h4['H2_n128']['diff']:+.3f} vs n=500 {h4['H2_n500']:+.3f}.", ""]
        for h in ("H2_S4k", "H3_S4k"):
            t = res["hypotheses"][h]
            lines.append(f"- {h} (eksploratif): {t['diff']:+.3f} [{t['ci95'][0]:+.3f}, {t['ci95'][1]:+.3f}]")
        for n, d in res["lengths"].items():
            lines += ["", f"### n = {n}", "",
                      f"Estimator klasik terkalibrasi terbaik (validasi): `{d['best_classical']}`. "
                      f"Model terpilih: M-fBm `{d['selected_models']['fbm']}`, M-kripto `{d['selected_models']['kripto']}`.", "",
                      "| Metode | " + " | ".join(TEST_SCENARIOS) + " |", "|---|" + "---|" * len(TEST_SCENARIOS)]
            keys = [k for k in d["test"]["S1"] if not k.startswith(("fbm:", "kripto:"))]
            keys += [k for k in d["test"]["S1"] if k.startswith(("fbm:", "kripto:"))]
            for k in keys:
                lines.append(f"| {k} | " + " | ".join(f"{d['test'][s][k]['balanced_accuracy']:.3f}" for s in TEST_SCENARIOS) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", choices=["data", "run"], required=True)
    p.add_argument("--jobs", type=int, default=12)
    p.add_argument("--smoke", action="store_true", help="data kecil + cache terpisah, untuk uji alur")
    args = p.parse_args()
    if args.smoke:
        global CACHE, N_SPLIT
        CACHE = ARTIFACTS_DIR / "synthetic_cache_smoke"
        N_SPLIT = {"train": 300, "validation": 150, "test": 150}
    out_name = "synthetic_benchmark_smoke" if args.smoke else "synthetic_benchmark"
    if args.stage == "data":
        build_cache(args.jobs)
        return

    t0 = time.time()
    out: Dict[str, Any] = {"preregistration": "docs/praregistrasi_fase1_sintetis.md"}
    for name, thr in (("utama", PRIMARY), ("sensitivitas", SENSITIVITY)):
        res = run_config(thr, name)
        res["hypotheses"] = hypotheses(res)
        out[name] = strip_private(res)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / f"{out_name}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = to_markdown(out)
    (ARTIFACTS_DIR / f"{out_name}.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"Selesai {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

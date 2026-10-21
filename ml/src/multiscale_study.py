"""Identifikasi regime multi-skala — praregistrasi docs/praregistrasi_multiskala.md.

Jalankan:
    python ml/src/multiscale_study.py

M1 skala ×1 (500) · M2 ×1+×4 · M3 ×1+×4+×24 · M4 ×1 jendela 2.000 (sub-jendela 512).
Ketepatan: BA uji S4 (MS-H1..H3, Holm). Kecepatan: deteksi pergantian regime
pada 20 deret × 30.000 bar, mulai bar 12.000, konfirmasi K = 3.

Keluaran: ml/artifacts/multiscale_study.{json,md}
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

from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.services import ai_detector  # noqa: E402
from block_bootstrap_eval import holm_bonferroni_correction  # noqa: E402
from regime_change_study import confirmed_events, pooled, series_metrics  # noqa: E402
from synthetic_benchmark import balanced_accuracy, labels_for  # noqa: E402
from synthetic_regimes import CLASSES, PRIMARY, SIGMA, CryptoParams, crypto_noise, fgn, make_series, sample_h  # noqa: E402

LENGTH = 12_000
W = 500
SCALES = (1, 4, 24)
LONG = (2000, 512)  # jendela, sub-jendela PS untuk M4
SPLITS = {"train": (0, 6000), "validation": (1, 1500), "test": (2, 3000)}
TRAIN_SCEN = ("S1", "S2", "S3", "S4")
TEST_SCEN = ("S4", "S1", "S4k")
SCEN_IDX = {"S1": 0, "S2": 1, "S3": 2, "S4": 3, "S4k": 5}
SEEDS = (42, 43, 44)
B = 2000
MODELS = {"M1": ("s1",), "M2": ("s1", "s4"), "M3": ("s1", "s4", "s24"), "M4": ("long",)}
LABELS = {"M1": "×1 (500)", "M2": "×1 + ×4", "M3": "×1 + ×4 + ×24", "M4": "×1 jendela 2.000"}
CACHE = ARTIFACTS_DIR / "multiscale_cache"
CP_LEN, CP_SERIES, CP_START = 30_000, 20, 12_000


# ------------------------------------------------------------------ fitur


def scale_inputs(r: np.ndarray, t: int, meta: Dict[str, Any]) -> Dict[str, Dict[str, np.ndarray]]:
    """Fitur tiap skala untuk jendela yang berakhir di return ke-t."""
    out = {}
    for k in SCALES:
        w = r[t - W * k + 1 : t + 1].reshape(W, k).sum(axis=1)
        out[f"s{k}"] = ai_detector.window_features(w, meta)
    long_meta = dict(meta, window=LONG[0], sub_window=LONG[1])
    out["long"] = ai_detector.window_features(r[t - LONG[0] + 1 : t + 1], long_meta)
    return out


def _sample(scen: str, split: str, idx: int, meta: Dict[str, Any]) -> Dict[str, Any]:
    rng = np.random.default_rng(np.random.SeedSequence([9100 + SPLITS[split][0], SCEN_IDX[scen], idx]))
    h = sample_h(CLASSES[idx % 3], rng, PRIMARY)
    r, _ = make_series(scen, LENGTH, h, rng)
    return {"h": h, **scale_inputs(r, LENGTH - 1, meta)}


def dataset(scen: str, split: str, meta: Dict[str, Any]) -> Dict[str, np.ndarray]:
    path = CACHE / f"{scen}_{split}.npz"
    if path.exists():
        with np.load(path) as z:
            return {k: z[k] for k in z.files}
    from joblib import Parallel, delayed

    t0 = time.time()
    rows = Parallel(n_jobs=-1, batch_size=16)(delayed(_sample)(scen, split, i, meta) for i in range(SPLITS[split][1]))
    out: Dict[str, np.ndarray] = {"h": np.array([r["h"] for r in rows])}
    for key in ("s1", "s4", "s24", "long"):
        out[f"feat_{key}"] = np.nan_to_num(np.stack([r[key]["feat"] for r in rows]))
        out[f"ps_{key}"] = np.stack([r[key]["ps"] for r in rows]).astype(np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **out)
    print(f"  data {scen} {split}: {len(rows)} deret {time.time() - t0:.0f}s", flush=True)
    return out


def concat(parts: List[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def model_inputs(d: Dict[str, np.ndarray], keys: Tuple[str, ...]) -> Tuple[np.ndarray, np.ndarray]:
    return (np.concatenate([d[f"ps_{k}"] for k in keys], axis=-1), np.concatenate([d[f"feat_{k}"] for k in keys], axis=-1))


# ------------------------------------------------------------------ latih


def train_model(key: str, tr: Dict[str, np.ndarray], va: Dict[str, np.ndarray], seed: int):
    import tensorflow as tf  # type: ignore

    from app.services.feature_builder import apply_scaler, fit_scaler
    from model_architecture import build_hybrid_attention_bilstm, compile_model
    from train import class_weights

    keys = MODELS[key]
    S_tr, F_tr = model_inputs(tr, keys)
    S_va, F_va = model_inputs(va, keys)
    mu, sd = F_tr.mean(axis=0), F_tr.std(axis=0)
    sd[sd < 1e-12] = 1.0
    sc = fit_scaler(S_tr)
    onehot = lambda h: np.eye(3)[[CLASSES.index(c) for c in labels_for(h, PRIMARY)]]  # noqa: E731
    y_tr, y_va = onehot(tr["h"]), onehot(va["h"])

    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(seed)
    model = compile_model(build_hybrid_attention_bilstm(S_tr.shape[1:], F_tr.shape[1], 3))
    model.fit(
        [apply_scaler(S_tr, sc), (F_tr - mu) / sd], y_tr,
        validation_data=([apply_scaler(S_va, sc), (F_va - mu) / sd], y_va),
        epochs=80, batch_size=64, class_weight=class_weights(y_tr), shuffle=True, verbose=0,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
        ],
    )

    def predict(d: Dict[str, np.ndarray]) -> np.ndarray:
        S, F = model_inputs(d, keys)
        return model.predict([apply_scaler(S, sc), (F - mu) / sd], batch_size=1024, verbose=0)

    return predict


# ------------------------------------------------------------------ kecepatan


def make_long_cp(i: int) -> Tuple[np.ndarray, List[Tuple[int, int, str]]]:
    rng = np.random.default_rng(np.random.SeedSequence([8100, i]))
    n_cp = int(rng.integers(12, 19))
    slack = CP_LEN - 1000 * (n_cp + 1)
    extra = np.diff(np.concatenate([[0], np.sort(rng.integers(0, slack + 1, n_cp)), [slack]]))
    bounds = np.concatenate([[0], np.cumsum(1000 + extra)])
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


def _cp_series(i: int, meta: Dict[str, Any]) -> Dict[str, Any]:
    path = CACHE / f"cp_{i}.npz"
    if path.exists():
        with np.load(path, allow_pickle=True) as z:
            return {k: z[k] for k in z.files}
    r, segs = make_long_cp(i)
    pos = np.arange(CP_START - 1, len(r), 4)
    rows = [scale_inputs(r, int(t), meta) for t in pos]
    out: Dict[str, Any] = {"pos": pos, "segs": np.array(segs, dtype=object)}
    for key in ("s1", "s4", "s24", "long"):
        out[f"feat_{key}"] = np.nan_to_num(np.stack([x[key]["feat"] for x in rows]))
        out[f"ps_{key}"] = np.stack([x[key]["ps"] for x in rows]).astype(np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **out)
    return out


def speed_data(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    from joblib import Parallel, delayed

    t0 = time.time()
    data = Parallel(n_jobs=-1)(delayed(_cp_series)(i, meta) for i in range(CP_SERIES))
    print(f"  deret kecepatan {time.time() - t0:.0f}s", flush=True)
    return data


def speed_study(data: List[Dict[str, Any]], cp_proba: Dict[str, List[List[np.ndarray]]]) -> Dict[str, Any]:
    """cp_proba[model][seed][deret] = probabilitas tiap titik deteksi."""
    per: Dict[str, List[Dict[str, Any]]] = {k: [] for k in MODELS}
    for i, d in enumerate(data):
        # Hanya titik ganti setelah awal evaluasi: segmen pertama dimulai di titik deteksi pertama.
        segs = [s for s in d["segs"] if int(s[1]) > CP_START]
        segs[0] = (int(d["pos"][0]), segs[0][1], segs[0][2])
        segs_arr = np.array(segs, dtype=object)
        n_bars = int(d["pos"][-1] - d["pos"][0])
        for key in MODELS:
            p = np.mean([seed_probs[i] for seed_probs in cp_proba[key]], axis=0)
            labels = np.array(CLASSES)[p.argmax(axis=1)]
            per[key].append(series_metrics(confirmed_events(labels, d["pos"]), segs_arr, n_bars))
    return {
        "changes": sum(x["changes"] for x in per["M1"]),
        "pooled": {k: {kk: round(v, 4) for kk, v in pooled(ms).items()} for k, ms in per.items()},
    }


# ------------------------------------------------------------------ main


def paired_boot(y: np.ndarray, pa: np.ndarray, pb: np.ndarray) -> Dict[str, Any]:
    """ΔBA (b − a), bootstrap per deret, p satu sisi H0: Δ ≤ 0."""
    rng = np.random.default_rng(2026)
    diffs = np.empty(B)
    for i in range(B):
        idx = rng.integers(0, len(y), len(y))
        diffs[i] = balanced_accuracy(y[idx], pb[idx]) - balanced_accuracy(y[idx], pa[idx])
    return {
        "delta": round(balanced_accuracy(y, pb) - balanced_accuracy(y, pa), 4),
        "ci95": [round(float(np.percentile(diffs, 2.5)), 4), round(float(np.percentile(diffs, 97.5)), 4)],
        "p_raw": round(float(np.mean(diffs <= 0)), 4),
    }


def to_md(o: Dict[str, Any]) -> str:
    L = ["# Identifikasi regime multi-skala", "",
         "Praregistrasi: `docs/praregistrasi_multiskala.md`. Skrip: `ml/src/multiscale_study.py`.", "",
         "## Ketepatan: BA uji (rata-rata ± std 3 seed)", "",
         "| Model | Masukan | " + " | ".join(TEST_SCEN) + " |", "|---|---|" + "---|" * len(TEST_SCEN)]
    for k in MODELS:
        cells = [f"{np.mean(o['ba_per_seed'][k][s]):.3f} ± {np.std(o['ba_per_seed'][k][s]):.3f}" for s in TEST_SCEN]
        L.append(f"| {k} | {LABELS[k]} | " + " | ".join(cells) + " |")
    L += ["", "## Hipotesis (S4, probabilitas rata-rata 3 seed, Holm atas 3 uji)", "",
          "| ID | Pembanding | ΔBA | CI95 | p mentah | p Holm | Keputusan |", "|---|---|---|---|---|---|---|"]
    for h in o["hypotheses"]:
        L.append(f"| {h['id']} | {h['b']} − {h['a']} | {h['delta']:+.4f} | [{h['ci95'][0]:+.4f}, {h['ci95'][1]:+.4f}] | "
                 f"{h['p_raw']:.4f} | {h['p_holm']:.4f} | **{h['keputusan']}** |")
    sp = o["speed"]
    L += ["", f"## Kecepatan ({CP_SERIES} deret S4 × {CP_LEN} bar, {sp['changes']} titik ganti setelah bar {CP_START}, K = 3)", "",
          "| Model | Median keterlambatan (bar) | Salah alarm / 1.000 bar | Terlewat |", "|---|---|---|---|"]
    for k, v in sp["pooled"].items():
        L.append(f"| {k} {LABELS[k]} | {v['median_delay']:.0f} | {v['fa_per_1000']:.2f} | {v['missed_share'] * 100:.1f}% |")
    L += ["", f"**Rekomendasi untuk sistem (aturan §7):** {o['recommendation']}", ""]
    return "\n".join(L)


def main() -> None:
    meta = ai_detector.meta()
    t0 = time.time()
    print("Data...", flush=True)
    tr = concat([dataset(s, "train", meta) for s in TRAIN_SCEN])
    va = concat([dataset(s, "validation", meta) for s in TRAIN_SCEN])
    te = {s: dataset(s, "test", meta) for s in TEST_SCEN}
    y = {s: labels_for(te[s]["h"], PRIMARY) for s in TEST_SCEN}
    print("Data kecepatan...", flush=True)
    cp_data = speed_data(meta)

    cp_proba: Dict[str, List[List[np.ndarray]]] = {k: [] for k in MODELS}
    proba: Dict[str, Dict[str, List[np.ndarray]]] = {k: {s: [] for s in TEST_SCEN} for k in MODELS}
    ba: Dict[str, Dict[str, List[float]]] = {k: {s: [] for s in TEST_SCEN} for k in MODELS}
    for key in MODELS:
        for seed in SEEDS:
            ts = time.time()
            f = train_model(key, tr, va, seed)
            cp_proba[key].append([f(d) for d in cp_data])
            for s in TEST_SCEN:
                p = f(te[s])
                proba[key][s].append(p)
                ba[key][s].append(balanced_accuracy(y[s], np.array(CLASSES)[p.argmax(axis=1)]))
            print(f"  {key} seed {seed}: {time.time() - ts:.0f}s, BA S4 {ba[key]['S4'][-1]:.4f}", flush=True)

    ens = {k: np.array(CLASSES)[np.mean(proba[k]["S4"], axis=0).argmax(axis=1)] for k in MODELS}
    hyps = []
    for hid, a, b in (("MS-H1", "M1", "M2"), ("MS-H2", "M1", "M3"), ("MS-H3", "M4", "M2")):
        hyps.append({"id": hid, "a": a, "b": b, **paired_boot(y["S4"], ens[a], ens[b])})
    for h, p in zip(hyps, holm_bonferroni_correction([h["p_raw"] for h in hyps])):
        h["p_holm"] = p
        h["keputusan"] = "TERBUKTI" if p < 0.05 and h["ci95"][0] > 0 else (
            "BERLAWANAN" if h["ci95"][1] < 0 else "TIDAK TERBUKTI")

    speed = speed_study(cp_data, cp_proba)

    base = speed["pooled"]["M1"]
    ok = []
    for key, hid in (("M2", "MS-H1"), ("M3", "MS-H2")):
        v = speed["pooled"][key]
        proven = next(h for h in hyps if h["id"] == hid)["keputusan"] == "TERBUKTI"
        if proven and v["median_delay"] <= 1.25 * base["median_delay"] and v["fa_per_1000"] <= base["fa_per_1000"]:
            ok.append((float(np.mean(ba[key]["S4"])), key))
    rec = (f"{max(ok)[1]} memenuhi ketiga syarat" if ok else
           "tidak ada model multi-skala yang memenuhi ketiga syarat; detektor resmi tetap satu skala")

    out = {
        "preregistration": "docs/praregistrasi_multiskala.md",
        "ba_per_seed": {k: {s: [round(x, 4) for x in v] for s, v in d.items()} for k, d in ba.items()},
        "hypotheses": hyps, "speed": speed, "recommendation": rec, "seconds": round(time.time() - t0),
    }
    path = ARTIFACTS_DIR / "multiscale_study.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(to_md(out), encoding="utf-8")
    print(to_md(out))


if __name__ == "__main__":
    main()

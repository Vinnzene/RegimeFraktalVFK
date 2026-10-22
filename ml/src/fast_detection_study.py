"""Mempercepat deteksi pergantian regime — praregistrasi docs/praregistrasi_deteksi_cepat.md.

Jalankan (setelah `regime_change_study.py`, yang membuat cache deret panjang):
    python ml/src/fast_detection_study.py

D0 detektor resmi · A jendela 500 + latih pergantian · B0 jendela 256 ·
B jendela 256 + latih pergantian. Kecepatan diuji pada 40 deret panjang yang
sama dengan adendum 5 Fase 1.

Keluaran: ml/artifacts/fast_detection_study.{json,md}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.services import ai_detector  # noqa: E402
from block_bootstrap_eval import holm_bonferroni_correction  # noqa: E402
from regime_change_study import CACHE as CP_CACHE  # noqa: E402
from regime_change_study import N_SERIES, confirmed_events, make_long, pooled, series_metrics  # noqa: E402
from synthetic_benchmark import balanced_accuracy, labels_for  # noqa: E402
from synthetic_regimes import CLASSES, PRIMARY, make_series, sample_h  # noqa: E402

SUB = {500: 128, 256: 70}
SPLITS = {"train": (0, 6000, 12000), "validation": (1, 1500, 3000), "test": (2, 3000, 3000)}  # id, per stasioner, berganti
STATIONARY = ("S1", "S2", "S3", "S4")
SCEN_IDX = {"S1": 0, "S2": 1, "S3": 2, "S4": 3, "S5": 4}
SEEDS = (42, 43, 44)
B = 2000
MODELS = {"A": (500, True), "B0": (256, False), "B": (256, True)}
LABELS = {
    "D0": "Detektor resmi (500)", "A": "500 + latih pergantian",
    "B0": "256", "B": "256 + latih pergantian",
}
CACHE = ARTIFACTS_DIR / "fast_detection_cache"


def attention_weights(model, X: List[np.ndarray]) -> np.ndarray:
    """Bobot attention per langkah, dihitung eager pada keluaran BiLSTM.

    `model_architecture.attention_extractor` membangun graf simbolik yang tidak
    lagi didukung Keras 3, sehingga bobot dihitung dari keluaran lapisan sebelum
    attention pooling (dropout nonaktif saat prediksi).
    """
    import tensorflow as tf  # type: ignore

    pool = model.get_layer("attention_pool")
    seq = tf.keras.Model(model.inputs, pool.input).predict(X, batch_size=1024, verbose=0)
    return np.concatenate([pool.compute_attention(tf.constant(seq[i : i + 2048])).numpy() for i in range(0, len(seq), 2048)])


def meta_for(meta: Dict[str, Any], w: int) -> Dict[str, Any]:
    return dict(meta, window=w, sub_window=SUB[w])


# ------------------------------------------------------------------ data


def _sample(scen: str, split: str, idx: int, w: int, meta: Dict[str, Any]) -> Dict[str, Any]:
    rng = np.random.default_rng(np.random.SeedSequence([9300 + SPLITS[split][0], SCEN_IDX[scen], idx, w]))
    h = sample_h(CLASSES[idx % 3], rng, PRIMARY)
    r, info = make_series(scen, w, h, rng)  # S5: h = H segmen terakhir (label)
    f = ai_detector.window_features(r, meta_for(meta, w))
    return {"h": info["h_true"], "feat": f["feat"], "ps": f["ps"]}


def dataset(scen: str, split: str, w: int, meta: Dict[str, Any]) -> Dict[str, np.ndarray]:
    path = CACHE / f"{scen}_{split}_w{w}.npz"
    if path.exists():
        with np.load(path) as z:
            return {k: z[k] for k in z.files}
    from joblib import Parallel, delayed

    n = SPLITS[split][2] if scen == "S5" else SPLITS[split][1]
    t0 = time.time()
    rows = Parallel(n_jobs=-1, batch_size=32)(delayed(_sample)(scen, split, i, w, meta) for i in range(n))
    out = {
        "h": np.array([r["h"] for r in rows]),
        "feat": np.nan_to_num(np.stack([r["feat"] for r in rows])),
        "ps": np.stack([r["ps"] for r in rows]).astype(np.float32),
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **out)
    print(f"  data {scen} {split} w{w}: {n} deret {time.time() - t0:.0f}s", flush=True)
    return out


def concat(parts: List[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def long_series(i: int, w: int, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Fitur deret panjang i pada titik deteksi yang sama dengan adendum 5 Fase 1."""
    with np.load(CP_CACHE / f"series_{i}.npz", allow_pickle=True) as z:
        base = {k: z[k] for k in z.files}
    if w == 500:
        return base
    path = CACHE / f"cp_{i}_w{w}.npz"
    if path.exists():
        with np.load(path) as z:
            return {**base, "feat": z["feat"], "ps": z["ps"]}
    r, _ = make_long(i)
    m = meta_for(meta, w)
    rows = [ai_detector.window_features(r[t - w + 1 : t + 1], m) for t in base["pos"]]
    feat = np.nan_to_num(np.stack([x["feat"] for x in rows]))
    ps = np.stack([x["ps"] for x in rows]).astype(np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, feat=feat, ps=ps)
    return {**base, "feat": feat, "ps": ps}


# ------------------------------------------------------------------ model


def train(w: int, switch: bool, seed: int, meta: Dict[str, Any]):
    import tensorflow as tf  # type: ignore

    from app.services.feature_builder import apply_scaler, fit_scaler
    from model_architecture import build_hybrid_attention_bilstm, compile_model
    from train import class_weights

    scen = STATIONARY + (("S5",) if switch else ())
    tr = concat([dataset(s, "train", w, meta) for s in scen])
    va = concat([dataset(s, "validation", w, meta) for s in scen])
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
    return (
        lambda d: model.predict(X(d), batch_size=1024, verbose=0),
        lambda d: attention_weights(model, X(d)),
    )


def d0_attention(d: Dict[str, np.ndarray], meta: Dict[str, Any]) -> np.ndarray:
    from app.services.feature_builder import apply_scaler

    model = ai_detector._load_model(meta)
    F = (d["feat"] - np.array(meta["feature_mean"])) / np.array(meta["feature_std"])
    return attention_weights(model, [apply_scaler(d["ps"], meta["ps_scaler"]), F])


def last_share(att: np.ndarray) -> float:
    """Rata-rata total bobot attention pada 8 langkah terakhir (seragam = 0,25)."""
    a = att.reshape(att.shape[0], -1)
    return round(float(a[:, -8:].sum(axis=1).mean()), 4)


# ------------------------------------------------------------------ main


def to_md(o: Dict[str, Any]) -> str:
    L = ["# Deteksi cepat: latih pergantian regime dan jendela pendek", "",
         "Praregistrasi: `docs/praregistrasi_deteksi_cepat.md`. Skrip: `ml/src/fast_detection_study.py`.", "",
         "## Ketepatan (BA uji, rata-rata ± std 3 seed; D0 satu model)", "",
         "| Model | BA S4 (stabil) | BA S5 (berganti di dalam jendela) | Bobot attention 8 langkah terakhir (S5) |", "|---|---|---|---|"]
    for k in ("D0", *MODELS):
        a = o["accuracy"][k]
        att = o["attention_last8"].get(k, "–")
        L.append(f"| {k} {LABELS[k]} | {np.mean(a['S4']):.3f} ± {np.std(a['S4']):.3f} | {np.mean(a['S5']):.3f} ± {np.std(a['S5']):.3f} | {att} |")
    L += ["", "Bobot attention seragam pada 8 dari 32 langkah = 0,25.", "",
          f"## Kecepatan ({N_SERIES} deret S4 × 20.000 bar, K = 3)", "",
          "| Model | Median keterlambatan (bar) | Salah alarm / 1.000 bar | Terlewat |", "|---|---|---|---|"]
    for k, v in o["speed"].items():
        L.append(f"| {k} {LABELS[k]} | {v['median_delay']:.0f} | {v['fa_per_1000']:.2f} | {v['missed_share'] * 100:.1f}% |")
    L += ["", "## Hipotesis (selisih median keterlambatan vs D0, bootstrap per deret, Holm atas 2 uji)", "",
          "| ID | Pembanding | Selisih (bar) | CI95 | p mentah | p Holm | Keputusan |", "|---|---|---|---|---|---|---|"]
    for h in o["hypotheses"]:
        L.append(f"| {h['id']} | {h['model']} − D0 | {h['delta']:+.0f} | [{h['ci95'][0]:+.0f}, {h['ci95'][1]:+.0f}] | "
                 f"{h['p_raw']:.4f} | {h['p_holm']:.4f} | **{h['keputusan']}** |")
    L += ["", f"**Rekomendasi untuk sistem (aturan §6):** {o['recommendation']}", ""]
    return "\n".join(L)


def main() -> None:
    meta = ai_detector.meta()
    t0 = time.time()
    print("Data uji dan deret panjang...", flush=True)
    tests = {w: {s: dataset(s, "test", w, meta) for s in ("S4", "S5")} for w in (500, 256)}
    from joblib import Parallel, delayed

    Parallel(n_jobs=-1)(delayed(long_series)(i, 256, meta) for i in range(N_SERIES))
    longs = {w: [long_series(i, w, meta) for i in range(N_SERIES)] for w in (500, 256)}

    acc: Dict[str, Dict[str, List[float]]] = {}
    cp_proba: Dict[str, List[List[np.ndarray]]] = {}
    att_last: Dict[str, float] = {}

    # D0: detektor resmi apa adanya.
    p = lambda d: ai_detector.predict_proba(d["feat"], d["ps"], meta)  # noqa: E731
    acc["D0"] = {s: [balanced_accuracy(labels_for(d["h"], PRIMARY), np.array(CLASSES)[p(d).argmax(axis=1)])]
                 for s, d in tests[500].items()}
    cp_proba["D0"] = [[p(d) for d in longs[500]]]
    att_last["D0"] = last_share(d0_attention(tests[500]["S5"], meta))

    for key, (w, switch) in MODELS.items():
        acc[key] = {"S4": [], "S5": []}
        cp_proba[key] = []
        atts = []
        for seed in SEEDS:
            ts = time.time()
            pred, att = train(w, switch, seed, meta)
            for s, d in tests[w].items():
                acc[key][s].append(balanced_accuracy(labels_for(d["h"], PRIMARY), np.array(CLASSES)[pred(d).argmax(axis=1)]))
            cp_proba[key].append([pred(d) for d in longs[w]])
            atts.append(last_share(att(tests[w]["S5"])))
            print(f"  {key} seed {seed}: {time.time() - ts:.0f}s BA S4 {acc[key]['S4'][-1]:.3f} S5 {acc[key]['S5'][-1]:.3f}", flush=True)
        att_last[key] = round(float(np.mean(atts)), 4)

    per: Dict[str, List[Dict[str, Any]]] = {}
    for key, probs in cp_proba.items():
        per[key] = []
        for i in range(N_SERIES):
            d = longs[500][i]
            pr = np.mean([seed_probs[i] for seed_probs in probs], axis=0)
            labels = np.array(CLASSES)[pr.argmax(axis=1)]
            per[key].append(series_metrics(confirmed_events(labels, d["pos"]), d["segs"], int(d["pos"][-1] - d["pos"][0])))
    speed = {k: {kk: round(v, 4) for kk, v in pooled(ms).items()} for k, ms in per.items()}

    rng = np.random.default_rng(2026)
    boots: Dict[str, List[float]] = {"A": [], "B": []}
    for _ in range(B):
        idx = rng.integers(0, N_SERIES, N_SERIES)
        base = pooled([per["D0"][i] for i in idx])["median_delay"]
        for k in boots:
            boots[k].append(pooled([per[k][i] for i in idx])["median_delay"] - base)
    hyps = []
    for hid, k in (("CEPAT-H1", "A"), ("CEPAT-H2", "B")):
        v = np.array(boots[k])
        hyps.append({
            "id": hid, "model": k, "delta": round(speed[k]["median_delay"] - speed["D0"]["median_delay"], 1),
            "ci95": [round(float(np.nanpercentile(v, 2.5)), 1), round(float(np.nanpercentile(v, 97.5)), 1)],
            "p_raw": round(float(np.nanmean(v >= 0)), 4),
        })
    for h, ph in zip(hyps, holm_bonferroni_correction([h["p_raw"] for h in hyps])):
        h["p_holm"] = ph
        h["keputusan"] = "TERBUKTI" if ph < 0.05 and h["ci95"][1] < 0 else "TIDAK TERBUKTI"

    d0 = speed["D0"]
    ok = []
    for h in hyps:
        k = h["model"]
        s = speed[k]
        if (h["keputusan"] == "TERBUKTI" and np.mean(acc[k]["S4"]) >= acc["D0"]["S4"][0] - 0.03
                and s["fa_per_1000"] <= 1.5 * d0["fa_per_1000"] and s["missed_share"] <= d0["missed_share"] + 0.05):
            ok.append((s["median_delay"], k))
    rec = (f"{min(ok)[1]} memenuhi semua syarat (keterlambatan {min(ok)[0]:.0f} bar)" if ok else
           "tidak ada model yang memenuhi semua syarat; detektor resmi tetap D0")

    out = {
        "preregistration": "docs/praregistrasi_deteksi_cepat.md",
        "accuracy": {k: {s: [round(x, 4) for x in v] for s, v in d.items()} for k, d in acc.items()},
        "attention_last8": att_last, "speed": speed, "hypotheses": hyps,
        "recommendation": rec, "seconds": round(time.time() - t0),
    }
    path = ARTIFACTS_DIR / "fast_detection_study.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(to_md(out), encoding="utf-8")
    print(to_md(out))


if __name__ == "__main__":
    main()

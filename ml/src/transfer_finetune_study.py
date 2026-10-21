"""Fase 0b: pralatih sintetis + fine-tune pada label Hurst-DFA BTC.

Praregistrasi: docs/praregistrasi_fase0b_transfer.md (dikunci sebelum skrip ini).

Jalankan:
    python ml/src/transfer_finetune_study.py --timeframe 1h
    python ml/src/transfer_finetune_study.py --timeframe 4h

Model:
    B0  Hybrid PS dari nol, Adam 1e-3
    T1  Hybrid PS mulai dari bobot detektor sintetis resmi, Adam 1e-4
    T2  T1 + label smoothing 0,1
    T0  detektor resmi tanpa fine-tune (deskriptif)

Masukan seluruh model sama dengan detektor resmi: return tiap jendela
diskalakan ke sigma 0,0066, lalu fitur distandarkan dengan statistik detektor
sintetis (tidak dihitung ulang dari BTC).

Keluaran: ml/artifacts/transfer_finetune_<tf>.{json,md}
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services import ai_detector  # noqa: E402
from app.services.feature_builder import apply_scaler  # noqa: E402
from app.services.hurst_dfa import to_log_return  # noqa: E402
from app.services.regime_labeling import calibrate_thresholds, label_from_exponents, label_series  # noqa: E402
from app.services.splitting import bars_to_rows, split_indices  # noqa: E402
from app.services.walk_forward import generate_folds  # noqa: E402
from block_bootstrap_eval import holm_bonferroni_correction, moving_block_bootstrap_comparison  # noqa: E402
from train import class_weights  # noqa: E402
from train_orderflow_ablation import classification_metrics  # noqa: E402
from walk_forward_neural import fit_range  # noqa: E402

# Praregistrasi §2: jumlah jendela yang mereproduksi split Fase 0.
N_WINDOWS = {"1h": 16952, "4h": 4129}
EXPECTED_N = {
    "1h": {"train": 5951, "validation": 1211, "test": 1610},
    "4h": {"train": 1446, "validation": 354, "test": 261},
}
SEEDS = (42, 43, 44)
BLOCK = 125
B = 2000
MODELS = ("B0", "T1", "T2")
LABELS = {
    "B0": "Hybrid PS dari nol",
    "T1": "Hybrid PS pralatih sintetis + fine-tune",
    "T2": "T1 + label smoothing 0,1",
    "T0": "Detektor sintetis tanpa fine-tune",
}
CLASSES = list(REGIME_CLASSES)
CACHE = ARTIFACTS_DIR / "transfer_cache"


# ------------------------------------------------------------------ data


def btc_inputs(tf: str, positions: np.ndarray, meta: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """Fitur ternormalisasi per jendela, sama dengan detektor resmi (di-cache)."""
    path = CACHE / f"btc_{tf}_{len(positions)}.npz"
    if path.exists():
        with np.load(path) as z:
            if np.array_equal(z["positions"], positions):
                return {"feat": z["feat"], "ps": z["ps"]}
    from joblib import Parallel, delayed

    log_ret = to_log_return(get_repository().get_ohlcv("BTCUSDT", tf)["close"].to_numpy())
    L = int(meta["window"])
    t0 = time.time()
    rows = Parallel(n_jobs=-1, batch_size=32)(
        delayed(ai_detector.window_features)(log_ret[t - L + 1 : t + 1], meta) for t in positions
    )
    feat = np.nan_to_num(np.stack([r["feat"] for r in rows]))
    ps = np.stack([r["ps"] for r in rows])
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, positions=positions, feat=feat, ps=ps)
    print(f"  fitur {len(positions)} jendela {time.time() - t0:.0f}s", flush=True)
    return {"feat": feat, "ps": ps}


def build(tf: str) -> Dict[str, Any]:
    cfg = get_config()
    regime = get_repository().get_regime("BTCUSDT", tf).iloc[: N_WINDOWS[tf]].reset_index(drop=True)
    assert len(regime) == N_WINDOWS[tf], "data lebih pendek dari Fase 0"
    n = len(regime)
    purge = bars_to_rows(cfg.analysis.L, int(regime["stride_bars"].iloc[0]))
    sp = split_indices(n, cfg.split.ratios, purge)
    train_mask = np.zeros(n, dtype=bool)
    train_mask[: sp["train"][1]] = True
    lab = label_series(
        regime, cfg.analysis.hurst_threshold, cfg.analysis.dfa_threshold,
        mode=cfg.analysis.threshold_mode, quantiles=cfg.analysis.threshold_quantiles,
        threshold_source="train_only", train_mask=train_mask,
    )
    labels = np.array(lab["regime"].tolist())
    mask = np.isin(labels, CLASSES)
    rows = {k: np.array([i for i in range(*sp[k]) if mask[i]], dtype=int) for k in ("train", "validation", "test")}
    got = {k: len(v) for k, v in rows.items()}
    assert got == EXPECTED_N[tf], f"split {got} != Fase 0 {EXPECTED_N[tf]}"

    meta = ai_detector.meta()
    x = btc_inputs(tf, regime["index"].to_numpy(dtype=int), meta)
    F = (x["feat"] - np.array(meta["feature_mean"])) / np.array(meta["feature_std"])
    S = apply_scaler(x["ps"], meta["ps_scaler"])
    Y = np.zeros((n, 3))
    for i, l in enumerate(labels):
        if l in CLASSES:
            Y[i, CLASSES.index(l)] = 1.0
    return {
        "S": S, "F": F, "Y": Y, "labels": labels, "mask": mask, "rows": rows, "purge": purge, "meta": meta,
        "hurst": regime["hurst"].to_numpy(dtype=float), "dfa": regime["dfa_alpha"].to_numpy(dtype=float),
        "end_time": int(regime["time"].iloc[-1]),
    }


# ------------------------------------------------------------------ model


def pretrained(meta: Dict[str, Any]):
    """Detektor resmi dengan kolom keluaran diurutkan ulang ke urutan kelas BTC."""
    import tensorflow as tf  # type: ignore

    from ml_layers import AttentionPooling

    model = tf.keras.models.load_model(
        ARTIFACTS_DIR / meta["file"], custom_objects={"AttentionPooling": AttentionPooling}, compile=False
    )
    order = [list(meta["classes"]).index(c) for c in CLASSES]
    out = model.layers[-1]
    kernel, bias = out.get_weights()
    out.set_weights([kernel[:, order], bias[order]])
    return model


def make_model(key: str, meta: Dict[str, Any], seq_shape, n_feat: int):
    import tensorflow as tf  # type: ignore

    from model_architecture import build_hybrid_attention_bilstm

    if key == "B0":
        model, lr, smooth = build_hybrid_attention_bilstm(seq_shape, n_feat, 3), 1e-3, 0.0
    else:
        model, lr, smooth = pretrained(meta), 1e-4, (0.1 if key == "T2" else 0.0)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=smooth),
        metrics=["accuracy"],
    )
    return model


def fit_predict(key: str, d: Dict[str, Any], rows: Dict[str, np.ndarray], Y: np.ndarray, seed: int) -> Dict[str, Any]:
    import tensorflow as tf  # type: ignore

    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(seed)
    model = make_model(key, d["meta"], d["S"].shape[1:], d["F"].shape[1])
    X = lambda r: [d["S"][r], d["F"][r]]  # noqa: E731
    hist = model.fit(
        X(rows["train"]), Y[rows["train"]],
        validation_data=(X(rows["validation"]), Y[rows["validation"]]),
        epochs=80, batch_size=64, class_weight=class_weights(Y[rows["train"]]), shuffle=True, verbose=0,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
        ],
    )
    proba = {k: model.predict(X(r), batch_size=1024, verbose=0) for k, r in rows.items()}
    return {"epochs": len(hist.history["loss"]), "proba": proba}


def to_labels(p: np.ndarray) -> List[str]:
    return [CLASSES[i] for i in p.argmax(axis=1)]


# ------------------------------------------------------------------ uji utama


def main_split(d: Dict[str, Any]) -> Dict[str, Any]:
    rows, Y = d["rows"], d["Y"]
    true = {k: to_labels(Y[r]) for k, r in rows.items()}
    out: Dict[str, Any] = {}
    test_proba: Dict[str, List[np.ndarray]] = {}
    for key in MODELS:
        per_seed = []
        test_proba[key] = []
        for seed in SEEDS:
            t0 = time.time()
            res = fit_predict(key, d, rows, Y, seed)
            m = {k: classification_metrics(true[k], to_labels(res["proba"][k]), CLASSES) for k in rows}
            per_seed.append({
                "seed": seed, "epochs": res["epochs"],
                "train_ba": m["train"]["balanced_accuracy"], "val_ba": m["validation"]["balanced_accuracy"],
                "test": m["test"],
            })
            test_proba[key].append(res["proba"]["test"])
            print(f"  {key} seed {seed}: {res['epochs']:3d} ep {time.time() - t0:4.0f}s | latih {m['train']['balanced_accuracy']:.3f} "
                  f"val {m['validation']['balanced_accuracy']:.3f} uji {m['test']['balanced_accuracy']:.3f} "
                  f"F1 {m['test']['macro_f1']:.3f}", flush=True)
        out[key] = per_seed

    # T0: detektor tanpa fine-tune (deskriptif).
    p0 = pretrained(d["meta"]).predict([d["S"][rows["test"]], d["F"][rows["test"]]], batch_size=1024, verbose=0)
    t0_metrics = classification_metrics(true["test"], to_labels(p0), CLASSES)

    ens = {k: to_labels(np.mean(v, axis=0)) for k, v in test_proba.items()}
    y = np.array(true["test"])
    tests = []
    for hid, a, b in (("T-H1", "B0", "T1"), ("T-H2", "T1", "T2")):
        bb = moving_block_bootstrap_comparison(y, np.array(ens[a]), np.array(ens[b]), CLASSES, BLOCK, B, seed=42)
        tests.append({"id": hid, "a": a, "b": b, "f1": bb["f1"], "balanced_accuracy": bb["balanced_accuracy"]})
    ens_metrics = {k: classification_metrics(true["test"], v, CLASSES) for k, v in ens.items()}
    return {"per_seed": out, "ensemble": ens_metrics, "tests": tests, "t0": t0_metrics}


# ------------------------------------------------------------------ walk-forward (sekunder)


def walk_forward(d: Dict[str, Any]) -> Dict[str, Any]:
    cfg = get_config()
    folds = generate_folds(len(d["mask"]), n_splits=5, purge=d["purge"], scheme="expanding")
    res: Dict[str, List[float]] = {"B0": [], "T1": []}
    for fold in folds:
        tr0, fit_end, va0 = fit_range(fold, d["purge"])
        q = cfg.analysis.threshold_quantiles
        thr_h = calibrate_thresholds(d["hurst"][tr0:fit_end], q)
        thr_d = calibrate_thresholds(d["dfa"][tr0:fit_end], q)
        labels = [label_from_exponents(h, a, thr_h, thr_d) for h, a in zip(d["hurst"], d["dfa"])]
        Y = np.zeros((len(labels), 3))
        mask = np.zeros(len(labels), dtype=bool)
        for i, lab in enumerate(labels):
            if lab in CLASSES:
                Y[i, CLASSES.index(lab)] = 1.0
                mask[i] = True
        pick = lambda a, b: np.array([i for i in range(a, b) if mask[i]], dtype=int)  # noqa: E731
        tr1, (te0, te1) = int(fold["train"][1]), fold["test"]  # type: ignore[index, misc]
        rows = {"train": pick(tr0, fit_end), "validation": pick(va0, tr1), "test": pick(int(te0), int(te1))}
        true = to_labels(Y[rows["test"]])
        for key in res:
            bas = []
            for seed in SEEDS:
                p = fit_predict(key, d, rows, Y, seed)["proba"]["test"]
                bas.append(classification_metrics(true, to_labels(p), CLASSES)["balanced_accuracy"])
            res[key].append(round(float(np.mean(bas)), 4))
        print(f"  fold {fold['fold']}: B0 {res['B0'][-1]:.3f}  T1 {res['T1'][-1]:.3f}", flush=True)
    wins = int(sum(t > b for t, b in zip(res["T1"], res["B0"])))
    return {
        "ba_per_fold": res,
        "summary": {k: {"mean": round(float(np.mean(v)), 4), "std": round(float(np.std(v)), 4)} for k, v in res.items()},
        "t1_wins": wins, "stabil_lebih_baik": wins >= 3,
    }


# ------------------------------------------------------------------ laporan


def fase0_reference(tf: str) -> Dict[str, float]:
    ref = json.loads((ARTIFACTS_DIR / f"ps_study_{tf}.json").read_text(encoding="utf-8"))["models"]
    return {k: ref[k]["summary"]["balanced_accuracy"]["mean"] for k in ("logreg", "structural_mlp", "hybrid_ps") if k in ref}


def to_md(o: Dict[str, Any]) -> str:
    tf = o["timeframe"].upper()
    L = [f"# Fase 0b: pralatih sintetis + fine-tune — {tf}", "",
         "Praregistrasi: `docs/praregistrasi_fase0b_transfer.md`. Skrip: `ml/src/transfer_finetune_study.py`.",
         f"Split identik Fase 0: {o['n']}.", "",
         "## Kinerja (rata-rata ± std 3 seed)", "",
         "| Model | BA latih | BA validasi | BA uji | Macro-F1 uji | Recall random-like | Selisih latih − uji |",
         "|---|---|---|---|---|---|---|"]
    for k in MODELS:
        ps = o["main"]["per_seed"][k]
        tr = np.array([r["train_ba"] for r in ps])
        va = np.array([r["val_ba"] for r in ps])
        te = np.array([r["test"]["balanced_accuracy"] for r in ps])
        f1 = np.array([r["test"]["macro_f1"] for r in ps])
        rr = np.mean([r["test"]["per_class"][CLASSES.index("random_like")]["recall"] for r in ps])
        L.append(f"| {LABELS[k]} | {tr.mean():.3f} ± {tr.std():.3f} | {va.mean():.3f} | {te.mean():.3f} ± {te.std():.3f} | "
                 f"{f1.mean():.3f} | {rr:.3f} | {(tr - te).mean():.3f} |")
    t0 = o["main"]["t0"]
    L.append(f"| {LABELS['T0']} | – | – | {t0['balanced_accuracy']:.3f} | {t0['macro_f1']:.3f} | – | – |")
    L += ["", f"Overfitting berkurang (selisih T1 < B0 pada ketiga seed): **{'ya' if o['overfit_reduced'] else 'tidak'}**", "",
          "Referensi Fase 0 (BA uji, masukan dan scaler Fase 0): " +
          ", ".join(f"{k} {v:.3f}" for k, v in o["fase0_reference"].items()), "",
          "## Hipotesis (ensemble 3 seed, bootstrap blok 125, Holm atas 4 uji 1H+4H)", "",
          "| ID | B vs A | ΔMacro-F1 [CI95] | ΔBA [CI95] | p mentah | p Holm | Keputusan |",
          "|---|---|---|---|---|---|---|"]
    for t in o["main"]["tests"]:
        f, b = t["f1"], t["balanced_accuracy"]
        L.append(f"| {t['id']} | {t['b']} vs {t['a']} | {f['mean_diff']:+.3f} [{f['ci95'][0]:+.3f}, {f['ci95'][1]:+.3f}] | "
                 f"{b['mean_diff']:+.3f} [{b['ci95'][0]:+.3f}, {b['ci95'][1]:+.3f}] | {f['p_value_raw']:.4f} | "
                 f"{t.get('p_holm', '—')} | **{t.get('keputusan', 'menunggu TF lain')}** |")
    wf = o["walk_forward"]
    if not wf["ba_per_fold"]["B0"]:
        return "\n".join(L + [""])
    L += ["", "## Walk-forward 5 fold (sekunder)", "",
          "| Model | " + " | ".join(f"Fold {i + 1}" for i in range(len(wf["ba_per_fold"]["B0"]))) + " | Rata-rata ± std |",
          "|---|" + "---|" * (len(wf["ba_per_fold"]["B0"]) + 1)]
    for k in ("B0", "T1"):
        s = wf["summary"][k]
        L.append(f"| {LABELS[k]} | " + " | ".join(f"{x:.3f}" for x in wf["ba_per_fold"][k]) + f" | {s['mean']:.3f} ± {s['std']:.3f} |")
    L += ["", f"T1 > B0 pada {wf['t1_wins']}/5 fold; stabil lebih baik (≥ 3/5): **{'ya' if wf['stabil_lebih_baik'] else 'tidak'}**", ""]
    return "\n".join(L)


def apply_holm() -> None:
    """Koreksi Holm atas 4 uji (T-H1, T-H2 × 1H, 4H) bila kedua TF sudah selesai."""
    paths = [ARTIFACTS_DIR / f"transfer_finetune_{tf}.json" for tf in ("1h", "4h")]
    if not all(p.exists() for p in paths):
        return
    outs = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    tests = [t for o in outs for t in o["main"]["tests"]]
    adj = holm_bonferroni_correction([t["f1"]["p_value_raw"] for t in tests])
    for t, p in zip(tests, adj):
        t["p_holm"] = p
        t["keputusan"] = "TERBUKTI" if p < 0.05 and t["f1"]["ci95"][0] > 0 else (
            "BERLAWANAN" if t["f1"]["ci95"][1] < 0 else "TIDAK TERBUKTI")
    for o, p in zip(outs, paths):
        p.write_text(json.dumps(o, indent=2), encoding="utf-8")
        p.with_suffix(".md").write_text(to_md(o), encoding="utf-8")
    print("Holm diterapkan atas 4 uji.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeframe", choices=["1h", "4h"], required=True)
    ap.add_argument("--skip-walk-forward", action="store_true")
    args = ap.parse_args()
    tf = args.timeframe

    t0 = time.time()
    print(f"[{tf}] menyiapkan data...", flush=True)
    d = build(tf)
    print(f"  split {({k: len(v) for k, v in d['rows'].items()})}, jendela terakhir {d['end_time']}", flush=True)
    main_res = main_split(d)
    gaps = {k: [r["train_ba"] - r["test"]["balanced_accuracy"] for r in main_res["per_seed"][k]] for k in ("B0", "T1")}
    out = {
        "timeframe": tf, "preregistration": "docs/praregistrasi_fase0b_transfer.md",
        "n": {k: len(v) for k, v in d["rows"].items()}, "end_time": d["end_time"], "seeds": list(SEEDS),
        "main": main_res,
        "overfit_reduced": bool(all(t < b for t, b in zip(gaps["T1"], gaps["B0"]))),
        "fase0_reference": fase0_reference(tf),
        "walk_forward": {"ba_per_fold": {"B0": [], "T1": []}, "summary": {}, "t1_wins": 0, "stabil_lebih_baik": False}
        if args.skip_walk_forward else walk_forward(d),
        "seconds": round(time.time() - t0),
    }
    path = ARTIFACTS_DIR / f"transfer_finetune_{tf}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(to_md(out), encoding="utf-8")
    apply_holm()
    print(path.with_suffix(".md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

"""Walk-forward untuk model usulan (Hybrid Attention-BiLSTM) dan pembandingnya.

Jalankan:
    python ml/src/walk_forward_neural.py --timeframe 1h
    python ml/src/walk_forward_neural.py --timeframe 4h --splits 5 --seeds 42 43 44

Menjawab masalah khusus "apakah hasilnya stabil antar periode". Berbeda dari
`walk_forward_study.py` (ExtraTrees), skrip ini melatih ulang model yang
DIBELA skripsi di setiap fold.

Fold (expanding, kronologis, `app.services.walk_forward.generate_folds`):

    [ train_fit | purge | val ] purge [ test ]
     ^^^^^^^^^^^^^^^^^^^^^^^^^ = rentang latih fold

- purge = L bar (dalam baris window) di DUA batas: train_fitâ†’val dan
  latihâ†’test, sehingga tidak ada window yang berbagi bar lintas batas.
- val = 15% akhir rentang latih, hanya untuk early stopping.
- Scaler sekuens & fitur dipasang ulang dari train_fit fold itu saja.
- Hurst/DFA tidak pernah menjadi input.

Keluaran:
    ml/artifacts/walk_forward_neural_{tf}.json
    ml/artifacts/walk_forward_neural_{tf}.md
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
from app.services.feature_builder import apply_scaler, fit_scaler  # noqa: E402
from app.services.splitting import bars_to_rows  # noqa: E402
from app.services.walk_forward import generate_folds  # noqa: E402
from leakage_study import build_base  # noqa: E402
from main_evaluation import LABELS as MAIN_LABELS  # noqa: E402
from persistence_sequence_study import LABELS as PS_LABELS  # noqa: E402
from persistence_sequence_study import SUB_WINDOW, inputs, seq_kind  # noqa: E402
from persistence_sequence_study import build as build_model  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.hurst_dfa import to_log_return  # noqa: E402
from app.services.persistence_sequence import build_persistence_sequences  # noqa: E402

LABELS = {**MAIN_LABELS, **PS_LABELS, "hybrid_attention_bilstm": MAIN_LABELS["hybrid_attention_bilstm"]}
ALIASES: Dict[str, str] = {"hybrid_attention_bilstm": "hybrid_swt"}


def inputs_for(key: str, S: np.ndarray, F: np.ndarray):
    return inputs(ALIASES.get(key, key), S, F)
from train import class_weights  # noqa: E402
from train_orderflow_ablation import block_bootstrap_f1_diff, classification_metrics  # noqa: E402

DEFAULT_MODELS = ["structural_mlp", "hybrid_attention_bilstm"]
VAL_FRACTION = 0.15


def fold_rows(fold: Dict, mask: np.ndarray, purge: int) -> Dict[str, np.ndarray]:
    tr0, tr1 = fold["train"]
    te0, te1 = fold["test"]
    n_val = int(round((tr1 - tr0) * VAL_FRACTION))
    va0 = tr1 - n_val
    fit_end = va0 - purge
    if fit_end - tr0 < 50 or n_val < 20:
        raise ValueError("fold terlalu kecil untuk dipisah train/val")
    pick = lambda a, b: np.array([i for i in range(a, b) if mask[i]], dtype=int)  # noqa: E731
    return {"train": pick(tr0, fit_end), "validation": pick(va0, tr1), "test": pick(te0, te1)}


def main() -> None:
    p = argparse.ArgumentParser(description="Walk-forward model neural")
    p.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    p.add_argument("--splits", type=int, default=5)
    p.add_argument("--seq-len", type=int, default=32)
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--seeds", type=int, nargs="+", default=None)
    p.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    p.add_argument("--tag", default="", help="akhiran nama berkas keluaran, mis. '_ps'")
    args = p.parse_args()

    import tensorflow as tf  # type: ignore

    cfg = get_config()
    seeds = args.seeds or [cfg.model.seed, cfg.model.seed + 1, cfg.model.seed + 2]
    classes = list(REGIME_CLASSES)
    t0 = time.time()
    print(f"[{args.timeframe}] menyiapkan fitur...")
    base = build_base(args.timeframe, args.seq_len, classes)
    seq_raw = {"swt": base["X_causal"]}
    if any(seq_kind(str(ALIASES.get(m, m))) == "ps" for m in args.models):
        log_ret = to_log_return(get_repository().get_ohlcv("BTCUSDT", args.timeframe)["close"].to_numpy())
        seq_raw["ps"] = build_persistence_sequences(log_ret, base["positions"], base["window"], SUB_WINDOW, args.seq_len)
    X = base["X_causal"]
    F = np.hstack([base["F_struct"], base["F_mf"]])
    Y = base["y"]
    mask = base["mask"]
    purge = bars_to_rows(cfg.analysis.L, base["stride"])
    folds = generate_folds(len(mask), n_splits=args.splits, purge=purge, scheme="expanding")
    print(f"  {len(folds)} fold, purge {purge} baris, fitur {F.shape[1]}")

    results: Dict[str, Dict] = {m: {"label": LABELS[m], "folds": []} for m in args.models}
    pooled: Dict[str, Dict[int, Dict[str, List[str]]]] = {m: {s: {"true": [], "pred": []} for s in seeds} for m in args.models}

    for fold in folds:
        rows = fold_rows(fold, mask, purge)
        seq_scaled = {k: apply_scaler(v, fit_scaler(v[rows["train"]])) for k, v in seq_raw.items()}
        mu, sd = F[rows["train"]].mean(axis=0), F[rows["train"]].std(axis=0)
        sd[sd < 1e-12] = 1.0
        Fs = (F - mu) / sd
        d_by_kind = {k: {s: (v[r], Fs[r], Y[r]) for s, r in rows.items()} for k, v in seq_scaled.items()}
        d = d_by_kind["swt"]
        n = {k: len(r) for k, r in rows.items()}
        dist = {c: int(v) for c, v in zip(classes, Y[rows["test"]].sum(axis=0))}
        print(f"\n--- fold {fold['fold']}: train {n['train']} val {n['validation']} test {n['test']} {dist}")
        true = [classes[i] for i in d["test"][2].argmax(axis=1)]

        for mkey in args.models:
            per_seed: List[Dict[str, Any]] = []
            canon = str(ALIASES.get(mkey, mkey))
            d = d_by_kind[seq_kind(canon)]
            for seed in seeds:
                tf.keras.backend.clear_session()
                tf.keras.utils.set_random_seed(seed)
                ts = time.time()
                model = build_model(canon, d["train"][0].shape[1:], F.shape[1], len(classes))
                hist = model.fit(
                    inputs_for(mkey, d["train"][0], d["train"][1]), d["train"][2],
                    validation_data=(inputs_for(mkey, d["validation"][0], d["validation"][1]), d["validation"][2]),
                    epochs=args.epochs, batch_size=args.batch_size,
                    class_weight=class_weights(d["train"][2]), shuffle=True,
                    callbacks=[
                        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
                        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
                    ],
                    verbose=0,
                )
                prob = model.predict(inputs_for(mkey, d["test"][0], d["test"][1]), batch_size=512, verbose=0)
                pred = [classes[i] for i in prob.argmax(axis=1)]
                m = classification_metrics(true, pred, classes)
                per_seed.append({"seed": seed, "epochs_ran": len(hist.history["loss"]), "test": m, "pred": pred})
                pooled[mkey][seed]["true"] += true
                pooled[mkey][seed]["pred"] += pred
                print(f"  {mkey:24s} seed {seed}: {len(hist.history['loss']):3d} ep {time.time() - ts:4.0f}s "
                      f"BA={m['balanced_accuracy']:.3f} F1={m['macro_f1']:.3f} MCC={m['mcc']:.3f}")
            ba = np.array([r["test"]["balanced_accuracy"] for r in per_seed])
            f1 = np.array([r["test"]["macro_f1"] for r in per_seed])
            mcc = np.array([r["test"]["mcc"] for r in per_seed])
            results[mkey]["folds"].append({
                "fold": fold["fold"], "rows": {k: [int(r.min()), int(r.max())] if len(r) else [] for k, r in rows.items()},
                "n": n, "test_distribution": dist,
                "balanced_accuracy": {"mean": round(float(ba.mean()), 4), "std": round(float(ba.std()), 4)},
                "macro_f1": {"mean": round(float(f1.mean()), 4), "std": round(float(f1.std()), 4)},
                "mcc": {"mean": round(float(mcc.mean()), 4), "std": round(float(mcc.std()), 4)},
                "per_seed": [{k: v for k, v in r.items() if k != "pred"} for r in per_seed],
                "_pred": {r["seed"]: r["pred"] for r in per_seed},
                "_true": true,
            })

    # Ringkasan: stabilitas antar fold + agregat (prediksi seluruh fold digabung).
    for mkey, r in results.items():
        fold_ba = np.array([f["balanced_accuracy"]["mean"] for f in r["folds"]])
        fold_f1 = np.array([f["macro_f1"]["mean"] for f in r["folds"]])
        agg = [classification_metrics(pooled[mkey][s]["true"], pooled[mkey][s]["pred"], classes) for s in seeds]
        r["stability"] = {
            "ba_mean_over_folds": round(float(fold_ba.mean()), 4), "ba_std_over_folds": round(float(fold_ba.std()), 4),
            "ba_min": round(float(fold_ba.min()), 4), "ba_max": round(float(fold_ba.max()), 4),
            "f1_mean_over_folds": round(float(fold_f1.mean()), 4), "f1_std_over_folds": round(float(fold_f1.std()), 4),
            "folds_above_chance": int((fold_ba > 1 / len(classes)).sum()),
        }
        r["aggregate"] = {
            k: {"mean": round(float(np.mean([a[k] for a in agg])), 4), "std": round(float(np.std([a[k] for a in agg])), 4)}
            for k in ("accuracy", "balanced_accuracy", "macro_f1", "mcc", "kappa")
        }
        r["aggregate"]["recall_per_class"] = {
            c: round(float(np.mean([a["per_class"][i]["recall"] for a in agg])), 4) for i, c in enumerate(classes)
        }

    comparison = {}
    ref = "structural_mlp"
    if ref in results:
        for b in [k for k in results if k != ref]:
            per_fold = []
            for fa, fb in zip(results[ref]["folds"], results[b]["folds"]):
                diffs = [block_bootstrap_f1_diff(fa["_true"], fa["_pred"][s], fb["_pred"][s], classes, seed=s) for s in seeds]
                per_fold.append({"fold": fa["fold"], "delta_f1_vs_mlp": [x.get("mean_diff") for x in diffs],
                                 "ci95": [x.get("ci95") for x in diffs]})
            wins = sum(
                1 for fa, fb in zip(results[ref]["folds"], results[b]["folds"])
                if fb["macro_f1"]["mean"] > fa["macro_f1"]["mean"]
            )
            comparison[b] = {"better_than_mlp_folds": wins, "n_folds": len(results[ref]["folds"]), "per_fold": per_fold}

    for r in results.values():
        for f in r["folds"]:
            f.pop("_pred", None)
            f.pop("_true", None)

    out = {
        "timeframe": args.timeframe, "task": "identification", "scheme": "expanding",
        "config_hash": cfg.config_hash, "seeds": seeds, "n_splits": len(folds),
        "purge_rows": purge, "val_fraction": VAL_FRACTION, "epochs_max": args.epochs,
        "folds": folds, "models": results, "comparison": comparison,
    }
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / f"walk_forward_neural_{args.timeframe}{args.tag}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = to_markdown(out, classes)
    (ARTIFACTS_DIR / f"walk_forward_neural_{args.timeframe}{args.tag}.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"Selesai {time.time() - t0:.0f}s")


def to_markdown(out: Dict, classes: List[str]) -> str:
    models = out["models"]
    keys = list(models)
    lines = [
        f"## Walk-forward (expanding) â€” {out['timeframe'].upper()}",
        "",
        f"{out['n_splits']} fold, seed {out['seeds']}, purge {out['purge_rows']} baris di setiap batas, config `{out['config_hash'][:12]}`",
        "",
        "| Fold | n test | " + " | ".join(f"BA {models[k]['label']}" for k in keys) + " |",
        "|---|---|" + "---|" * len(keys),
    ]
    for i, f0 in enumerate(models[keys[0]]["folds"]):
        cells = [f"{models[k]['folds'][i]['balanced_accuracy']['mean']:.3f} Â± {models[k]['folds'][i]['balanced_accuracy']['std']:.3f}" for k in keys]
        lines.append(f"| {f0['fold']} | {f0['n']['test']} | " + " | ".join(cells) + " |")
    lines += ["", "| Model | BA rata-rata fold | std antar fold | minâ€“maks | BA agregat | Macro F1 agregat | MCC agregat | "
              + " | ".join(f"Recall {c}" for c in classes) + " |",
              "|---|---|---|---|---|---|---|" + "---|" * len(classes)]
    for k in keys:
        s, a = models[k]["stability"], models[k]["aggregate"]
        rec = " | ".join(f"{a['recall_per_class'][c]:.3f}" for c in classes)
        lines.append(
            f"| {models[k]['label']} | {s['ba_mean_over_folds']:.3f} | {s['ba_std_over_folds']:.3f} | "
            f"{s['ba_min']:.3f}â€“{s['ba_max']:.3f} | {a['balanced_accuracy']['mean']:.3f} | "
            f"{a['macro_f1']['mean']:.3f} | {a['mcc']['mean']:.3f} | {rec} |"
        )
    for key, c in (out.get("comparison") or {}).items():
        lines += ["", f"{models[key]['label']} unggul atas MLP (Macro F1) di {c['better_than_mlp_folds']} dari {c['n_folds']} fold.", ""]
        for pf in c["per_fold"]:
            cis = ", ".join(f"[{x[0]:+.3f}, {x[1]:+.3f}]" for x in pf["ci95"] if x)
            lines.append(f"- fold {pf['fold']}: Î”F1 vs MLP per seed {pf['delta_f1_vs_mlp']}, CI95 {cis}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()

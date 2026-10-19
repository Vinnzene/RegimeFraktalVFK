"""Evaluasi utama skripsi — semua model, split identik, multi-seed.

Jalankan:
    python ml/src/main_evaluation.py --timeframe 1h
    python ml/src/main_evaluation.py --timeframe 4h
    python ml/src/main_evaluation.py --timeframe 1h --seeds 42 43 44 --epochs 80

Tugas: IDENTIFIKASI regime (h = 0). Target = label konsensus Hurst-DFA pada
window yang sama. Window `uncertain_rule` (Hurst dan DFA tidak sepakat)
dikeluarkan dari training dan evaluasi, sama seperti pipeline existing.

Model yang dibandingkan (semua memakai dataset, split, purge, scaler, class
weight, dan callback yang SAMA):

    majority            tebak kelas terbanyak di training (batas bawah)
    stratified          tebak acak sesuai proporsi kelas training
    structural_mlp      MLP atas 44 fitur statistik window (tanpa sekuens)
    swt_bilstm          BiLSTM atas sekuens SWT, tanpa attention
    swt_attention_bilstm  BiLSTM + attention atas sekuens SWT
    hybrid_attention_bilstm  MODEL USULAN: cabang sekuens SWT + Attention-BiLSTM
                             digabung cabang fitur statistik

Hurst dan DFA TIDAK pernah menjadi input model mana pun.

Keluaran (tidak menimpa artefak lama):
    ml/artifacts/main_eval_{tf}.json        metrik lengkap per model per seed
    ml/artifacts/main_eval_{tf}.md          tabel ringkas untuk Bab 4
    ml/artifacts/main_eval_pred_{tf}.parquet  prediksi test per sampel (seed pertama)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from dataset import build_dataset  # noqa: E402
from train import class_weights  # noqa: E402
from train_orderflow_ablation import (  # noqa: E402
    block_bootstrap_f1_diff,
    classification_metrics,
    mcnemar,
)

NEURAL = ["structural_mlp", "swt_bilstm", "swt_attention_bilstm", "hybrid_attention_bilstm"]
DUMMY = ["majority", "stratified"]
PROPOSED = "hybrid_attention_bilstm"
LABELS = {
    "majority": "Baseline: kelas mayoritas",
    "stratified": "Baseline: acak proporsional",
    "structural_mlp": "MLP fitur statistik",
    "swt_bilstm": "SWT + BiLSTM",
    "swt_attention_bilstm": "SWT + Attention-BiLSTM",
    "hybrid_attention_bilstm": "Hybrid Attention-BiLSTM (usulan)",
}


def build_model(key: str, seq_shape, n_feat: int, n_classes: int):
    from model_architecture import (
        build_hybrid_attention_bilstm,
        build_structural_mlp,
        build_swt_attention_bilstm,
        build_swt_bilstm,
        compile_model,
    )

    if key == "structural_mlp":
        return compile_model(build_structural_mlp(n_feat, n_classes))
    if key == "swt_bilstm":
        return compile_model(build_swt_bilstm(seq_shape, n_classes))
    if key == "swt_attention_bilstm":
        return compile_model(build_swt_attention_bilstm(seq_shape, n_classes))
    if key == "hybrid_attention_bilstm":
        return compile_model(build_hybrid_attention_bilstm(seq_shape, n_feat, n_classes))
    raise ValueError(key)


def inputs_for(key: str, Xs: np.ndarray, Xf: np.ndarray):
    if key == "structural_mlp":
        return Xf
    if key in ("swt_bilstm", "swt_attention_bilstm"):
        return Xs
    return [Xs, Xf]


def dummy_predict(key: str, y_train: np.ndarray, n: int, classes: Sequence[str], seed: int) -> List[str]:
    counts = y_train.sum(axis=0)
    if key == "majority":
        return [classes[int(counts.argmax())]] * n
    rng = np.random.default_rng(seed)
    return list(rng.choice(classes, size=n, p=counts / counts.sum()))


def summarize(per_seed: List[Dict], classes: Sequence[str]) -> Dict:
    def agg(get: Callable[[Dict], float]) -> Dict[str, float]:
        v = np.array([get(r) for r in per_seed], dtype=float)
        return {"mean": round(float(v.mean()), 4), "std": round(float(v.std()), 4)}

    out: Dict[str, Any] = {
        m: agg(lambda r, m=m: r["test"][m])
        for m in ("accuracy", "balanced_accuracy", "precision_macro", "recall_macro", "macro_f1", "kappa", "mcc")
    }
    out["val_balanced_accuracy"] = agg(lambda r: r["validation"]["balanced_accuracy"])
    out["recall_per_class"] = {
        c: agg(lambda r, i=i: r["test"]["per_class"][i]["recall"]) for i, c in enumerate(classes)
    }
    out["f1_per_class"] = {c: agg(lambda r, i=i: r["test"]["per_class"][i]["f1"]) for i, c in enumerate(classes)}
    out["confusion_matrix_sum"] = np.sum([np.asarray(r["test"]["confusion_matrix"]) for r in per_seed], axis=0).tolist()
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluasi utama identifikasi regime")
    p.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    p.add_argument("--seq-len", type=int, default=32)
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--seeds", type=int, nargs="+", default=None)
    p.add_argument("--models", nargs="+", default=DUMMY + NEURAL)
    args = p.parse_args()

    import tensorflow as tf  # type: ignore

    cfg = get_config()
    seeds = args.seeds or [cfg.model.seed, cfg.model.seed + 1, cfg.model.seed + 2]
    classes = list(REGIME_CLASSES)

    t0 = time.time()
    close = get_repository().get_ohlcv("BTCUSDT", args.timeframe)["close"].to_numpy()
    data = build_dataset(close, seq_len=args.seq_len, h_bars=0, classes=classes, with_structural=True)
    assert data["task"] == "identification"
    Xs = {s: data[s][0] for s in ("train", "validation", "test")}
    Xf = {s: data[s][1] for s in ("train", "validation", "test")}
    Y = {s: data[s][2] for s in ("train", "validation", "test")}
    true = {s: [classes[i] for i in Y[s].argmax(axis=1)] for s in Y}
    print(f"[{args.timeframe}] dataset {time.time() - t0:.0f}s | seq {Xs['train'].shape[1:]} | fitur {Xf['train'].shape[1]}")
    for s in Y:
        dist = {c: int(n) for c, n in zip(classes, Y[s].sum(axis=0))}
        print(f"  {s:10s} n={len(Y[s]):5d} {dist}")

    results: Dict[str, Dict] = {}
    test_preds: Dict[str, Dict[int, List[str]]] = {}

    for key in args.models:
        print(f"\n=== {LABELS[key]} ===")
        per_seed = []
        test_preds[key] = {}
        for seed in seeds:
            ts = time.time()
            if key in DUMMY:
                pv = dummy_predict(key, Y["train"], len(Y["validation"]), classes, seed)
                pt = dummy_predict(key, Y["train"], len(Y["test"]), classes, seed + 1000)
                extra = {"epochs_ran": 0}
            else:
                tf.keras.backend.clear_session()
                tf.keras.utils.set_random_seed(seed)
                model = build_model(key, Xs["train"].shape[1:], Xf["train"].shape[1], len(classes))
                hist = model.fit(
                    inputs_for(key, Xs["train"], Xf["train"]),
                    Y["train"],
                    validation_data=(inputs_for(key, Xs["validation"], Xf["validation"]), Y["validation"]),
                    epochs=args.epochs,
                    batch_size=args.batch_size,
                    class_weight=class_weights(Y["train"]),
                    shuffle=True,
                    callbacks=[
                        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
                        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
                    ],
                    verbose=0,
                )
                prob_v = model.predict(inputs_for(key, Xs["validation"], Xf["validation"]), batch_size=512, verbose=0)
                prob_t = model.predict(inputs_for(key, Xs["test"], Xf["test"]), batch_size=512, verbose=0)
                pv = [classes[i] for i in prob_v.argmax(axis=1)]
                pt = [classes[i] for i in prob_t.argmax(axis=1)]
                extra = {
                    "epochs_ran": len(hist.history["loss"]),
                    "best_val_loss": round(float(min(hist.history["val_loss"])), 4),
                    "mean_max_prob": round(float(prob_t.max(axis=1).mean()), 4),
                }
            m_val = classification_metrics(true["validation"], pv, classes)
            m_test = classification_metrics(true["test"], pt, classes)
            per_seed.append({"seed": seed, **extra, "validation": m_val, "test": m_test})
            test_preds[key][seed] = pt
            print(
                f"  seed {seed}: {extra['epochs_ran']:3d} ep {time.time() - ts:5.0f}s | "
                f"BA={m_test['balanced_accuracy']:.4f} F1={m_test['macro_f1']:.4f} "
                f"MCC={m_test['mcc']:.4f} kappa={m_test['kappa']:.4f}"
            )
        results[key] = {"label": LABELS[key], "summary": summarize(per_seed, classes), "per_seed": per_seed}

    comparisons = {}
    if PROPOSED in test_preds:
        for other in [k for k in test_preds if k != PROPOSED]:
            comparisons[other] = [
                {
                    "seed": s,
                    "mcnemar": mcnemar(true["test"], test_preds[other][s], test_preds[PROPOSED][s]),
                    "bootstrap_macro_f1_diff": block_bootstrap_f1_diff(
                        true["test"], test_preds[other][s], test_preds[PROPOSED][s], classes, seed=s
                    ),
                }
                for s in seeds
            ]

    split = data["split"]
    out = {
        "timeframe": args.timeframe,
        "task": "identification",
        "h_bars": 0,
        "classes": classes,
        "config_hash": cfg.config_hash,
        "seeds": seeds,
        "seq_len": args.seq_len,
        "epochs_max": args.epochs,
        "batch_size": args.batch_size,
        "effective_window": data["effective_window"],
        "stride_bars": data["stride_bars"],
        "purge_bars": data["purge_bars"],
        "split_rows": {k: list(v) for k, v in split.items() if isinstance(v, (list, tuple))},
        "n": {s: len(Y[s]) for s in Y},
        "class_distribution": {s: {c: int(n) for c, n in zip(classes, Y[s].sum(axis=0))} for s in Y},
        "n_structural_features": Xf["train"].shape[1],
        "feature_names": data["feature_names"],
        "models": results,
        "proposed": PROPOSED,
        "comparisons_vs_proposed": comparisons,
        "catatan": (
            "Identifikasi (h=0). Label = konsensus Hurst-DFA; uncertain_rule dikeluarkan. "
            "Hurst/DFA tidak dipakai sebagai input. Split kronologis tanpa shuffle, "
            "purge = L bar, scaler dari train saja. Metrik = rata-rata +/- std atas seed. "
            "ΔF1 di comparisons = F1(usulan) - F1(pembanding), block bootstrap."
        ),
    }
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / f"main_eval_{args.timeframe}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    first = seeds[0]
    pred_df = pd.DataFrame({"true": true["test"], **{k: v[first] for k, v in test_preds.items()}})
    pred_df.to_parquet(ARTIFACTS_DIR / f"main_eval_pred_{args.timeframe}.parquet", index=False)

    md = write_markdown(out)
    (ARTIFACTS_DIR / f"main_eval_{args.timeframe}.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"Selesai {time.time() - t0:.0f}s")


def write_markdown(out: Dict) -> str:
    classes = out["classes"]
    tf = out["timeframe"].upper()
    lines = [
        f"## Evaluasi utama identifikasi regime — {tf}",
        "",
        f"n train/val/test = {out['n']['train']}/{out['n']['validation']}/{out['n']['test']}, "
        f"seed {out['seeds']}, purge {out['purge_bars']} bar, config `{out['config_hash'][:12]}`",
        "",
        "| Model | Balanced Acc | Macro F1 | MCC | Kappa | " + " | ".join(f"Recall {c}" for c in classes) + " |",
        "|---|---|---|---|---|" + "---|" * len(classes),
    ]
    for key, r in out["models"].items():
        s = r["summary"]

        def f(m):
            return f"{s[m]['mean']:.3f} ± {s[m]['std']:.3f}"

        rec = " | ".join(f"{s['recall_per_class'][c]['mean']:.3f}" for c in classes)
        name = f"**{r['label']}**" if key == out["proposed"] else r["label"]
        lines.append(f"| {name} | {f('balanced_accuracy')} | {f('macro_f1')} | {f('mcc')} | {f('kappa')} | {rec} |")
    if out["comparisons_vs_proposed"]:
        lines += ["", "Usulan vs pembanding (ΔF1 = usulan − pembanding, CI95 block bootstrap; McNemar p):", ""]
        for k, lst in out["comparisons_vs_proposed"].items():
            cells = []
            for c in lst:
                b = c["bootstrap_macro_f1_diff"]
                cells.append(
                    f"seed {c['seed']}: ΔF1 {b.get('mean_diff', float('nan')):+.3f} "
                    f"[{b.get('ci95', [float('nan')] * 2)[0]:+.3f}, {b.get('ci95', [float('nan')] * 2)[1]:+.3f}], "
                    f"p={c['mcnemar']['p_value']:.3g}"
                )
            lines.append(f"- vs {LABELS[k]}: " + "; ".join(cells))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()

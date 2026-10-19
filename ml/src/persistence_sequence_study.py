"""Eksperimen praregistrasi: Sekuens Statistik Persistensi (PS).

Rancangan, hipotesis H1–H6, dan kriteria keputusan ditetapkan SEBELUM run di
docs/praregistrasi_persistence_sequence.md. Skrip ini hanya menjalankannya.

Jalankan:
    python ml/src/persistence_sequence_study.py --timeframe 1h
    python ml/src/persistence_sequence_study.py --timeframe 4h

Protokol identik main_evaluation.py: label & split kronologis sama
(dicek terhadap main_eval_{tf}.json), purge L bar, scaler dari train,
seed 42/43/44, epoch maks 80, early stopping patience 12, class weight.

Keluaran:
    ml/artifacts/ps_study_{tf}.json
    ml/artifacts/ps_study_{tf}.md
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
from app.services.feature_builder import apply_scaler, fit_scaler  # noqa: E402
from app.services.hurst_dfa import to_log_return  # noqa: E402
from app.services.persistence_sequence import PS_CHANNELS, build_persistence_sequences  # noqa: E402
from leakage_study import VARIANTS, build_base, make_split  # noqa: E402
from tabular_baselines import TABULAR, fit_predict_proba  # noqa: E402
from train import class_weights  # noqa: E402
from train_orderflow_ablation import block_bootstrap_f1_diff, classification_metrics, mcnemar  # noqa: E402

SUB_WINDOW = 128
MODELS = [
    "logreg",
    "lightgbm",
    "structural_mlp",
    "swt_attention_bilstm",
    "hybrid_swt",
    "ps_bilstm",
    "ps_attention_bilstm",
    "ps_attention_bilstm_shuffled",
    "hybrid_ps",
]
LABELS = {
    **TABULAR,
    "structural_mlp": "MLP fitur statistik",
    "swt_attention_bilstm": "SWT + Attention-BiLSTM",
    "hybrid_swt": "Hybrid SWT (usulan lama)",
    "ps_bilstm": "PS + BiLSTM (tanpa attention)",
    "ps_attention_bilstm": "PS + Attention-BiLSTM",
    "ps_attention_bilstm_shuffled": "PS + Attention-BiLSTM, urutan diacak",
    "hybrid_ps": "Hybrid PS",
}
HYPOTHESES = [
    ("H1", "swt_attention_bilstm", "ps_attention_bilstm", "Input PS lebih informatif dari SWT?"),
    ("H2", "ps_attention_bilstm_shuffled", "ps_attention_bilstm", "Urutan waktu persistensi membawa informasi?"),
    ("H3", "ps_bilstm", "ps_attention_bilstm", "Attention menambah nilai?"),
    ("H4", "hybrid_swt", "hybrid_ps", "PS memperbaiki model hybrid?"),
    ("H5", "structural_mlp", "hybrid_ps", "Hybrid PS melampaui MLP?"),
    ("H6", "structural_mlp", "ps_attention_bilstm", "Model sekuens murni menyamai/melampaui MLP?"),
]
# Adendum 2026-10-19 (docs/praregistrasi_addendum.md): pembanding tabular
# ditambahkan setelah praregistrasi, jadi dilaporkan TERPISAH dan tidak masuk
# keluarga Holm H1-H6.
ADDENDUM = [
    ("A1", "lightgbm", "hybrid_ps", "Hybrid PS melampaui LightGBM fitur statistik?"),
    ("A2", "logreg", "hybrid_ps", "Hybrid PS melampaui regresi logistik fitur statistik?"),
]
CANDIDATES = ["hybrid_swt", "hybrid_ps", "ps_attention_bilstm"]


def build(key: str, seq_shape, n_feat: int, n_classes: int):
    from model_architecture import (
        build_hybrid_attention_bilstm,
        build_structural_mlp,
        build_swt_attention_bilstm,
        build_swt_bilstm,
        compile_model,
    )

    if key == "structural_mlp":
        return compile_model(build_structural_mlp(n_feat, n_classes))
    if key == "ps_bilstm":
        return compile_model(build_swt_bilstm(seq_shape, n_classes))
    if key in ("swt_attention_bilstm", "ps_attention_bilstm", "ps_attention_bilstm_shuffled"):
        return compile_model(build_swt_attention_bilstm(seq_shape, n_classes))
    if key in ("hybrid_swt", "hybrid_ps"):
        return compile_model(build_hybrid_attention_bilstm(seq_shape, n_feat, n_classes))
    raise ValueError(key)


def seq_kind(key: str) -> str:
    return "swt" if key in ("swt_attention_bilstm", "hybrid_swt") else "ps"


def inputs(key: str, S: np.ndarray, F: np.ndarray):
    if key == "structural_mlp":
        return F
    if key.startswith("hybrid"):
        return [S, F]
    return S


def verdict(diffs: List[Dict]) -> str:
    pos = sum(1 for d in diffs if d.get("ci95") and d["ci95"][0] > 0)
    neg = sum(1 for d in diffs if d.get("ci95") and d["ci95"][1] < 0)
    if pos >= 2:
        return "TERBUKTI"
    if neg >= 2:
        return "BERLAWANAN"
    return "TIDAK TERBUKTI (setara)"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    p.add_argument("--seq-len", type=int, default=32)
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--seeds", type=int, nargs="+", default=None)
    p.add_argument("--models", nargs="+", default=MODELS)
    args = p.parse_args()

    import tensorflow as tf  # type: ignore

    cfg = get_config()
    seeds = args.seeds or [cfg.model.seed, cfg.model.seed + 1, cfg.model.seed + 2]
    classes = list(REGIME_CLASSES)
    t0 = time.time()
    print(f"[{args.timeframe}] fitur dasar...")
    base = build_base(args.timeframe, args.seq_len, classes)
    close = get_repository().get_ohlcv("BTCUSDT", args.timeframe)["close"].to_numpy()
    log_ret = to_log_return(close)
    tps = time.time()
    PS = build_persistence_sequences(log_ret, base["positions"], base["window"], SUB_WINDOW, args.seq_len)
    print(f"  PS {PS.shape} ({time.time() - tps:.1f}s), kanal {PS_CHANNELS}")

    rows = make_split(base, VARIANTS["clean"], None, seeds[0])
    n = {k: len(v) for k, v in rows.items()}
    ref = ARTIFACTS_DIR / f"main_eval_{args.timeframe}.json"
    if ref.exists():
        ref_n = json.loads(ref.read_text(encoding="utf-8"))["n"]
        if ref_n != n:
            raise SystemExit(f"split berbeda dari main_eval: {n} vs {ref_n}")
        print(f"  split identik main_eval: {n}")

    tr = rows["train"]
    seqs = {
        "swt": apply_scaler(base["X_causal"], fit_scaler(base["X_causal"][tr])),
        "ps": apply_scaler(PS, fit_scaler(PS[tr])),
    }
    F = np.hstack([base["F_struct"], base["F_mf"]])
    mu, sd = F[tr].mean(axis=0), F[tr].std(axis=0)
    sd[sd < 1e-12] = 1.0
    F = (F - mu) / sd
    Y = base["y"]
    true = {k: [classes[i] for i in Y[r].argmax(axis=1)] for k, r in rows.items()}

    results: Dict[str, Dict] = {}
    preds: Dict[str, Dict[int, List[str]]] = {}
    for key in args.models:
        print(f"\n=== {LABELS[key]} ===")
        per_seed: List[Dict[str, Any]] = []
        preds[key] = {}
        for seed in seeds:
            S = seqs[seq_kind(key)]
            if key == "ps_attention_bilstm_shuffled":
                rng = np.random.default_rng(seed)
                perm = np.argsort(rng.random((S.shape[0], S.shape[1])), axis=1)
                S = np.take_along_axis(S, perm[:, :, None], axis=1)
            d = {k: (S[r], F[r], Y[r]) for k, r in rows.items()}
            ts = time.time()
            if key in TABULAR:
                pv, pt = fit_predict_proba(
                    key, d["train"][1], d["train"][2], d["validation"][1], d["validation"][2],
                    [d["validation"][1], d["test"][1]], seed,
                )
                hist = None
            else:
                tf.keras.backend.clear_session()
                tf.keras.utils.set_random_seed(seed)
                model = build(key, S.shape[1:], F.shape[1], len(classes))
                hist = model.fit(
                    inputs(key, d["train"][0], d["train"][1]), d["train"][2],
                    validation_data=(inputs(key, d["validation"][0], d["validation"][1]), d["validation"][2]),
                    epochs=args.epochs, batch_size=args.batch_size, class_weight=class_weights(d["train"][2]), shuffle=True,
                    callbacks=[
                        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
                        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
                    ],
                    verbose=0,
                )
                pv = model.predict(inputs(key, d["validation"][0], d["validation"][1]), batch_size=512, verbose=0)
                pt = model.predict(inputs(key, d["test"][0], d["test"][1]), batch_size=512, verbose=0)
            epochs_ran = len(hist.history["loss"]) if hist is not None else 0
            pred_v = [classes[i] for i in pv.argmax(axis=1)]
            pred_t = [classes[i] for i in pt.argmax(axis=1)]
            mv = classification_metrics(true["validation"], pred_v, classes)
            mt = classification_metrics(true["test"], pred_t, classes)
            extra: Dict[str, Any] = {}
            if "attention" in key or key.startswith("hybrid"):
                try:
                    att = model.get_layer("attention_pool")
                    sub = tf.keras.Model(model.inputs[0] if isinstance(model.inputs, list) else model.inputs, att.input)
                    alpha = att.compute_attention(
                        tf.convert_to_tensor(sub.predict(d["test"][0], batch_size=512, verbose=0))
                    ).numpy()
                    ent = (-(alpha * np.log(alpha + 1e-12)).sum(axis=1)).mean() / np.log(alpha.shape[1])
                    extra["attention_entropy"] = round(float(ent), 4)
                except Exception as exc:  # noqa: BLE001
                    extra["attention_entropy_error"] = str(exc)[:120]
            per_seed.append({"seed": seed, "epochs_ran": epochs_ran, "validation": mv, "test": mt, **extra})
            preds[key][seed] = pred_t
            print(f"  seed {seed}: {epochs_ran:3d} ep {time.time() - ts:4.0f}s | val BA={mv['balanced_accuracy']:.3f} "
                  f"| test BA={mt['balanced_accuracy']:.3f} F1={mt['macro_f1']:.3f} MCC={mt['mcc']:.3f}"
                  + (f" attH={extra['attention_entropy']:.3f}" if "attention_entropy" in extra else ""))

        def agg(path):
            v = np.array([r[path[0]][path[1]] if len(path) == 2 else r[path[0]] for r in per_seed], dtype=float)
            return {"mean": round(float(v.mean()), 4), "std": round(float(v.std()), 4)}

        summ = {m: agg(("test", m)) for m in ("accuracy", "balanced_accuracy", "macro_f1", "mcc", "kappa")}
        summ["val_balanced_accuracy"] = agg(("validation", "balanced_accuracy"))
        summ["recall_per_class"] = {
            c: round(float(np.mean([r["test"]["per_class"][i]["recall"] for r in per_seed])), 4) for i, c in enumerate(classes)
        }
        if all("attention_entropy" in r for r in per_seed):
            summ["attention_entropy"] = agg(("attention_entropy",))
        results[key] = {"label": LABELS[key], "summary": summ, "per_seed": per_seed}

    hyps = []
    for hid, a, b, q in HYPOTHESES + ADDENDUM:
        if a not in preds or b not in preds:
            continue
        diffs = []
        for s in seeds:
            bb = block_bootstrap_f1_diff(true["test"], preds[a][s], preds[b][s], classes, seed=s)
            diffs.append({"seed": s, "mean_diff": bb.get("mean_diff"), "ci95": bb.get("ci95"),
                          "mcnemar_p": mcnemar(true["test"], preds[a][s], preds[b][s])["p_value"]})
        hyps.append({"id": hid, "a": a, "b": b, "question": q, "diffs": diffs, "verdict": verdict(diffs)})

    cand = {k: results[k]["summary"]["val_balanced_accuracy"]["mean"] for k in CANDIDATES if k in results}
    chosen = max(cand, key=lambda k: cand[k]) if cand else None

    out = {
        "timeframe": args.timeframe, "task": "identification", "config_hash": cfg.config_hash,
        "preregistration": "docs/praregistrasi_persistence_sequence.md",
        "seeds": seeds, "seq_len": args.seq_len, "sub_window": SUB_WINDOW, "ps_channels": PS_CHANNELS,
        "effective_window": base["window"], "n": n, "models": results, "hypotheses": hyps,
        "selection_by_validation_ba": cand, "selected_on_validation": chosen,
    }
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / f"ps_study_{args.timeframe}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = to_md(out, classes)
    (ARTIFACTS_DIR / f"ps_study_{args.timeframe}.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"Selesai {time.time() - t0:.0f}s")


def to_md(out: Dict, classes: List[str]) -> str:
    L = [f"## Studi Sekuens Statistik Persistensi — {out['timeframe'].upper()}", "",
         f"Praregistrasi: `{out['preregistration']}`. n = {out['n']}, seed {out['seeds']}, config `{out['config_hash'][:12]}`", "",
         "| Model | Val BA | Test BA | Macro F1 | MCC | " + " | ".join(f"Recall {c}" for c in classes) + " | Entropi attention |",
         "|---|---|---|---|---|" + "---|" * len(classes) + "---|"]
    for k, r in out["models"].items():
        s = r["summary"]
        ent = s.get("attention_entropy")
        rec = " | ".join(f"{s['recall_per_class'][c]:.3f}" for c in classes)
        ent_txt = f"{ent['mean']:.3f}" if ent else "–"
        L.append(
            f"| {r['label']} | {s['val_balanced_accuracy']['mean']:.3f} | "
            f"{s['balanced_accuracy']['mean']:.3f} ± {s['balanced_accuracy']['std']:.3f} | "
            f"{s['macro_f1']['mean']:.3f} ± {s['macro_f1']['std']:.3f} | {s['mcc']['mean']:.3f} | {rec} | {ent_txt} |"
        )
    L += ["", "| H | Pertanyaan | B vs A | ΔF1 per seed [CI95] | Keputusan |", "|---|---|---|---|---|"]
    for h in out["hypotheses"]:
        cells = "; ".join(
            f"{d['mean_diff']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]" for d in h["diffs"] if d.get("ci95")
        )
        L.append(f"| {h['id']} | {h['question']} | {LABELS[h['b']]} vs {LABELS[h['a']]} | {cells} | **{h['verdict']}** |")
    if any(h["id"].startswith("A") for h in out["hypotheses"]):
        L += ["", "A1-A2 = adendum di luar praregistrasi awal (lihat docs/praregistrasi_addendum.md)."]
    L += ["", f"Pilihan model usulan berdasarkan BA VALIDASI: {out['selected_on_validation']} "
          f"({', '.join(f'{k}={v:.3f}' for k, v in out['selection_by_validation_ba'].items())})"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()

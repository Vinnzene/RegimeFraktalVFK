"""Ablation order flow: Model A (SWT) vs B (+OFI) vs C (+CVD) vs D (+OFI+CVD).

Jalankan:
    python ml/src/sanity_check_orderflow.py --timeframe 1h      # wajib lulus dulu
    python ml/src/train_orderflow_ablation.py --timeframe 1h
    python ml/src/train_orderflow_ablation.py --timeframe 4h --seeds 42 43 44

Tugas: IDENTIFIKASI regime (h = 0). Target = label Hurst-DFA pada window yang
sama. Hurst dan DFA TIDAK masuk input; input hanya sekuens SWT dan (opsional)
OFI/CVD. Window uncertain_rule dikeluarkan dari training/evaluasi seperti
pipeline existing; uncertainty model dilaporkan lewat ambang tau.

Keadilan perbandingan: dataset, split, purge, scaler, seed, epoch, callback,
class weight, dan seluruh hyperparameter IDENTIK. Satu-satunya perbedaan
adalah kanal order flow yang diberikan. Tiap model dilatih pada beberapa seed
dan hasilnya dilaporkan sebagai rata-rata ± simpangan baku, karena selisih
kecil antar model pada satu seed bisa saja hanya variasi inisialisasi.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple, cast

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orderflow_common import ABLATION_MODELS, load_orderflow_dataset, select_channels  # noqa: E402

from app.core.config import ARTIFACTS_DIR, get_config  # noqa: E402
from app.services.regime_labeling import regime_distribution, regime_durations  # noqa: E402


def class_weights(y: np.ndarray) -> dict:
    counts = y.sum(axis=0)
    total = counts.sum()
    return {i: float(total / (len(counts) * c)) if c > 0 else 1.0 for i, c in enumerate(counts)}


def classification_metrics(true: Sequence[str], pred: Sequence[str], classes: Sequence[str]) -> Dict:
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        cohen_kappa_score,
        confusion_matrix,
        matthews_corrcoef,
        precision_recall_fscore_support,
    )

    res = precision_recall_fscore_support(
        true, pred, labels=list(classes), zero_division=cast(Any, 0)
    )
    p, r, f, s = cast(Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray], res)
    mres = precision_recall_fscore_support(
        true, pred, labels=list(classes), average="macro", zero_division=cast(Any, 0)
    )
    mp, mr, mf = cast(Tuple[float, float, float, Any], mres)[:3]
    return {
        "n": len(true),
        "accuracy": round(float(accuracy_score(true, pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(true, pred)), 4),
        "precision_macro": round(float(mp), 4),
        "recall_macro": round(float(mr), 4),
        "macro_f1": round(float(mf), 4),
        "kappa": round(float(cohen_kappa_score(true, pred, labels=list(classes))), 4),
        "mcc": round(float(matthews_corrcoef(true, pred)), 4),
        "confusion_matrix": confusion_matrix(true, pred, labels=list(classes)).tolist(),
        "per_class": [
            {
                "regime": c,
                "precision": round(float(p[i]), 4),
                "recall": round(float(r[i]), 4),
                "f1": round(float(f[i]), 4),
                "support": int(s[i]),
            }
            for i, c in enumerate(classes)
        ],
    }


def sequence_stats(seq: Sequence[str]) -> Dict:
    """Distribusi, durasi, transisi, dan stabilitas deret regime kronologis."""
    seq = list(seq)
    n = len(seq)
    switches = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    durs = regime_durations(seq)
    all_runs = [d for v in durs.values() for d in v]
    return {
        "n": n,
        "distribution": regime_distribution(seq),
        "n_transitions": switches,
        "transitions_per_100": round(100.0 * switches / max(1, n - 1), 3),
        "mean_duration": round(float(np.mean(all_runs)), 3) if all_runs else 0.0,
        "median_duration": float(np.median(all_runs)) if all_runs else 0.0,
        "duration_by_regime": {
            k: {"mean": round(float(np.mean(v)), 3), "n_runs": len(v)} for k, v in durs.items() if v
        },
        # Stabilitas: peluang regime bertahan dari satu window ke berikutnya.
        "stay_probability": round(1.0 - switches / max(1, n - 1), 4),
    }


def mcnemar(true, pred_a, pred_b) -> Dict:
    """Uji McNemar (koreksi kontinuitas) A vs B pada sampel yang sama."""
    from scipy.stats import chi2  # type: ignore

    a_ok = np.asarray(pred_a) == np.asarray(true)
    b_ok = np.asarray(pred_b) == np.asarray(true)
    n01 = int(np.sum(a_ok & ~b_ok))
    n10 = int(np.sum(~a_ok & b_ok))
    if n01 + n10 == 0:
        return {"n01": 0, "n10": 0, "chi2": 0.0, "p_value": 1.0}
    stat = (abs(n01 - n10) - 1) ** 2 / (n01 + n10)
    return {"n01": n01, "n10": n10, "chi2": round(float(stat), 4), "p_value": round(float(chi2.sf(stat, 1)), 4)}


def block_bootstrap_f1_diff(true, pred_a, pred_b, classes, block=50, reps=1000, seed=42) -> Dict:
    """Moving-block bootstrap selisih macro F1 (B − A).

    Blok berurutan dipakai karena window bertetangga saling tumpang tindih;
    bootstrap biasa per sampel akan meremehkan ketidakpastian.
    """
    from sklearn.metrics import f1_score

    true, pa, pb = np.asarray(true), np.asarray(pred_a), np.asarray(pred_b)
    n = len(true)
    if n < block * 2:
        return {}
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    diffs = []
    for _ in range(reps):
        starts = rng.integers(0, n - block + 1, n_blocks)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]
        fa = f1_score(true[idx], pa[idx], labels=list(classes), average="macro", zero_division=cast(Any, 0))
        fb = f1_score(true[idx], pb[idx], labels=list(classes), average="macro", zero_division=cast(Any, 0))
        diffs.append(fb - fa)
    d = np.asarray(diffs)
    return {
        "mean_diff": round(float(d.mean()), 4),
        "ci95": [round(float(np.quantile(d, 0.025)), 4), round(float(np.quantile(d, 0.975)), 4)],
        "p_le_0": round(float((d <= 0).mean()), 4),
    }


def apply_tau(probs: np.ndarray, classes: Sequence[str], tau: float) -> List[str]:
    out = []
    for row in probs:
        k = int(row.argmax())
        out.append(classes[k] if row[k] >= tau else "uncertain_lowconf")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Ablation order flow A/B/C/D")
    p.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    p.add_argument("--seq-len", type=int, default=32)
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--seeds", type=int, nargs="+", default=None)
    p.add_argument("--models", nargs="+", default=list(ABLATION_MODELS))
    args = p.parse_args()

    import tensorflow as tf  # type: ignore

    from model_architecture import build_orderflow_fusion_model, compile_model

    cfg = get_config()
    seeds = args.seeds or [cfg.model.seed, cfg.model.seed + 1, cfg.model.seed + 2]

    t0 = time.time()
    data = load_orderflow_dataset(args.timeframe, seq_len=args.seq_len)
    classes: List[str] = list(data["classes"])  # type: ignore[arg-type]
    of = data["orderflow"]
    full = data["full"]
    rows = data["rows"]
    print(f"[{args.timeframe}] dataset siap {time.time() - t0:.0f}s, kelas {classes}, seed {seeds}")

    Xs = {s: data[s][0] for s in ("train", "validation", "test")}
    Ys = {s: data[s][2] for s in ("train", "validation", "test")}
    Xo = {s: of[s] for s in ("train", "validation", "test")}
    for s in Xs:
        print(f"  {s:10s} X_swt={Xs[s].shape} X_orderflow={Xo[s].shape} y={Ys[s].shape}")

    # Seluruh window di rentang test (termasuk uncertain_rule) — untuk
    # statistik stabilitas deret prediksi dan timeline.
    split = data["split"]
    te_lo, te_hi = split["test"]
    test_range = np.arange(te_lo, te_hi)
    true_test = [classes[i] for i in Ys["test"].argmax(axis=1)]
    label_seq_test_range = [full["labels"][i] for i in test_range]

    results: Dict[str, Dict] = {}
    test_preds: Dict[str, Dict[int, List[str]]] = {}
    full_preds: Dict[str, np.ndarray] = {}

    for key in args.models:
        spec = ABLATION_MODELS[key]
        ch: List[int] = spec["channels"]  # type: ignore[assignment]
        print(f"\n=== Model {key}: {spec['name']} (kanal order flow {ch}) ===")
        per_seed: List[Dict[str, Any]] = []
        test_preds[key] = {}
        prob_sum = None
        for seed in seeds:
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            model = compile_model(
                build_orderflow_fusion_model(
                    swt_shape=Xs["train"].shape[1:], orderflow_channels=len(ch), n_classes=len(classes)
                )
            )

            def inp(s, X_swt=None, X_of=None):
                xs = Xs[s] if X_swt is None else X_swt
                if not ch:
                    return xs
                xo = Xo[s] if X_of is None else X_of
                return [xs, select_channels(xo, ch)]

            ts = time.time()
            hist = model.fit(
                inp("train"),
                Ys["train"],
                validation_data=(inp("validation"), Ys["validation"]),
                epochs=args.epochs,
                batch_size=args.batch_size,
                class_weight=class_weights(Ys["train"]),
                shuffle=True,
                callbacks=[
                    tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True),
                    tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=5, min_lr=1e-5),
                ],
                verbose=0,
            )
            ep = len(hist.history["loss"])

            pv = model.predict(inp("validation"), batch_size=512, verbose=0)
            pt = model.predict(inp("test"), batch_size=512, verbose=0)
            # Prediksi atas SEMUA window di rentang test (termasuk uncertain_rule).
            X_all_swt = full["X_swt"][test_range]
            X_all_of = full["X_orderflow"][test_range]
            pr = model.predict(
                X_all_swt if not ch else [X_all_swt, select_channels(X_all_of, ch)],
                batch_size=512,
                verbose=0,
            )
            pred_val = [classes[i] for i in pv.argmax(axis=1)]
            pred_test = [classes[i] for i in pt.argmax(axis=1)]
            pred_range = [classes[i] for i in pr.argmax(axis=1)]
            true_val = [classes[i] for i in Ys["validation"].argmax(axis=1)]

            m_val = classification_metrics(true_val, pred_val, classes)
            m_test = classification_metrics(true_test, pred_test, classes)
            tau_pred = apply_tau(pt, classes, cfg.model.tau)
            conf = [i for i, t in enumerate(tau_pred) if t != "uncertain_lowconf"]
            m_conf = (
                classification_metrics([true_test[i] for i in conf], [tau_pred[i] for i in conf], classes)
                if conf
                else {}
            )
            per_seed.append(
                {
                    "seed": seed,
                    "epochs_ran": ep,
                    "best_val_loss": round(float(min(hist.history["val_loss"])), 4),
                    "validation": m_val,
                    "test": m_test,
                    "tau": cfg.model.tau,
                    "uncertain_lowconf_share": round(1 - len(conf) / max(1, len(tau_pred)), 4),
                    "test_confident": m_conf,
                    "test_range_sequence": sequence_stats(pred_range),
                    "mean_max_prob": round(float(pt.max(axis=1).mean()), 4),
                }
            )
            test_preds[key][seed] = pred_test
            prob_sum = pr if prob_sum is None else prob_sum + pr
            print(
                f"  seed {seed}: {ep:3d} epoch {time.time() - ts:5.0f}s | test acc={m_test['accuracy']:.4f} "
                f"BA={m_test['balanced_accuracy']:.4f} F1={m_test['macro_f1']:.4f} "
                f"kappa={m_test['kappa']:.4f} MCC={m_test['mcc']:.4f}"
            )
            if seed == seeds[0]:
                ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
                model.save(ARTIFACTS_DIR / f"orderflow_ablation_{key}_{args.timeframe}.keras")

        assert prob_sum is not None
        full_preds[key] = prob_sum / len(seeds)  # ensemble rata-rata seed, untuk timeline

        def agg(path):
            vals = []
            for r in per_seed:
                v = r
                for k in path:
                    v = v.get(k, {}) if isinstance(v, dict) else {}
                if isinstance(v, (int, float)):
                    vals.append(float(v))
            return {"mean": round(float(np.mean(vals)), 4), "std": round(float(np.std(vals)), 4)} if vals else {}

        summary: Dict[str, Any] = {
            m: agg(("test", m))
            for m in ("accuracy", "balanced_accuracy", "precision_macro", "recall_macro", "macro_f1", "kappa", "mcc")
        }
        summary["val_macro_f1"] = agg(("validation", "macro_f1"))
        summary["transitions_per_100"] = agg(("test_range_sequence", "transitions_per_100"))
        summary["mean_duration"] = agg(("test_range_sequence", "mean_duration"))
        summary["uncertain_lowconf_share"] = agg(("uncertain_lowconf_share",))
        summary["per_class_f1"] = {
            c: {
                "mean": round(float(np.mean([r["test"]["per_class"][i]["f1"] for r in per_seed])), 4),
                "std": round(float(np.std([r["test"]["per_class"][i]["f1"] for r in per_seed])), 4),
            }
            for i, c in enumerate(classes)
        }
        cm = np.sum([np.asarray(r["test"]["confusion_matrix"]) for r in per_seed], axis=0)
        results[key] = {
            **spec,
            "summary": summary,
            "confusion_matrix_sum_seeds": cm.tolist(),
            "per_seed": per_seed,
        }

    # Uji signifikansi B/C/D terhadap A, per seed (sampel test identik).
    comparisons = {}
    if "A" in test_preds:
        for key in [k for k in test_preds if k != "A"]:
            comparisons[key] = []
            for seed in seeds:
                comparisons[key].append(
                    {
                        "seed": seed,
                        "mcnemar": mcnemar(true_test, test_preds["A"][seed], test_preds[key][seed]),
                        "bootstrap_macro_f1_diff": block_bootstrap_f1_diff(
                            true_test, test_preds["A"][seed], test_preds[key][seed], classes, seed=seed
                        ),
                    }
                )

    # Timeline rentang test: harga, label Hurst-DFA, prediksi model, OFI, CVD.
    timeline = pd.DataFrame(
        {
            "time": full["time"][test_range],
            "close": full["close"][test_range],
            "hurst_dfa_regime": label_seq_test_range,
            "ofi": full["ofi_raw"][test_range],
            "cvd": full["cvd_raw"][test_range],
            "cvd_norm": full["cvd_norm_raw"][test_range],
            "evaluated": full["mask"][test_range],
        }
    )
    for key, probs in full_preds.items():
        timeline[f"model_{key}"] = [classes[i] for i in probs.argmax(axis=1)]
        timeline[f"model_{key}_maxprob"] = probs.max(axis=1)
    timeline.to_parquet(ARTIFACTS_DIR / f"orderflow_timeline_{args.timeframe}.parquet", index=False)

    hd_range = sequence_stats(label_seq_test_range)
    out = {
        "timeframe": args.timeframe,
        "task": "identification",
        "classes": classes,
        "config_hash": cfg.config_hash,
        "seeds": seeds,
        "seq_len": args.seq_len,
        "epochs_max": args.epochs,
        "batch_size": args.batch_size,
        "effective_window": data["effective_window"],
        "stride_bars": data["stride_bars"],
        "purge_bars": data["purge_bars"],
        "cvd_window": of["cvd_window"],
        "cvd_method": of["cvd_method"],
        "orderflow_scaler": of["scaler"],
        "n": {s: len(Ys[s]) for s in Ys},
        "split_time": {
            s: [int(full["time"][rows[s][0]]), int(full["time"][rows[s][-1]])] for s in rows if rows[s]
        },
        "hurst_dfa_test_range_sequence": hd_range,
        "hurst_dfa_test_evaluated_sequence": sequence_stats(true_test),
        "models": results,
        "comparisons_vs_A": comparisons,
        "catatan": (
            "Hurst dan DFA hanya membentuk label; input model = sekuens SWT (+ OFI/CVD). "
            "Metrik = rata-rata ± std atas seed. Window uncertain_rule dikeluarkan dari "
            "training/evaluasi, tetapi ikut diprediksi untuk statistik stabilitas dan timeline."
        ),
    }
    path = ARTIFACTS_DIR / f"orderflow_ablation_{args.timeframe}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"\n=== Ringkasan test [{args.timeframe}] - rata-rata +/- std atas {len(seeds)} seed ===")
    hdr = f"{'Model':6}{'OFI':5}{'CVD':5}{'Acc':>18}{'BA':>18}{'MacroF1':>18}{'Kappa':>18}{'MCC':>18}{'Trans/100':>12}"
    print(hdr)
    for key, r in results.items():
        summ: Dict[str, Any] = r["summary"]

        def f(m: str) -> str:
            val = summ.get(m, {})
            if isinstance(val, dict):
                return f"{val.get('mean', 0.0):.4f}+/-{val.get('std', 0.0):.4f}"
            return str(val)

        t_val = summ.get("transitions_per_100", {})
        t_mean = t_val.get("mean", 0.0) if isinstance(t_val, dict) else 0.0
        print(
            f"{key:6}{'Yes' if r['ofi'] else 'No':5}{'Yes' if r['cvd'] else 'No':5}"
            f"{f('accuracy'):>18}{f('balanced_accuracy'):>18}{f('macro_f1'):>18}{f('kappa'):>18}{f('mcc'):>18}"
            f"{t_mean:>12.2f}"
        )
    hd = hd_range
    print(f"Hurst-DFA (referensi) transisi/100 window = {hd['transitions_per_100']:.2f}")
    for key, lst in comparisons.items():
        ps = [c["mcnemar"]["p_value"] for c in lst]
        ds = [c["bootstrap_macro_f1_diff"].get("mean_diff", 0) for c in lst]
        cis = [c["bootstrap_macro_f1_diff"].get("ci95") for c in lst]
        print(f"  {key} vs A: dF1 per seed {ds}, CI95 {cis}, McNemar p {ps}")
    print(f"\nDisimpan: {path.name}, orderflow_timeline_{args.timeframe}.parquet  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()

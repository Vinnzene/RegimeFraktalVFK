"""Studi horizon Hybrid PS dengan label Trend-Aware Soft Consensus (review poin 14)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import review_eval as rv  # noqa: E402
import run_updated_evaluation as rue  # noqa: E402
from app.services.feature_builder import apply_scaler, fit_scaler  # noqa: E402

HORIZONS = [0, 125, 250, 500]


def _bal(y: np.ndarray, p: np.ndarray) -> float:
    rec = [float((p[y == c] == c).mean()) for c in range(3) if (y == c).any()]
    return float(np.mean(rec)) if rec else float("nan")


def run(tf: str, threads: int) -> Dict[str, Any]:
    import tensorflow as tf_  # type: ignore

    tf_.config.threading.set_intra_op_parallelism_threads(threads)
    tf_.config.threading.set_inter_op_parallelism_threads(2)
    d = rue.prepare_timeframe_data(tf)
    n, stride = len(d["mask"]), d["stride"]
    sp = d["split"]
    Y0, M0 = d["y_all"], d["mask"]
    bs = 96 if tf == "1h" else 64
    out: Dict[str, Any] = {"timeframe": tf, "stride_bars": stride, "split": {k: sp[k] for k in ("train", "validation", "test")},
                           "augmentation_4h": False, "class_weight_power": 0.60, "seeds": rue.SEEDS, "horizons": {}}
    for h in HORIZONS:
        t0 = time.time()
        k = int(np.floor(h / stride + 0.5))
        idx = np.arange(n)
        tgt_ok = idx + k < n
        Yt = np.zeros_like(Y0)
        Mt = np.zeros(n, dtype=bool)
        Yt[tgt_ok] = Y0[idx[tgt_ok] + k]
        Mt[tgt_ok] = M0[idx[tgt_ok] + k]
        tr = np.array([i for i in range(*sp["train"]) if Mt[i] and i + k < sp["train"][1]], dtype=int)
        va = np.array([i for i in range(*sp["validation"]) if Mt[i] and i + k < sp["validation"][1]], dtype=int)
        te = np.array([i for i in range(*sp["test"]) if Mt[i]], dtype=int)
        ps_sc = fit_scaler(d["PS"][tr])
        PS = apply_scaler(d["PS"], ps_sc)
        mu, sd = d["F_all"][tr].mean(0), d["F_all"][tr].std(0)
        sd[sd < 1e-12] = 1.0
        F = (d["F_all"] - mu) / sd
        cw = rv._cw("hybrid_ps", Yt[tr], 0.60)
        pt, pv = [], []
        for seed in rue.SEEDS:
            (p_va, p_te), _ = rv._fit_predict("hybrid_ps", "standard", PS[tr], F[tr], Yt[tr], PS[va], F[va], Yt[va],
                                              [(PS[va], F[va]), (PS[te], F[te])], cw, 60, bs, 10, seed)
            pv.append(p_va)
            pt.append(p_te)
        y_te, y_va = Yt[te].argmax(1), Yt[va].argmax(1)
        ens = np.mean(pt, 0).argmax(1)
        ens_v = np.mean(pv, 0).argmax(1)
        seed_acc = [float((p.argmax(1) == y_te).mean()) for p in pt]
        seed_ba = [_bal(y_te, p.argmax(1)) for p in pt]
        # Baseline persistence: label pada t dipakai sebagai tebakan label t+h.
        maj = int(Yt[tr].sum(0).argmax())
        base = np.where(M0[te], Y0[te].argmax(1), maj)
        rec = {
            "h_bars_requested": h, "row_offset": k, "h_bars_effective": k * stride,
            "n_train": int(len(tr)), "n_val": int(len(va)), "n_test": int(len(te)),
            "test_dist": {c: int((y_te == i).sum()) for i, c in enumerate(rue.CLASSES)},
            "ensemble": {"correct": int((ens == y_te).sum()), "accuracy_pct": round(100 * float((ens == y_te).mean()), 2),
                         "balanced_pct": round(100 * _bal(y_te, ens), 2),
                         "recall_pct": {c: round(100 * float((ens[y_te == i] == i).mean()), 2) if (y_te == i).any() else None
                                        for i, c in enumerate(rue.CLASSES)}},
            "seed_mean": {"accuracy_pct": round(100 * float(np.mean(seed_acc)), 2), "accuracy_std": round(100 * float(np.std(seed_acc)), 2),
                          "balanced_pct": round(100 * float(np.mean(seed_ba)), 2)},
            "validation_ensemble": {"accuracy_pct": round(100 * float((ens_v == y_va).mean()), 2), "balanced_pct": round(100 * _bal(y_va, ens_v), 2)},
            "persistence_baseline": {"accuracy_pct": round(100 * float((base == y_te).mean()), 2), "balanced_pct": round(100 * _bal(y_te, base), 2),
                                     "note": "tebakan = label pada t; mayoritas latih bila label t uncertain_rule"},
            "seconds": round(time.time() - t0, 1),
        }
        out["horizons"][str(h)] = rec
        print(f"[{tf}] h={h} (k={k}) ens {rec['ensemble']['correct']}/{len(te)} = {rec['ensemble']['accuracy_pct']}% "
              f"BA {rec['ensemble']['balanced_pct']}% | baseline {rec['persistence_baseline']['accuracy_pct']}% ({rec['seconds']}s)", flush=True)
    return out


def write_md() -> None:
    R = rv.REVIEW_DIR
    md = ["# Studi horizon Hybrid PS, label soft consensus (poin 14)", "",
          "Target = label Trend-Aware Soft Consensus pada jendela t + h bar. h = 0 adalah identifikasi. Model, fitur (PS 32×14 + 56),",
          "seed 42/43/44, hiperparameter, class weight 0,60, dan ambang train-only sama dengan `run_updated_evaluation.py`; split backtest",
          "tetap, baris yang targetnya menyeberang batas partisi dibuang. **Tanpa augmentasi ETH/BNB** di 4H (lihat catatan).",
          "Persentase benar = akurasi ensemble; rata-rata persentase benar ketiga kelas = rata-rata recall (balanced accuracy).", ""]
    ref = json.loads((rv.ARTIFACTS_DIR / "updated_eval_summary.json").read_text(encoding="utf-8"))
    for tf in ("1h", "4h"):
        p = R / f"horizon_study_{tf}.json"
        if not p.exists():
            continue
        o = json.loads(p.read_text(encoding="utf-8"))
        md += [f"## {tf.upper()}", "",
               "| h (bar) | h efektif | n uji | Benar (ens) | % benar (ens) | rata-rata % benar 3 kelas | % benar mean±sd 3 seed | recall P / R / A | baseline persistence % benar / BA | validasi % benar / BA |",
               "|---|---|---|---|---|---|---|---|---|---|"]
        for h, r in o["horizons"].items():
            e = r["ensemble"]
            rc = " / ".join(str(e["recall_pct"][c]).replace(".", ",") for c in rue.CLASSES)
            md.append(f"| {h} | {r['h_bars_effective']} | {r['n_test']} | {e['correct']} | {str(e['accuracy_pct']).replace('.', ',')} | "
                      f"{str(e['balanced_pct']).replace('.', ',')} | {str(r['seed_mean']['accuracy_pct']).replace('.', ',')} ± {str(r['seed_mean']['accuracy_std']).replace('.', ',')} | {rc} | "
                      f"{str(r['persistence_baseline']['accuracy_pct']).replace('.', ',')} / {str(r['persistence_baseline']['balanced_pct']).replace('.', ',')} | "
                      f"{str(r['validation_ensemble']['accuracy_pct']).replace('.', ',')} / {str(r['validation_ensemble']['balanced_pct']).replace('.', ',')} |")
        e0 = ref[tf]["historical_backtest"]["models"]["hybrid_ps"]["ensemble"]
        md += ["", f"Rujukan h = 0 dari run utama{' (dengan augmentasi ETH/BNB)' if tf == '4h' else ''}: "
               f"{e0['correct']}/{ref[tf]['historical_backtest']['models']['hybrid_ps']['total_test']} = {e0['pct']}%, BA {e0['balanced_pct']}%.", ""]
    md += ["Catatan:", "- h efektif = baris geser × stride (1H stride 4 bar, 4H stride 2 bar), dibulatkan ke baris terdekat.",
           "- Baseline persistence menebak label t+h dengan label t. Bila model tidak mengalahkan baseline ini, model belum memberi informasi prediktif tambahan.",
           "- Old `ml/src/horizon_study.py` memakai dataset SWT lama dan label lama, sehingga tidak dijalankan ulang; skrip ini menggantikannya untuk pipeline baru.", ""]
    (R / "horizon_study.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", choices=["1h", "4h"])
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--md-only", action="store_true")
    a = ap.parse_args()
    if not a.md_only:
        res = run(a.tf, a.threads)
        (rv.REVIEW_DIR / f"horizon_study_{a.tf}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    write_md()


if __name__ == "__main__":
    main()

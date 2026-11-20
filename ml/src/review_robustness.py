"""Uji ketahanan metode: walk-forward, sensitivitas, dan Monte Carlo.

Bagian:
  --part sensitivity --tf 1h|4h
      Sensitivitas ambang aturan Trend-Aware Soft Consensus (ER atas 0,60, ER bawah 0,35,
      ER kuat 0,85), satu per satu. Untuk tiap setelan: label dibentuk ulang (ambang Hurst/DFA
      dan skor ER_q tetap, dari data latih), Hybrid PS dilatih ulang (3 seed, hiperparameter
      Bab 4) dan diuji pada partisi uji backtest. 4H TANPA augmentasi ETH/BNB agar semua
      setelan sebanding (label augmentasi tidak dapat dibentuk ulang).
  --part montecarlo
      Dari probabilitas tersimpan (review/raw/{tf}_normal.npz):
        * moving-block bootstrap (blok = L/stride jendela = 500 bar) untuk selang
          kepercayaan 95% akurasi dan rata-rata 3 kelas (backtest & walk-forward pooled);
        * uji permutasi geser-sirkular (label digeser ≥ 1 blok terhadap prediksi; menjaga
          autokorelasi) untuk p-value terhadap kebetulan;
        * sebaran antar-seed.
  --part assemble
      Gabungkan semuanya (+ walk-forward, sweep bobot kelas, ablasi, horizon, surrogat)
      ke ml/artifacts/robustness_tests.json (dibaca endpoint /api/v1/model/robustness)
      dan review/robustness_tests.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import review_eval as rv  # noqa: E402
import run_updated_evaluation as rue  # noqa: E402
from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.services.feature_builder import apply_scaler, fit_scaler  # noqa: E402
from app.services.regime_labeling import label_from_exponents  # noqa: E402

REVIEW = ARTIFACTS_DIR / "review"
OUT_JSON = ARTIFACTS_DIR / "robustness_tests.json"
CLASSES = rue.CLASSES
DEFAULT = {"er_lo": 0.35, "er_hi": 0.60, "strong": 0.85}
SETTINGS: List[Dict[str, Any]] = [
    {"name": "bawaan", "param": "-", **DEFAULT},
    {"name": "ER atas 0,55", "param": "er_hi", **{**DEFAULT, "er_hi": 0.55}},
    {"name": "ER atas 0,65", "param": "er_hi", **{**DEFAULT, "er_hi": 0.65}},
    {"name": "ER bawah 0,30", "param": "er_lo", **{**DEFAULT, "er_lo": 0.30}},
    {"name": "ER bawah 0,40", "param": "er_lo", **{**DEFAULT, "er_lo": 0.40}},
    {"name": "ER kuat 0,80", "param": "strong", **{**DEFAULT, "strong": 0.80}},
    {"name": "ER kuat 0,90", "param": "strong", **{**DEFAULT, "strong": 0.90}},
]
BLOCK = {"1h": 125, "4h": 250}  # 500 bar / stride
SEED_MC = 20261119


def ba(y: np.ndarray, p: np.ndarray) -> float:
    rec = [float((p[y == c] == c).mean()) for c in range(3) if (y == c).any()]
    return float(np.mean(rec)) if rec else float("nan")


# ------------------------------------------------------------------ sensitivitas
def run_sensitivity(tf: str, threads: int) -> None:
    import tensorflow as tf_  # type: ignore

    tf_.config.threading.set_intra_op_parallelism_threads(threads)
    tf_.config.threading.set_inter_op_parallelism_threads(2)
    d = rue.prepare_timeframe_data(tf)
    sp, thr = d["split"], d["thresholds"]
    H, A, ER = d["hurst"], d["dfa"], d["er_q"]
    bs = 96 if tf == "1h" else 64
    base_labels = None
    rows = []
    for s in SETTINGS:
        t0 = time.time()
        labs = np.array([label_from_exponents(h, a, thr["hurst"], thr["dfa"], efficiency_ratio=float(e), soft_consensus=True,
                                              er_threshold=(s["er_lo"], s["er_hi"]), strong_er=s["strong"])
                         for h, a, e in zip(H, A, ER)], dtype=object)
        if base_labels is None:
            base_labels = labs
        mask = np.isin(labs, CLASSES)
        Y = np.zeros((len(labs), 3), dtype=np.float32)
        for i, c in enumerate(CLASSES):
            Y[labs == c, i] = 1.0
        pick = lambda k: np.array([i for i in range(*sp[k]) if mask[i]], dtype=int)  # noqa: E731
        tr, va, te = pick("train"), pick("validation"), pick("test")
        ps_sc = fit_scaler(d["PS"][tr])
        PS = apply_scaler(d["PS"], ps_sc)
        mu, sd = d["F_all"][tr].mean(0), d["F_all"][tr].std(0)
        sd[sd < 1e-12] = 1.0
        F = (d["F_all"] - mu) / sd
        cw = rv._cw("hybrid_ps", Y[tr], 0.60)
        pv, pt = [], []
        for seed in rue.SEEDS:
            (p_va, p_te), _ = rv._fit_predict("hybrid_ps", "standard", PS[tr], F[tr], Y[tr], PS[va], F[va], Y[va],
                                              [(PS[va], F[va]), (PS[te], F[te])], cw, 60, bs, 10, seed)
            pv.append(p_va)
            pt.append(p_te)
        yt, yv = Y[te].argmax(1), Y[va].argmax(1)
        et, ev = np.mean(pt, 0).argmax(1), np.mean(pv, 0).argmax(1)
        r = {
            **s,
            "labeled_pct": round(100 * float(mask.mean()), 2),
            "dist_pct": {c: round(100 * float((labs == c).mean()), 2) for c in CLASSES + ["uncertain_rule"]},
            "same_label_as_default_pct": round(100 * float((labs == base_labels).mean()), 2),
            "n_test": int(len(te)),
            "test_correct": int((et == yt).sum()),
            "test_acc_pct": round(100 * float((et == yt).mean()), 2),
            "test_ba_pct": round(100 * ba(yt, et), 2),
            "test_recall_pct": {c: round(100 * float((et[yt == i] == i).mean()), 2) if (yt == i).any() else None for i, c in enumerate(CLASSES)},
            "val_acc_pct": round(100 * float((ev == yv).mean()), 2),
            "val_ba_pct": round(100 * ba(yv, ev), 2),
            "seed_acc_pct": [round(100 * float((p.argmax(1) == yt).mean()), 2) for p in pt],
            "seconds": round(time.time() - t0, 1),
        }
        rows.append(r)
        print(f"[{tf}] {s['name']:14s} berlabel {r['labeled_pct']}% | uji {r['test_correct']}/{r['n_test']} = {r['test_acc_pct']}% "
              f"BA {r['test_ba_pct']}% | val {r['val_acc_pct']}% ({r['seconds']}s)", flush=True)
    out = {"timeframe": tf, "augmentation_4h": False, "class_weight_power": 0.60, "seeds": rue.SEEDS,
           "note": "Satu ambang diubah per baris; ambang Hurst/DFA dan skor ER_q tetap (data latih).", "rows": rows}
    (REVIEW / f"robustness_sensitivity_{tf}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


# ------------------------------------------------------------------ Monte Carlo
def block_bootstrap(y: np.ndarray, p: np.ndarray, block: int, B: int, rng) -> Dict[str, Any]:
    n = len(y)
    block = max(1, min(block, n))
    nb = int(np.ceil(n / block))
    accs, bas = np.empty(B), np.empty(B)
    for b in range(B):
        starts = rng.integers(0, n, size=nb)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel() % n  # circular block bootstrap
        idx = idx[:n]
        accs[b] = (p[idx] == y[idx]).mean()
        bas[b] = ba(y[idx], p[idx])
    q = lambda a: [round(100 * float(np.percentile(a, 2.5)), 2), round(100 * float(np.percentile(a, 97.5)), 2)]  # noqa: E731
    return {"block_windows": block, "n_blocks": nb, "B": B, "acc_ci95_pct": q(accs), "ba_ci95_pct": q(bas),
            "acc_sd_pct": round(100 * float(accs.std()), 2)}


def shift_permutation(y: np.ndarray, p: np.ndarray, block: int, n_perm: int, rng) -> Dict[str, Any]:
    n = len(y)
    obs = float((p == y).mean())
    lo, hi = block, n - block
    if hi <= lo:
        return {"note": "data uji terlalu pendek untuk geser ≥ 1 blok"}
    shifts = rng.integers(lo, hi, size=n_perm)
    null = np.array([(p == np.roll(y, int(k))).mean() for k in shifts])
    hist, edges = np.histogram(100 * null, bins=30)
    return {"observed_acc_pct": round(100 * obs, 2), "null_mean_pct": round(100 * float(null.mean()), 2),
            "null_p95_pct": round(100 * float(np.percentile(null, 95)), 2), "null_max_pct": round(100 * float(null.max()), 2),
            "n_perm": n_perm, "p_value": float((np.sum(null >= obs) + 1) / (n_perm + 1)),
            "hist": {"counts": hist.tolist(), "edges": [round(float(e), 2) for e in edges]}}


def run_montecarlo() -> None:
    rng = np.random.default_rng(SEED_MC)
    out: Dict[str, Any] = {}
    for tf in ("1h", "4h"):
        with np.load(REVIEW / "raw" / f"{tf}_normal.npz") as z:
            yb, pb_seeds = z["bt__y_test"], z["bt__hybrid_ps__p_test"]
            folds = sorted({int(k.split("__")[0][2:]) for k in z.files if k.startswith("wf") and k.endswith("__y_test")})
            yw = np.concatenate([z[f"wf{f}__y_test"] for f in folds])
            pw_seeds = np.concatenate([z[f"wf{f}__hybrid_ps__p_test"] for f in folds], axis=1)
        pb, pw = pb_seeds.mean(0).argmax(1), pw_seeds.mean(0).argmax(1)
        counts = np.bincount(yb, minlength=3)
        out[tf] = {
            "backtest": {
                "n": int(len(yb)), "acc_pct": round(100 * float((pb == yb).mean()), 2), "ba_pct": round(100 * ba(yb, pb), 2),
                "majority_class_pct": round(100 * float(counts.max() / counts.sum()), 2), "chance_pct": 33.33,
                "bootstrap": block_bootstrap(yb, pb, BLOCK[tf], 5000, rng),
                "permutation": shift_permutation(yb, pb, BLOCK[tf], 5000, rng),
                "seed_acc_pct": [round(100 * float((s.argmax(1) == yb).mean()), 2) for s in pb_seeds],
                "seed_ba_pct": [round(100 * ba(yb, s.argmax(1)), 2) for s in pb_seeds],
            },
            "walk_forward_pooled": {
                "n": int(len(yw)), "acc_pct": round(100 * float((pw == yw).mean()), 2), "ba_pct": round(100 * ba(yw, pw), 2),
                "bootstrap": block_bootstrap(yw, pw, BLOCK[tf], 5000, rng),
                "permutation": shift_permutation(yw, pw, BLOCK[tf], 5000, rng),
                "seed_acc_pct": [round(100 * float((s.argmax(1) == yw).mean()), 2) for s in pw_seeds],
            },
        }
        print(tf, {k: (v["acc_pct"], v["bootstrap"]["acc_ci95_pct"], v["permutation"].get("p_value")) for k, v in out[tf].items()}, flush=True)
    (REVIEW / "robustness_montecarlo.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


# ------------------------------------------------------------------ gabung
def assemble() -> None:
    summ = json.loads((ARTIFACTS_DIR / "updated_eval_summary.json").read_text(encoding="utf-8"))
    mc = json.loads((REVIEW / "robustness_montecarlo.json").read_text(encoding="utf-8"))
    band = json.loads((REVIEW / "random_band_check.json").read_text(encoding="utf-8"))
    cw = json.loads((REVIEW / "cw_sweep.json").read_text(encoding="utf-8"))
    abl_er = json.loads((REVIEW / "ablation_no_er.json").read_text(encoding="utf-8"))
    abl_sa = json.loads((REVIEW / "ablation_swt_attention.json").read_text(encoding="utf-8"))
    out: Dict[str, Any] = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "horizon_bars": 0,
                           "sources": "ml/src/review_robustness.py; ml/artifacts/review/*", "timeframes": {}}

    def ens(v, part="backtest"):
        e = v[part]["test"]["ensemble"]
        return {"acc_pct": round(100 * e["accuracy"], 2), "ba_pct": round(100 * e["balanced_accuracy"], 2)}

    vs_path = REVIEW / "vs_indicators.json"
    vs = json.loads(vs_path.read_text(encoding="utf-8")) if vs_path.exists() else None
    if vs:
        out["vs_indicators_rules"] = {k: vs[k] for k in ("adx_rule", "chop_rule", "lookback_bars", "horizons_bars")}
    for tf in ("1h", "4h"):
        wf = summ[tf]["walk_forward_5fold"]
        sens_path = REVIEW / f"robustness_sensitivity_{tf}.json"
        hz_path = REVIEW / f"horizon_study_{tf}.json"
        hz = json.loads(hz_path.read_text(encoding="utf-8")) if hz_path.exists() else None
        out["timeframes"][tf] = {
            "walk_forward": {
                "folds": [{"fold": f["fold"], "n_train": f["n_train"], "n_test": f["n_test"],
                           "correct": f["models"]["hybrid_ps"]["ensemble"]["correct"],
                           "pct": f["models"]["hybrid_ps"]["ensemble"]["pct"],
                           "balanced_pct": f["models"]["hybrid_ps"]["ensemble"]["balanced_pct"],
                           "mlp_pct": f["models"]["structural_mlp"]["ensemble"]["pct"]} for f in wf["folds"]],
                "pooled": wf["summary"]["hybrid_ps"],
                "backtest_pct": summ[tf]["historical_backtest"]["models"]["hybrid_ps"]["ensemble"]["pct"],
            },
            "sensitivity": {
                "er_rule": json.loads(sens_path.read_text(encoding="utf-8")) if sens_path.exists() else None,
                "class_weight_power": cw.get(tf, []),
                "ablation": {
                    "normal": {"backtest": ens(abl_sa[tf]["normal"]), "walk_forward": ens(abl_sa[tf]["normal"], "walk_forward_pooled")},
                    "tanpa_ER": {"backtest": ens(abl_er[tf]["no_er"]["hybrid_ps"]), "walk_forward": ens(abl_er[tf]["no_er"]["hybrid_ps"], "walk_forward_pooled")},
                    "tanpa_SWT": {"backtest": ens(abl_sa[tf]["no_swt_energy"]), "walk_forward": ens(abl_sa[tf]["no_swt_energy"], "walk_forward_pooled")},
                    "tanpa_attention": {"backtest": ens(abl_sa[tf]["no_attention"]), "walk_forward": ens(abl_sa[tf]["no_attention"], "walk_forward_pooled")},
                },
                "horizon": [{"h_bars": int(h), "h_effective": r["h_bars_effective"], "acc_pct": r["ensemble"]["accuracy_pct"],
                             "ba_pct": r["ensemble"]["balanced_pct"], "baseline_acc_pct": r["persistence_baseline"]["accuracy_pct"]}
                            for h, r in hz["horizons"].items()] if hz else None,
            },
            "vs_indicators": None if not vs else {
                "association": vs["timeframes"][tf]["association"]["cramers_v"],
                "crosstab_model_vs_ADX14": vs["timeframes"][tf]["association"]["crosstab_model_vs_ADX14"],
                "momentum_short": {
                    h: {"base_hit_pct": m["base_hit_pct"],
                        **{k.split(" ")[0]: v for k, v in m.items() if isinstance(v, dict) and "spread_pp" in v}}
                    for h, m in vs["timeframes"][tf]["momentum"].items()
                },
                "momentum_scale_matched": vs.get("scale_matched", {}).get(tf),
            },
            "monte_carlo": {
                **mc[tf],
                "surrogate": {
                    "per_window_shuffle": {k: band["timeframes"][tf]["surrogate_per_window_shuffle"][k]
                                           for k in ("n_windows", "n_shuffles", "pct_windows_H_reject_5pct", "pct_windows_alpha_reject_5pct",
                                                     "pct_windows_both_reject_5pct", "ks_H_allwindows_vs_surrogate", "ks_alpha_allwindows_vs_surrogate")},
                    "both_outside_random_band_pct": band["timeframes"][tf]["bands"]["S1"]["all"]["pct_both_outside"],
                },
            },
        }
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    write_md(out)
    print("assembled ->", OUT_JSON)


def write_md(o: Dict[str, Any]) -> None:
    c = lambda v: "–" if v is None else str(v).replace(".", ",")  # noqa: E731
    md = ["# Uji ketahanan metode: walk-forward, sensitivitas, Monte Carlo", "",
          "Model: Hybrid PS Attention-BiLSTM (identifikasi, h = 0), ensemble 3 seed. Data: `ml/artifacts/robustness_tests.json` "
          "(juga ditampilkan di halaman aplikasi **Uji Ketahanan**).", ""]
    for tf, t in o["timeframes"].items():
        w, s, m = t["walk_forward"], t["sensitivity"], t["monte_carlo"]
        md += [f"## {tf.upper()}", "", "### 1. Walk-forward (5 fold, expanding, purge 500 bar)", "",
               "| Fold | Latih | Uji | Benar | % benar | Rata-rata 3 kelas | MLP % benar |", "|---|---|---|---|---|---|---|"]
        for f in w["folds"]:
            md.append(f"| {f['fold']} | {f['n_train']} | {f['n_test']} | {f['correct']} | {c(f['pct'])} | {c(f['balanced_pct'])} | {c(f['mlp_pct'])} |")
        p = w["pooled"]
        md += [f"| Gabungan | | {p['total_test_pooled']} | {p['total_correct_ensemble']} | {c(p['pooled_pct_ensemble'])} | | |", "",
               f"Backtest tunggal: {c(w['backtest_pct'])}%. Rata-rata antar-fold {c(p['fold_avg_pct'])} ± {c(p['fold_std_pct'])}.", "",
               "### 2. Sensitivitas", ""]
        er = s["er_rule"]
        if er:
            md += [f"Ambang aturan ER, satu per satu ({'tanpa augmentasi ETH/BNB' if tf == '4h' else 'sama dengan Bab 4'}):", "",
                   "| Setelan | Jendela berlabel | Label sama dgn bawaan | Uji n | % benar | Rata-rata 3 kelas | Validasi % benar |", "|---|---|---|---|---|---|---|"]
            for r in er["rows"]:
                md.append(f"| {r['name']} | {c(r['labeled_pct'])}% | {c(r['same_label_as_default_pct'])}% | {r['n_test']} | {c(r['test_acc_pct'])} | {c(r['test_ba_pct'])} | {c(r['val_acc_pct'])} |")
            accs = [r["test_acc_pct"] for r in er["rows"]]
            md += ["", f"Rentang % benar uji: {c(min(accs))}–{c(max(accs))} (bawaan {c(er['rows'][0]['test_acc_pct'])}).", ""]
        md += ["Eksponen bobot kelas (backtest Hybrid PS):", "", "| Eksponen | Validasi % benar | Uji % benar |", "|---|---|---|"]
        for r in s["class_weight_power"]:
            md.append(f"| {c(r['power'])} | {c(round(100 * r['val_ens_acc'], 2))} | {c(round(100 * r['test_ens_acc'], 2))} |")
        md += ["", "Ablasi fitur dan arsitektur:", "", "| Varian | Backtest % benar | WF % benar |", "|---|---|---|"]
        for k, v in s["ablation"].items():
            md.append(f"| {k} | {c(v['backtest']['acc_pct'])} | {c(v['walk_forward']['acc_pct'])} |")
        if s["horizon"]:
            md += ["", "Horizon target:", "", "| h (bar) | % benar | baseline persistence |", "|---|---|---|"]
            for r in s["horizon"]:
                md.append(f"| {r['h_bars']} | {c(r['acc_pct'])} | {c(r['baseline_acc_pct'])} |")
        bt, wfp = m["backtest"], m["walk_forward_pooled"]
        md += ["", "### 3. Monte Carlo", "",
               "| Uji | Backtest | Walk-forward gabungan |", "|---|---|---|",
               f"| % benar | {c(bt['acc_pct'])} | {c(wfp['acc_pct'])} |",
               f"| SK 95% block bootstrap (blok {bt['bootstrap']['block_windows']} jendela = 500 bar, 5.000×) | {c(bt['bootstrap']['acc_ci95_pct'][0])}–{c(bt['bootstrap']['acc_ci95_pct'][1])} | {c(wfp['bootstrap']['acc_ci95_pct'][0])}–{c(wfp['bootstrap']['acc_ci95_pct'][1])} |",
               f"| SK 95% rata-rata 3 kelas | {c(bt['bootstrap']['ba_ci95_pct'][0])}–{c(bt['bootstrap']['ba_ci95_pct'][1])} | {c(wfp['bootstrap']['ba_ci95_pct'][0])}–{c(wfp['bootstrap']['ba_ci95_pct'][1])} |",
               f"| Permutasi geser-sirkular: rata-rata nol / P95 nol | {c(bt['permutation'].get('null_mean_pct'))} / {c(bt['permutation'].get('null_p95_pct'))} | {c(wfp['permutation'].get('null_mean_pct'))} / {c(wfp['permutation'].get('null_p95_pct'))} |",
               f"| p-value permutasi (5.000×) | {bt['permutation'].get('p_value', '–'):.4g} | {wfp['permutation'].get('p_value', '–'):.4g} |",
               f"| Antar-seed % benar | {', '.join(c(x) for x in bt['seed_acc_pct'])} | {', '.join(c(x) for x in wfp['seed_acc_pct'])} |",
               f"| Kelas terbanyak / peluang | {c(bt['majority_class_pct'])} / 33,33 | |", "",
               f"Surrogat (acak urutan return per jendela, {m['surrogate']['per_window_shuffle']['n_shuffles']}× pada "
               f"{m['surrogate']['per_window_shuffle']['n_windows']} jendela): H ditolak {c(m['surrogate']['per_window_shuffle']['pct_windows_H_reject_5pct'])}%, "
               f"α ditolak {c(m['surrogate']['per_window_shuffle']['pct_windows_alpha_reject_5pct'])}% jendela; H dan α di luar pita acak: "
               f"{c(m['surrogate']['both_outside_random_band_pct'])}%.", ""]
    (REVIEW / "robustness_tests.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True, choices=["sensitivity", "montecarlo", "assemble"])
    ap.add_argument("--tf", choices=["1h", "4h"])
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()
    if a.part == "sensitivity":
        run_sensitivity(a.tf, a.threads)
    elif a.part == "montecarlo":
        run_montecarlo()
    else:
        assemble()


if __name__ == "__main__":
    main()

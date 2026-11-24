"""Metrik review dari probabilitas tersimpan (ml/artifacts/review/raw/*.npz).

Menghasilkan:
  review/full_metrics.json + .md               (poin 4)
  review/ablation_no_er.json + .md             (poin 2)
  review/ablation_swt_attention.json + .md     (poin 7)
  review/market_pivot_independent.json + .md   (poin 3)
  review/cw_sweep.json (+ ringkasan di full_metrics.md) bila raw sweep ada

    python ml/src/review_metrics.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_updated_evaluation as rue  # noqa: E402
from app.core.config import ARTIFACTS_DIR  # noqa: E402

REVIEW = ARTIFACTS_DIR / "review"
RAW = REVIEW / "raw"
CLASSES = rue.CLASSES  # persistent, random_like, anti_persistent
SHORT = {"persistent": "Pers", "random_like": "Rand", "anti_persistent": "Anti"}
ORIG = json.loads((ARTIFACTS_DIR / "updated_eval_summary.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ metrik dasar
def cm(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    m = np.zeros((3, 3), dtype=int)
    for a, b in zip(y, p):
        m[a, b] += 1
    return m


def metrics(y: np.ndarray, p: np.ndarray) -> Dict[str, Any]:
    m = cm(y, p)
    n = m.sum()
    tp = np.diag(m).astype(float)
    sup = m.sum(1).astype(float)
    pred = m.sum(0).astype(float)
    rec = np.divide(tp, sup, out=np.zeros(3), where=sup > 0)
    prec = np.divide(tp, pred, out=np.zeros(3), where=pred > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros(3), where=(prec + rec) > 0)
    # MCC multikelas (Gorodkin)
    c = tp.sum()
    cov_ytyp = c * n - (sup * pred).sum()
    cov_ypyp = n * n - (pred * pred).sum()
    cov_ytyt = n * n - (sup * sup).sum()
    mcc = cov_ytyp / np.sqrt(cov_ypyp * cov_ytyt) if cov_ypyp > 0 and cov_ytyt > 0 else 0.0
    return {"n": int(n), "correct": int(c), "accuracy": float(c / max(n, 1)), "balanced_accuracy": float(rec.mean()),
            "macro_f1": float(f1.mean()), "mcc": float(mcc),
            "recall": {k: float(rec[i]) for i, k in enumerate(CLASSES)},
            "precision": {k: float(prec[i]) for i, k in enumerate(CLASSES)},
            "f1": {k: float(f1[i]) for i, k in enumerate(CLASSES)},
            "support": {k: int(sup[i]) for i, k in enumerate(CLASSES)}}


def summarize(y: np.ndarray, probs: np.ndarray) -> Dict[str, Any]:
    """probs: (n_seed, n, 3). Mengembalikan mean±std per seed + ensemble (rata-rata softmax)."""
    per_seed = [metrics(y, pr.argmax(1)) for pr in probs]
    ens_pred = probs.mean(0).argmax(1)
    ens = metrics(y, ens_pred)
    ens["confusion_matrix"] = {"rows_true_cols_pred": CLASSES, "matrix": cm(y, ens_pred).tolist()}
    agg: Dict[str, Any] = {}
    for k in ("accuracy", "balanced_accuracy", "macro_f1", "mcc"):
        v = np.array([s[k] for s in per_seed])
        agg[k] = {"mean": float(v.mean()), "std": float(v.std())}
    agg["recall"] = {c: {"mean": float(np.mean([s["recall"][c] for s in per_seed])),
                         "std": float(np.std([s["recall"][c] for s in per_seed]))} for c in CLASSES}
    return {"seed_mean": agg, "ensemble": ens, "per_seed": per_seed}


def load_raw(tf: str, tag: str) -> Optional[Dict[str, np.ndarray]]:
    p = RAW / f"{tf}_{tag}.npz"
    if not p.exists():
        return None
    with np.load(p, allow_pickle=True) as z:
        return {k: z[k] for k in z.files}


def models_in(raw: Dict[str, np.ndarray], prefix: str = "bt") -> List[str]:
    return sorted({k.split("__")[1] for k in raw if k.startswith(prefix + "__") and k.endswith("__p_test")},
                  key=lambda m: rue.MODELS.index(m) if m in rue.MODELS else 99)


def n_folds(raw) -> List[int]:
    return sorted({int(k.split("__")[0][2:]) for k in raw if k.startswith("wf") and k.endswith("__y_test")})


def eval_variant(raw: Dict[str, np.ndarray]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    folds = n_folds(raw)
    for m in models_in(raw):
        r: Dict[str, Any] = {
            "backtest": {"test": summarize(raw["bt__y_test"], raw[f"bt__{m}__p_test"]),
                         "validation": summarize(raw["bt__y_val"], raw[f"bt__{m}__p_val"])}}
        if folds:
            yt = np.concatenate([raw[f"wf{f}__y_test"] for f in folds])
            pt = np.concatenate([raw[f"wf{f}__{m}__p_test"] for f in folds], axis=1)
            yv = np.concatenate([raw[f"wf{f}__y_val"] for f in folds])
            pv = np.concatenate([raw[f"wf{f}__{m}__p_val"] for f in folds], axis=1)
            r["walk_forward_pooled"] = {"test": summarize(yt, pt), "validation": summarize(yv, pv)}
            r["walk_forward_per_fold"] = {
                int(f): {"test": _compact(summarize(raw[f"wf{f}__y_test"], raw[f"wf{f}__{m}__p_test"])),
                         "validation": _compact(summarize(raw[f"wf{f}__y_val"], raw[f"wf{f}__{m}__p_val"]))}
                for f in folds}
        out[m] = r
    return out


def _compact(s: Dict[str, Any]) -> Dict[str, Any]:
    e = s["ensemble"]
    return {"n": e["n"], "ens_acc": round(e["accuracy"], 4), "ens_ba": round(e["balanced_accuracy"], 4),
            "ens_macro_f1": round(e["macro_f1"], 4), "ens_mcc": round(e["mcc"], 4),
            "seed_mean_acc": round(s["seed_mean"]["accuracy"]["mean"], 4), "seed_mean_ba": round(s["seed_mean"]["balanced_accuracy"]["mean"], 4)}


def rnd(o: Any, nd: int = 4) -> Any:
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, dict):
        return {k: rnd(v, nd) for k, v in o.items()}
    if isinstance(o, list):
        return [rnd(v, nd) for v in o]
    return o


def P(x: float) -> str:
    return f"{100 * x:.2f}".replace(".", ",")


def F(x: float) -> str:
    return f"{x:.3f}".replace(".", ",")


def row_line(label: str, s: Dict[str, Any]) -> str:
    sm, e = s["seed_mean"], s["ensemble"]
    rec = " / ".join(P(sm["recall"][c]["mean"]) for c in CLASSES)
    erec = " / ".join(P(e["recall"][c]) for c in CLASSES)
    return (f"| {label} | {P(sm['accuracy']['mean'])} ± {P(sm['accuracy']['std'])} | {P(e['accuracy'])} | "
            f"{P(sm['balanced_accuracy']['mean'])} | {P(e['balanced_accuracy'])} | {F(sm['macro_f1']['mean'])} | {F(e['macro_f1'])} | "
            f"{F(sm['mcc']['mean'])} | {F(e['mcc'])} | {rec} | {erec} |")


HDR = ("| Model | Acc mean±sd (%) | Acc ens (%) | BA mean (%) | BA ens (%) | F1 mean | F1 ens | MCC mean | MCC ens | "
       "Recall mean P/R/A (%) | Recall ens P/R/A (%) |\n|---|---|---|---|---|---|---|---|---|---|---|")


def cm_md(e: Dict[str, Any]) -> str:
    m = e["confusion_matrix"]["matrix"]
    lines = ["| benar \\ prediksi | " + " | ".join(SHORT[c] for c in CLASSES) + " |", "|---|---|---|---|"]
    for i, c in enumerate(CLASSES):
        lines.append(f"| {SHORT[c]} | " + " | ".join(str(v) for v in m[i]) + " |")
    return "\n".join(lines)


# ------------------------------------------------------------------ poin 4
def full_metrics(res: Dict[str, Dict[str, Any]], sweep: Dict[str, Any]) -> str:
    md = ["# Metrik lengkap (poin 4)", "",
          "Sumber: `ml/src/review_eval.py --variant normal` (replikasi `run_updated_evaluation.py`: seed 42/43/44, split, purge, "
          "ambang train-only, class-weight 0,60 backtest / 0,55 walk-forward) lalu `ml/src/review_metrics.py`.",
          "Ensemble = rata-rata softmax 3 seed. Mean = rata-rata metrik per seed. Walk-forward pooled = gabungan prediksi uji 5 fold.",
          "Recall P/R/A = persistent / random_like / anti_persistent.", ""]
    for tf in ("1h", "4h"):
        r = res.get(tf)
        if not r:
            md.append(f"## {tf.upper()}: belum ada hasil\n")
            continue
        md += [f"## {tf.upper()}", ""]
        # replikasi vs angka asli
        md += ["### Replikasi terhadap updated_eval_summary.json", "",
               "| Model | BT ens asli | BT ens replikasi | BT mean asli | BT mean replikasi | WF pooled ens asli | WF pooled ens replikasi |",
               "|---|---|---|---|---|---|---|"]
        o_bt = ORIG[tf]["historical_backtest"]["models"]
        o_wf = ORIG[tf]["walk_forward_5fold"]["summary"]
        for m, v in r.items():
            wf = v.get("walk_forward_pooled")
            md.append(f"| {rue.MODEL_LABELS[m]} | {o_bt[m]['ensemble']['pct']} | {P(v['backtest']['test']['ensemble']['accuracy'])} | "
                      f"{o_bt[m]['mean_pct']} | {P(v['backtest']['test']['seed_mean']['accuracy']['mean'])} | "
                      f"{o_wf[m]['pooled_pct_ensemble']} | {P(wf['test']['ensemble']['accuracy']) if wf else '-'} |")
        md.append("")
        for split_key, title in (("backtest", "Historical backtest"), ("walk_forward_pooled", "Walk-forward 5 fold (pooled)")):
            for part in ("test", "validation"):
                md += [f"### {title}: set {'UJI' if part == 'test' else 'VALIDASI'}", "", HDR]
                for m, v in r.items():
                    if split_key in v:
                        md.append(row_line(rue.MODEL_LABELS[m], v[split_key][part]))
                md.append("")
            md += [f"#### Confusion matrix ensemble, {title}, set uji", ""]
            for m, v in r.items():
                if split_key in v:
                    md += [f"**{rue.MODEL_LABELS[m]}** (n = {v[split_key]['test']['ensemble']['n']})", "", cm_md(v[split_key]["test"]["ensemble"]), ""]
        # ranking val vs test
        md += ["### Apakah peringkat model di validasi sama dengan di uji?", "",
               "| Model | BT val ens acc | BT uji ens acc | BT val ens BA | BT uji ens BA | WF val ens acc | WF uji ens acc |", "|---|---|---|---|---|---|---|"]
        for m, v in r.items():
            wf = v.get("walk_forward_pooled")
            md.append(f"| {rue.MODEL_LABELS[m]} | {P(v['backtest']['validation']['ensemble']['accuracy'])} | {P(v['backtest']['test']['ensemble']['accuracy'])} | "
                      f"{P(v['backtest']['validation']['ensemble']['balanced_accuracy'])} | {P(v['backtest']['test']['ensemble']['balanced_accuracy'])} | "
                      f"{P(wf['validation']['ensemble']['accuracy']) if wf else '-'} | {P(wf['test']['ensemble']['accuracy']) if wf else '-'} |")
        md.append("")
    md += ["## Asal eksponen class weight 0,60 dan 0,55", "",
           "- Kedua angka masuk dalam satu commit (`fc7ebf5`, 15 Nov 2026) langsung di `run_updated_evaluation.py` baris 375 dan 568. "
           "Komentar kodenya menyebut 'power 0.65' padahal nilai yang dipakai 0,60.",
           "- Repositori tidak berisi skrip, log, atau artefak sweep yang memilih 0,60/0,55, dan tidak ada praregistrasi untuk angka ini. "
           "Jadi tidak ada bukti tertulis bahwa pemilihannya hanya memakai validasi, dan juga tidak ada bukti sebaliknya.",
           "- Untuk mengujinya, `review_eval.py --variant cw_sweep` melatih ulang Hybrid PS (backtest, 3 seed) dengan eksponen "
           "0,40–1,00 dan mencatat metrik validasi (uji dicatat terpisah, hanya untuk transparansi).", ""]
    if sweep:
        for tf, rows in sweep.items():
            md += [f"### Sweep eksponen Hybrid PS, backtest {tf.upper()}", "",
                   "| Eksponen | Val ens acc | Val ens BA | Val mean acc | Uji ens acc | Uji ens BA |", "|---|---|---|---|---|---|"]
            best_acc = max(rows, key=lambda r: r["val_ens_acc"])
            best_ba = max(rows, key=lambda r: r["val_ens_ba"])
            for r_ in rows:
                md.append(f"| {r_['power']:.2f} | {P(r_['val_ens_acc'])} | {P(r_['val_ens_ba'])} | {P(r_['val_mean_acc'])} | "
                          f"{P(r_['test_ens_acc'])} | {P(r_['test_ens_ba'])} |")
            best_test = max(rows, key=lambda r: r["test_ens_acc"])
            md += ["", f"Terbaik di validasi: acc → {best_acc['power']:.2f}, BA → {best_ba['power']:.2f}. "
                   f"Terbaik di uji (acc): {best_test['power']:.2f}.", ""]
    else:
        md += ["Sweep belum dijalankan.", ""]
    return "\n".join(md)


# ------------------------------------------------------------------ poin 2 / 7
def ablation_md(title: str, intro: List[str], tf_rows: Dict[str, List[tuple]]) -> str:
    md = [f"# {title}", ""] + intro + [""]
    for tf, rows in tf_rows.items():
        md += [f"## {tf.upper()}", ""]
        for split_key, name in (("backtest", "Historical backtest, set uji"), ("walk_forward_pooled", "Walk-forward 5 fold pooled, set uji")):
            md += [f"### {name}", "", HDR]
            for label, v in rows:
                if v is not None and split_key in v:
                    md.append(row_line(label, v[split_key]["test"]))
            md.append("")
        md += ["### Validasi (backtest / WF pooled), ensemble", "",
               "| Model | BT val acc | BT val BA | WF val acc | WF val BA |", "|---|---|---|---|---|"]
        for label, v in rows:
            if v is None:
                continue
            wf = v.get("walk_forward_pooled")
            md.append(f"| {label} | {P(v['backtest']['validation']['ensemble']['accuracy'])} | {P(v['backtest']['validation']['ensemble']['balanced_accuracy'])} | "
                      f"{P(wf['validation']['ensemble']['accuracy']) if wf else '-'} | {P(wf['validation']['ensemble']['balanced_accuracy']) if wf else '-'} |")
        md.append("")
        md += ["### Confusion matrix ensemble (backtest uji)", ""]
        for label, v in rows:
            if v is not None:
                md += [f"**{label}**", "", cm_md(v["backtest"]["test"]["ensemble"]), ""]
    return "\n".join(md)


# ------------------------------------------------------------------ poin 3
def market_conditions(tf: str):
    d = rue.prepare_timeframe_data(tf)
    from app.db.repository import get_repository  # noqa: PLC0415
    from app.services.hurst_dfa import to_log_return  # noqa: PLC0415

    lr = to_log_return(get_repository().get_ohlcv("BTCUSDT", tf)["close"].to_numpy(dtype=float))
    L = d["window"]
    pos = d["positions"]
    c1 = np.concatenate([[0.0], np.cumsum(lr)])
    c2 = np.concatenate([[0.0], np.cumsum(lr * lr)])
    s1 = c1[pos + 1] - c1[pos + 1 - L]
    s2 = c2[pos + 1] - c2[pos + 1 - L]
    var = np.maximum(s2 / L - (s1 / L) ** 2, 1e-24)
    tstat = s1 / (np.sqrt(var) * np.sqrt(L))  # = signed_trend_slope; ret_500 = s1
    return d, s1, tstat


def pivot(d, ret, tstat, rows: np.ndarray, y_true: np.ndarray, preds: Dict[str, np.ndarray], thr: float,
          tercile: Optional[tuple] = None) -> Dict[str, Any]:
    te_ret, te_t = ret[rows], tstat[rows]
    if tercile is not None:
        lo, hi = tercile  # kuantil 1/3 & 2/3 signed t dari partisi latih
        conds = {"uptrend": te_t > hi, "downtrend": te_t < lo, "sideways": (te_t >= lo) & (te_t <= hi)}
    else:
        trend = np.abs(te_t) >= thr
        conds = {"uptrend": trend & (te_ret > 0), "downtrend": trend & (te_ret < 0), "sideways": ~trend}
    old = np.array(d["lab_old_same"], dtype=object)[rows]
    out = {}
    for cname, cm_ in conds.items():
        idx = np.where(cm_)[0]
        r: Dict[str, Any] = {"total": int(len(idx)),
                             "label_dist_soft_consensus": {c: int((y_true[idx] == i).sum()) for i, c in enumerate(CLASSES)},
                             "label_dist_old_hard_consensus": {c: int((old[idx] == c).sum()) for c in CLASSES + ["uncertain_rule"]},
                             "models": {}}
        for k, p in preds.items():
            cor = int((p[idx] == y_true[idx]).sum())
            r["models"][k] = {"correct": cor, "pct": round(100 * cor / max(1, len(idx)), 2),
                              "balanced_pct": round(100 * metrics(y_true[idx], p[idx])["balanced_accuracy"], 2) if len(idx) else None,
                              "pred_dist": {c: int((p[idx] == i).sum()) for i, c in enumerate(CLASSES)}}
        out[cname] = r
    return out


def main() -> None:
    REVIEW.mkdir(parents=True, exist_ok=True)
    res: Dict[str, Dict[str, Dict[str, Any]]] = {}
    raws: Dict[str, Dict[str, Any]] = {}
    for tf in ("1h", "4h"):
        for tag in ("normal", "no_er", "no_swt_energy", "no_attention"):
            raw = load_raw(tf, tag)
            if raw is not None:
                raws[f"{tf}_{tag}"] = raw
                res.setdefault(tf, {})[tag] = eval_variant(raw)

    # sweep
    sweep: Dict[str, List[Dict[str, Any]]] = {}
    for tf in ("1h", "4h"):
        for p in sorted(RAW.glob(f"{tf}_cw_sweep_p*.npz")):
            raw = load_raw(tf, p.stem[len(tf) + 1:])
            s_v = summarize(raw["bt__y_val"], raw["bt__hybrid_ps__p_val"])
            s_t = summarize(raw["bt__y_test"], raw["bt__hybrid_ps__p_test"])
            sweep.setdefault(tf, []).append({
                "power": int(p.stem.split("_p")[-1]) / 100,
                "val_ens_acc": s_v["ensemble"]["accuracy"], "val_ens_ba": s_v["ensemble"]["balanced_accuracy"],
                "val_mean_acc": s_v["seed_mean"]["accuracy"]["mean"], "val_mean_ba": s_v["seed_mean"]["balanced_accuracy"]["mean"],
                "test_ens_acc": s_t["ensemble"]["accuracy"], "test_ens_ba": s_t["ensemble"]["balanced_accuracy"]})
    if sweep:
        (REVIEW / "cw_sweep.json").write_text(json.dumps(rnd(sweep), indent=2), encoding="utf-8")

    normal = {tf: res[tf]["normal"] for tf in res if "normal" in res[tf]}
    (REVIEW / "full_metrics.json").write_text(json.dumps(rnd({"source": "review_eval.py --variant normal", "results": normal,
                                                               "cw_sweep_hybrid_ps_backtest": sweep}), indent=2), encoding="utf-8")
    (REVIEW / "full_metrics.md").write_text(full_metrics(normal, sweep), encoding="utf-8")

    # poin 2
    no_er_rows, no_er_json = {}, {}
    for tf in res:
        rows = []
        for m in ("structural_mlp", "hybrid_swt", "hybrid_ps"):
            rows.append((f"{rue.MODEL_LABELS[m]} (normal)", res[tf].get("normal", {}).get(m)))
            rows.append((f"{rue.MODEL_LABELS[m]} TANPA ER", res[tf].get("no_er", {}).get(m)))
        no_er_rows[tf] = rows
        no_er_json[tf] = {"normal": {m: res[tf].get("normal", {}).get(m) for m in ("structural_mlp", "hybrid_swt", "hybrid_ps")},
                          "no_er": res[tf].get("no_er")}
    intro2 = ["Fitur dihapus dari input: F_struct `er_full, er_128, er_64, trend_tstat_full, trend_tstat_128, signed_trend_slope` "
              "(56 → 50 kolom); kanal PS `er_w, er_fast, trend_tstat` (PS 32×14 → 32×11). Label tetap Trend-Aware Soft Consensus. "
              "Seed, split, purge, ambang train-only, class weight, dan augmentasi ETH/BNB 4H (fitur yang sama ikut dihapus) identik dengan run normal.",
              "", "Catatan: label soft consensus sendiri tetap memakai ER multiskala (`er_q`), jadi ablasi ini mengukur seberapa besar "
              "akurasi bergantung pada fitur yang ikut membentuk label, bukan menghapus ER dari definisi label."]
    (REVIEW / "ablation_no_er.json").write_text(json.dumps(rnd(no_er_json), indent=2), encoding="utf-8")
    (REVIEW / "ablation_no_er.md").write_text(ablation_md("Ablasi tanpa fitur Efficiency Ratio (poin 2)", intro2, no_er_rows), encoding="utf-8")

    # poin 7
    swt_rows, swt_json = {}, {}
    for tf in res:
        swt_rows[tf] = [("Hybrid PS (normal, attention, 56 fitur)", res[tf].get("normal", {}).get("hybrid_ps")),
                        ("Hybrid PS tanpa 12 fitur energi SWT (44 fitur)", res[tf].get("no_swt_energy", {}).get("hybrid_ps")),
                        ("Hybrid PS tanpa attention (BiLSTM + GAP)", res[tf].get("no_attention", {}).get("hybrid_ps"))]
        swt_json[tf] = {k: v for k, v in zip(("normal", "no_swt_energy", "no_attention"), [r[1] for r in swt_rows[tf]])}
    intro7 = ["- Tanpa SWT: 12 kolom `swt_energy_w{1.0,0.5,0.25}_d{0..3}` dihapus dari F (56 → 44); PS tetap 32×14.",
              "- Tanpa attention: `AttentionPooling` diganti `GlobalAveragePooling1D`; bagian lain arsitektur, input, dan pelatihan identik.",
              "- Pipeline baru (soft consensus, ER), data BTC, seed 42/43/44."]
    (REVIEW / "ablation_swt_attention.json").write_text(json.dumps(rnd(swt_json), indent=2), encoding="utf-8")
    (REVIEW / "ablation_swt_attention.md").write_text(ablation_md("Ablasi SWT dan attention pada pipeline baru (poin 7)", intro7, swt_rows), encoding="utf-8")

    # poin 3
    mp_json: Dict[str, Any] = {"definition": {
        "trend_tstat": "t = sum(r_{t-499..t}) / (std(r) * sqrt(500)) pada log-return jendela L = 500 (sama dengan signed_trend_slope)",
        "uptrend": "|t| >= 2 dan ret_500 > 0", "downtrend": "|t| >= 2 dan ret_500 < 0", "sideways": "|t| < 2",
        "uses_y_true": False, "uses_er_q": False,
        "sensitivity_thresholds": [1.0, 1.5, 2.5],
        "alternative": "tersil signed t: ambang kuantil 1/3 dan 2/3 dihitung dari jendela partisi latih saja"}, "timeframes": {}}
    md3 = ["# Kondisi pasar independen dari label (poin 3)", "",
           "Definisi hanya dari harga: t-stat tren jendela 500 bar `t = Σr / (σ·√500)`; **tren bila |t| ≥ 2**, arah = tanda `ret_500`; sisanya sideways. "
           "Tidak memakai `y_true` maupun `er_q`.", "",
           "Definisi lama di `run_updated_evaluation.py` (baris 458): `is_trend = (er_q >= 0.58) | (y_true == 0)` — memakai label benar "
           "(semua jendela persistent otomatis masuk 'tren') dan `er_q`, yang juga dipakai membentuk label.", "",
           "Akurasi = ensemble 3 seed pada set uji backtest (sama seperti Tabel 4.9). P/R/A = persistent/random_like/anti_persistent.", ""]
    for tf in ("1h", "4h"):
        if f"{tf}_normal" not in raws:
            continue
        d, ret, tstat = market_conditions(tf)
        rn = raws[f"{tf}_normal"]
        rows = rn["bt__rows_test"]
        y = rn["bt__y_test"]
        preds = {f"{m}_normal": rn[f"bt__{m}__p_test"].mean(0).argmax(1) for m in ("structural_mlp", "hybrid_swt", "hybrid_ps")}
        if f"{tf}_no_er" in raws:
            re_ = raws[f"{tf}_no_er"]
            assert np.array_equal(re_["bt__rows_test"], rows)
            preds.update({f"{m}_no_er": re_[f"bt__{m}__p_test"].mean(0).argmax(1) for m in ("structural_mlp", "hybrid_swt", "hybrid_ps")})
        tfo = {"tstat_test_desc": {"abs_ge_2_pct": round(100 * float((np.abs(tstat[rows]) >= 2).mean()), 2),
                                   "median_abs_t": round(float(np.median(np.abs(tstat[rows]))), 3)},
               "main_thr_2": pivot(d, ret, tstat, rows, y, preds, 2.0),
               "sens_thr_1.0": pivot(d, ret, tstat, rows, y, preds, 1.0),
               "sens_thr_1.5": pivot(d, ret, tstat, rows, y, preds, 1.5),
               "sens_thr_2.5": pivot(d, ret, tstat, rows, y, preds, 2.5),
               "original_table_4_9": ORIG[tf]["historical_backtest"]["market_pivot"]}
        tr_end = d["split"]["train"][1]
        terc = tuple(float(x) for x in np.quantile(tstat[:tr_end], [1 / 3, 2 / 3]))
        tfo["tercile_train_cutoffs_signed_t"] = [round(terc[0], 4), round(terc[1], 4)]
        tfo["alt_tercile_train"] = pivot(d, ret, tstat, rows, y, preds, 0.0, tercile=terc)
        # WF pooled (tambahan)
        folds = n_folds(rn)
        if folds:
            wrows = np.concatenate([rn[f"wf{f}__rows_test"] for f in folds])
            wy = np.concatenate([rn[f"wf{f}__y_test"] for f in folds])
            wp = {f"{m}_normal": np.concatenate([rn[f"wf{f}__{m}__p_test"].mean(0).argmax(1) for f in folds]) for m in ("structural_mlp", "hybrid_swt", "hybrid_ps")}
            if f"{tf}_no_er" in raws and n_folds(raws[f"{tf}_no_er"]):
                re_ = raws[f"{tf}_no_er"]
                wp.update({f"{m}_no_er": np.concatenate([re_[f"wf{f}__{m}__p_test"].mean(0).argmax(1) for f in folds]) for m in ("structural_mlp", "hybrid_swt", "hybrid_ps")})
            tfo["walk_forward_pooled_thr_2"] = pivot(d, ret, tstat, wrows, wy, wp, 2.0)
        mp_json["timeframes"][tf] = tfo
        keys = list(preds)
        for sec, name in (("main_thr_2", "Backtest uji, |t| ≥ 2"), ("walk_forward_pooled_thr_2", "Walk-forward pooled uji, |t| ≥ 2 (tambahan)"),
                          ("sens_thr_1.0", "Sensitivitas |t| ≥ 1,0"), ("sens_thr_1.5", "Sensitivitas |t| ≥ 1,5"),
                          ("sens_thr_2.5", "Sensitivitas |t| ≥ 2,5"),
                          ("alt_tercile_train", "Alternatif: tersil signed t dari partisi latih (uptrend > q2/3, downtrend < q1/3)")):
            if sec not in tfo:
                continue
            pv = tfo[sec]
            md3 += [f"## {tf.upper()}: {name}", "",
                    "| Kondisi | Jendela | Label soft P/R/A | Label lama P/R/A/unc | " + " | ".join(k.replace("_normal", "").replace("_no_er", " noER") for k in keys if k in next(iter(pv.values()))["models"]) + " |",
                    "|---|---|---|---|" + "---|" * len([k for k in keys if k in next(iter(pv.values()))["models"]])]
            for cname, r in pv.items():
                ls = r["label_dist_soft_consensus"]
                lo = r["label_dist_old_hard_consensus"]
                accs = " | ".join(f"{str(r['models'][k]['pct']).replace('.', ',')}" for k in keys if k in r["models"])
                md3.append(f"| {cname} | {r['total']} | {ls['persistent']}/{ls['random_like']}/{ls['anti_persistent']} | "
                           f"{lo['persistent']}/{lo['random_like']}/{lo['anti_persistent']}/{lo['uncertain_rule']} | {accs} |")
            md3.append("")
        o = tfo["original_table_4_9"]
        md3 += [f"Pembanding Tabel 4.9 asli {tf.upper()} (definisi memakai y_true/er_q): " +
                "; ".join(f"{k} {v['total']} jendela, Hybrid PS {v['pct']}%" for k, v in o.items()), "",
                f"Porsi jendela uji dengan |t| ≥ 2: {tfo['tstat_test_desc']['abs_ge_2_pct']}% (median |t| = {tfo['tstat_test_desc']['median_abs_t']}).", ""]
    (REVIEW / "market_pivot_independent.json").write_text(json.dumps(rnd(mp_json), indent=2), encoding="utf-8")
    (REVIEW / "market_pivot_independent.md").write_text("\n".join(md3), encoding="utf-8")
    print("metrics ok", {tf: list(v) for tf, v in res.items()}, "sweep", {k: len(v) for k, v in sweep.items()})


if __name__ == "__main__":
    main()

"""Analisis review tanpa pelatihan: pita acak + surrogat."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_updated_evaluation as rue  # noqa: E402
from app.core.config import ARTIFACTS_DIR, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.hurst_dfa import dfa_alpha, hurst_rs, rolling_hurst_dfa, to_log_return  # noqa: E402
from app.services.regime_labeling import label_series  # noqa: E402
from app.services.splitting import bars_to_rows, split_indices  # noqa: E402

REVIEW = ARTIFACTS_DIR / "review"
LABELS4 = ["persistent", "random_like", "anti_persistent", "uncertain_rule"]
BAND = json.loads((ARTIFACTS_DIR / "random_band.json").read_text(encoding="utf-8"))["bands"]
BAR_HOURS = {"1h": 1, "4h": 4}
SEED = 20261117


def _load(tf: str) -> Dict[str, Any]:
    d = rue.prepare_timeframe_data(tf)
    ohlcv = get_repository().get_ohlcv("BTCUSDT", tf)
    d["bar_time"] = ohlcv["time"].to_numpy()  # open time bar ke-(index+1) karena log_ret[t] = ln(c[t+1]/c[t])
    d["log_ret"] = to_log_return(ohlcv["close"].to_numpy(dtype=float))
    # log_ret[t] memakai close[t+1]; window berakhir di return t -> bar terakhir = t+1
    d["win_time"] = d["bar_time"][d["positions"] + 1]
    return d


def _pct(x: float) -> float:
    return round(100.0 * float(x), 2)


def _desc(a: np.ndarray) -> Dict[str, float]:
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"n": 0}
    return {"n": int(a.size), "mean": round(float(a.mean()), 4), "median": round(float(np.median(a)), 4),
            "p25": round(float(np.percentile(a, 25)), 4), "p75": round(float(np.percentile(a, 75)), 4),
            "std": round(float(a.std()), 4)}


# ---------------------------------------------------------------- poin 5
def _shuffle_stats(seg: np.ndarray, n_shuf: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.empty((n_shuf, 2))
    for k in range(n_shuf):
        s = rng.permutation(seg)
        out[k] = (hurst_rs(s), dfa_alpha(s))
    return out


def part_band(n_windows: int = 400, n_shuf: int = 200, n_global: int = 100, global_pos: int = 200) -> Dict[str, Any]:
    res: Dict[str, Any] = {"band_source": "ml/artifacts/random_band.json (n=500)", "seed": SEED, "timeframes": {}}
    for tf in ("1h", "4h"):
        t0 = time.time()
        d = _load(tf)
        H, A, lab = d["hurst"], d["dfa"], np.array(d["lab_new"], dtype=object)
        tfo: Dict[str, Any] = {"n_windows": int(len(H)), "bands": {}}
        for sc in ("S1", "S4"):
            b = BAND[sc]["500"]
            hl, hu = b["hurst_rs"]["lower"], b["hurst_rs"]["upper"]
            al, au = b["dfa_alpha"]["lower"], b["dfa_alpha"]["upper"]
            h_out, a_out = (H < hl) | (H > hu), (A < al) | (A > au)
            both, either = h_out & a_out, h_out | a_out
            per = {}
            for c in LABELS4:
                m = lab == c
                n = int(m.sum())
                per[c] = {"n": n, "pct_both_outside": _pct(both[m].mean()) if n else None,
                          "pct_H_outside": _pct(h_out[m].mean()) if n else None,
                          "pct_alpha_outside": _pct(a_out[m].mean()) if n else None,
                          "pct_either_outside": _pct(either[m].mean()) if n else None,
                          "pct_H_above_band": _pct((H[m] > hu).mean()) if n else None,
                          "pct_alpha_above_band": _pct((A[m] > au).mean()) if n else None,
                          "pct_H_below_band": _pct((H[m] < hl).mean()) if n else None,
                          "pct_alpha_below_band": _pct((A[m] < al).mean()) if n else None}
            tfo["bands"][sc] = {"hurst_band": [hl, hu], "dfa_band": [al, au],
                                "all": {"pct_both_outside": _pct(both.mean()), "pct_H_outside": _pct(h_out.mean()),
                                        "pct_alpha_outside": _pct(a_out.mean()), "pct_either_outside": _pct(either.mean())},
                                "per_label": per}

        # Surrogat A: per-jendela, acak urutan 500 return (distribusi marginal jendela dipertahankan).
        rng = np.random.default_rng(SEED + (1 if tf == "1h" else 4))
        pick = np.sort(rng.choice(len(H), size=min(n_windows, len(H)), replace=False))
        lr = d["log_ret"]
        L = d["window"]
        segs = [lr[int(p) - L + 1: int(p) + 1] for p in d["positions"][pick]]
        sur = Parallel(n_jobs=4)(delayed(_shuffle_stats)(s, n_shuf, SEED + i) for i, s in enumerate(segs))
        sur = np.stack(sur)  # (n_windows, n_shuf, 2)
        h_s, a_s = sur[:, :, 0], sur[:, :, 1]
        h_o, a_o = H[pick], A[pick]
        # p-value dua sisi empiris per jendela
        p_h = np.minimum(1.0, 2 * np.minimum((h_s >= h_o[:, None]).mean(1), (h_s <= h_o[:, None]).mean(1)) + 1 / (n_shuf + 1))
        p_a = np.minimum(1.0, 2 * np.minimum((a_s >= a_o[:, None]).mean(1), (a_s <= a_o[:, None]).mean(1)) + 1 / (n_shuf + 1))
        lab_s = lab[pick]
        per_lab = {}
        for c in LABELS4:
            m = lab_s == c
            if m.sum() == 0:
                per_lab[c] = {"n": 0}
                continue
            per_lab[c] = {"n": int(m.sum()),
                          "pct_H_reject_5pct": _pct((p_h[m] < 0.05).mean()), "pct_alpha_reject_5pct": _pct((p_a[m] < 0.05).mean()),
                          "pct_both_reject_5pct": _pct(((p_h[m] < 0.05) & (p_a[m] < 0.05)).mean()),
                          "H_orig_mean": round(float(h_o[m].mean()), 4), "H_surr_mean": round(float(h_s[m].mean()), 4),
                          "alpha_orig_mean": round(float(a_o[m].mean()), 4), "alpha_surr_mean": round(float(a_s[m].mean()), 4)}
        ks_h = stats.ks_2samp(h_o, h_s.ravel())
        ks_a = stats.ks_2samp(a_o, a_s.ravel())
        ks_h_full = stats.ks_2samp(H, h_s.ravel())
        ks_a_full = stats.ks_2samp(A, a_s.ravel())
        tfo["surrogate_per_window_shuffle"] = {
            "method": f"{len(pick)} jendela acak (seed), tiap jendela 500 return diacak urutannya {n_shuf} kali; "
                      "H R/S & alpha DFA-1 dihitung dengan estimator yang sama (hurst_rs, dfa_alpha).",
            "n_windows": int(len(pick)), "n_shuffles": n_shuf,
            "H_orig_sample": _desc(h_o), "H_surrogate": _desc(h_s.ravel()),
            "alpha_orig_sample": _desc(a_o), "alpha_surrogate": _desc(a_s.ravel()),
            "surrogate_band_2.5_97.5": {"hurst": [round(float(np.percentile(h_s, 2.5)), 4), round(float(np.percentile(h_s, 97.5)), 4)],
                                        "dfa": [round(float(np.percentile(a_s, 2.5)), 4), round(float(np.percentile(a_s, 97.5)), 4)]},
            "ks_H_sample_vs_surrogate": {"stat": round(float(ks_h.statistic), 4), "p": float(ks_h.pvalue)},
            "ks_alpha_sample_vs_surrogate": {"stat": round(float(ks_a.statistic), 4), "p": float(ks_a.pvalue)},
            "ks_H_allwindows_vs_surrogate": {"stat": round(float(ks_h_full.statistic), 4), "p": float(ks_h_full.pvalue)},
            "ks_alpha_allwindows_vs_surrogate": {"stat": round(float(ks_a_full.statistic), 4), "p": float(ks_a_full.pvalue)},
            "pct_windows_H_reject_5pct": _pct((p_h < 0.05).mean()),
            "pct_windows_alpha_reject_5pct": _pct((p_a < 0.05).mean()),
            "pct_windows_both_reject_5pct": _pct(((p_h < 0.05) & (p_a < 0.05)).mean()),
            "note": "Uji per-jendela tidak dikoreksi multiple testing; di bawah H0 diharapkan ~5% ditolak. Jendela tumpang tindih -> KS p-value terlalu optimistis.",
            "per_label": per_lab,
        }

        # Surrogat B: acak seluruh deret return (menghapus pula volatility clustering), 100 kali.
        def _global(k: int) -> np.ndarray:
            r = np.random.default_rng(SEED + 1000 + k)
            s = r.permutation(lr)
            ps = r.choice(np.arange(L - 1, len(s)), size=global_pos, replace=False)
            return np.array([(hurst_rs(s[p - L + 1: p + 1]), dfa_alpha(s[p - L + 1: p + 1])) for p in ps])

        g = np.concatenate(Parallel(n_jobs=4)(delayed(_global)(k) for k in range(n_global)))
        ks_hg, ks_ag = stats.ks_2samp(H, g[:, 0]), stats.ks_2samp(A, g[:, 1])
        tfo["surrogate_global_shuffle"] = {
            "method": f"seluruh deret log-return diacak {n_global} kali; tiap kali {global_pos} jendela 500 diambil acak",
            "n_values": int(len(g)), "H_orig_all": _desc(H), "H_surrogate": _desc(g[:, 0]),
            "alpha_orig_all": _desc(A), "alpha_surrogate": _desc(g[:, 1]),
            "surrogate_band_2.5_97.5": {"hurst": [round(float(np.percentile(g[:, 0], 2.5)), 4), round(float(np.percentile(g[:, 0], 97.5)), 4)],
                                        "dfa": [round(float(np.percentile(g[:, 1], 2.5)), 4), round(float(np.percentile(g[:, 1], 97.5)), 4)]},
            "ks_H": {"stat": round(float(ks_hg.statistic), 4), "p": float(ks_hg.pvalue)},
            "ks_alpha": {"stat": round(float(ks_ag.statistic), 4), "p": float(ks_ag.pvalue)},
            "pct_orig_both_outside_surrogate_band": _pct((((H < np.percentile(g[:, 0], 2.5)) | (H > np.percentile(g[:, 0], 97.5)))
                                                          & ((A < np.percentile(g[:, 1], 2.5)) | (A > np.percentile(g[:, 1], 97.5)))).mean()),
        }
        tfo["seconds"] = round(time.time() - t0, 1)
        res["timeframes"][tf] = tfo
        print(f"[band] {tf} selesai {tfo['seconds']}s", flush=True)
    return res


# ---------------------------------------------------------------- poin 6
def _runs(labels: np.ndarray):
    out = []
    cur, n = labels[0], 1
    for x in labels[1:]:
        if x == cur:
            n += 1
        else:
            out.append((cur, n))
            cur, n = x, 1
    out.append((cur, n))
    return out


def part_tf() -> Dict[str, Any]:
    res: Dict[str, Any] = {"timeframes": {}}
    frames = {}
    for tf in ("1h", "4h"):
        d = _load(tf)
        lab = np.array(d["lab_new"], dtype=object)
        H, A = d["hurst"], d["dfa"]
        step_h = d["stride"] * BAR_HOURS[tf]
        o: Dict[str, Any] = {"n_windows": int(len(lab)), "stride_bars": d["stride"], "hours_per_window_step": step_h,
                             "thresholds_train_only": d["thresholds"]}
        o["H_all"], o["alpha_all"] = _desc(H), _desc(A)
        o["per_label"] = {c: {"n": int((lab == c).sum()), "share_pct": _pct((lab == c).mean()),
                              "H": _desc(H[lab == c]), "alpha": _desc(A[lab == c])} for c in LABELS4}
        runs = _runs(lab)
        dur = {}
        for c in LABELS4:
            r = np.array([n for x, n in runs if x == c], dtype=float) * step_h
            dur[c] = {"n_runs": int(r.size), "mean_hours": round(float(r.mean()), 1) if r.size else None,
                      "median_hours": round(float(np.median(r)), 1) if r.size else None,
                      "p75_hours": round(float(np.percentile(r, 75)), 1) if r.size else None,
                      "max_hours": round(float(r.max()), 1) if r.size else None}
        o["duration"] = dur
        o["duration_note"] = (f"durasi run = jumlah jendela berurutan berlabel sama x {step_h} jam (stride {d['stride']} bar x {BAR_HOURS[tf]} jam). "
                              "Jendela 500 bar tumpang tindih, jadi durasi adalah lama label bertahan, bukan panjang memori.")
        idx = {c: i for i, c in enumerate(LABELS4)}
        cnt = np.zeros((4, 4), dtype=int)
        for a, b in zip(lab[:-1], lab[1:]):
            cnt[idx[a], idx[b]] += 1
        rs = cnt.sum(1, keepdims=True)
        o["transition"] = {"categories": LABELS4, "counts": cnt.tolist(),
                           "prob": np.round(np.divide(cnt, rs, out=np.zeros((4, 4)), where=rs > 0), 4).tolist()}
        # tanpa uncertain: transisi antar label definitif berikutnya (lompati uncertain)
        dl = lab[lab != "uncertain_rule"]
        c3 = np.zeros((3, 3), dtype=int)
        for a, b in zip(dl[:-1], dl[1:]):
            c3[idx[a], idx[b]] += 1
        r3 = c3.sum(1, keepdims=True)
        o["transition_definitive_only"] = {"categories": LABELS4[:3], "counts": c3.tolist(),
                                           "prob": np.round(c3 / np.maximum(r3, 1), 4).tolist()}
        yrs = pd.to_datetime(d["win_time"], unit="s", utc=True).year
        df_y = pd.DataFrame({"year": yrs, "lab": lab})
        o["per_year"] = {int(y): {"n": int(len(g)), "uncertain_pct": _pct((g["lab"] == "uncertain_rule").mean()),
                                  **{f"{c}_pct": _pct((g["lab"] == c).mean()) for c in LABELS4[:3]}}
                         for y, g in df_y.groupby("year")}
        res["timeframes"][tf] = o
        frames[tf] = pd.DataFrame({"close_time": d["win_time"].astype(np.int64) + BAR_HOURS[tf] * 3600, "lab": lab,
                                   "H": H, "A": A}).sort_values("close_time")

    f1, f4 = frames["1h"], frames["4h"]
    exact = f4.merge(f1, on="close_time", suffixes=("_4h", "_1h"))
    asof = pd.merge_asof(f4, f1, on="close_time", direction="backward", tolerance=4 * 3600, suffixes=("_4h", "_1h")).dropna(subset=["lab_1h"])

    def _agree(m: pd.DataFrame) -> Dict[str, Any]:
        same = m["lab_4h"] == m["lab_1h"]
        both_def = m["lab_4h"].isin(LABELS4[:3]) & m["lab_1h"].isin(LABELS4[:3])
        ct = pd.crosstab(m["lab_4h"], m["lab_1h"]).reindex(index=LABELS4, columns=LABELS4, fill_value=0)
        return {"n_pairs": int(len(m)), "pct_same_label_all4": _pct(same.mean()),
                "n_both_definitive": int(both_def.sum()), "pct_same_label_both_definitive": _pct(same[both_def].mean()),
                "cohen_kappa_all4": round(float(_kappa(m["lab_4h"], m["lab_1h"])), 4),
                "crosstab_rows_4h_cols_1h": ct.to_dict(orient="index"),
                "corr_H_1h_4h": round(float(np.corrcoef(m["H_4h"], m["H_1h"])[0, 1]), 4),
                "corr_alpha_1h_4h": round(float(np.corrcoef(m["A_4h"], m["A_1h"])[0, 1]), 4)}

    res["agreement_1h_vs_4h"] = {
        "method": "pasangan jendela 4H dan 1H dengan waktu tutup bar terakhir identik (exact); asof = jendela 1H terakhir "
                  "yang tutup <= waktu tutup jendela 4H, toleransi 4 jam. Jendela 1H mencakup 500 jam, 4H mencakup 2000 jam.",
        "exact": _agree(exact), "asof": _agree(asof)}
    return res


def _kappa(a: pd.Series, b: pd.Series) -> float:
    cats = sorted(set(a) | set(b))
    po = float((a.values == b.values).mean())
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 0.0


# ---------------------------------------------------------------- poin 8
def part_numbers() -> Dict[str, Any]:
    cfg = get_config()
    repo = get_repository()
    out: Dict[str, Any] = {}
    for tf in ("1h", "4h"):
        o = repo.get_ohlcv("BTCUSDT", tf)
        out[f"bars_{tf}"] = {"rows": int(len(o)),
                             "first": str(pd.to_datetime(o["time"].iloc[0], unit="s", utc=True)),
                             "last": str(pd.to_datetime(o["time"].iloc[-1], unit="s", utc=True))}
    # Rekonstruksi ambang 1H pada snapshot 67.927 bar
    window = cfg.analysis.L
    o1 = repo.get_ohlcv("BTCUSDT", "1h")
    reg = repo.get_regime("BTCUSDT", "1h").copy()
    from app.services.hurst_dfa import compute_rolling_er  # noqa: PLC0415

    lr = to_log_return(o1["close"].to_numpy(dtype=float))
    trials = {}
    for n_bars in (67927, len(o1)):
        n_ret = n_bars - 1
        r = reg[reg["index"] < n_ret].reset_index(drop=True)
        for k, v in compute_rolling_er(lr, r["index"].astype(int).tolist(), window=window).items():
            r[k] = v
        sp = split_indices(len(r), cfg.split.ratios, bars_to_rows(window, 4))
        tm = np.zeros(len(r), dtype=bool)
        tm[: sp["train"][1]] = True
        for src in ("train_only", "full_history"):
            lab = label_series(r, cfg.analysis.hurst_threshold, cfg.analysis.dfa_threshold, mode="quantile",
                               quantiles=(1 / 3, 2 / 3), threshold_source=src, train_mask=tm, soft_consensus=True)
            trials[f"{n_bars}_bars_{src}"] = {
                "n_windows": int(len(r)), "train_windows": int(sp["train"][1]),
                "last_bar": str(pd.to_datetime(o1["time"].iloc[n_bars - 1], unit="s", utc=True)),
                "hurst": [float(lab["hurst_lower"].iloc[0]), float(lab["hurst_upper"].iloc[0])],
                "dfa": [float(lab["dfa_lower"].iloc[0]), float(lab["dfa_upper"].iloc[0])]}
    out["threshold_reconstruction_1h"] = trials
    # Sumber ambang naskah lain (old consensus, regime parquet tersimpan)
    out["regime_parquet_stored_thresholds_1h"] = {
        "hurst": [float(reg["hurst_lower"].iloc[0]), float(reg["hurst_upper"].iloc[0])],
        "dfa": [float(reg["dfa_lower"].iloc[0]), float(reg["dfa_upper"].iloc[0])],
        "threshold_mode": str(reg["threshold_mode"].iloc[0]), "n_windows": int(len(reg))}

    # ETH/BNB augmentasi 4H
    d4 = rue.prepare_timeframe_data("4h")
    sp = d4["split"]
    max_train_bar = int(d4["positions"][sp["train"][1] - 1]) + 1
    o4 = repo.get_ohlcv("BTCUSDT", "4h")
    aug: Dict[str, Any] = {"btc_train_end_row": int(sp["train"][1]), "max_train_bar_index_exclusive": max_train_bar,
                           "btc_time_at_cut": str(pd.to_datetime(o4["time"].iloc[max_train_bar - 1], unit="s", utc=True)),
                           "btc_last_train_window_bar_time": str(pd.to_datetime(o4["time"].iloc[int(d4['positions'][sp['train'][1] - 1]) + 1], unit="s", utc=True)),
                           "cut_method": "indeks: ex_df['close'][:max_train_bar] (run_updated_evaluation.py baris 211), bukan timestamp",
                           "symbols": {}}
    tot = 0
    for sym in ("ETHUSDT", "BNBUSDT"):
        ex = repo.get_ohlcv(sym, "4h")
        close = ex["close"].to_numpy(dtype=float)[:max_train_bar]
        met = rolling_hurst_dfa(to_log_return(close), window=window, step=d4["stride"])
        lab = label_series(met, cfg.analysis.hurst_threshold, cfg.analysis.dfa_threshold, mode="quantile",
                           quantiles=(1 / 3, 2 / 3), threshold_source="full_history", soft_consensus=True)
        vc = lab["regime"].value_counts().to_dict()
        n_def = int(sum(vc.get(c, 0) for c in LABELS4[:3]))
        tot += n_def
        t_cut = ex["time"].iloc[min(max_train_bar, len(ex)) - 1]
        gaps = int((np.diff(ex["time"].to_numpy()[:max_train_bar]) != 4 * 3600).sum())
        aug["symbols"][sym] = {
            "bars_total": int(len(ex)), "first_bar": str(pd.to_datetime(ex["time"].iloc[0], unit="s", utc=True)),
            "bars_used": int(min(max_train_bar, len(ex))), "time_at_cut": str(pd.to_datetime(t_cut, unit="s", utc=True)),
            "cut_time_minus_btc_cut_hours": round((int(t_cut) - int(o4["time"].iloc[max_train_bar - 1])) / 3600, 1),
            "non_4h_gaps_in_used_range": gaps,
            "windows_total": int(len(lab)), "windows_definitive_added": n_def,
            "label_dist": {c: int(vc.get(c, 0)) for c in LABELS4},
            "thresholds_full_history_of_truncated_series": {"hurst": [float(lab["hurst_lower"].iloc[0]), float(lab["hurst_upper"].iloc[0])],
                                                            "dfa": [float(lab["dfa_lower"].iloc[0]), float(lab["dfa_upper"].iloc[0])]}}
    with np.load(rue.PROCESSED_DIR / "cache" / "updated_extra_4h_eth_bnb_train.npz") as z:
        aug["cache_rows"] = int(len(z["y"]))
    aug["recomputed_total"] = tot
    out["eth_bnb_augmentation_4h"] = aug
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="all", choices=["band", "tf", "numbers", "all"])
    a = ap.parse_args()
    REVIEW.mkdir(parents=True, exist_ok=True)
    if a.part in ("numbers", "all"):
        (REVIEW / "number_check.json").write_text(json.dumps(part_numbers(), indent=2), encoding="utf-8")
        print("numbers ok", flush=True)
    if a.part in ("tf", "all"):
        (REVIEW / "timeframe_characteristics.json").write_text(json.dumps(part_tf(), indent=2), encoding="utf-8")
        print("tf ok", flush=True)
    if a.part in ("band", "all"):
        (REVIEW / "random_band_check.json").write_text(json.dumps(part_band(), indent=2), encoding="utf-8")
        print("band ok", flush=True)


if __name__ == "__main__":
    main()

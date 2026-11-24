"""RFraktal dibandingkan indikator klasik ADX(14) dan Choppiness Index (14 dan 500)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_updated_evaluation as rue  # noqa: E402
from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.db.repository import get_repository  # noqa: E402

REVIEW = ARTIFACTS_DIR / "review"
CLASSES = rue.CLASSES
HORIZONS = [12, 24, 48]
LOOKBACK = 24
BLOCK = {"1h": 125, "4h": 250}
SEED = 20261120


def wilder(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full_like(x, np.nan, dtype=float)
    if len(x) < n:
        return out
    out[n - 1] = np.nansum(x[:n])
    for i in range(n, len(x)):
        out[i] = out[i - 1] - out[i - 1] / n + x[i]
    return out


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    """ADX Wilder (1978)."""
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    up = np.concatenate([[0.0], high[1:] - high[:-1]])
    dn = np.concatenate([[0.0], low[:-1] - low[1:]])
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr = wilder(tr, n)
    pdi = 100 * wilder(plus_dm, n) / atr
    mdi = 100 * wilder(minus_dm, n) / atr
    dx = 100 * np.abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-12)
    out = np.full_like(dx, np.nan)
    start = 2 * n - 2
    if len(dx) > start:
        out[start] = np.nanmean(dx[n - 1: start + 1])
        for i in range(start + 1, len(dx)):
            out[i] = (out[i - 1] * (n - 1) + dx[i]) / n
    return out


def choppiness(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray:
    """Choppiness Index (Dreiss): 100 · log10(Σ TR / (maxH − minL)) / log10(n)."""
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    c = np.concatenate([[0.0], np.cumsum(tr)])
    out = np.full(len(close), np.nan)
    from numpy.lib.stride_tricks import sliding_window_view as swv

    hh = swv(high, n).max(1)
    ll = swv(low, n).min(1)
    s = c[n:] - c[:-n]
    out[n - 1:] = 100 * np.log10(s / np.maximum(hh - ll, 1e-12)) / np.log10(n)
    return out


def cramers_v(a: np.ndarray, b: np.ndarray) -> float:
    ua, ub = np.unique(a), np.unique(b)
    t = np.array([[np.sum((a == x) & (b == y)) for y in ub] for x in ua], dtype=float)
    n = t.sum()
    exp = t.sum(1, keepdims=True) * t.sum(0, keepdims=True) / n
    chi2 = np.nansum((t - exp) ** 2 / np.where(exp > 0, exp, np.nan))
    k = min(t.shape) - 1
    return float(np.sqrt(chi2 / (n * k))) if k > 0 else float("nan")


def crosstab(a: np.ndarray, b: np.ndarray, ra, cb) -> Dict[str, Dict[str, int]]:
    return {x: {y: int(np.sum((a == x) & (b == y))) for y in cb} for x in ra}


def momentum_hits(close: np.ndarray, bar: np.ndarray, h: int) -> np.ndarray:
    """1 bila arah return LOOKBACK bar terakhir = arah return h bar berikutnya; NaN bila tak lengkap."""
    lc = np.log(close)
    out = np.full(len(bar), np.nan)
    ok = (bar - LOOKBACK >= 0) & (bar + h < len(close))
    past = lc[bar[ok]] - lc[bar[ok] - LOOKBACK]
    fut = lc[bar[ok] + h] - lc[bar[ok]]
    out[ok] = (np.sign(past) == np.sign(fut)).astype(float)
    return out


def spread_ci(hits: np.ndarray, group: np.ndarray, hi: str, lo: str, block: int, rng, B: int = 3000) -> Dict[str, Any]:
    """Selisih ketepatan momentum kelompok `hi` − `lo`, dengan circular block bootstrap."""
    valid = ~np.isnan(hits)
    h, g = hits[valid], group[valid]
    def stat(hh, gg):
        a, b = hh[gg == hi], hh[gg == lo]
        return (a.mean() - b.mean()) if len(a) and len(b) else np.nan
    obs = stat(h, g)
    n = len(h)
    nb = int(np.ceil(n / block))
    boots = []
    for _ in range(B):
        idx = ((rng.integers(0, n, nb)[:, None] + np.arange(block)[None, :]).ravel() % n)[:n]
        boots.append(stat(h[idx], g[idx]))
    boots = np.array(boots)
    boots = boots[~np.isnan(boots)]
    return {"spread_pp": round(100 * float(obs), 2),
            "ci95_pp": [round(100 * float(np.percentile(boots, 2.5)), 2), round(100 * float(np.percentile(boots, 97.5)), 2)],
            "hit_hi_pct": round(100 * float(h[g == hi].mean()), 2), "n_hi": int((g == hi).sum()),
            "hit_lo_pct": round(100 * float(h[g == lo].mean()), 2), "n_lo": int((g == lo).sum())}


def main() -> None:
    rng = np.random.default_rng(SEED)
    out: Dict[str, Any] = {"lookback_bars": LOOKBACK, "horizons_bars": HORIZONS,
                           "adx_rule": "trending ADX ≥ 25, ranging ADX < 20, netral di antaranya (Wilder 1978)",
                           "chop_rule": "trending CHOP < 38,2, choppy CHOP > 61,8, netral di antaranya (Dreiss)", "timeframes": {}}
    for tf in ("1h", "4h"):
        d = rue.prepare_timeframe_data(tf)
        o = get_repository().get_ohlcv("BTCUSDT", tf)
        hi_, lo_, cl = (o[c].to_numpy(dtype=float) for c in ("high", "low", "close"))
        ADX = adx(hi_, lo_, cl, 14)
        CH14 = choppiness(hi_, lo_, cl, 14)
        CH500 = choppiness(hi_, lo_, cl, 500)
        with np.load(REVIEW / "raw" / f"{tf}_normal.npz") as z:
            rows, y = z["bt__rows_test"], z["bt__y_test"]
            pred = z["bt__hybrid_ps__p_test"].mean(0).argmax(1)
        bar = d["positions"][rows] + 1  # bar terakhir jendela
        truth = np.array(CLASSES)[y]
        model = np.array(CLASSES)[pred]
        adx_cat = np.where(ADX[bar] >= 25, "trending", np.where(ADX[bar] < 20, "ranging", "netral"))
        ch_cat = np.where(CH14[bar] < 38.2, "trending", np.where(CH14[bar] > 61.8, "choppy", "netral"))
        ch5_q = np.nanpercentile(CH500[d["positions"][: d["split"]["train"][1]] + 1], [33.33, 66.67])
        ch5_cat = np.where(CH500[bar] < ch5_q[0], "trending", np.where(CH500[bar] > ch5_q[1], "choppy", "netral"))

        t: Dict[str, Any] = {"n_test_windows": int(len(rows))}
        t["association"] = {
            "cramers_v": {
                "label_acuan_vs_ADX14": round(cramers_v(truth, adx_cat), 3),
                "label_acuan_vs_CHOP14": round(cramers_v(truth, ch_cat), 3),
                "label_acuan_vs_CHOP500": round(cramers_v(truth, ch5_cat), 3),
                "prediksi_model_vs_ADX14": round(cramers_v(model, adx_cat), 3),
                "prediksi_model_vs_CHOP14": round(cramers_v(model, ch_cat), 3),
                "prediksi_model_vs_CHOP500": round(cramers_v(model, ch5_cat), 3),
            },
            "crosstab_model_vs_ADX14": crosstab(model, adx_cat, CLASSES, ["trending", "netral", "ranging"]),
            "crosstab_model_vs_CHOP14": crosstab(model, ch_cat, CLASSES, ["trending", "netral", "choppy"]),
            "crosstab_model_vs_CHOP500": crosstab(model, ch5_cat, CLASSES, ["trending", "netral", "choppy"]),
            "chop500_train_tercile_cutoffs": [round(float(x), 2) for x in ch5_q],
        }
        t["momentum"] = {}
        for h in HORIZONS:
            hits = momentum_hits(cl, bar, h)
            valid = ~np.isnan(hits)
            t["momentum"][str(h)] = {
                "base_hit_pct": round(100 * float(np.nanmean(hits)), 2),
                "n": int(valid.sum()),
                "RFraktal_model (persistent − anti)": spread_ci(hits, model, "persistent", "anti_persistent", BLOCK[tf], rng),
                "RFraktal_acuan (persistent − anti)": spread_ci(hits, truth, "persistent", "anti_persistent", BLOCK[tf], rng),
                "ADX14 (trending − ranging)": spread_ci(hits, adx_cat, "trending", "ranging", BLOCK[tf], rng),
                "CHOP14 (trending − choppy)": spread_ci(hits, ch_cat, "trending", "choppy", BLOCK[tf], rng),
                "CHOP500 (trending − choppy)": spread_ci(hits, ch5_cat, "trending", "choppy", BLOCK[tf], rng),
                "per_class_hit_pct": {
                    "model": {c: round(100 * float(np.nanmean(hits[model == c])), 2) for c in CLASSES if (model == c).any()},
                    "ADX14": {c: round(100 * float(np.nanmean(hits[adx_cat == c])), 2) for c in ("trending", "netral", "ranging") if (adx_cat == c).any()},
                },
            }
        out["timeframes"][tf] = t
        m24 = t["momentum"]["24"]
        print(tf, "V(model,ADX)", t["association"]["cramers_v"]["prediksi_model_vs_ADX14"],
              "| spread24 model", m24["RFraktal_model (persistent − anti)"]["spread_pp"], m24["RFraktal_model (persistent − anti)"]["ci95_pp"],
              "ADX", m24["ADX14 (trending − ranging)"]["spread_pp"], m24["ADX14 (trending − ranging)"]["ci95_pp"],
              "CHOP14", m24["CHOP14 (trending − choppy)"]["spread_pp"], "CHOP500", m24["CHOP500 (trending − choppy)"]["spread_pp"], flush=True)
    (REVIEW / "vs_indicators.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    write_md(out)


def write_md(o: Dict[str, Any]) -> None:
    c = lambda v: str(v).replace(".", ",")  # noqa: E731
    md = ["# RFraktal dibandingkan ADX dan Choppiness Index", "",
          "Jendela uji backtest yang sama dengan Bab 4 (1H 2.005, 4H 761 jendela); nilai indikator diambil pada bar terakhir jendela.",
          f"- ADX(14): {o['adx_rule']}.", f"- Choppiness(14): {o['chop_rule']}.",
          "- Choppiness(500): panjang sama dengan jendela RFraktal; batas tersil dari data latih.", "",
          f"Uji kegunaan: aturan momentum (arah return {o['lookback_bars']} bar terakhir = tebakan arah h bar berikutnya). "
          "Spread = ketepatan pada kelompok tren − ketepatan pada kelompok berbalik/sideways, dalam poin persen. "
          "Selang kepercayaan 95% dari circular block bootstrap (blok 500 bar), 3.000×. Tanpa biaya; bukan uji profit.", ""]
    for tf, t in o["timeframes"].items():
        cv = t["association"]["cramers_v"]
        md += [f"## {tf.upper()} ({t['n_test_windows']} jendela uji)", "", "### Keterkaitan label (Cramér's V; 0 = tidak terkait, 1 = identik)", "",
               "| Pasangan | V |", "|---|---|"] + [f"| {k} | {c(v)} |" for k, v in cv.items()]
        ct = t["association"]["crosstab_model_vs_ADX14"]
        md += ["", "Prediksi model × ADX(14):", "", "| Model \\ ADX | trending | netral | ranging |", "|---|---|---|---|"]
        md += [f"| {k} | {v['trending']} | {v['netral']} | {v['ranging']} |" for k, v in ct.items()]
        md += ["", "### Kegunaan: spread ketepatan momentum", "",
               "| h (bar) | Dasar | RFraktal model | RFraktal acuan | ADX(14) | CHOP(14) | CHOP(500) |", "|---|---|---|---|---|---|---|"]
        for h, m in t["momentum"].items():
            f = lambda k: f"{c(m[k]['spread_pp'])} [{c(m[k]['ci95_pp'][0])}; {c(m[k]['ci95_pp'][1])}]"  # noqa: E731
            md.append(f"| {h} | {c(m['base_hit_pct'])}% | {f('RFraktal_model (persistent − anti)')} | {f('RFraktal_acuan (persistent − anti)')} | "
                      f"{f('ADX14 (trending − ranging)')} | {f('CHOP14 (trending − choppy)')} | {f('CHOP500 (trending − choppy)')} |")
        m = t["momentum"]["24"]
        md += ["", "Ketepatan momentum per kelompok (h = 24):", "",
               "- Model: " + ", ".join(f"{k} {c(v)}%" for k, v in m["per_class_hit_pct"]["model"].items()),
               "- ADX(14): " + ", ".join(f"{k} {c(v)}%" for k, v in m["per_class_hit_pct"]["ADX14"].items()), ""]
    (REVIEW / "vs_indicators.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()

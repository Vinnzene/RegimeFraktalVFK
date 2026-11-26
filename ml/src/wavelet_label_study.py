"""Tahap 2 (tanpa melatih ulang): penduga wavelet sebagai penduga label ketiga.

Penduga Abry-Veitch (DWT) dan varian SWT (energi per level, sama dengan dekomposisi aplikasi) dibandingkan
dengan R/S dan DFA:
1. Data sintetis dengan H diketahui: korelasi dengan H sebenarnya, ketepatan kelas, dan konsensus 2/3 dan 3/3.
2. BTC: kesesuaian label wavelet dengan label penelitian, dan akurasi model saat ketiga penduga sepakat.
Model dan label utama tidak diubah; tidak ada cache yang ditulis.

Pemakaian: python ml/src/wavelet_label_study.py
Keluaran: ml/artifacts/wavelet_label_study.json dan wavelet_label_study.md
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pywt
from scipy import special, stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fit_diagnostics as fd  # noqa: E402
import label_validity as lv  # noqa: E402
from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.hurst_dfa import compute_rolling_er, to_log_return  # noqa: E402
from app.services.regime_labeling import calibrate_thresholds, compute_er_quantile_score, label_from_exponents  # noqa: E402
from app.services.swt import swt_decompose  # noqa: E402

OUT_JSON = ARTIFACTS_DIR / "wavelet_label_study.json"
OUT_MD = ARTIFACTS_DIR / "wavelet_label_study.md"
CLASSES = fd.CLASSES  # persistent, random_like, anti_persistent
WAVELET = "db4"
J1, J2 = 1, 5  # oktaf yang dipakai pada regresi log-skala (n = 500)
SWT_LEVELS = 4  # sama dengan fitur energi SWT aplikasi


# ------------------------------------------------------------------ penduga
def wavelet_h_dwt(x: np.ndarray, j1: int = J1, j2: int = J2) -> float:
    """Abry-Veitch: regresi berbobot log2 energi detail DWT per oktaf; untuk fGn H = (kemiringan + 1) / 2."""
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    level = min(j2, pywt.dwt_max_level(len(x), pywt.Wavelet(WAVELET).dec_len))
    coeffs = pywt.wavedec(x, WAVELET, mode="periodization", level=level)
    details = coeffs[:0:-1]  # oktaf 1 (halus) .. level (kasar)
    js, ys, ws = [], [], []
    for j, d in enumerate(details, start=1):
        if j < j1 or len(d) < 2:
            continue
        nj = len(d)
        mu = float(np.mean(d**2))
        if mu <= 0:
            continue
        g = special.digamma(nj / 2) / np.log(2) - np.log2(nj / 2)  # koreksi bias log
        var = special.polygamma(1, nj / 2) / np.log(2) ** 2
        js.append(j)
        ys.append(np.log2(mu) - g)
        ws.append(1 / var)
    if len(js) < 3:
        return float("nan")
    slope = np.polyfit(js, ys, 1, w=np.sqrt(ws))[0]
    return float((slope + 1) / 2)


def wavelet_h_swt(x: np.ndarray, level: int = SWT_LEVELS) -> float:
    """Varian SWT: kemiringan log2 energi detail SWT per level (dekomposisi yang sama dengan aplikasi)."""
    x = np.asarray(x, dtype=float)
    dec = swt_decompose(x - x.mean(), level=level, wavelet=WAVELET)
    js = sorted(int(k.split("_")[1]) for k in dec if k.startswith("detail_"))
    ys = [np.log2(np.mean(dec[f"detail_{j}"] ** 2)) for j in js]
    if len(js) < 3:
        return float("nan")
    slope = np.polyfit(js, ys, 1)[0]
    return float((slope + 1) / 2)


def classify(v: np.ndarray, thr: List[float]) -> np.ndarray:
    """Indeks CLASSES: > atas persistent (0), < bawah anti (2), di antaranya random (1); NaN = -1."""
    out = np.where(v > thr[1], 0, np.where(v < thr[0], 2, 1))
    return np.where(np.isfinite(v), out, -1)


def score(y: np.ndarray, p: np.ndarray) -> Dict[str, Any]:
    m = p >= 0
    yl, pl = y[m], p[m]
    if not m.any():
        return {"labeled_pct": 0.0}
    rec = {CLASSES[c]: round(float((pl[yl == c] == c).mean()), 4) for c in range(3) if (yl == c).any()}
    return {
        "labeled_pct": round(100 * float(m.mean()), 1),
        "accuracy": round(float((pl == yl).mean()), 4),
        "balanced_accuracy": round(float(np.mean(list(rec.values()))), 4),
        "recall": rec,
        "qwk": round(lv.qwk(yl, pl), 4),
    }


def vote(*cls: np.ndarray, need: int) -> np.ndarray:
    """Label bila sedikitnya `need` penduga memberi kelas yang sama; selain itu -1 (tidak pasti)."""
    stack = np.stack(cls)
    out = np.full(stack.shape[1], -1)
    for c in range(3):
        out = np.where(((stack == c).sum(0) >= need) & (out < 0), c, out)
    return out


# ------------------------------------------------------------------ 1: sintetis
def synthetic(scenario: str) -> Dict[str, Any]:
    import synthetic_benchmark as sb  # noqa: PLC0415
    from synthetic_regimes import CLASSES as SYN_CLASSES  # noqa: PLC0415
    from synthetic_regimes import PRIMARY, make_series, sample_h  # noqa: PLC0415

    n, split = 500, "test"
    cache = sb.load(scenario, n, split)
    s_idx = sb.TEST_SCENARIOS.index(scenario)
    dwt, swt, er_rows = [], [], []
    for i in range(len(cache["h"])):
        rng = np.random.default_rng(np.random.SeedSequence([sb.SEED_BASE[split], s_idx, n, i]))
        h = sample_h(SYN_CLASSES[i % 3], rng, PRIMARY)
        r, _ = make_series(scenario, n, h, rng)
        if h != cache["h"][i]:
            raise SystemExit(f"[{scenario}] deret {i} tidak sama dengan cache benchmark")
        dwt.append(wavelet_h_dwt(r))
        swt.append(wavelet_h_swt(r))
        er_rows.append({k: float(v[0]) for k, v in compute_rolling_er(r, [n - 1], window=n).items()})
    h_true = cache["h"]
    est = {
        "R/S": cache["est"][:, 0],
        "DFA": cache["est"][:, 1],
        "Wavelet DWT (Abry-Veitch)": np.array(dwt),
        "Wavelet SWT (energi per level)": np.array(swt),
    }
    y = np.array([0 if h > PRIMARY[1] else 2 if h < PRIMARY[0] else 1 for h in h_true])
    half = len(y) // 2
    ev = slice(half, None)
    cls, single = {}, {}
    for name, v in est.items():
        thr = calibrate_thresholds(v[:half])
        cls[name] = classify(v, thr)[ev]
        ok = np.isfinite(v)
        rho = stats.spearmanr(v[ok], h_true[ok]).statistic
        single[name] = {"spearman_true_h": round(float(rho), 4), "thresholds": thr, **score(y[ev], cls[name])}

    # Aturan BTC saat ini (soft consensus + ER) sebagai pembanding.
    df = pd.DataFrame({"hurst": est["R/S"], "dfa_alpha": est["DFA"]}).join(pd.DataFrame(er_rows))
    er_q = compute_er_quantile_score(df.iloc[half:].reset_index(drop=True), df.iloc[:half])
    h_thr, a_thr = single["R/S"]["thresholds"], single["DFA"]["thresholds"]
    soft = np.array([
        CLASSES.index(lab) if (lab := label_from_exponents(h, a, h_thr, a_thr, efficiency_ratio=float(e))) in CLASSES else -1
        for h, a, e in zip(est["R/S"][ev], est["DFA"][ev], er_q)
    ])
    rs, dfa, wd = cls["R/S"], cls["DFA"], cls["Wavelet DWT (Abry-Veitch)"]
    combos = {
        "R/S + DFA sepakat (konsensus keras)": score(y[ev], vote(rs, dfa, need=2)),
        "Soft consensus + ER (aturan penelitian)": score(y[ev], soft),
        "R/S + DFA + wavelet, ≥ 2 dari 3 sepakat": score(y[ev], vote(rs, dfa, wd, need=2)),
        "R/S + DFA + wavelet, 3 dari 3 sepakat": score(y[ev], vote(rs, dfa, wd, need=3)),
    }
    return {"scenario": scenario, "n_eval": int(len(y) - half), "estimators": single, "combos": combos}


# ------------------------------------------------------------------ 2: BTC
def btc(tf: str) -> Dict[str, Any]:
    d = fd.rebuild(tf)
    stride, window = fd.STRIDE[tf], 500
    log_ret = to_log_return(get_repository().get_ohlcv("BTCUSDT", tf)["close"].to_numpy(dtype=float))
    import numpy as _np  # noqa: PLC0415

    with _np.load(fd.PROCESSED_DIR / "cache" / f"updated_feat_{tf}_s{stride}_f56_ps14.npz") as z:
        positions = z["positions"].astype(int)
    wav = np.array([wavelet_h_dwt(log_ret[t - window + 1: t + 1]) for t in positions])
    tr_end = d["split"]["train"][1]
    thr = {
        "wavelet": calibrate_thresholds(wav[:tr_end]),
        "hurst": d["thresholds"]["hurst"],
        "dfa": d["thresholds"]["dfa"],
    }
    c_w = classify(wav, thr["wavelet"])
    c_h = classify(d["hurst"], thr["hurst"])
    c_a = classify(d["dfa"], thr["dfa"])

    raw = np.load(ARTIFACTS_DIR / "review" / "raw" / f"{tf}_normal.npz")
    rows = d["rows"]["test"]
    if not np.array_equal(rows, raw["bt__rows_test"]):
        raise SystemExit(f"[{tf}] baris uji berbeda dari evaluasi")
    y = d["y"][rows]
    p = raw["bt__hybrid_ps__p_test"].mean(0).argmax(1)
    w = c_w[rows]
    agree_w = w == y
    all3 = (c_h[rows] == c_a[rows]) & (c_a[rows] == w)
    M = np.zeros((3, 3), dtype=int)
    np.add.at(M, (y, np.clip(w, 0, 2)), 1)

    def acc(mask: np.ndarray) -> Dict[str, Any]:
        return {"n": int(mask.sum()), "accuracy": round(float((p[mask] == y[mask]).mean()), 4) if mask.any() else None}

    ok = np.isfinite(wav)
    return {
        "thresholds": thr,
        "spearman": {
            "wavelet_vs_rs": round(float(stats.spearmanr(wav[ok], d["hurst"][ok]).statistic), 4),
            "wavelet_vs_dfa": round(float(stats.spearmanr(wav[ok], d["dfa"][ok]).statistic), 4),
            "rs_vs_dfa": round(float(stats.spearmanr(d["hurst"], d["dfa"]).statistic), 4),
        },
        "test": {
            "n": int(len(y)),
            "wavelet_agrees_with_label_pct": round(100 * float(agree_w.mean()), 1),
            "label_vs_wavelet_matrix": M.tolist(),
            "model_accuracy": round(float((p == y).mean()), 4),
            "model_when_wavelet_agrees": acc(agree_w),
            "model_when_wavelet_disagrees": acc(~agree_w),
            "model_when_all_three_agree": acc(all3),
            "model_otherwise": acc(~all3),
            "all_three_agree_pct": round(100 * float(all3.mean()), 1),
        },
    }


# ------------------------------------------------------------------ 3: sensitivitas rentang oktaf
SCALE_GRID = [(1, 5), (2, 5), (2, 6), (3, 6)]


def scale_sensitivity() -> List[Dict[str, Any]]:
    """Spearman wavelet terhadap H sebenarnya (sintetis) dan terhadap R/S, DFA (BTC) untuk tiap rentang oktaf."""
    import synthetic_benchmark as sb  # noqa: PLC0415
    from synthetic_regimes import CLASSES as SYN_CLASSES  # noqa: PLC0415
    from synthetic_regimes import PRIMARY, make_series, sample_h  # noqa: PLC0415

    series: Dict[str, List[np.ndarray]] = {}
    for sc in ("S1", "S4k"):
        s_idx = sb.TEST_SCENARIOS.index(sc)
        series[sc] = []
        for i in range(3000):
            rng = np.random.default_rng(np.random.SeedSequence([sb.SEED_BASE["test"], s_idx, 500, i]))
            h = sample_h(SYN_CLASSES[i % 3], rng, PRIMARY)
            series[sc].append(make_series(sc, 500, h, rng)[0])
    btc_win: Dict[str, Any] = {}
    for tf in ("1h", "4h"):
        d = fd.rebuild(tf)
        lr = to_log_return(get_repository().get_ohlcv("BTCUSDT", tf)["close"].to_numpy(dtype=float))
        with np.load(fd.PROCESSED_DIR / "cache" / f"updated_feat_{tf}_s{fd.STRIDE[tf]}_f56_ps14.npz") as z:
            pos = z["positions"].astype(int)
        btc_win[tf] = ([lr[t - 499: t + 1] for t in pos], d["hurst"], d["dfa"])
    rows = []
    for j1, j2 in SCALE_GRID:
        row: Dict[str, Any] = {"octaves": [j1, j2], "approx_bars": [2**j1, 2 ** (j2 + 1)]}
        for sc, ser in series.items():
            v = np.array([wavelet_h_dwt(r, j1, j2) for r in ser])
            row[f"{sc}_vs_true_h"] = round(float(stats.spearmanr(v, sb.load(sc, 500, "test")["h"], nan_policy="omit").statistic), 4)
        for tf, (wins, h, a) in btc_win.items():
            v = np.array([wavelet_h_dwt(w, j1, j2) for w in wins])
            row[f"btc_{tf}_vs_rs"] = round(float(stats.spearmanr(v, h, nan_policy="omit").statistic), 4)
            row[f"btc_{tf}_vs_dfa"] = round(float(stats.spearmanr(v, a, nan_policy="omit").statistic), 4)
        rows.append(row)
    return rows


def rs_dfa_agreement() -> Dict[str, float]:
    """Korelasi R/S dengan DFA: sintetis vs BTC (seberapa sepakat dua penduga lama)."""
    import synthetic_benchmark as sb  # noqa: PLC0415

    out = {}
    for sc in ("S1", "S4", "S4k"):
        est = sb.load(sc, 500, "test")["est"]
        out[f"sintetis_{sc}"] = round(float(stats.spearmanr(est[:, 0], est[:, 1]).statistic), 4)
    for tf in ("1h", "4h"):
        d = fd.rebuild(tf)
        out[f"btc_{tf}"] = round(float(stats.spearmanr(d["hurst"], d["dfa"]).statistic), 4)
    return out


# ------------------------------------------------------------------ laporan
def pct(v: float | None, d: int = 1) -> str:
    return "–" if v is None else f"{100 * v:.{d}f}".replace(".", ",") + "%"


def to_md(out: Dict[str, Any]) -> str:
    L = ["# Tahap 2: penduga wavelet sebagai penduga label ketiga (tanpa melatih ulang)", "",
         f"Skrip: `{out['source']}` · {out['generated_at']}. Wavelet {WAVELET}; DWT oktaf {J1}–{J2}, SWT {SWT_LEVELS} level.", "",
         "## Data sintetis (n = 500, separuh pertama kalibrasi ambang, separuh kedua evaluasi)", ""]
    for s in out["synthetic"]:
        L += [f"### {s['scenario']}", "", "| Penduga | Spearman vs H sebenarnya | Kelas benar | Recall random-like | QWK |", "|---|---|---|---|---|"]
        for name, e in s["estimators"].items():
            L.append(f"| {name} | {e['spearman_true_h']:.3f} | {pct(e['accuracy'])} | {pct(e['recall'].get('random_like'))} | {e['qwk']:.3f} |")
        L += ["", "| Aturan label | Berlabel | Benar (dari yang berlabel) | Recall random-like |", "|---|---|---|---|"]
        for name, c in s["combos"].items():
            L.append(f"| {name} | {c['labeled_pct']}% | {pct(c.get('accuracy'))} | {pct(c.get('recall', {}).get('random_like'))} |")
        L.append("")
    L += ["## BTC/USDT (label penelitian tidak diubah)", ""]
    for tf, b in out["btc"].items():
        t = b["test"]
        L += [f"### {tf.upper()}", "",
              f"Spearman wavelet vs R/S {b['spearman']['wavelet_vs_rs']:.3f}, wavelet vs DFA {b['spearman']['wavelet_vs_dfa']:.3f}, "
              f"R/S vs DFA {b['spearman']['rs_vs_dfa']:.3f}.", "",
              f"Uji (n = {t['n']}): label wavelet sama dengan label penelitian pada {t['wavelet_agrees_with_label_pct']}% jendela; "
              f"ketiga penduga sepakat pada {t['all_three_agree_pct']}% jendela.", "",
              "| Kondisi | Jendela | Akurasi model |", "|---|---|---|",
              f"| Semua jendela uji | {t['n']} | {pct(t['model_accuracy'])} |",
              f"| Wavelet setuju dengan label | {t['model_when_wavelet_agrees']['n']} | {pct(t['model_when_wavelet_agrees']['accuracy'])} |",
              f"| Wavelet tidak setuju | {t['model_when_wavelet_disagrees']['n']} | {pct(t['model_when_wavelet_disagrees']['accuracy'])} |",
              f"| R/S, DFA, dan wavelet sepakat | {t['model_when_all_three_agree']['n']} | {pct(t['model_when_all_three_agree']['accuracy'])} |",
              f"| Selain itu | {t['model_otherwise']['n']} | {pct(t['model_otherwise']['accuracy'])} |", ""]
    L += ["## Kesepakatan R/S dengan DFA (Spearman)", "",
          " · ".join(f"{k.replace('_', ' ')} {v:.3f}" for k, v in out["rs_dfa_agreement"].items()), "",
          "## Sensitivitas rentang oktaf wavelet (Spearman)", "",
          "| Oktaf (≈ bar) | S1 vs H | S4k vs H | BTC 1H vs R/S | BTC 1H vs DFA | BTC 4H vs R/S | BTC 4H vs DFA |",
          "|---|---|---|---|---|---|---|"]
    for r in out["scale_sensitivity"]:
        L.append(f"| {r['octaves'][0]}–{r['octaves'][1]} (≈ {r['approx_bars'][0]}–{r['approx_bars'][1]}) | {r['S1_vs_true_h']:.3f} | "
                 f"{r['S4k_vs_true_h']:.3f} | {r['btc_1h_vs_rs']:.3f} | {r['btc_1h_vs_dfa']:.3f} | {r['btc_4h_vs_rs']:.3f} | {r['btc_4h_vs_dfa']:.3f} |")
    L += ["", f"Konfigurasi utama oktaf {J1}–{J2} ditetapkan sebelum hasil dilihat; tabel ini hanya untuk transparansi.", ""]
    L += ["Catatan: model memakai 12 energi SWT sebagai fitur. Jika kelak model dilatih dengan label wavelet, "
          "ablasi tanpa fitur SWT wajib untuk menghindari sirkularitas.", ""]
    return "\n".join(L)


def main() -> None:
    t0 = time.time()
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ml/src/wavelet_label_study.py",
        "wavelet": WAVELET,
        "dwt_octaves": [J1, J2],
        "swt_levels": SWT_LEVELS,
        "synthetic": [synthetic(s) for s in ("S1", "S4", "S4k")],
        "btc": {tf: btc(tf) for tf in ("1h", "4h")},
        "rs_dfa_agreement": rs_dfa_agreement(),
        "scale_sensitivity": scale_sensitivity(),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_MD.write_text(to_md(out), encoding="utf-8")
    print(OUT_MD.read_text(encoding="utf-8"))
    print(f"selesai {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

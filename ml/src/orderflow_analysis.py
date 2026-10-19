"""Analisis hubungan regime Hurst-DFA dengan distribusi OFI dan CVD.

Jalankan:
    python ml/src/orderflow_analysis.py --timeframe 1h
    python ml/src/orderflow_analysis.py --timeframe 1h --plot   # + gambar timeline

Tidak ada pola yang diasumsikan. Untuk tiap regime dihitung statistik deskriptif
OFI/CVD pada window-nya, lalu diuji apakah distribusinya berbeda antar regime
(Kruskal-Wallis + effect size epsilon²). Karena window bertetangga tumpang
tindih dan OFI berautokorelasi, p-value uji klasik terlalu optimistis; maka
juga dilaporkan uji permutasi BLOK (label regime digeser melingkar) yang
mempertahankan struktur autokorelasi.

Statistik per window (dihitung dari bar di dalam window [t−L+1, t] saja):
- ofi_mean          : rata-rata OFI — arah tekanan bersih
- ofi_abs_mean      : rata-rata |OFI| — intensitas ketidakseimbangan
- ofi_sign_persist  : porsi bar dengan tanda OFI sama dengan bar sebelumnya
- ofi_ac1           : autokorelasi lag-1 OFI
- ofi_ret_agree     : porsi bar dengan tanda OFI = tanda return (searah harga)
- cvd_norm_end      : CVD z-score pada akhir window
- cvd_slope         : delta CVD window / volume window, dalam [−1, 1]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import ARTIFACTS_DIR, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.hurst_dfa import to_log_return  # noqa: E402
from app.services.order_flow import build_order_flow_bars, coverage  # noqa: E402

MAIN_REGIMES = ["persistent", "random_like", "anti_persistent"]
STATS = [
    "ofi_mean",
    "ofi_abs_mean",
    "ofi_sign_persist",
    "ofi_ac1",
    "ofi_ret_agree",
    "cvd_norm_end",
    "cvd_slope",
]


def window_stats(bars: pd.DataFrame, log_ret: np.ndarray, positions: np.ndarray, L: int) -> pd.DataFrame:
    ofi = bars["ofi"].to_numpy()[1:]  # ruang indeks log-return
    cvd_norm = bars["cvd_norm"].to_numpy()[1:]
    delta = bars["delta_volume"].to_numpy()[1:]
    vol = (bars["buy_volume"] + bars["sell_volume"]).to_numpy()[1:]
    c_delta = np.concatenate([[0.0], np.cumsum(delta)])
    c_vol = np.concatenate([[0.0], np.cumsum(vol)])

    rows = []
    for t in positions:
        lo = max(0, t - L + 1)
        seg = ofi[lo : t + 1]
        ret = log_ret[lo : t + 1]
        s = np.sign(seg)
        ac1 = np.corrcoef(seg[:-1], seg[1:])[0, 1] if seg.size > 3 and seg.std() > 0 else 0.0
        nz = (s != 0) & (np.sign(ret) != 0)
        rows.append(
            {
                "ofi_mean": float(seg.mean()),
                "ofi_abs_mean": float(np.abs(seg).mean()),
                "ofi_sign_persist": float((s[1:] == s[:-1]).mean()) if seg.size > 1 else 0.0,
                "ofi_ac1": float(ac1) if np.isfinite(ac1) else 0.0,
                "ofi_ret_agree": float((s[nz] == np.sign(ret[nz])).mean()) if nz.any() else 0.5,
                "cvd_norm_end": float(cvd_norm[t]),
                "cvd_slope": float((c_delta[t + 1] - c_delta[lo]) / (c_vol[t + 1] - c_vol[lo] + 1e-12)),
            }
        )
    return pd.DataFrame(rows)


def epsilon_squared(h: float, n: int) -> float:
    return float(h / ((n**2 - 1) / (n + 1))) if n > 1 else 0.0


def block_permutation_p(values: np.ndarray, labels: np.ndarray, reps: int = 500, seed: int = 42) -> float:
    """p-value Kruskal-Wallis lewat pergeseran melingkar label (menjaga autokorelasi)."""
    from scipy.stats import kruskal  # type: ignore

    def H(lab):
        groups = [values[lab == r] for r in MAIN_REGIMES if (lab == r).sum() > 5]
        return kruskal(*groups).statistic if len(groups) >= 2 else 0.0

    obs = H(labels)
    rng = np.random.default_rng(seed)
    n = len(labels)
    shifts = rng.integers(n // 10, n - n // 10, reps)
    null = np.array([H(np.roll(labels, int(k))) for k in shifts])
    return float((1 + (null >= obs).sum()) / (reps + 1))


def analyse(timeframe: str, plot: bool) -> Dict:
    from scipy.stats import kruskal, mannwhitneyu  # type: ignore

    cfg = get_config()
    repo = get_repository()
    ohlcv = repo.get_ohlcv("BTCUSDT", timeframe)
    if coverage(ohlcv) < 0.99:
        raise SystemExit(f"Jalankan dulu: python ml/src/prepare_order_flow.py --timeframe {timeframe}")
    regime = repo.get_regime("BTCUSDT", timeframe)
    L = int(regime["effective_window"].iloc[0])
    log_ret = to_log_return(ohlcv["close"].to_numpy())
    bars = build_order_flow_bars(ohlcv, cvd_window=L)
    positions = regime["index"].to_numpy(dtype=int)

    st = window_stats(bars, log_ret, positions, L)
    st["regime"] = regime["regime"].to_numpy()
    st["time"] = regime["time"].to_numpy()

    report: Dict = {"timeframe": timeframe, "window": L, "n_windows": len(st), "per_regime": {}, "tests": {}}
    for r in MAIN_REGIMES + ["uncertain_rule"]:
        sub = st[st["regime"] == r]
        if sub.empty:
            continue
        report["per_regime"][r] = {
            "n": len(sub),
            **{
                k: {
                    "mean": round(float(np.mean(sub[k])), 4),
                    "median": round(float(np.median(sub[k])), 4),
                    "std": round(float(np.std(sub[k])), 4),
                    "q25": round(float(np.quantile(sub[k], 0.25)), 4),
                    "q75": round(float(np.quantile(sub[k], 0.75)), 4),
                    "share_positive": round(float(np.mean(np.asarray(sub[k]) > 0)), 4),
                }
                for k in STATS
            },
        }

    main = st[st["regime"].isin(MAIN_REGIMES)].reset_index(drop=True)
    lab = np.asarray(main["regime"])
    for k in STATS:
        vals = np.asarray(main[k], dtype=float)
        groups = [vals[lab == r] for r in MAIN_REGIMES]
        h, p = kruskal(*groups)
        pair = {}
        for a, b in (("persistent", "random_like"), ("persistent", "anti_persistent"), ("random_like", "anti_persistent")):
            u, pu = mannwhitneyu(vals[lab == a], vals[lab == b])
            # Rank-biserial: >0 berarti nilai di regime a cenderung lebih besar.
            rb = 1 - 2 * u / ((lab == a).sum() * (lab == b).sum())
            pair[f"{a}_vs_{b}"] = {"rank_biserial": round(float(-rb), 4), "p_value": float(f"{pu:.3g}")}
        report["tests"][k] = {
            "kruskal_H": round(float(h), 3),
            "p_value_naive": float(f"{p:.3g}"),
            "p_value_block_permutation": round(block_permutation_p(vals, lab, seed=cfg.model.seed), 4),
            "epsilon_squared": round(epsilon_squared(h, len(vals)), 4),
            "pairwise": pair,
        }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    st.to_parquet(ARTIFACTS_DIR / f"orderflow_window_stats_{timeframe}.parquet", index=False)
    (ARTIFACTS_DIR / f"orderflow_analysis_{timeframe}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"=== Regime vs order flow [{timeframe}], window {L} bar, {len(st)} window ===")
    print(f"{'statistik':18}" + "".join(f"{r:>18}" for r in MAIN_REGIMES) + f"{'eps2':>8}{'p_blok':>9}")
    for k in STATS:
        cells = "".join(
            f"{report['per_regime'][r][k]['median']:>10.4f} ({report['per_regime'][r][k]['share_positive']:.2f})"
            for r in MAIN_REGIMES
        )
        t = report["tests"][k]
        print(f"{k:18}{cells}{t['epsilon_squared']:>8.4f}{t['p_value_block_permutation']:>9.4f}")
    print("Sel: median (porsi window bernilai positif). eps2 = effect size Kruskal-Wallis.")
    print("eps2 < 0.01 diabaikan, 0.01-0.06 kecil, 0.06-0.14 sedang, > 0.14 besar.")

    if plot:
        plot_timeline(timeframe)
    return report


def plot_timeline(timeframe: str, n_last: int = 400) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = ARTIFACTS_DIR / f"orderflow_timeline_{timeframe}.parquet"
    if not path.exists():
        print(f"  {path.name} belum ada; jalankan train_orderflow_ablation.py dulu.")
        return
    tl = pd.read_parquet(path).tail(n_last).reset_index(drop=True)
    t = pd.to_datetime(tl["time"], unit="s")
    colors = {"persistent": "#4a9eff", "random_like": "#8b949e", "anti_persistent": "#f0b90b",
              "uncertain_rule": "#3b4250", "uncertain_lowconf": "#b07cf5"}
    model_cols = [c for c in tl.columns if c.startswith("model_") and not c.endswith("maxprob")]
    rows = 1 + 1 + len(model_cols) + 2
    ratios = [3, 0.5] + [0.5] * len(model_cols) + [1.2, 1.2]
    fig, ax = plt.subplots(rows, 1, figsize=(15, 2 + 1.2 * rows), sharex=True,
                           gridspec_kw={"height_ratios": ratios})
    ax[0].plot(t, tl["close"], color="black", lw=0.8)
    ax[0].set_ylabel("BTC/USDT")
    ax[0].set_title(f"Timeline gabungan [{timeframe}] - rentang test")

    def band(a, seq, name):
        for i in range(len(seq)):
            a.axvspan(t.iloc[i], t.iloc[min(i + 1, len(t) - 1)], color=colors.get(seq[i], "#fff"), lw=0)
        a.set_yticks([])
        a.set_ylabel(name, rotation=0, ha="right", va="center")

    band(ax[1], tl["hurst_dfa_regime"].tolist(), "Hurst-DFA")
    for j, c in enumerate(model_cols):
        band(ax[2 + j], tl[c].tolist(), c.replace("model_", "Model "))
    k = 2 + len(model_cols)
    ax[k].bar(t, tl["ofi"], color=np.where(tl["ofi"] >= 0, "#2ebd85", "#f6465d"), width=0.1)
    ax[k].axhline(0, color="grey", lw=0.5)
    ax[k].set_ylabel("OFI")
    ax[k + 1].plot(t, tl["cvd_norm"], color="#7a5cff", lw=0.9)
    ax[k + 1].axhline(0, color="grey", lw=0.5)
    ax[k + 1].set_ylabel("CVD (z)")
    from matplotlib.patches import Patch

    fig.legend(handles=[Patch(color=v, label=k2) for k2, v in colors.items()], loc="lower center", ncol=5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out = ARTIFACTS_DIR / f"orderflow_timeline_{timeframe}.png"
    fig.savefig(out, dpi=110)
    print(f"  gambar: {out.name}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    p.add_argument("--plot", action="store_true")
    args = p.parse_args()
    analyse(args.timeframe, args.plot)


if __name__ == "__main__":
    main()

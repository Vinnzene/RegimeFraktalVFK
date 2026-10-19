"""Konsistensi label Hurst-DFA — masalah khusus 1 (tanpa training).

Jalankan:
    python ml/src/label_consistency.py
    python ml/src/label_consistency.py --timeframes 1h 4h --plot

Pertanyaan: seberapa sering dua estimator persistensi (Hurst R/S dan DFA)
TIDAK sepakat tentang regime sebuah window, dan bagaimana itu bervariasi
antar timeframe dan antar tahun?

Sumber: data/processed/regime_btcusdt_{tf}.parquet (tabel regime existing).
Tidak ada yang dihitung ulang; ambang yang dipakai adalah ambang yang
tersimpan di tabel itu.

Keluaran:
    ml/artifacts/label_consistency.json
    ml/artifacts/label_consistency.md
    ml/artifacts/figures/fig_label_consistency_{tf}.png   (--plot)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, cast

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import ARTIFACTS_DIR, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402

ORDER = ["persistent", "random_like", "anti_persistent"]
ALL = ORDER + ["uncertain_rule"]
FIG_DIR = ARTIFACTS_DIR / "figures"


def bucket(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
    out = np.full(v.shape, "random_like", dtype=object)
    out[v < lo] = "anti_persistent"
    out[v > hi] = "persistent"
    out[~np.isfinite(v)] = "nan"
    return out


def mean_run_length(labels: List[str]) -> float:
    if not labels:
        return 0.0
    runs, cur = [], 1
    for a, b in zip(labels, labels[1:]):
        if a == b:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
    runs.append(cur)
    return float(np.mean(runs))


def analyse(tf: str) -> Dict:
    from scipy.stats import pearsonr, spearmanr  # type: ignore

    df = get_repository().get_regime("BTCUSDT", tf)
    h = df["hurst"].to_numpy(dtype=float)
    a = df["dfa_alpha"].to_numpy(dtype=float)
    ok = np.isfinite(h) & np.isfinite(a)
    hl, hu = float(df["hurst_lower"].iloc[0]), float(df["hurst_upper"].iloc[0])
    dl, du = float(df["dfa_lower"].iloc[0]), float(df["dfa_upper"].iloc[0])
    bh, bd = bucket(h, hl, hu), bucket(a, dl, du)

    cross = pd.crosstab(pd.Series(bh[ok], name="hurst"), pd.Series(bd[ok], name="dfa")).reindex(
        index=ORDER, columns=ORDER, fill_value=0
    )
    cross_arr = cross.to_numpy()
    agree = int(np.trace(cross_arr))
    n = int(ok.sum())
    opposite = int(cross_arr[0, 2] + cross_arr[2, 0])

    labels = df["regime"].astype(str)
    dist = labels.value_counts().reindex(ALL, fill_value=0)
    years = pd.to_datetime(df["time"], unit="s", utc=True).dt.year
    per_year = (
        pd.DataFrame({"year": years, "unc": labels == "uncertain_rule"})
        .groupby("year")
        .agg(n=("unc", "size"), uncertain_share=("unc", "mean"))
        .reset_index()
    )
    pear = pearsonr(h[ok], a[ok])
    spear = spearmanr(h[ok], a[ok])
    return {
        "timeframe": tf,
        "n_windows": len(df),
        "window_bars": int(df["effective_window"].iloc[0]),
        "stride_bars": int(df["stride_bars"].iloc[0]),
        "threshold_mode": str(df["threshold_mode"].iloc[0]),
        "thresholds": {"hurst": [hl, hu], "dfa": [dl, du]},
        "hurst": {"mean": round(float(h[ok].mean()), 4), "std": round(float(h[ok].std()), 4)},
        "dfa": {"mean": round(float(a[ok].mean()), 4), "std": round(float(a[ok].std()), 4)},
        "corr_pearson": round(float(cast(Any, pear)[0]), 4),
        "corr_spearman": round(float(cast(Any, spear)[0]), 4),
        "agreement_share": round(agree / n, 4),
        "disagreement_share": round(1 - agree / n, 4),
        "opposite_share": round(opposite / n, 4),
        "cross_table": {r: {c: int(cross_arr[i, j]) for j, c in enumerate(ORDER)} for i, r in enumerate(ORDER)},
        "label_distribution": {k: int(cast(Any, v)) for k, v in dist.items()},
        "label_share": {k: round(float(v / len(df)), 4) for k, v in dist.items()},
        "mean_run_length_windows": round(mean_run_length(labels.tolist()), 3),
        "per_year": [
            {"year": int(getattr(r, "year")), "n": int(getattr(r, "n")), "uncertain_share": round(float(getattr(r, "uncertain_share")), 4)}
            for r in per_year.itertuples()
        ],
        "_h": h, "_a": a, "_labels": labels.to_numpy(), "_years": per_year,
    }


def plot(res: Dict) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"persistent": "#1f77b4", "random_like": "#7f7f7f", "anti_persistent": "#ff7f0e", "uncertain_rule": "#d62728"}
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1.2, 1]})
    h, a, lab = res["_h"], res["_a"], res["_labels"]
    rng = np.random.default_rng(42)
    idx = rng.permutation(len(h))[: min(len(h), 4000)]
    for k, c in colors.items():
        sel = idx[lab[idx] == k]
        ax[0].scatter(h[sel], a[sel], s=4, alpha=0.5, c=c, label=k)
    (hl, hu), (dl, du) = res["thresholds"]["hurst"], res["thresholds"]["dfa"]
    for v in (hl, hu):
        ax[0].axvline(v, color="k", lw=0.7, ls="--")
    for v in (dl, du):
        ax[0].axhline(v, color="k", lw=0.7, ls="--")
    ax[0].set_xlabel("Hurst (R/S)")
    ax[0].set_ylabel("DFA alpha")
    ax[0].set_title(
        f"{res['timeframe'].upper()}: Hurst vs DFA (r = {res['corr_pearson']:.2f}, "
        f"tidak sepakat {res['disagreement_share']:.0%})"
    )
    ax[0].legend(markerscale=3, fontsize=8)
    py = res["_years"]
    ax[1].bar(py["year"].astype(str), py["uncertain_share"] * 100, color="#d62728")
    ax[1].set_ylabel("% window uncertain_rule")
    ax[1].set_title("Ketidaksepakatan Hurst-DFA per tahun")
    ax[1].set_ylim(0, 100)
    fig.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / f"fig_label_consistency_{res['timeframe']}.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def to_markdown(results: List[Dict]) -> str:
    lines = ["## Konsistensi label Hurst-DFA", ""]
    lines += [
        "| TF | n window | Korelasi H-DFA (Pearson / Spearman) | Sepakat | Tidak sepakat | Berlawanan (P vs A) | "
        "Persistent | Random-like | Anti-persistent | Uncertain | Durasi rata-rata (window) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        s = r["label_share"]
        lines.append(
            f"| {r['timeframe'].upper()} | {r['n_windows']} | {r['corr_pearson']:.3f} / {r['corr_spearman']:.3f} | "
            f"{r['agreement_share']:.1%} | {r['disagreement_share']:.1%} | {r['opposite_share']:.1%} | "
            f"{s['persistent']:.1%} | {s['random_like']:.1%} | {s['anti_persistent']:.1%} | {s['uncertain_rule']:.1%} | "
            f"{r['mean_run_length_windows']:.2f} |"
        )
    for r in results:
        lines += ["", f"### {r['timeframe'].upper()} — tabel silang (baris = Hurst, kolom = DFA)", "",
                  "| Hurst \\ DFA | " + " | ".join(ORDER) + " |", "|---|" + "---|" * len(ORDER)]
        for row in ORDER:
            lines.append(f"| {row} | " + " | ".join(str(r["cross_table"][row][c]) for c in ORDER) + " |")
        lines += ["", "Porsi uncertain_rule per tahun: " + ", ".join(
            f"{y['year']}: {y['uncertain_share']:.0%}" for y in r["per_year"])]
        lines += [f"Ambang ({r['threshold_mode']}): Hurst {r['thresholds']['hurst']}, DFA {r['thresholds']['dfa']}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--timeframes", nargs="+", default=["1h", "4h"])
    p.add_argument("--plot", action="store_true")
    args = p.parse_args()
    cfg = get_config()
    results = [analyse(tf) for tf in args.timeframes]
    if args.plot:
        for r in results:
            print("gambar:", plot(r).name)
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "label_consistency.json").write_text(
        json.dumps({"config_hash": cfg.config_hash, "results": clean}, indent=2), encoding="utf-8"
    )
    md = to_markdown(clean)
    (ARTIFACTS_DIR / "label_consistency.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()

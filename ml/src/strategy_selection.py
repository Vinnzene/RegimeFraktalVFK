"""Fase 2: pemilihan strategi berbasis regime lintas aset.

Rancangan terkunci: docs/praregistrasi_fase2_strategi.md. Memakai titik deteksi
dan label yang sama dengan uji generalisasi (`generalization_study.py`).

Jalankan (setelah `generalization_study.py --stage features`):
    python ml/src/strategy_selection.py

Keluaran:
    ml/artifacts/strategy_selection.{json,md}
    ml/artifacts/figures/fig_strategy_selection.png
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, PROCESSED_DIR  # noqa: E402
from generalization_study import ASSETS, CACHE, DETECTORS, HORIZON, L, STRIDE, detect  # noqa: E402

LOOKBACK = 24
Z_ENTRY = 1.0
B = 2000
COST = {"kripto": 0.00085, "emas_1h": 0.00085, "emas_1d": 0.0003, "saham_idx": 0.0025}
BARS_PER_YEAR = {"1h": 8760, "1d_emas": 252, "1d_idx": 242}
BLOCK = {"1h": 168, "1d": 20}


def cost_of(a: Dict[str, str]) -> float:
    if a["group"] == "emas":
        return COST["emas_1h" if a["tf"] == "1h" else "emas_1d"]
    return COST[a["group"]]


def bars_per_year(a: Dict[str, str]) -> int:
    if a["tf"] == "1h":
        return BARS_PER_YEAR["1h"]
    return BARS_PER_YEAR["1d_emas" if a["group"] == "emas" else "1d_idx"]


def momentum(r: np.ndarray) -> np.ndarray:
    """Posisi yang berlaku untuk return indeks j, diputuskan dari r[j-24 : j]."""
    c = np.concatenate([[0.0], np.cumsum(r)])
    pos = np.zeros_like(r)
    j = np.arange(LOOKBACK, len(r))
    pos[j] = np.sign(c[j] - c[j - LOOKBACK])
    return pos


def mean_reversion(r: np.ndarray) -> np.ndarray:
    """Posisi untuk return indeks j dari z-score log harga pada penutupan j."""
    logp = pd.Series(np.concatenate([[0.0], np.cumsum(r)]))  # logp[k] = log harga penutupan k
    mu = logp.rolling(LOOKBACK).mean().to_numpy()
    sd = logp.rolling(LOOKBACK).std(ddof=0).to_numpy()
    z = np.where(sd > 0, (logp.to_numpy() - mu) / np.where(sd > 0, sd, 1), 0.0)
    pos = np.zeros_like(r)
    cur = 0.0
    for j in range(LOOKBACK, len(r)):
        zj = z[j]
        if cur == 0.0 and abs(zj) > Z_ENTRY:
            cur = -np.sign(zj)
        elif cur != 0.0 and np.sign(zj) != -cur:
            cur = 0.0
        pos[j] = cur
    return pos


def net_returns(pos: np.ndarray, ret: np.ndarray, cost: float) -> np.ndarray:
    turnover = np.abs(np.diff(np.concatenate([[0.0], pos])))
    return pos * ret - turnover * cost


def metrics(x: np.ndarray, pos: np.ndarray, ann: int) -> Dict[str, float]:
    eq = np.cumprod(1 + x)
    peak = np.maximum.accumulate(eq)
    sd = x.std()
    years = len(x) / ann
    return {
        "total_return": round(float(eq[-1] - 1), 4),
        "sharpe": round(float(x.mean() / sd * math.sqrt(ann)) if sd > 0 else 0.0, 3),
        "max_drawdown": round(float((eq / peak - 1).min()), 4),
        "exposure": round(float(np.mean(pos != 0)), 3),
        "turnover_per_year": round(float(np.abs(np.diff(np.concatenate([[0.0], pos]))).sum() / years), 1),
    }


def sharpe_rows(X: np.ndarray, ann: int) -> np.ndarray:
    sd = X.std(axis=1)
    return np.where(sd > 0, X.mean(axis=1) / np.where(sd > 0, sd, 1) * math.sqrt(ann), 0.0)


def analyse(a: Dict[str, str], meta: Dict[str, Any]) -> Dict[str, Any]:
    with np.load(CACHE / f"{a['symbol']}_{a['tf']}.npz") as z:
        d = {k: z[k] for k in z.files}
    labels = detect(meta, d)
    df = pd.read_parquet(PROCESSED_DIR / f"ohlcv_{a['symbol'].lower()}_{a['tf']}.parquet")
    df = df[df["close"] > 0].reset_index(drop=True)
    r = np.diff(np.log(df["close"].to_numpy(dtype=float)))
    det = np.arange(L - 1, len(r) - 1 - HORIZON[a["tf"]], STRIDE)
    assert len(det) == len(d["time"]), "titik deteksi tidak cocok dengan cache"

    # Bar yang dievaluasi: j = t+1 … t+4 untuk setiap titik deteksi t.
    j = np.arange(det[0] + 1, det[-1] + 1 + STRIDE)
    j = j[j < len(r)]
    which = (j - 1 - det[0]) // STRIDE
    ret = np.expm1(r[j])
    long_only = a["group"] == "saham_idx"
    cost = cost_of(a)
    ann = bars_per_year(a)

    mom_all, mr_all = momentum(r), mean_reversion(r)
    clip = (lambda p: np.maximum(p, 0.0)) if long_only else (lambda p: p)
    mom, mr = clip(mom_all[j]), clip(mr_all[j])
    positions: Dict[str, np.ndarray] = {"MOM": mom, "MR": mr, "BH": np.ones_like(ret), "FLAT": np.zeros_like(ret)}
    for k in DETECTORS:
        lab = labels[k][which]
        positions[f"SW({k})"] = np.where(lab == "persistent", mom, np.where(lab == "anti_persistent", mr, 0.0))
    # E2: MOM/MR hanya di periode berlabel random-like (D-sintetis).
    rnd = labels["D-sintetis"][which] == "random_like"
    positions["E2:MOM@random"] = np.where(rnd, mom, 0.0)
    positions["E2:MR@random"] = np.where(rnd, mr, 0.0)

    # D-BTC pada BTC: hanya setelah batas latih BTC.
    mask = np.ones(len(j), bool)
    if a["symbol"] == "BTCUSDT":
        bar_time = df["time"].to_numpy()[j]
        mask = bar_time > meta["d_btc"]["btc_train_end_time"]

    names = list(positions)
    R = np.stack([net_returns(positions[k], ret, cost) for k in names])
    res = {k: metrics(R[i], positions[k], ann) for i, k in enumerate(names)}
    res["SW(D-BTC)"] = metrics(R[names.index("SW(D-BTC)")][mask], positions["SW(D-BTC)"][mask], ann)

    best_single = "MOM" if res["MOM"]["sharpe"] >= res["MR"]["sharpe"] else "MR"
    tests = {
        "F1": ("SW(D-sintetis)", best_single),
        "F2": ("SW(D-sintetis)", "BH"),
        "F3": ("SW(D-sintetis)", "SW(D-klasik)"),
        "F4": ("SW(D-sintetis)", "SW(D-konsensus)"),
        "F5": ("SW(D-sintetis)", "SW(D-BTC)"),
    }
    n = len(j)
    block = BLOCK[a["tf"]]
    rng = np.random.default_rng(42)
    n_blocks = math.ceil(n / block)
    idx_m = np.flatnonzero(mask)
    boot = {h: np.empty(B) for h in tests}
    for b in range(B):
        starts = rng.integers(0, n, n_blocks)
        idx = ((starts[:, None] + np.arange(block)[None, :]) % n).ravel()[:n]
        S = dict(zip(names, sharpe_rows(R[:, idx], ann)))
        for h, (x, y) in tests.items():
            if h == "F5" and a["symbol"] == "BTCUSDT":
                sub = idx[mask[idx]]
                s2 = sharpe_rows(R[[names.index(x), names.index(y)]][:, sub], ann) if len(sub) > 1 else np.zeros(2)
                boot[h][b] = s2[0] - s2[1]
            else:
                boot[h][b] = S[x] - S[y]
    hyp = {}
    for h, (x, y) in tests.items():
        lo, hi = np.quantile(boot[h], [0.025, 0.975])
        if h == "F5" and a["symbol"] == "BTCUSDT":
            s2 = sharpe_rows(R[[names.index(x), names.index(y)]][:, idx_m], ann)
            diff = float(s2[0] - s2[1])
        else:
            diff = res[x]["sharpe"] - res[y]["sharpe"]
        hyp[h] = {"a": x, "b": y, "diff_sharpe": round(diff, 3), "ci95": [round(float(lo), 3), round(float(hi), 3)],
                  "verdict": "lebih baik" if lo > 0 else ("lebih buruk" if hi < 0 else "setara")}

    # E1: VR maju setelah random-like dibanding setelah anti-persistent (D-sintetis).
    fwd, lab0 = d["fwd_log_vr"], labels["D-sintetis"]
    e1 = float(fwd[lab0 == "random_like"].mean() - fwd[lab0 == "anti_persistent"].mean()) \
        if np.any(lab0 == "random_like") and np.any(lab0 == "anti_persistent") else math.nan

    return {**a, "bars": n, "cost_per_side": cost, "long_only": long_only, "best_single": best_single,
            "strategies": res, "hypotheses": hyp, "E1_random_minus_anti_fwd_log_vr": round(e1, 4),
            "_equity": {k: np.cumprod(1 + R[names.index(k)]) for k in ("SW(D-sintetis)", "MOM", "MR", "BH")},
            "_time": df["time"].to_numpy()[j]}


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for g in ("kripto", "emas", "saham_idx"):
        rs = [r for r in results if r["group"] == g]
        out[g] = {}
        for h in ("F1", "F2", "F3", "F4", "F5"):
            better = sum(r["hypotheses"][h]["verdict"] == "lebih baik" for r in rs)
            worse = sum(r["hypotheses"][h]["verdict"] == "lebih buruk" for r in rs)
            out[g][h] = {"better": better, "worse": worse, "assets": len(rs),
                         "holds": better >= math.ceil(2 * len(rs) / 3) and worse == 0}
        dd_sw = [r["strategies"]["SW(D-sintetis)"]["max_drawdown"] for r in rs]
        dd_best = [r["strategies"][r["best_single"]]["max_drawdown"] for r in rs]
        out[g]["drawdown_smaller_than_best_single"] = sum(a > b for a, b in zip(dd_sw, dd_best))
    return out


def to_markdown(out: Dict[str, Any]) -> str:
    s = out["summary"]
    lines = ["# Fase 2: pemilihan strategi berbasis regime", "",
             "Praregistrasi: `docs/praregistrasi_fase2_strategi.md`. Selisih Sharpe tahunan, CI95 bootstrap blok sirkular.", "",
             "## Ringkasan per kelompok (jumlah aset lebih baik / lebih buruk)", "",
             "| Kelompok | F1 vs strategi tunggal terbaik | F2 vs beli-tahan | F3 vs D-klasik | F4 vs D-konsensus | F5 vs D-BTC | Drawdown SW lebih kecil |",
             "|---|---|---|---|---|---|---|"]
    for g, v in s.items():
        cell = lambda h: f"{v[h]['better']}/{v[h]['worse']} dari {v[h]['assets']}" + (" **berlaku**" if v[h]["holds"] else "")  # noqa: E731
        lines.append(f"| {g} | {cell('F1')} | {cell('F2')} | {cell('F3')} | {cell('F4')} | {cell('F5')} | {v['drawdown_smaller_than_best_single']} |")
    lines += ["", "## Per aset (Sharpe tahunan bersih; drawdown maksimum; waktu memegang posisi)", "",
              "| Aset | SW(D-sintetis) | MOM | MR | BH | SW(D-klasik) | SW(D-konsensus) | F1 | F2 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in out["assets"]:
        st = r["strategies"]
        c = lambda k: f"{st[k]['sharpe']:+.2f} ({st[k]['max_drawdown']:.0%}, {st[k]['exposure']:.0%})"  # noqa: E731
        f = lambda h: f"{r['hypotheses'][h]['diff_sharpe']:+.2f} {r['hypotheses'][h]['verdict']}"  # noqa: E731
        lines.append(f"| {r['symbol']} {r['tf']} | {c('SW(D-sintetis)')} | {c('MOM')} | {c('MR')} | {c('BH')} | "
                     f"{c('SW(D-klasik)')} | {c('SW(D-konsensus)')} | {f('F1')} | {f('F2')} |")
    lines += ["", "## Eksploratif", "", "| Aset | E1: Δ log VR maju (random − anti) | E2: Sharpe MOM saat random | E2: Sharpe MR saat random |", "|---|---|---|---|"]
    for r in out["assets"]:
        st = r["strategies"]
        lines.append(f"| {r['symbol']} {r['tf']} | {r['E1_random_minus_anti_fwd_log_vr']:+.3f} | "
                     f"{st['E2:MOM@random']['sharpe']:+.2f} | {st['E2:MR@random']['sharpe']:+.2f} |")
    return "\n".join(lines) + "\n"


def figure(results: List[Dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    picks = [r for r in results if r["symbol"] in ("BTCUSDT", "PAXGUSDT", "JKSE")]
    colors = {"SW(D-sintetis)": "#ff7a1a", "MOM": "#4a9eff", "MR": "#f0b90b", "BH": "#8b949e"}
    fig, axes = plt.subplots(1, len(picks), figsize=(15, 4.2))
    for ax, r in zip(np.atleast_1d(axes), picks):
        t = pd.to_datetime(r["_time"], unit="s")
        for k, eq in r["_equity"].items():
            ax.plot(t, eq, color=colors[k], lw=1.6 if k.startswith("SW") else 1.0, label=k)
        ax.set_yscale("log")
        ax.set_title(f"{r['symbol']} {r['tf']} (biaya {r['cost_per_side']:.3%}/sisi)")
        ax.axhline(1, color="#444", lw=0.6)
    np.atleast_1d(axes)[0].legend(fontsize=8)
    fig.tight_layout()
    (ARTIFACTS_DIR / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(ARTIFACTS_DIR / "figures" / "fig_strategy_selection.png", dpi=150)


def main() -> None:
    meta = json.loads((ARTIFACTS_DIR / "detector_meta.json").read_text(encoding="utf-8"))
    results = []
    for a in ASSETS:
        t0 = time.time()
        results.append(analyse(a, meta))
        print(f"{a['symbol']:10s} {time.time() - t0:.0f}s", flush=True)
    figure(results)
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    out = {"preregistration": "docs/praregistrasi_fase2_strategi.md", "assets": clean, "summary": summarize(clean)}
    (ARTIFACTS_DIR / "strategy_selection.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = to_markdown(out)
    (ARTIFACTS_DIR / "strategy_selection.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()

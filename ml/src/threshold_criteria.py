"""Dasar pemilihan ambang kelas regime untuk Fase 1 (sebelum praregistrasi dikunci).

Jalankan:
    python ml/src/threshold_criteria.py

Ambang kelas tidak boleh dipilih dari kinerja model (itu menyetel kunci
jawaban). Skrip ini menghitung dua kriteria yang independen dari hasil Fase 1
dan tidak menyentuh data BTC:

B. Statistik: sebaran taksiran R/S dan DFA pada deret acak murni (H = 0,5)
   sepanjang n bar. Selisih |H - 0,5| di dalam pita ini tidak dapat dibedakan
   dari acak oleh estimator klasik.
C. Ekonomi: H di mana strategi yang cocok (momentum untuk H > 0,5,
   mean-reversion untuk H < 0,5) mulai untung setelah biaya. Di antara kedua
   titik impas itu tidak ada strategi yang menguntungkan, yaitu definisi
   praktis "acak".

Strategi dan biaya sama dengan `regime_strategy_demo.py`.

Keluaran: ml/artifacts/threshold_criteria.{json,md}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.services.hurst_dfa import dfa_alpha, fbm_increments, hurst_rs  # noqa: E402
from regime_strategy_demo import COST_PER_SIDE, LOOKBACK, SIGMA, Z_ENTRY  # noqa: E402

NULL_LENGTHS = [128, 256, 500]
NULL_SERIES = 2000
H_GRID = np.round(np.arange(0.40, 0.6001, 0.01), 2)
ECON_PATHS = 300
ECON_BARS = 2000


def fgn(n: int, h: float, seed: int) -> np.ndarray:
    x = fbm_increments(n, h, seed=seed)
    return SIGMA * x / x.std()


def null_band() -> Dict[str, Dict[str, float]]:
    """Kuantil taksiran R/S dan DFA pada fGn H = 0,5 untuk tiap panjang window."""
    out: Dict[str, Dict[str, float]] = {}
    for n in NULL_LENGTHS:
        rs, dfa = [], []
        for s in range(NULL_SERIES):
            x = fgn(n, 0.5, seed=50_000 + 10 * n + s)
            rs.append(hurst_rs(x))
            dfa.append(dfa_alpha(x))
        for name, v in (("rs", np.array(rs)), ("dfa", np.array(dfa))):
            v = v[np.isfinite(v)]
            out[f"{name}_n{n}"] = {
                "mean": round(float(v.mean()), 4),
                "sd": round(float(v.std()), 4),
                "q025": round(float(np.quantile(v, 0.025)), 4),
                "q975": round(float(np.quantile(v, 0.975)), 4),
                "half_width_95": round(float((np.quantile(v, 0.975) - np.quantile(v, 0.025)) / 2), 4),
            }
        print(f"null n={n}: R/S {out[f'rs_n{n}']} | DFA {out[f'dfa_n{n}']}")
    return out


def _net(r: np.ndarray, pos: np.ndarray) -> float:
    held = np.concatenate([[0.0], pos[:-1]])
    turnover = np.abs(np.diff(np.concatenate([[0.0], held])))
    return float(np.expm1((held * r - turnover * COST_PER_SIDE).sum()))


def momentum_pos(r: np.ndarray) -> np.ndarray:
    c = np.concatenate([[0.0], np.cumsum(r)])
    pos = np.zeros_like(r)
    pos[LOOKBACK:] = np.sign(c[LOOKBACK + 1 :] - c[1 : len(r) - LOOKBACK + 1])
    return pos


def mean_reversion_pos(r: np.ndarray) -> np.ndarray:
    logp = pd.Series(np.cumsum(r))
    mu = logp.rolling(LOOKBACK).mean().to_numpy()
    sd = logp.rolling(LOOKBACK).std(ddof=0).to_numpy()
    z = np.where(sd > 0, (logp.to_numpy() - mu) / np.where(sd > 0, sd, 1), 0.0)
    pos = np.zeros_like(r)
    cur = 0.0
    for t in range(LOOKBACK, len(r)):
        if cur == 0.0 and abs(z[t]) > Z_ENTRY:
            cur = -np.sign(z[t])
        elif cur != 0.0 and np.sign(z[t]) != -cur:
            cur = 0.0
        pos[t] = cur
    return pos


def economic_curve() -> List[Dict[str, float]]:
    rows = []
    for h in H_GRID:
        mom, mr = [], []
        for s in range(ECON_PATHS):
            r = fgn(ECON_BARS, float(h), seed=70_000 + int(round(h * 1000)) * 1000 + s)
            mom.append(_net(r, momentum_pos(r)))
            mr.append(_net(r, mean_reversion_pos(r)))
        rho1 = 2 ** (2 * h - 1) - 1  # autokorelasi lag-1 teoretis fGn
        rows.append({
            "h": float(h), "rho1": round(float(rho1), 4),
            "momentum_median": round(float(np.median(mom)), 4),
            "mean_reversion_median": round(float(np.median(mr)), 4),
        })
        print(f"H={h:.2f} rho1={rho1:+.3f} momentum={np.median(mom):+.3f} mean-rev={np.median(mr):+.3f}")
    return rows


def breakeven(rows: List[Dict[str, float]], key: str, side: str) -> float | None:
    """H pertama (dari 0,5 menjauh) di mana median return bersih strategi > 0, diinterpolasi linear."""
    pts = [(r["h"], r[key]) for r in rows if (r["h"] >= 0.5 if side == "up" else r["h"] <= 0.5)]
    pts.sort(key=lambda p: p[0], reverse=(side == "down"))
    for (h0, v0), (h1, v1) in zip(pts, pts[1:]):
        if v0 <= 0 < v1:
            return round(h0 + (h1 - h0) * (0 - v0) / (v1 - v0), 3)
    return None


def main() -> None:
    null = null_band()
    curve = economic_curve()
    upper = breakeven(curve, "momentum_median", "up")
    lower = breakeven(curve, "mean_reversion_median", "down")
    out = {
        "null_distribution_h05": null,
        "economic_curve": curve,
        "economic_breakeven": {"lower": lower, "upper": upper},
        "design": {"null_series": NULL_SERIES, "econ_paths": ECON_PATHS, "econ_bars": ECON_BARS,
                   "lookback": LOOKBACK, "z_entry": Z_ENTRY, "cost_per_side": COST_PER_SIDE},
    }
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "threshold_criteria.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    md = ["## Kriteria ambang kelas regime (data sintetis)", "",
          "### B. Sebaran taksiran pada deret acak murni (H = 0,5)", "",
          "| n | R/S rata-rata | R/S 95% | DFA rata-rata | DFA 95% |", "|---|---|---|---|---|"]
    for n in NULL_LENGTHS:
        a, b = null[f"rs_n{n}"], null[f"dfa_n{n}"]
        md.append(f"| {n} | {a['mean']:.3f} | {a['q025']:.3f}–{a['q975']:.3f} | {b['mean']:.3f} | {b['q025']:.3f}–{b['q975']:.3f} |")
    md += ["", "### C. Titik impas strategi setelah biaya", "",
           f"Mean-reversion untung bila H < **{lower}**; momentum untung bila H > **{upper}**.", "",
           "| H | ρ₁ | Momentum (median) | Mean-reversion (median) |", "|---|---|---|---|"]
    for r in curve:
        md.append(f"| {r['h']:.2f} | {r['rho1']:+.3f} | {r['momentum_median']:+.1%} | {r['mean_reversion_median']:+.1%} |")
    (ARTIFACTS_DIR / "threshold_criteria.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"titik impas: bawah {lower}, atas {upper}")


if __name__ == "__main__":
    main()

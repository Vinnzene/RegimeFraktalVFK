"""Demo mekanisme: strategi yang tepat bergantung pada regime persistensi.

Jalankan:
    python ml/src/regime_strategy_demo.py

Seluruh data di sini SINTETIS (fractional Gaussian noise dengan H diketahui).
Data BTC sengaja tidak disentuh: kinerja strategi per regime pada BTC adalah
pertanyaan Fase 2 yang harus dipraregistrasi lebih dulu (docs/
rencana_pengembangan.md). Demo ini hanya menunjukkan mekanismenya.

Rancangan (tetap, tidak disetel):
- H = 0,40 / 0,50 / 0,60 untuk memperlihatkan mekanismenya. Pada fGn,
  H = 0,40/0,60 berarti autokorelasi lag-1 sekitar -/+0,13, jauh lebih kuat dari
  BTC 1H (sekitar -0,03; Bab 4 §4.7.1), sehingga besarnya hasil DILEBIH-LEBIHKAN.
- H = 0,48 / 0,52 (autokorelasi lag-1 sekitar -/+0,03) sebagai skenario
  setara BTC: apakah keunggulan masih tersisa setelah biaya?
- Volatilitas per bar 0,6% (setara orde BTC 1H), 2.000 bar per jalur,
  300 jalur per H.
- Momentum: posisi = tanda return 24 bar terakhir (long/short).
- Mean-reversion: posisi = kebalikan tanda z-score harga terhadap rata-rata
  24 bar bila |z| > 1, ditutup saat z kembali melewati 0.
- Biaya: 0,075% fee + 0,01% slippage per perubahan posisi (per sisi).
- Posisi diputuskan di akhir bar t dan berlaku untuk return bar t+1.

Keluaran: ml/artifacts/regime_strategy_demo.json, disalin ke
frontend/public/data/ untuk halaman /strategi di dashboard.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.services.hurst_dfa import dfa_alpha, fbm_increments, hurst_rs  # noqa: E402

HS = [0.40, 0.48, 0.50, 0.52, 0.60]
N_BARS = 2000
N_PATHS = 300
SIGMA = 0.006
LOOKBACK = 24
Z_ENTRY = 1.0
COST_PER_SIDE = 0.00075 + 0.0001
BARS_PER_YEAR = 24 * 365
QUIZ_HS = [0.40, 0.50, 0.60]
QUIZ_BARS = 500
QUIZ_SEED = 2026


def returns_for(h: float, seed: int, n: int = N_BARS) -> np.ndarray:
    x = fbm_increments(n, h, seed=seed)
    return SIGMA * x / x.std()


def momentum_positions(r: np.ndarray) -> np.ndarray:
    pos = np.zeros_like(r)
    csum = np.concatenate([[0.0], np.cumsum(r)])
    for t in range(LOOKBACK, len(r)):
        pos[t] = np.sign(csum[t + 1] - csum[t + 1 - LOOKBACK])
    return pos


def mean_reversion_positions(r: np.ndarray) -> np.ndarray:
    logp = np.cumsum(r)
    pos = np.zeros_like(r)
    cur = 0.0
    for t in range(LOOKBACK, len(r)):
        w = logp[t + 1 - LOOKBACK : t + 1]
        sd = w.std()
        z = (logp[t] - w.mean()) / sd if sd > 0 else 0.0
        if cur == 0.0 and abs(z) > Z_ENTRY:
            cur = -np.sign(z)
        elif cur != 0.0 and np.sign(z) != -cur:
            cur = 0.0
        pos[t] = cur
    return pos


def net_returns(r: np.ndarray, pos: np.ndarray) -> np.ndarray:
    held = np.concatenate([[0.0], pos[:-1]])  # keputusan di t berlaku di t+1
    turnover = np.abs(np.diff(np.concatenate([[0.0], held])))
    return held * r - turnover * COST_PER_SIDE


def summarize(net: np.ndarray) -> Dict[str, float]:
    total = np.expm1(net.sum(axis=1))
    mu, sd = net.mean(axis=1), net.std(axis=1)
    sharpe = np.where(sd > 0, mu / np.where(sd > 0, sd, 1) * np.sqrt(BARS_PER_YEAR), 0.0)
    return {
        "median_total_return": round(float(np.median(total)), 4),
        "p25_total_return": round(float(np.quantile(total, 0.25)), 4),
        "p75_total_return": round(float(np.quantile(total, 0.75)), 4),
        "share_profitable": round(float((total > 0).mean()), 3),
        "median_sharpe": round(float(np.median(sharpe)), 2),
    }


def equity_band(net: np.ndarray, step: int = 20) -> Dict[str, List[float]]:
    eq = np.exp(np.cumsum(net, axis=1))[:, ::step]
    return {
        "p25": np.round(np.quantile(eq, 0.25, axis=0), 4).tolist(),
        "median": np.round(np.median(eq, axis=0), 4).tolist(),
        "p75": np.round(np.quantile(eq, 0.75, axis=0), 4).tolist(),
    }


def main() -> None:
    out: Dict = {
        "design": {
            "hurst": HS, "n_bars": N_BARS, "n_paths": N_PATHS, "sigma_per_bar": SIGMA,
            "lookback": LOOKBACK, "z_entry": Z_ENTRY, "cost_per_side": COST_PER_SIDE,
            "equity_step": 20,
        },
        "results": {},
        "quiz": [],
    }
    for h in HS:
        rets = np.array([returns_for(h, seed=10_000 * int(h * 100) + s) for s in range(N_PATHS)])
        mom = np.array([net_returns(r, momentum_positions(r)) for r in rets])
        mr = np.array([net_returns(r, mean_reversion_positions(r)) for r in rets])
        rho1 = float(np.mean([np.corrcoef(r[:-1], r[1:])[0, 1] for r in rets]))
        out["results"][f"{h:.2f}"] = {
            "lag1_autocorr": round(rho1, 4),
            "momentum": {**summarize(mom), "equity": equity_band(mom)},
            "mean_reversion": {**summarize(mr), "equity": equity_band(mr)},
        }
        print(f"H={h:.2f} rho1={rho1:+.3f} | momentum {summarize(mom)} | mean-rev {summarize(mr)}")

    # Kuis: satu jalur per H, seed tetap (tidak dipilih-pilih), urutan diacak.
    order = np.random.default_rng(QUIZ_SEED).permutation(len(QUIZ_HS))
    for label, i in zip("ABC", order):
        h = QUIZ_HS[i]
        r = returns_for(h, seed=QUIZ_SEED + i, n=QUIZ_BARS)
        price = 100 * np.exp(np.cumsum(r))
        out["quiz"].append({
            "label": label, "true_h": h,
            "est_hurst_rs": round(float(hurst_rs(r)), 3), "est_dfa": round(float(dfa_alpha(r)), 3),
            "price": np.round(price, 3).tolist(),
        })

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS_DIR / "regime_strategy_demo.json"
    path.write_text(json.dumps(out), encoding="utf-8")
    public = ROOT / "frontend" / "public" / "data" / path.name
    public.parent.mkdir(parents=True, exist_ok=True)
    public.write_text(json.dumps(out), encoding="utf-8")
    print(f"tersimpan: {path} dan {public}")


if __name__ == "__main__":
    main()

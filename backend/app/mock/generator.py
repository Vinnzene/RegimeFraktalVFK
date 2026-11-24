"""Generator data mock realistis untuk fase 1 (runtime.use_mock = true).

Tujuan: chart bisa dibangun & diuji sebelum data exchange asli tersedia
(sumber data resmi masih open question di skripsi). Karakter data sengaja
dibuat menyerupai BTC/USDT:
- harga bergerak di rentang ~25.000-70.000 lewat GBM dengan drift & vol berubah
- volatilitas dan persistensi berganti fase, supaya regime tidak monoton
- DFA alpha berkorelasi dengan Hurst TAPI tidak identik, sehingga kategori
  uncertain_rule benar-benar muncul (bukan nol) di visualisasi.

Semua fungsi deterministik terhadap seed dari config.
"""

from __future__ import annotations


import numpy as np
import pandas as pd

TF_MINUTES = {"1h": 60, "4h": 240}
DEFAULT_BARS = {"1h": 6000, "4h": 1800}


def _phase_profile(n: int, rng: np.random.Generator) -> np.ndarray:
    """Deret target-Hurst yang berganti fase secara bertahap."""
    profile = np.empty(n, dtype=float)
    i = 0
    while i < n:
        seg = int(rng.integers(300, 900))
        target = float(rng.uniform(0.32, 0.68))
        end = min(n, i + seg)
        profile[i:end] = target
        i = end
    kernel = np.ones(120) / 120
    return np.convolve(profile, kernel, mode="same")


def generate_ohlcv(timeframe: str, seed: int = 42, bars: int | None = None) -> pd.DataFrame:
    """OHLCV BTC/USDT sintetis dengan volatilitas & persistensi bervariasi."""
    rng = np.random.default_rng(seed + hash(timeframe) % 1000)
    n = bars or DEFAULT_BARS.get(timeframe, 4000)
    minutes = TF_MINUTES.get(timeframe, 60)

    target_h = _phase_profile(n, rng)
    # AR(1) dengan koefisien terkait target Hurst: phi > 0 -> persisten,
    # phi < 0 -> anti-persisten (mean-reverting).
    phi = np.clip((target_h - 0.5) * 1.6, -0.75, 0.75)
    vol = 0.004 * np.exp(0.35 * np.cumsum(rng.normal(scale=0.02, size=n)))
    vol = np.clip(vol, 0.0015, 0.02)

    ret = np.zeros(n)
    prev = 0.0
    for t in range(n):
        eps = rng.normal(scale=vol[t])
        prev = phi[t] * prev + eps
        ret[t] = prev

    price = 32000.0 * np.exp(np.cumsum(ret))
    # Petakan ke rentang wajar BTC tanpa merusak bentuk deret.
    price = 25000 + (price - price.min()) / (price.max() - price.min() + 1e-9) * 45000

    start = pd.Timestamp("2023-01-01", tz="UTC")
    ts = pd.date_range(start=start, periods=n, freq=f"{minutes}min", tz="UTC")

    close = price
    open_ = np.concatenate([[close[0] * (1 - 0.001)], close[:-1]])
    spread = np.abs(rng.normal(scale=0.004, size=n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = np.abs(rng.lognormal(mean=6.0, sigma=0.6, size=n)) * (1 + vol / vol.mean())

    return pd.DataFrame(
        {
            "time": (ts.astype("int64") // 10**9).astype("int64"),
            "open": np.round(open_, 2),
            "high": np.round(high, 2),
            "low": np.round(low, 2),
            "close": np.round(close, 2),
            "volume": np.round(volume, 4),
        }
    )



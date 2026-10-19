"""Estimasi Hurst Exponent (R/S) dan DFA alpha pada rolling window.

Aturan domain penting:
- Input WAJIB log-return, bukan harga level. Harga BTC bersifat non-stasioner
  (unit root); estimasi Hurst pada harga level akan menghasilkan H ~ 0.9-1.0
  untuk hampir semua window sehingga label regime kehilangan daya beda.
- Seluruh perhitungan bersifat causal: window pada indeks t hanya memakai
  data pada indeks <= t.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


def to_log_return(close: np.ndarray | pd.Series) -> np.ndarray:
    """Ubah deret harga menjadi log-return. Elemen pertama di-drop."""
    arr = np.asarray(close, dtype=float)
    if arr.size < 2:
        return np.array([], dtype=float)
    return np.diff(np.log(arr))


def _log_scales(n: int, min_scale: int = 8, max_divisor: int = 4, count: int = 12) -> np.ndarray:
    """Skala segmen ter-spasi logaritmik, dibatasi n/max_divisor."""
    max_scale = max(min_scale + 1, n // max_divisor)
    if max_scale <= min_scale:
        return np.array([], dtype=int)
    scales = np.unique(
        np.floor(np.logspace(np.log10(min_scale), np.log10(max_scale), count)).astype(int)
    )
    return scales[scales >= min_scale]


def _dfa_fluctuation(y: np.ndarray, scale: int) -> float:
    """RMS fluktuasi setelah detrend linear per segmen (DFA-1)."""
    n_seg = y.size // scale
    if n_seg < 1:
        return np.nan
    segments = y[: n_seg * scale].reshape(n_seg, scale)
    t = np.arange(scale, dtype=float)
    design = np.column_stack([t, np.ones(scale)])
    coef, *_ = np.linalg.lstsq(design, segments.T, rcond=None)
    resid = segments.T - design @ coef
    return float(np.sqrt(np.mean(resid**2)))


def dfa_alpha(x: np.ndarray, min_scale: int = 8, count: int = 12) -> float:
    """Detrended Fluctuation Analysis orde 1 -> eksponen alpha."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 32:
        return np.nan
    profile = np.cumsum(x - x.mean())
    scales = _log_scales(x.size, min_scale=min_scale, count=count)
    if scales.size < 3:
        return np.nan
    fluct = np.array([_dfa_fluctuation(profile, int(s)) for s in scales])
    ok = np.isfinite(fluct) & (fluct > 0)
    if ok.sum() < 3:
        return np.nan
    slope = np.polyfit(np.log(scales[ok]), np.log(fluct[ok]), 1)[0]
    return float(slope)


def _rs_statistic(x: np.ndarray, scale: int) -> float:
    """Rescaled range rata-rata untuk satu ukuran segmen."""
    n_seg = x.size // scale
    if n_seg < 1:
        return np.nan
    segments = x[: n_seg * scale].reshape(n_seg, scale)
    centered = segments - segments.mean(axis=1, keepdims=True)
    cumdev = np.cumsum(centered, axis=1)
    rng = cumdev.max(axis=1) - cumdev.min(axis=1)
    std = segments.std(axis=1, ddof=1)
    ok = std > 0
    if not ok.any():
        return np.nan
    return float(np.mean(rng[ok] / std[ok]))


def hurst_rs(x: np.ndarray, min_scale: int = 8, count: int = 12) -> float:
    """Hurst Exponent via Rescaled Range (R/S) analysis."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 32:
        return np.nan
    scales = _log_scales(x.size, min_scale=min_scale, count=count)
    if scales.size < 3:
        return np.nan
    rs = np.array([_rs_statistic(x, int(s)) for s in scales])
    ok = np.isfinite(rs) & (rs > 0)
    if ok.sum() < 3:
        return np.nan
    slope = np.polyfit(np.log(scales[ok]), np.log(rs[ok]), 1)[0]
    return float(slope)


def rolling_hurst_dfa(
    log_returns: np.ndarray,
    window: int,
    step: int = 1,
    positions: Optional[Iterable[int]] = None,
) -> pd.DataFrame:
    """Hitung H dan alpha secara rolling.

    Nilai pada indeks t dihitung dari log_returns[t-window+1 : t+1] sehingga
    tidak pernah menyentuh data setelah t.
    """
    x = np.asarray(log_returns, dtype=float)
    n = x.size
    if n < window:
        return pd.DataFrame(columns=["index", "hurst", "dfa_alpha"])

    idx: List[int] = (
        list(positions) if positions is not None else list(range(window - 1, n, step))
    )
    rows = []
    for t in idx:
        if t < window - 1 or t >= n:
            continue
        seg = x[t - window + 1 : t + 1]
        rows.append(
            {
                "index": int(t),
                "hurst": hurst_rs(seg),
                "dfa_alpha": dfa_alpha(seg),
            }
        )
    return pd.DataFrame(rows, columns=["index", "hurst", "dfa_alpha"])


def fbm_increments(n: int, hurst: float, seed: int = 0) -> np.ndarray:
    """Bangkitkan fractional Gaussian noise dengan H diketahui (Davies-Harte).

    Dipakai untuk memvalidasi estimator: kalau hurst_rs/dfa_alpha tidak mampu
    memulihkan H pada data sintetis, seluruh label regime di dashboard batal.
    """
    rng = np.random.default_rng(seed)
    size = 1
    while size < n:
        size *= 2
    k = np.arange(size + 1, dtype=float)
    gamma = 0.5 * (
        np.abs(k - 1) ** (2 * hurst)
        - 2 * np.abs(k) ** (2 * hurst)
        + np.abs(k + 1) ** (2 * hurst)
    )
    row = np.concatenate([gamma[: size + 1], gamma[1:size][::-1]])
    eigenvalues = np.fft.fft(row).real
    eigenvalues[eigenvalues < 0] = 0.0
    m = row.size
    noise = rng.normal(size=m) + 1j * rng.normal(size=m)
    spectrum = np.sqrt(eigenvalues / (2 * m)) * noise
    series = np.fft.fft(spectrum).real
    return series[:n]

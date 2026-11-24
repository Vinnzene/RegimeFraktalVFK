"""Estimasi Hurst Exponent (R/S) dan DFA alpha pada rolling window."""

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


def andrews_lag(n: int, rho: float) -> int:
    """Lag Newey-West optimal Andrews (1991) untuk proses AR(1) dengan koefisien rho."""
    rho = float(np.clip(rho, -0.99, 0.99))
    a = abs(2 * rho / (1 - rho**2))
    q = int(np.floor((1.5 * n) ** (1 / 3) * a ** (2 / 3)))
    return max(0, min(q, n // 4))


def _lo_rs_statistic(x: np.ndarray, scale: int, rho: float) -> float:
    """R/S termodifikasi Lo untuk satu ukuran segmen."""
    n_seg = x.size // scale
    if n_seg < 1:
        return np.nan
    segments = x[: n_seg * scale].reshape(n_seg, scale)
    centered = segments - segments.mean(axis=1, keepdims=True)
    cumdev = np.cumsum(centered, axis=1)
    rng = cumdev.max(axis=1) - cumdev.min(axis=1)
    s2 = np.mean(centered**2, axis=1)
    q = andrews_lag(scale, rho)
    for j in range(1, q + 1):
        gamma = np.sum(centered[:, j:] * centered[:, :-j], axis=1) / scale
        s2 = s2 + 2 * (1 - j / (q + 1)) * gamma
    ok = s2 > 0
    if not ok.any():
        return np.nan
    return float(np.mean(rng[ok] / np.sqrt(s2[ok])))


def hurst_lo(x: np.ndarray, min_scale: int = 8, count: int = 12) -> float:
    """Hurst via R/S termodifikasi Lo (1991), skala dan regresi sama dengan hurst_rs."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 32:
        return np.nan
    scales = _log_scales(x.size, min_scale=min_scale, count=count)
    if scales.size < 3:
        return np.nan
    c = x - x.mean()
    rho = float((c[1:] * c[:-1]).sum() / (c * c).sum()) if np.any(c) else 0.0
    rs = np.array([_lo_rs_statistic(x, int(s), rho) for s in scales])
    ok = np.isfinite(rs) & (rs > 0)
    if ok.sum() < 3:
        return np.nan
    return float(np.polyfit(np.log(scales[ok]), np.log(rs[ok]), 1)[0])


def compute_rolling_er(
    log_returns: np.ndarray,
    positions: Iterable[int],
    window: int = 500,
) -> Dict[str, np.ndarray]:
    """Hitung Directional Efficiency Ratio (Kaufman ER) multiskala secara kausal."""
    x = np.asarray(log_returns, dtype=float)
    x_clean = np.nan_to_num(x, nan=0.0)
    c1 = np.concatenate([[0.0], np.cumsum(x_clean)])
    ca = np.concatenate([[0.0], np.cumsum(np.abs(x_clean))])
    pos = np.asarray(list(positions), dtype=int)
    if pos.size == 0:
        empty = np.array([], dtype=float)
        return {"er_full": empty, "er_128": empty, "er_64": empty}

    def _er_w(w: int) -> np.ndarray:
        start = np.maximum(0, pos - w + 1)
        s1 = np.abs(c1[pos + 1] - c1[start])
        sa = ca[pos + 1] - ca[start]
        return s1 / (sa + 1e-12)

    return {
        "er_full": _er_w(window),
        "er_128": _er_w(min(128, window)),
        "er_64": _er_w(min(64, window)),
    }


def rolling_hurst_dfa(
    log_returns: np.ndarray,
    window: int,
    step: int = 1,
    positions: Optional[Iterable[int]] = None,
) -> pd.DataFrame:
    """Hitung H, alpha, dan Directional Efficiency Ratio secara rolling kausal."""
    x = np.asarray(log_returns, dtype=float)
    n = x.size
    cols = ["index", "hurst", "dfa_alpha", "er_full", "er_128", "er_64"]
    if n < window:
        return pd.DataFrame(columns=cols)

    idx: List[int] = (
        list(positions) if positions is not None else list(range(window - 1, n, step))
    )
    valid_idx = [int(t) for t in idx if window - 1 <= t < n]
    if not valid_idx:
        return pd.DataFrame(columns=cols)

    er_dict = compute_rolling_er(x, valid_idx, window=window)
    rows = []
    for i, t in enumerate(valid_idx):
        seg = x[t - window + 1 : t + 1]
        rows.append(
            {
                "index": t,
                "hurst": hurst_rs(seg),
                "dfa_alpha": dfa_alpha(seg),
                "er_full": float(er_dict["er_full"][i]),
                "er_128": float(er_dict["er_128"][i]),
                "er_64": float(er_dict["er_64"][i]),
            }
        )
    return pd.DataFrame(rows, columns=cols)


def fbm_increments(n: int, hurst: float, seed: int = 0) -> np.ndarray:
    """Bangkitkan fractional Gaussian noise dengan H diketahui (Davies-Harte)."""
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

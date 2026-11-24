"""Fitur struktural untuk identifikasi regime."""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from app.services.swt import causal_swt_at

# Konfigurasi lag dan horizon.
RETURN_LAGS = (1, 2, 3, 4, 5, 8, 10, 15, 20, 30, 50)
ABS_LAGS = (1, 2, 5, 10, 20)
VR_HORIZONS = (2, 3, 4, 6, 8, 12, 16, 24, 32, 48)
SWT_FRACTIONS = (1.0, 0.5, 0.25)
SWT_LEVELS_KEPT = 4

FEATURE_DIM = (
    len(RETURN_LAGS)
    + len(ABS_LAGS)
    + len(VR_HORIZONS)
    + 1  # kemiringan VR terhadap log q
    + len(SWT_FRACTIONS) * SWT_LEVELS_KEPT
    + 5  # statistik sebaran
    + 6  # Directional Efficiency Ratio (Kaufman ER) & Trend t-Stat / Signed Slope
)


def feature_names() -> List[str]:
    """Nama tiap kolom fitur, untuk menafsirkan feature importance."""
    names = [f"ac_ret_lag{l}" for l in RETURN_LAGS]
    names += [f"ac_abs_lag{l}" for l in ABS_LAGS]
    names += [f"vr_q{q}" for q in VR_HORIZONS]
    names += ["vr_slope"]
    for frac in SWT_FRACTIONS:
        names += [f"swt_energy_w{frac}_d{i}" for i in range(SWT_LEVELS_KEPT)]
    names += ["sign_flip_rate", "kurtosis", "skewness", "mad_over_std", "vol_ratio_half"]
    names += ["er_full", "er_128", "er_64", "trend_tstat_full", "trend_tstat_128", "signed_trend_slope"]
    return names


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 3 or b.size < 3:
        return 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        c = np.corrcoef(a, b)[0, 1]
    return float(c) if np.isfinite(c) else 0.0


def variance_ratio(segment: np.ndarray, q: int) -> float:
    """VR(q) = Var(agregat q) / (q · Var(1))."""
    n = segment.size // q * q
    if n < q * 4:
        return 1.0
    aggregated = segment[:n].reshape(-1, q).sum(axis=1)
    base_var = segment[:n].var()
    if base_var <= 0:
        return 1.0
    return float(aggregated.var() / (q * base_var))


def compute_features(
    log_returns: np.ndarray,
    t: int,
    window: int,
    swt_level: int = 4,
) -> List[float]:
    """Vektor fitur struktural pada indeks t, hanya dari data ≤ t."""
    start = max(0, t - window + 1)
    seg = np.asarray(log_returns[start : t + 1], dtype=float)
    seg = seg[np.isfinite(seg)]
    if seg.size < 64:
        return [0.0] * FEATURE_DIM

    absr = np.abs(seg)
    out: List[float] = []

    for lag in RETURN_LAGS:
        out.append(_safe_corr(seg[:-lag], seg[lag:]) if seg.size > lag + 2 else 0.0)
    for lag in ABS_LAGS:
        out.append(_safe_corr(absr[:-lag], absr[lag:]) if absr.size > lag + 2 else 0.0)

    vrs = [variance_ratio(seg, q) for q in VR_HORIZONS]
    out.extend(vrs)
    # Kemiringan VR terhadap log q merangkum arah persistensi lintas horizon.
    out.append(float(np.polyfit(np.log(VR_HORIZONS), vrs, 1)[0]))

    for frac in SWT_FRACTIONS:
        sub_window = max(64, int(window * frac))
        coeffs = causal_swt_at(log_returns, t, level=swt_level, window=sub_window)
        detail_keys = sorted(k for k in coeffs if k.startswith("detail"))
        energies = [abs(coeffs[k]) for k in detail_keys] or [0.0]
        total = sum(energies) or 1.0
        normalized = [e / total for e in energies[:SWT_LEVELS_KEPT]]
        normalized += [0.0] * (SWT_LEVELS_KEPT - len(normalized))
        out.extend(normalized)

    std = float(seg.std())
    var = float(seg.var())
    out.append(float(((seg[1:] * seg[:-1]) < 0).mean()))
    out.append(float(((seg - seg.mean()) ** 4).mean() / (var**2 + 1e-12)))
    out.append(float(((seg - seg.mean()) ** 3).mean() / (std**3 + 1e-12)))
    out.append(float(absr.mean() / (std + 1e-12)))
    half = seg.size // 2
    out.append(float(seg[half:].std() / (seg[:half].std() + 1e-12)))

    # Directional Efficiency Ratio.
    w128 = min(128, seg.size)
    w64 = min(64, seg.size)
    seg128 = seg[-w128:]
    seg64 = seg[-w64:]
    std128 = float(seg128.std())
    er_full = float(abs(seg.sum()) / (absr.sum() + 1e-12))
    er_128 = float(abs(seg128.sum()) / (np.abs(seg128).sum() + 1e-12))
    er_64 = float(abs(seg64.sum()) / (np.abs(seg64).sum() + 1e-12))
    trend_tstat_full = float(abs(seg.sum()) / (std * np.sqrt(seg.size) + 1e-12))
    trend_tstat_128 = float(abs(seg128.sum()) / (std128 * np.sqrt(w128) + 1e-12))
    signed_trend_slope = float(seg.sum() / (std * np.sqrt(seg.size) + 1e-12))
    out.extend([er_full, er_128, er_64, trend_tstat_full, trend_tstat_128, signed_trend_slope])

    if len(out) != FEATURE_DIM:  # pragma: no cover - penjaga konsistensi
        out = (out + [0.0] * FEATURE_DIM)[:FEATURE_DIM]
    return out


def build_feature_matrix(
    log_returns: np.ndarray,
    positions: Sequence[int],
    window: int,
    swt_level: int = 4,
) -> np.ndarray:
    """Matriks fitur (n_window, FEATURE_DIM) untuk sekumpulan posisi."""
    rows = [compute_features(log_returns, int(t), window, swt_level) for t in positions]
    if not rows:
        return np.empty((0, FEATURE_DIM), dtype=float)
    return np.asarray(rows, dtype=float)

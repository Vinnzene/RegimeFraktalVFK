"""Stationary Wavelet Transform (SWT) dengan jaminan kausalitas."""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pywt

DEFAULT_WAVELET = "db4"


def _next_pow2(n: int) -> int:
    size = 1
    while size < n:
        size *= 2
    return size


def max_useful_level(n: int, wavelet: str = DEFAULT_WAVELET) -> int:
    """Level SWT maksimum yang masih masuk akal untuk panjang n."""
    if n < 8:
        return 0
    padded = _next_pow2(n)
    return int(min(pywt.swt_max_level(padded), np.floor(np.log2(padded)) - 1))


def _pad_to_pow2(x: np.ndarray) -> np.ndarray:
    """Padding kiri ke panjang 2^k memakai mode 'symmetric'."""
    n = x.size
    size = _next_pow2(n)
    if size == n:
        return x
    pad = size - n
    head = x[:pad][::-1] if pad <= n else np.resize(x[::-1], pad)
    return np.concatenate([head, x])


def swt_decompose(x: np.ndarray, level: int, wavelet: str = DEFAULT_WAVELET) -> Dict[str, np.ndarray]:
    """Dekomposisi SWT satu blok data. Mengembalikan approx + detail per level."""
    x = np.asarray(x, dtype=float)
    n = x.size
    lvl = min(level, max_useful_level(n, wavelet))
    if lvl < 1:
        return {"approx": x.copy()}

    padded = _pad_to_pow2(x)
    offset = padded.size - n
    coeffs = pywt.swt(padded, wavelet, level=lvl, trim_approx=False, norm=False)

    out: Dict[str, np.ndarray] = {}
    # pywt.swt mengurutkan dari level terkasar ke terhalus.
    for i, (_, cD) in enumerate(coeffs):
        detail_level = lvl - i
        out[f"detail_{detail_level}"] = np.asarray(cD)[offset:]
    out["approx"] = np.asarray(coeffs[0][0])[offset:]
    return out


def causal_swt_at(
    x: np.ndarray,
    t: int,
    level: int,
    window: Optional[int] = None,
    wavelet: str = DEFAULT_WAVELET,
) -> Dict[str, float]:
    """Koefisien SWT pada indeks t, dihitung HANYA dari data x[..t]."""
    x = np.asarray(x, dtype=float)
    if t < 0 or t >= x.size:
        raise IndexError(f"t={t} di luar rentang deret (n={x.size})")
    start = 0 if window is None else max(0, t - window + 1)
    seg = x[start : t + 1]
    if seg.size < 8:
        return {"approx": float(seg[-1]) if seg.size else float("nan")}
    dec = swt_decompose(seg, level=level, wavelet=wavelet)
    return {k: float(v[-1]) for k, v in dec.items()}



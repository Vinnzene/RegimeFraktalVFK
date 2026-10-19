"""Stationary Wavelet Transform (SWT) dengan jaminan kausalitas.

Masalah yang dihindari:
    `pywt.swt` memakai filter simetris + padding sehingga koefisien pada indeks
    t ikut menyerap sampel setelah t. Menghitung SWT sekali pada seluruh deret
    lalu memotongnya per window akan memasukkan informasi masa depan ke fitur
    model (look-ahead bias) tanpa terlihat jelas.

Solusi:
    `causal_swt_at` menghitung ulang SWT hanya dari data <= t, lalu mengambil
    koefisien pada ujung kanan window. Konsekuensinya lebih mahal secara
    komputasi, tapi properti kausal terjaga dan bisa diuji
    (lihat backend/tests/test_causal_swt.py).
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pywt

DEFAULT_WAVELET = "db4"


def _next_pow2(n: int) -> int:
    size = 1
    while size < n:
        size *= 2
    return size


def max_useful_level(n: int, wavelet: str = DEFAULT_WAVELET) -> int:
    """Level SWT maksimum yang masih masuk akal untuk panjang n.

    Dihitung dari panjang SETELAH padding ke 2^k, karena itulah panjang yang
    benar-benar masuk ke pywt.swt.
    """
    if n < 8:
        return 0
    padded = _next_pow2(n)
    return int(min(pywt.swt_max_level(padded), np.floor(np.log2(padded)) - 1))


def _pad_to_pow2(x: np.ndarray) -> np.ndarray:
    """Padding kiri ke panjang 2^k memakai mode 'symmetric'.

    Padding dilakukan di SISI KIRI (masa lalu) supaya ujung kanan window —
    yaitu titik t yang kita ambil koefisiennya — tidak terkontaminasi nilai
    buatan.
    """
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
    for i, (cA, cD) in enumerate(coeffs):
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
    """Koefisien SWT pada indeks t, dihitung HANYA dari data x[..t].

    Ini fungsi yang dipakai untuk membangun fitur model. Tidak ada satu pun
    sampel setelah t yang masuk ke perhitungan.
    """
    x = np.asarray(x, dtype=float)
    if t < 0 or t >= x.size:
        raise IndexError(f"t={t} di luar rentang deret (n={x.size})")
    start = 0 if window is None else max(0, t - window + 1)
    seg = x[start : t + 1]
    if seg.size < 8:
        return {"approx": float(seg[-1]) if seg.size else float("nan")}
    dec = swt_decompose(seg, level=level, wavelet=wavelet)
    return {k: float(v[-1]) for k, v in dec.items()}


def causal_swt_series(
    x: np.ndarray,
    level: int,
    window: int,
    step: int = 1,
    wavelet: str = DEFAULT_WAVELET,
) -> Dict[str, List[float]]:
    """Deret koefisien SWT kausal untuk banyak titik t sekaligus."""
    x = np.asarray(x, dtype=float)
    out: Dict[str, List[float]] = {}
    indices: List[int] = []
    for t in range(window - 1, x.size, step):
        coeffs = causal_swt_at(x, t, level=level, window=window, wavelet=wavelet)
        indices.append(t)
        for key, val in coeffs.items():
            out.setdefault(key, []).append(val)
    out["index"] = [float(i) for i in indices]
    return out

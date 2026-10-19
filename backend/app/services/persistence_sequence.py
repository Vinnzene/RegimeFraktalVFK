"""Sekuens Statistik Persistensi (PS) — input cabang Attention-BiLSTM.

Rancangan dan hipotesis: docs/praregistrasi_persistence_sequence.md.

Untuk sampel bertitik akhir t dan window label L, sekuens berisi T langkah.
Langkah k berakhir di

    e_k = t − (T − 1 − k) · s,      s = (L − W) / (T − 1)

dan setiap kanal dihitung atas sub-window [e_k − W + 1, e_k] (W bar). Langkah
pertama mulai tepat di t − L + 1, langkah terakhir berakhir di t. Seluruh
sekuens memakai bar di dalam window label saja dan tidak ada bar > t.

Kanal (semua tanpa Hurst/DFA):
    vr_2, vr_4, vr_8, vr_16     variance ratio (Lo & MacKinlay)
    ac_1, ac_2, ac_3, ac_5      autokorelasi return
    acabs_1                     autokorelasi |return| (volatility clustering)
    sign_flip                   laju pergantian tanda return
    log_vol                     log simpangan baku sub-window

Implementasi vektor (rolling sum) — setiap kanal dihitung sekali untuk semua
titik akhir, lalu diindeks; hasilnya identik dengan perhitungan per segmen.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

PS_VR_Q = (2, 4, 8, 16)
PS_AC_LAGS = (1, 2, 3, 5)
PS_CHANNELS: List[str] = (
    [f"vr_{q}" for q in PS_VR_Q]
    + [f"ac_{l}" for l in PS_AC_LAGS]
    + ["acabs_1", "sign_flip", "log_vol"]
)


def _csum(x: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(x)])


def _window_sum(c: np.ndarray, end: np.ndarray, length: int) -> np.ndarray:
    """Σ x[end−length+1 .. end] via cumsum c (c[i] = Σ x[:i])."""
    return c[end + 1] - c[end + 1 - length]


def step_offsets(window: int, sub_window: int, seq_len: int) -> np.ndarray:
    """Offset (≤ 0) titik akhir tiap langkah terhadap t."""
    if seq_len < 2 or sub_window > window:
        raise ValueError("butuh seq_len >= 2 dan sub_window <= window")
    span = window - sub_window
    if span % (seq_len - 1):
        raise ValueError(f"(window − sub_window) = {span} harus habis dibagi seq_len − 1 = {seq_len - 1}")
    s = span // (seq_len - 1)
    return -(seq_len - 1 - np.arange(seq_len)) * s


def channel_series(log_ret: np.ndarray, sub_window: int) -> Dict[str, np.ndarray]:
    """Nilai tiap kanal untuk sub-window yang BERAKHIR di setiap indeks e.

    Indeks e < sub_window − 1 (riwayat kurang) bernilai NaN.
    """
    x = np.asarray(log_ret, dtype=float)
    n = x.size
    W = sub_window
    out: Dict[str, np.ndarray] = {}
    ends = np.arange(W - 1, n)
    full = lambda v: np.concatenate([np.full(W - 1, np.nan), v])  # noqa: E731

    c1, c2 = _csum(x), _csum(x * x)
    s1 = _window_sum(c1, ends, W)
    s2 = _window_sum(c2, ends, W)
    mean = s1 / W
    var1 = np.maximum(s2 / W - mean**2, 0.0)

    for q in PS_VR_Q:
        # Agregat q tidak-tumpang-tindih yang berakhir di e: blok [e−q+1..e],
        # [e−2q+1..e−q], ... sebanyak m = W // q blok (rata kanan).
        m = W // q
        blk = np.full(n, np.nan)
        cs = _csum(x)
        idx = np.arange(q - 1, n)
        blk[idx] = cs[idx + 1] - cs[idx + 1 - q]
        vals = np.full(ends.size, np.nan)
        offs = np.arange(m) * q
        for j, e in enumerate(ends):
            b = blk[e - offs]
            vals[j] = b.var()
        with np.errstate(invalid="ignore", divide="ignore"):
            vr = np.where(var1 > 0, vals / (q * var1), 1.0)
        out[f"vr_{q}"] = full(vr)

    def autocorr(series: np.ndarray, lag: int) -> np.ndarray:
        a = series
        prod = np.concatenate([np.full(lag, 0.0), a[lag:] * a[:-lag]])
        cp = _csum(prod)
        ca, ca2 = _csum(a), _csum(a * a)
        L = W - lag
        e = ends
        sxy = cp[e + 1] - cp[e + 1 - L]
        sx = ca[e + 1 - lag] - ca[e + 1 - lag - L]          # a[e−W+1 .. e−lag]
        sy = ca[e + 1] - ca[e + 1 - L]                      # a[e−W+1+lag .. e]
        sxx = ca2[e + 1 - lag] - ca2[e + 1 - lag - L]
        syy = ca2[e + 1] - ca2[e + 1 - L]
        cov = sxy / L - (sx / L) * (sy / L)
        vx = np.maximum(sxx / L - (sx / L) ** 2, 0.0)
        vy = np.maximum(syy / L - (sy / L) ** 2, 0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            r = cov / np.sqrt(vx * vy)
        return full(np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0))

    for lag in PS_AC_LAGS:
        out[f"ac_{lag}"] = autocorr(x, lag)
    out["acabs_1"] = autocorr(np.abs(x), 1)

    flip = np.concatenate([[0.0], ((x[1:] * x[:-1]) < 0).astype(float)])
    cf = _csum(flip)
    out["sign_flip"] = full((cf[ends + 1] - cf[ends + 2 - W]) / (W - 1))
    out["log_vol"] = full(np.log(np.sqrt(var1) + 1e-12))
    return out


def build_persistence_sequences(
    log_ret: np.ndarray,
    positions: Sequence[int],
    window: int,
    sub_window: int = 128,
    seq_len: int = 32,
) -> np.ndarray:
    """Tensor (N, seq_len, len(PS_CHANNELS)). Langkah tanpa riwayat cukup = 0."""
    series = channel_series(log_ret, sub_window)
    mat = np.stack([series[c] for c in PS_CHANNELS], axis=1)
    offs = step_offsets(window, sub_window, seq_len)
    pos = np.asarray(list(positions), dtype=int)
    idx = pos[:, None] + offs[None, :]
    valid = idx >= sub_window - 1
    out = mat[np.clip(idx, 0, None)]
    out[~valid] = 0.0
    return np.nan_to_num(out, nan=0.0)

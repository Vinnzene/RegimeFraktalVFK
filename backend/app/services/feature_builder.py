"""Pembentukan fitur SWT untuk inference.

Fungsi di sini WAJIB menghasilkan tensor yang identik dengan `ml/src/dataset.py`.
Bila keduanya berbeda—urutan channel, panjang sekuens, atau cara padding—model
menerima masukan yang tidak pernah dilihatnya saat training, dan keluarannya
tidak bermakna meski tidak ada error yang muncul.

Karena itu urutan koefisien diambil dengan `sorted(...)` di kedua sisi, dan
`seq_len` dibaca dari metadata artefak, bukan dari angka yang ditulis ulang.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from app.services.swt import causal_swt_at


def build_sequence_features(
    log_returns: np.ndarray,
    positions: Sequence[int],
    level: int,
    seq_len: int,
    swt_window: int,
) -> np.ndarray:
    """Sekuens fitur SWT causal berbentuk (n_samples, seq_len, n_channels).

    Nilai pada langkah ke-k mengacu pada indeks t-(seq_len-1-k), sehingga elemen
    terakhir selalu koefisien pada t. Tidak ada data setelah t yang tersentuh.
    """
    cache: Dict[int, List[float]] = {}

    def coeffs(t: int) -> List[float]:
        if t not in cache:
            c = causal_swt_at(log_returns, t, level=level, window=swt_window)
            cache[t] = [c[k] for k in sorted(c)]
        return cache[t]

    positions = list(positions)
    if not positions:
        return np.empty((0, seq_len, 1), dtype=float)

    width = len(coeffs(positions[0]))
    samples = np.zeros((len(positions), seq_len, width), dtype=float)

    for i, t in enumerate(positions):
        for k in range(seq_len):
            idx = t - (seq_len - 1 - k)
            if idx >= 8:
                samples[i, k] = coeffs(idx)

    return samples


def fit_scaler(features: np.ndarray) -> Dict[str, List[float]]:
    """Hitung mean/std per channel dari SUBSET TRAINING saja.

    Koefisien SWT log-return berskala ~1e-3, sedangkan bobot LSTM diinisialisasi
    untuk masukan berskala ~1. Tanpa penskalaan, gradien nyaris nol sejak awal
    dan model runtuh menebak satu kelas saja.

    Statistik wajib berasal dari data training. Menghitungnya dari seluruh
    dataset akan menyelipkan informasi periode test ke dalam praproses —
    kebocoran yang halus dan sulit terlihat pada metrik.
    """
    if features.size == 0:
        return {"mean": [], "std": []}
    flat = features.reshape(-1, features.shape[-1])
    mean = flat.mean(axis=0)
    std = flat.std(axis=0)
    std[std < 1e-12] = 1.0
    return {"mean": [float(m) for m in mean], "std": [float(s) for s in std]}


def apply_scaler(features: np.ndarray, scaler: Optional[Dict[str, List[float]]]) -> np.ndarray:
    """Terapkan standarisasi; tanpa scaler, kembalikan apa adanya."""
    if not scaler or not scaler.get("mean"):
        return features
    mean = np.asarray(scaler["mean"], dtype=float)
    std = np.asarray(scaler["std"], dtype=float)
    if features.size == 0 or features.shape[-1] != mean.shape[0]:
        return features
    return (features - mean) / std

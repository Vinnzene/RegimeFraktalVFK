"""Fitur struktural untuk identifikasi regime.

Alasan keberadaan modul ini
---------------------------
Koefisien SWT saja hanya mencapai balanced accuracy ~0.38 pada tugas
identifikasi. Sebaliknya, memberikan Hurst dan DFA langsung sebagai fitur
mencapai ~0.99 — tetapi angka itu tidak sah: label regime DIBENTUK dari Hurst
dan DFA lewat aturan ambang, sehingga model hanya menghafal aturan if-else.
Itu label sirkular.

Fitur di bawah dipilih karena memenuhi dua syarat sekaligus:

1. Berkaitan dengan persistensi secara teoretis, sehingga masuk akal dipakai.
2. Dihitung dengan cara yang BERBEDA dari Hurst maupun DFA, sehingga model
   harus benar-benar mempelajari hubungannya, bukan menyalin hasil.

Kelompok fitur
--------------
- **Variance ratio (Lo & MacKinlay, 1988)** — uji baku untuk hipotesis random
  walk. VR(q) = Var(agregat q) / (q · Var(1)). Nilai > 1 menandakan
  persistensi, < 1 menandakan pembalikan, ≈ 1 menyerupai random walk.
  Pada pengujian, kelompok inilah yang paling berpengaruh.
- **Autokorelasi multi-lag** — persistensi meninggalkan jejak pada banyak lag,
  bukan hanya lag-1.
- **Autokorelasi |return|** — clustering volatilitas, sifat yang berbeda dari
  persistensi arah.
- **Rasio energi antar-skala SWT** — distribusi energi lintas frekuensi,
  dihitung pada beberapa ukuran sub-window.
- **Statistik sebaran** — kurtosis, skewness, sign-change rate, rasio
  volatilitas paruh akhir terhadap paruh awal.

Seluruh perhitungan bersifat causal: hanya memakai data sampai indeks t.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from app.services.swt import causal_swt_at

# Konfigurasi lag dan horizon. Diekspor agar nama fitur dapat dibentuk
# konsisten untuk keperluan interpretasi.
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
    return names


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 3 or b.size < 3:
        return 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        c = np.corrcoef(a, b)[0, 1]
    return float(c) if np.isfinite(c) else 0.0


def variance_ratio(segment: np.ndarray, q: int) -> float:
    """VR(q) = Var(agregat q) / (q · Var(1)).

    VR ≈ 1 menyerupai random walk, > 1 persisten, < 1 cenderung berbalik.
    """
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

"""Generalized Hurst exponent H(q) — flow.md langkah 2 & 5.

Kenapa H(q), bukan H tunggal
----------------------------
R/S dan DFA menghasilkan satu angka per window. Angka itu meringkas skala rata
rata saja, sehingga dua window dengan struktur sangat berbeda dapat memiliki H
yang sama: satu didominasi lompatan besar yang jarang, satunya oleh fluktuasi
kecil yang merata.

Metode fungsi struktur (Barabasi & Vicsek, 1991; Di Matteo, 2007) memisahkan
keduanya. Untuk profil kumulatif Y,

    K_q(tau) = < |Y(t + tau) - Y(t)|^q >_t  ~  tau^(q * H(q))

sehingga H(q) diperoleh dari kemiringan regresi log K_q terhadap log tau,
dibagi q. Pada deret monofraktal (fBm murni) H(q) konstan terhadap q; makin
melebar selisihnya, makin multifraktal deretnya.

Fitur turunan yang dipakai model
--------------------------------
- `hq_1`, `hq_2`, `hq_4` — nilai H pada tiga momen.
- `hq_width` = H(1) - H(4) — lebar spektrum, ukuran langsung multifraktalitas.
  Nol berarti monofraktal.
- `hq_slope` — kemiringan H(q) terhadap q lewat regresi, versi kontinu dari
  lebar spektrum yang memakai seluruh titik q.
- `tau_curvature` — kelengkungan fungsi skala tau(q) = q*H(q) - 1. Pada deret
  monofraktal tau(q) linear, sehingga kelengkungan nol.

H(2) di sini TIDAK sama dengan Hurst R/S di `hurst_dfa.py`: estimatornya
berbeda (fungsi struktur vs rescaled range). Kesamaan nilainya justru berguna
sebagai pemeriksaan silang, bukan duplikasi.

Seluruh perhitungan causal: hanya memakai data sampai indeks t.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

DEFAULT_Q = (1.0, 2.0, 4.0)

FEATURE_NAMES: List[str] = [
    "hq_1",
    "hq_2",
    "hq_4",
    "hq_width",
    "hq_slope",
    "tau_curvature",
]

FEATURE_DIM = len(FEATURE_NAMES)


def _scales(n: int, min_tau: int = 2, max_divisor: int = 5, count: int = 12) -> np.ndarray:
    """Skala tau ter-spasi logaritmik, dibatasi n/max_divisor.

    Batas atas penting: pada tau mendekati n hanya tersisa segelintir pasangan
    sehingga rata-rata momennya ditentukan oleh derau, bukan oleh skala.
    """
    max_tau = n // max_divisor
    if max_tau <= min_tau:
        return np.array([], dtype=int)
    taus = np.unique(
        np.floor(np.logspace(np.log10(min_tau), np.log10(max_tau), count)).astype(int)
    )
    return taus[taus >= min_tau]


def structure_function(profile: np.ndarray, tau: int, q: float) -> float:
    """K_q(tau) = rata-rata |Y(t+tau) - Y(t)|^q."""
    if tau <= 0 or profile.size <= tau:
        return np.nan
    increments = np.abs(profile[tau:] - profile[:-tau])
    increments = increments[np.isfinite(increments) & (increments > 0)]
    if increments.size < 3:
        return np.nan
    # Momen dihitung lewat rata-rata log agar orde tinggi tidak kehilangan
    # ketelitian: pada q = 4 dan increment berskala ~1e-3, |dY|^q menyentuh
    # ~1e-12 dan penjumlahan langsung mulai didominasi satu-dua nilai terbesar.
    log_inc = np.log(increments)
    shift = float(log_inc.max())
    moment = float(np.mean(np.exp(q * (log_inc - shift))))
    if moment <= 0:
        return np.nan
    return float(np.exp(np.log(moment) + q * shift))


def generalized_hurst(
    log_returns: np.ndarray,
    q: float,
    min_tau: int = 2,
    count: int = 12,
) -> float:
    """H(q) dari log-return lewat fungsi struktur pada profil kumulatifnya.

    Input adalah log-return (stasioner); profilnya — jumlah kumulatif — yang
    berperilaku seperti fractional Brownian motion dan menjadi objek fungsi
    struktur. Memberi harga level langsung akan menambah unit root kedua.
    """
    x = np.asarray(log_returns, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 32 or q <= 0:
        return np.nan

    profile = np.cumsum(x - x.mean())
    taus = _scales(profile.size, min_tau=min_tau, count=count)
    if taus.size < 3:
        return np.nan

    values = np.array([structure_function(profile, int(t), q) for t in taus])
    ok = np.isfinite(values) & (values > 0)
    if ok.sum() < 3:
        return np.nan

    slope = np.polyfit(np.log(taus[ok]), np.log(values[ok]), 1)[0]
    return float(slope / q)


def hq_spectrum(
    log_returns: np.ndarray,
    qs: Sequence[float] = DEFAULT_Q,
    min_tau: int = 2,
    count: int = 12,
) -> Dict[float, float]:
    """H(q) untuk beberapa orde momen sekaligus."""
    return {
        float(q): generalized_hurst(log_returns, float(q), min_tau=min_tau, count=count)
        for q in qs
    }


def compute_features(
    log_returns: np.ndarray,
    t: int,
    window: int,
    qs: Sequence[float] = DEFAULT_Q,
) -> List[float]:
    """Vektor fitur multifraktal pada indeks t, hanya dari data <= t."""
    start = max(0, t - window + 1)
    seg = np.asarray(log_returns[start : t + 1], dtype=float)
    seg = seg[np.isfinite(seg)]
    if seg.size < 64:
        return [0.0] * FEATURE_DIM

    spectrum = hq_spectrum(seg, qs=qs)
    values = [spectrum.get(float(q), np.nan) for q in qs]
    if not all(np.isfinite(v) for v in values):
        return [0.0] * FEATURE_DIM

    q_arr = np.asarray([float(q) for q in qs], dtype=float)
    h_arr = np.asarray(values, dtype=float)

    width = float(h_arr[0] - h_arr[-1])
    slope = float(np.polyfit(q_arr, h_arr, 1)[0])

    # tau(q) = q*H(q) - 1 linear pada deret monofraktal; koefisien kuadratnya
    # mengukur seberapa jauh deret menyimpang dari sifat itu.
    tau_q = q_arr * h_arr - 1.0
    curvature = float(np.polyfit(q_arr, tau_q, 2)[0]) if q_arr.size >= 3 else 0.0

    out = [float(h_arr[0]), float(h_arr[1]), float(h_arr[-1]), width, slope, curvature]
    return [v if np.isfinite(v) else 0.0 for v in out]


def build_feature_matrix(
    log_returns: np.ndarray,
    positions: Sequence[int],
    window: int,
    qs: Sequence[float] = DEFAULT_Q,
) -> np.ndarray:
    """Matriks fitur (n_window, FEATURE_DIM) untuk sekumpulan posisi."""
    rows = [compute_features(log_returns, int(t), window, qs=qs) for t in positions]
    if not rows:
        return np.empty((0, FEATURE_DIM), dtype=float)
    return np.asarray(rows, dtype=float)


def feature_names() -> List[str]:
    return list(FEATURE_NAMES)


def rolling_hq(
    log_returns: np.ndarray,
    window: int,
    step: int = 1,
    qs: Sequence[float] = DEFAULT_Q,
    positions: Sequence[int] | None = None,
) -> List[Dict[str, float]]:
    """Deret H(q) rolling untuk ditampilkan di panel multifraktalitas."""
    x = np.asarray(log_returns, dtype=float)
    idx = (
        list(positions)
        if positions is not None
        else list(range(window - 1, x.size, max(1, step)))
    )
    out: List[Dict[str, float]] = []
    for t in idx:
        if t < window - 1 or t >= x.size:
            continue
        seg = x[max(0, t - window + 1) : t + 1]
        spectrum = hq_spectrum(seg, qs=qs)
        row: Dict[str, float] = {"index": int(t)}
        for q, val in spectrum.items():
            row[f"hq_{int(q)}"] = float(val) if np.isfinite(val) else float("nan")
        finite = [v for v in spectrum.values() if np.isfinite(v)]
        row["hq_width"] = (
            float(spectrum[float(qs[0])] - spectrum[float(qs[-1])])
            if len(finite) == len(qs)
            else float("nan")
        )
        out.append(row)
    return out

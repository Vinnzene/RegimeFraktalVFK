"""Fitur mikrostruktur dari order flow.

Latar belakang
--------------
PRD HR-SOAB mengusulkan penambahan sinyal mikrostruktur sebagai leading
indicator perubahan regime. Order Book Imbalance (OBI) memerlukan arsip
order book L2 yang untuk BTC/USDT spot tidak tersedia di Binance Vision
(`bookTicker` dan `bookDepth` spot mengembalikan HTTP 404; hanya futures yang
tersedia, dan itu pasangan berbeda).

Order Flow Imbalance (OFI) tetap dapat dihitung penuh sejak 2019, karena
respons kline Binance sudah memuat `takerBuyBaseAssetVolume`:

    OFI_t = (V_buy − V_sell) / (V_buy + V_sell)

dengan V_buy = volume taker sisi beli, V_sell = volume − V_buy. Nilai berkisar
[−1, +1]: positif berarti tekanan beli agresif mendominasi.

Hipotesis awal
--------------
Regime persistent diduga lahir dari aliran order yang searah dan berkelanjutan,
sedangkan regime anti-persistent dari aliran yang berbalik-balik. Sifat itu
diperkirakan terlihat pada struktur temporal OFI — autokorelasi, variance ratio,
dan kegigihan tandanya.

Hasil pengujian: hipotesis TIDAK terdukung
------------------------------------------
Ablation pada BTC/USDT 1H, konfigurasi identik kecuali ada/tidaknya OFI:

    fitur                    dim   akurasi       BA   macro F1
    SWT saja                 160    0.5899   0.5632     0.5573
    + struktural              44    0.8686   0.8584     0.8636   <- terbaik
    + struktural + OFI        70    0.8399   0.8230     0.8305
    OFI saja                  26    0.6020   0.5544     0.5156

Penambahan OFI justru MENURUNKAN akurasi (biner 0.8686 -> 0.8399; tiga kelas
0.6895 -> 0.6814). Fitur OFI memperoleh 28,4% feature importance namun tetap
memperburuk hasil — pola khas fitur derau yang dipakai pohon keputusan untuk
memecah secara semu. Seleksi hanya 2-8 fitur OFI terbaik pun tidak menolong
(0.8293-0.8391), semuanya masih di bawah konfigurasi tanpa OFI.

Tafsir: persistensi yang diukur Hurst-DFA adalah sifat struktur HARGA pada
rentang window ratusan bar, sedangkan OFI per bar merangkum tekanan beli-jual
sesaat. Keduanya bekerja pada skala waktu yang berbeda.

Modul dipertahankan agar hasil negatif ini dapat direproduksi dan dilaporkan.
Aktifkan lewat `build_dataset(with_orderflow=True, ohlcv=...)`.

Catatan metodologis: seperti pada `structural_features`, tidak ada satu pun
fitur di sini yang memakai Hurst atau DFA. Label regime dibentuk dari keduanya,
sehingga memakainya sebagai input akan menghasilkan label sirkular.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

# Horizon agregasi untuk variance ratio pada deret OFI.
OFI_VR_HORIZONS = (2, 4, 8, 16)
# Lag autokorelasi OFI.
OFI_LAGS = (1, 2, 3, 5, 10, 20)
# Jendela pendek untuk mengukur pergeseran rezim aliran order.
SHORT_FRACTIONS = (0.5, 0.25)

FEATURE_DIM = (
    len(OFI_LAGS)          # autokorelasi OFI
    + len(OFI_VR_HORIZONS) # variance ratio OFI
    + 6                    # statistik sebaran OFI
    + 3                    # keterkaitan OFI dengan return
    + len(SHORT_FRACTIONS) * 2  # pergeseran mean & volatilitas OFI
    + 3                    # intensitas transaksi
)


def feature_names() -> List[str]:
    names = [f"ofi_ac_lag{l}" for l in OFI_LAGS]
    names += [f"ofi_vr_q{q}" for q in OFI_VR_HORIZONS]
    names += [
        "ofi_mean",
        "ofi_std",
        "ofi_abs_mean",
        "ofi_sign_persistence",
        "ofi_skew",
        "ofi_kurtosis",
    ]
    names += ["ofi_ret_corr", "ofi_ret_corr_lag1", "ofi_lead_ret_corr"]
    for frac in SHORT_FRACTIONS:
        names += [f"ofi_mean_shift_w{frac}", f"ofi_vol_shift_w{frac}"]
    names += ["trade_intensity_ratio", "trade_size_mean", "trade_size_trend"]
    return names


def compute_ofi(volume: np.ndarray, taker_buy: np.ndarray) -> np.ndarray:
    """OFI per bar: (buy − sell) / total, aman terhadap volume nol."""
    volume = np.asarray(volume, dtype=float)
    taker_buy = np.asarray(taker_buy, dtype=float)
    sell = volume - taker_buy
    total = volume
    with np.errstate(divide="ignore", invalid="ignore"):
        ofi = np.where(total > 0, (taker_buy - sell) / total, 0.0)
    return np.nan_to_num(ofi, nan=0.0, posinf=0.0, neginf=0.0)


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 3 or b.size < 3 or a.size != b.size:
        return 0.0
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        c = np.corrcoef(a, b)[0, 1]
    return float(c) if np.isfinite(c) else 0.0


def _variance_ratio(seg: np.ndarray, q: int) -> float:
    n = seg.size // q * q
    if n < q * 4:
        return 1.0
    agg = seg[:n].reshape(-1, q).sum(axis=1)
    base = seg[:n].var()
    return float(agg.var() / (q * base)) if base > 0 else 1.0


def compute_features(
    ofi: np.ndarray,
    log_returns: np.ndarray,
    n_trades: np.ndarray,
    volume: np.ndarray,
    t: int,
    window: int,
) -> List[float]:
    """Vektor fitur order flow pada indeks t, hanya dari data ≤ t.

    Catatan indeks: `ofi`, `n_trades`, dan `volume` berbasis BAR, sedangkan
    `log_returns` lebih pendek satu elemen karena selisih. Pemanggil wajib
    menyelaraskan keduanya sebelum memanggil fungsi ini.
    """
    start = max(0, t - window + 1)
    seg = np.asarray(ofi[start : t + 1], dtype=float)
    ret = np.asarray(log_returns[start : t + 1], dtype=float)
    trades = np.asarray(n_trades[start : t + 1], dtype=float)
    vol = np.asarray(volume[start : t + 1], dtype=float)

    if seg.size < 64:
        return [0.0] * FEATURE_DIM

    out: List[float] = []

    # Autokorelasi OFI — aliran order yang gigih menandakan regime persistent.
    for lag in OFI_LAGS:
        out.append(_safe_corr(seg[:-lag], seg[lag:]) if seg.size > lag + 2 else 0.0)

    # Variance ratio pada OFI: apakah ketidakseimbangan terakumulasi atau saling
    # meniadakan saat diagregasi.
    for q in OFI_VR_HORIZONS:
        out.append(_variance_ratio(seg, q))

    # Statistik sebaran.
    std = float(seg.std())
    out.append(float(seg.mean()))
    out.append(std)
    out.append(float(np.abs(seg).mean()))
    # Kegigihan tanda: porsi bar yang tandanya sama dengan bar sebelumnya.
    out.append(float((np.sign(seg[1:]) == np.sign(seg[:-1])).mean()))
    out.append(float(((seg - seg.mean()) ** 3).mean() / (std**3 + 1e-12)))
    out.append(float(((seg - seg.mean()) ** 4).mean() / (seg.var() ** 2 + 1e-12)))

    # Keterkaitan OFI dengan return, termasuk kemungkinan OFI mendahului harga.
    m = min(seg.size, ret.size)
    a, b = seg[-m:], ret[-m:]
    out.append(_safe_corr(a, b))
    out.append(_safe_corr(a[:-1], b[1:]) if m > 3 else 0.0)  # OFI(t) vs return(t+1)
    out.append(_safe_corr(a[1:], b[:-1]) if m > 3 else 0.0)  # return(t) vs OFI(t+1)

    # Pergeseran perilaku aliran order pada jendela yang lebih pendek.
    for frac in SHORT_FRACTIONS:
        k = max(16, int(seg.size * frac))
        recent, earlier = seg[-k:], seg[:-k] if seg.size > k else seg
        out.append(float(recent.mean() - earlier.mean()))
        out.append(float(recent.std() / (earlier.std() + 1e-12)))

    # Intensitas transaksi: jumlah trade dan ukuran rata-rata per trade.
    half = trades.size // 2
    recent_tr = trades[half:].mean() if half else 0.0
    early_tr = trades[:half].mean() if half else 0.0
    out.append(float(recent_tr / (early_tr + 1e-12)))
    size = np.divide(vol, trades, out=np.zeros_like(vol), where=trades > 0)
    out.append(float(size.mean()))
    if size.size > 8:
        slope = float(np.polyfit(np.arange(size.size), size, 1)[0])
    else:
        slope = 0.0
    out.append(slope)

    if len(out) != FEATURE_DIM:  # pragma: no cover - penjaga konsistensi
        out = (out + [0.0] * FEATURE_DIM)[:FEATURE_DIM]
    return [float(v) if np.isfinite(v) else 0.0 for v in out]


def build_feature_matrix(
    ofi: np.ndarray,
    log_returns: np.ndarray,
    n_trades: np.ndarray,
    volume: np.ndarray,
    positions: Sequence[int],
    window: int,
) -> np.ndarray:
    """Matriks fitur order flow (n_window, FEATURE_DIM)."""
    rows = [
        compute_features(ofi, log_returns, n_trades, volume, int(t), window)
        for t in positions
    ]
    if not rows:
        return np.empty((0, FEATURE_DIM), dtype=float)
    return np.asarray(rows, dtype=float)

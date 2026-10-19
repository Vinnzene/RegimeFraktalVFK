"""Pembentukan dataset training — titik paling rawan look-ahead bias.

Tiga aturan yang dijaga di sini:

1. Fitur X_t hanya dari data <= t (SWT causal per window).
2. Target Y_t = Regime(window yang berakhir di t+h) — bukan regime window yang
   sama, supaya tugas model benar-benar prediktif dan bukan meniru rumus
   Hurst-DFA (label sirkular).
3. Sampel dengan target uncertain_rule dibuang, TAPI deret input tidak
   dipotong. Yang hilang adalah barisnya, bukan kontinuitas sekuensnya.
   Di batas split dibuang purge_gap bar agar window train tidak tumpang tindih
   dengan window test.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import REGIME_CLASSES, get_config  # noqa: E402
from app.services.feature_builder import (  # noqa: E402
    apply_scaler,
    build_sequence_features,
    fit_scaler,
)
from app.services.multifractal import (  # noqa: E402
    build_feature_matrix as build_multifractal_matrix,
)
from app.services.multifractal import feature_names as multifractal_names  # noqa: E402
from app.services.orderflow_features import (  # noqa: E402
    build_feature_matrix as build_orderflow_matrix,
)
from app.services.orderflow_features import compute_ofi  # noqa: E402
from app.services.orderflow_features import feature_names as orderflow_names  # noqa: E402
from app.services.structural_features import (  # noqa: E402
    build_feature_matrix,
    feature_names,
)
from app.services.hurst_dfa import rolling_hurst_dfa, to_log_return  # noqa: E402
from app.services.regime_labeling import (  # noqa: E402
    build_targets,
    label_series,
    trainable_mask,
)
from app.services.order_flow import (  # noqa: E402
    ORDER_FLOW_CHANNELS,
    bars_to_return_space,
    build_order_flow_bars,
    prepare_order_flow_windows,
)
from app.services.splitting import bars_to_rows, split_indices  # noqa: E402
from app.services.swt import causal_swt_at  # noqa: E402


# Pembentukan fitur memakai fungsi yang sama dengan backend inference.
# Menduplikasinya di dua tempat pernah menjadi sumber ketidakcocokan senyap:
# model menerima tensor berbeda dari yang dilihatnya saat training tanpa ada
# error yang muncul.
build_features = build_sequence_features


def build_dataset(
    close: np.ndarray,
    seq_len: int = 32,
    step: int | None = None,
    h_bars: int | None = None,
    classes: Sequence[str] | None = None,
    with_structural: bool = True,
    with_multifractal: bool = True,
    with_orderflow: bool = False,
    ohlcv: "pd.DataFrame | None" = None,
    return_hurst: bool = False,
    with_orderflow_seq: bool = False,
    cvd_window: int | None = None,
    cvd_method: str = "zscore",
    purge_bars_override: int | None = None,
    threshold_source: str = "full_history",
) -> Dict[str, Any]:
    """Rakit X, Y, dan indeks split dari deret harga penutupan.

    Parameter
    ---------
    h_bars
        Menimpa `model.h` dari config. Nilai 0 berarti tugas IDENTIFIKASI:
        target adalah regime window yang sedang diamati. Nilai > 0 berarti
        tugas PREDIKSI ke depan sejauh h bar.
    classes
        Subset kelas yang dipakai. Memberi ["persistent", "anti_persistent"]
        menghasilkan tugas biner; window di luar daftar itu dikeluarkan.
    with_structural
        Menyertakan fitur struktural (variance ratio, autokorelasi multi-lag,
        energi antar-skala) di samping sekuens SWT. Fitur ini menaikkan
        balanced accuracy identifikasi dari ~0.38 ke ~0.61 tanpa memakai
        Hurst/DFA sebagai input — lihat app/services/structural_features.py.
    with_multifractal
        Menyertakan generalized Hurst H(q) untuk q = 1, 2, 4 beserta lebar
        spektrumnya (flow.md langkah 2 & 5). H(q) dihitung lewat fungsi
        struktur, estimator yang BERBEDA dari R/S maupun DFA yang membentuk
        label, sehingga tidak menjadikan label sirkular. Yang ditambahkan
        adalah informasi multifraktalitas — bagaimana persistensi berubah
        antar orde momen — yang tidak tertangkap oleh H tunggal.
    return_hurst
        Ikut mengembalikan nilai Hurst dan DFA kontinu per split sebagai target
        auxiliary untuk head regresi (flow.md langkah 6). Nilai ini TIDAK boleh
        dipakai sebagai fitur; ia hanya sah sebagai target.
    with_orderflow
        Menyertakan fitur mikrostruktur dari Order Flow Imbalance. Memerlukan
        `ohlcv` yang memuat kolom `taker_buy_volume` dan `n_trades`.

        Bawaannya False berdasarkan hasil ablation: penambahan 26 fitur OFI
        MENURUNKAN akurasi identifikasi pada 1H — biner 0.8686 → 0.8399,
        tiga kelas 0.6895 → 0.6814. Fitur OFI memperoleh 28,4% feature
        importance namun tetap memperburuk hasil, pola khas fitur derau yang
        dipakai pohon untuk memecah secara semu. OFI sendirian hanya mencapai
        0.6020 (biner), hampir setara tebakan mayoritas.

        Parameter dipertahankan agar hasil negatif ini dapat direproduksi dan
        dilaporkan, bukan dihapus diam-diam.
    ohlcv
        DataFrame OHLCV lengkap. Diperlukan bila `with_orderflow` atau
        `with_orderflow_seq` aktif.
    with_orderflow_seq
        Menyiapkan input branch order flow SEKUENSIAL (OFI, CVD) berbentuk
        (N, seq_len, 2) dengan indeks yang identik dengan sekuens SWT. Input
        SWT, label, mask, dan split TIDAK berubah. Hasil tersedia lewat kunci
        `orderflow` (per split) dan `full` (seluruh baris, untuk timeline).
    cvd_window
        Panjang rolling window (bar) untuk normalisasi z-score CVD. Bawaan:
        panjang window Hurst-DFA, sehingga CVD dinilai pada rentang yang sama
        dengan window yang diberi label.
    purge_bars_override
        Purge gap eksplisit dalam bar. Dipakai eksperimen ablation agar keempat
        model memakai split identik dengan purge yang menutup jangkauan input
        terpanjang (window CVD + seq_len).
    threshold_source
        "full_history" (bawaan skripsi) atau "train_only" (uji sensitivitas bebas kebocoran).
    """
    cfg = get_config()
    target_classes: List[str] = list(classes) if classes else list(REGIME_CLASSES)
    log_ret = to_log_return(close)

    window = min(cfg.analysis.L, max(64, len(log_ret) // 4))
    stride_bars = step or max(1, cfg.analysis.stride_bars)

    effective_h = h_bars if h_bars is not None else cfg.model.h
    purge_bars = (
        cfg.model.purge_gap
        if h_bars is None
        else min(cfg.analysis.L + effective_h, cfg.model.purge_gap)
    )
    if effective_h == 0:
        purge_bars = cfg.analysis.L
    if purge_bars_override is not None:
        purge_bars = purge_bars_override

    metrics = rolling_hurst_dfa(log_ret, window=window, step=stride_bars)
    train_mask = None
    if threshold_source == "train_only":
        purge_rows = bars_to_rows(purge_bars, stride_bars)
        pre_split = split_indices(len(metrics), cfg.split.ratios, purge_rows)
        train_end = pre_split["train"][1]
        train_mask = np.zeros(len(metrics), dtype=bool)
        train_mask[:train_end] = True

    labeled = label_series(
        metrics,
        cfg.analysis.hurst_threshold,
        cfg.analysis.dfa_threshold,
        mode=cfg.analysis.threshold_mode,
        quantiles=cfg.analysis.threshold_quantiles,
        threshold_source=threshold_source,
        train_mask=train_mask,
    )
    labels = labeled["regime"].tolist()
    positions = labeled["index"].astype(int).tolist()

    # h dinyatakan dalam bar; deret label bergerak per stride_bars bar.
    # Konversi memakai helper yang sama dengan router /model/compare supaya
    # horizon evaluasi dan horizon training tidak bisa berbeda diam-diam.
    #
    # h = 0 berarti tugas IDENTIFIKASI: target adalah regime window yang sedang
    # diamati, bukan window di masa depan. Ini bukan label sirkular selama fitur
    # yang dipakai berbeda dari cara label dibentuk — model belajar mengenali
    # regime dari koefisien SWT, sementara label berasal dari Hurst dan DFA.
    effective_h = h_bars if h_bars is not None else cfg.model.h
    h_windows = bars_to_rows(effective_h, stride_bars) if effective_h > 0 else 0
    targets = labels[:] if h_windows == 0 else build_targets(labels, h_windows)
    # Sampel hanya dipakai bila targetnya termasuk kelas yang diminta. Pada mode
    # biner, window random_like ikut tersaring di sini.
    mask = [t in target_classes for t in targets]

    # Target auxiliary untuk head regresi (flow.md langkah 6): nilai Hurst
    # kontinu pada window yang SAMA dengan target klasifikasi. Menggesernya
    # berbeda dari label akan membuat dua head belajar horizon yang berbeda.
    hurst_series = labeled["hurst"].to_numpy(dtype=float)
    if h_windows == 0:
        hurst_targets = hurst_series.copy()
    else:
        shifted = np.full(hurst_series.shape, np.nan, dtype=float)
        if h_windows < hurst_series.size:
            shifted[: hurst_series.size - h_windows] = hurst_series[h_windows:]
        hurst_targets = shifted
    # NaN tidak boleh masuk ke loss. Window yang nilainya tidak terdefinisi
    # sudah tersaring lewat `mask` karena labelnya bukan salah satu kelas,
    # tetapi penggantian ini menjaga array tetap aman bila urutan berubah.
    hurst_targets = np.nan_to_num(hurst_targets, nan=0.5)

    X_all = build_features(
        log_ret, positions, level=cfg.analysis.J, seq_len=seq_len, swt_window=window
    )
    F_all = (
        build_feature_matrix(log_ret, positions, window=window, swt_level=cfg.analysis.J)
        if with_structural
        else np.empty((len(positions), 0), dtype=float)
    )

    # Fitur multifraktal H(q). Ditempel setelah fitur struktural supaya urutan
    # kolom tetap stabil: `feature_names` di bawah mengikuti urutan yang sama,
    # dan artefak lama yang tidak memakainya tetap dapat dibaca berdasarkan
    # jumlah kolom yang tersimpan di metadata.
    mf_names: List[str] = []
    if with_multifractal:
        MF_all = build_multifractal_matrix(log_ret, positions, window=window)
        mf_names = multifractal_names()
        F_all = np.hstack([F_all, MF_all]) if F_all.shape[1] else MF_all

    # Fitur order flow. Penyelarasan indeks penting: `positions` menunjuk ke
    # indeks pada deret LOG-RETURN, sedangkan OFI berbasis BAR. Log-return
    # memangkas satu bar di awal, sehingga bar yang bersesuaian adalah
    # positions + 1.
    of_names: List[str] = []
    if with_orderflow and ohlcv is not None and "taker_buy_volume" in ohlcv.columns:
        vol = ohlcv["volume"].to_numpy(dtype=float)
        taker = ohlcv["taker_buy_volume"].to_numpy(dtype=float)
        trades = ohlcv["n_trades"].to_numpy(dtype=float)
        if float(taker.sum()) > 0:
            ofi_bar = compute_ofi(vol, taker)
            # Sejajarkan ke ruang indeks log-return dengan membuang bar pertama.
            ofi = ofi_bar[1:]
            trades_aligned = trades[1:]
            vol_aligned = vol[1:]
            OF_all = build_orderflow_matrix(
                ofi, log_ret, trades_aligned, vol_aligned, positions, window=window
            )
            of_names = orderflow_names()
            F_all = (
                np.hstack([F_all, OF_all]) if F_all.shape[1] else OF_all
            )

    # Purge gap harus mengikuti horizon yang benar-benar dipakai. Saat h
    # diubah untuk uji sensitivitas, memakai nilai tetap dari config membuat
    # gap terlalu sempit (bocor) atau terlalu lebar (membuang data sia-sia).
    purge_bars = (
        cfg.model.purge_gap
        if h_bars is None
        else min(cfg.analysis.L + effective_h, cfg.model.purge_gap)
    )
    # Pada tugas identifikasi (h = 0) purge tetap sebesar L: window training dan
    # test masih berbagi bar yang sama selama L bar terakhir, sehingga gap itu
    # tetap diperlukan meski tidak ada jarak ke depan.
    if effective_h == 0:
        purge_bars = cfg.analysis.L
    if purge_bars_override is not None:
        purge_bars = purge_bars_override
    split = split_indices(
        len(positions),
        cfg.split.ratios,
        bars_to_rows(purge_bars, stride_bars),
    )
    class_index = {c: i for i, c in enumerate(target_classes)}

    # Scaler dipasang HANYA pada rentang training, lalu diterapkan ke semua
    # split. Menghitungnya dari seluruh data akan membocorkan statistik periode
    # test ke dalam praproses.
    train_start, train_end = split["train"]  # type: ignore[misc]
    train_rows = [i for i in range(train_start, train_end) if mask[i]]
    scaler = fit_scaler(X_all[train_rows]) if train_rows else {"mean": [], "std": []}
    X_all = apply_scaler(X_all, scaler)

    # Fitur struktural dinormalisasi terpisah, dengan statistik dari training
    # saja. Skalanya sangat berbeda antar kolom (korelasi ~1, variance ratio
    # bisa puluhan), jadi tanpa penskalaan kolom besar akan mendominasi.
    if F_all.shape[1] and train_rows:
        f_mean = F_all[train_rows].mean(axis=0)
        f_std = F_all[train_rows].std(axis=0)
        f_std[f_std < 1e-12] = 1.0
        F_all = (F_all - f_mean) / f_std
        feature_scaler = {"mean": f_mean.tolist(), "std": f_std.tolist()}
    else:
        feature_scaler = {"mean": [], "std": []}

    # Branch order flow sekuensial. Deret per bar dibangun kausal (OFI dari
    # candle itu sendiri, CVD dinormalisasi rolling ke belakang), lalu digeser
    # ke ruang indeks log-return dan dipotong dengan indeks yang SAMA dengan
    # sekuens SWT. Scaler dipasang dari baris training saja.
    OFS_all: np.ndarray | None = None
    of_bars = None
    of_scaler: Dict[str, List[float]] = {"mean": [], "std": []}
    of_cvd_window = cvd_window or window
    if with_orderflow_seq:
        if ohlcv is None or "taker_buy_volume" not in ohlcv.columns:
            raise ValueError("with_orderflow_seq memerlukan ohlcv dengan taker_buy_volume")
        if len(ohlcv) != len(close):
            raise ValueError("ohlcv dan close harus berasal dari deret bar yang sama")
        if not np.allclose(ohlcv["close"].to_numpy(dtype=float), np.asarray(close, dtype=float)):
            raise ValueError("kolom close pada ohlcv tidak cocok dengan `close`")
        of_bars = build_order_flow_bars(ohlcv, cvd_window=of_cvd_window, cvd_method=cvd_method)
        of_series = bars_to_return_space(of_bars, ["ofi", "cvd_norm"])
        OFS_all = prepare_order_flow_windows(of_series, positions, seq_len)
        if train_rows:
            of_scaler = fit_scaler(OFS_all[train_rows])
            OFS_all = apply_scaler(OFS_all, of_scaler)

    n_classes = len(target_classes)

    def rows_of(rng: List[int]) -> List[int]:
        start, end = rng
        return [i for i in range(start, end) if mask[i]]

    def take(rng: List[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Tuple (sekuens, fitur, target kelas).

        Bentuknya sengaja tetap 3 elemen meski head regresi sudah ada. Target
        Hurst dikembalikan lewat kunci terpisah `hurst_targets` supaya seluruh
        pemanggil lama — train.py, train_identification.py, walk_forward_study
        — tidak perlu diubah dan tidak bisa diam-diam salah membongkar tuple.
        """
        sel = rows_of(rng)
        if not sel:
            return (
                np.empty((0, seq_len, X_all.shape[2])),
                np.empty((0, F_all.shape[1])),
                np.empty((0, n_classes)),
            )
        y = np.zeros((len(sel), n_classes))
        for j, i in enumerate(sel):
            y[j, class_index[str(targets[i])]] = 1.0
        return X_all[sel], F_all[sel], y

    def take_hurst(rng: List[int]) -> np.ndarray:
        sel = rows_of(rng)
        if not sel:
            return np.empty((0, 1), dtype=float)
        return hurst_targets[sel].reshape(-1, 1)

    result: Dict[str, Any] = {
        "train": take(split["train"]),  # type: ignore[arg-type]
        "validation": take(split["validation"]),  # type: ignore[arg-type]
        "test": take(split["test"]),  # type: ignore[arg-type]
        "split": split,
        "scaler": scaler,
        "feature_scaler": feature_scaler,
        "feature_names": (
            (feature_names() if with_structural else []) + mf_names + of_names
        ),
        "n_structural_features": len(feature_names()) if with_structural else 0,
        "n_multifractal_features": len(mf_names),
        "n_orderflow_features": len(of_names),
        "classes": target_classes,
        "task": "identification" if effective_h == 0 else "forecasting",
        "h_bars": effective_h,
        "h_windows": h_windows,
        "purge_bars": purge_bars,
        "stride_bars": stride_bars,
        "effective_window": window,
        "labels": labels,
        "targets": targets,
        "config_hash": cfg.config_hash,
        "threshold_source": threshold_source,
        "thresholds": {
            "hurst": [float(labeled["hurst_lower"].iloc[0]), float(labeled["hurst_upper"].iloc[0])],
            "dfa": [float(labeled["dfa_lower"].iloc[0]), float(labeled["dfa_upper"].iloc[0])],
        },
    }

    if OFS_all is not None and of_bars is not None:
        def take_of(rng: List[int]) -> np.ndarray:
            sel = rows_of(rng)
            if not sel:
                return np.empty((0, seq_len, OFS_all.shape[2]))
            return OFS_all[sel]

        result["orderflow"] = {
            "train": take_of(split["train"]),  # type: ignore[arg-type]
            "validation": take_of(split["validation"]),  # type: ignore[arg-type]
            "test": take_of(split["test"]),  # type: ignore[arg-type]
            "channels": list(ORDER_FLOW_CHANNELS),
            "scaler": of_scaler,
            "cvd_window": of_cvd_window,
            "cvd_method": cvd_method,
        }
        bar_idx = np.asarray(positions, dtype=int) + 1
        result["full"] = {
            "positions": np.asarray(positions, dtype=int),
            "time": ohlcv["time"].to_numpy()[bar_idx],  # type: ignore[index]
            "close": np.asarray(close, dtype=float)[bar_idx],
            "labels": labels,
            "mask": np.asarray(mask, dtype=bool),
            "X_swt": X_all,
            "X_orderflow": OFS_all,
            "ofi_raw": of_bars["ofi"].to_numpy()[bar_idx],
            "cvd_norm_raw": of_bars["cvd_norm"].to_numpy()[bar_idx],
            "cvd_raw": of_bars["cvd"].to_numpy()[bar_idx],
            "bars": of_bars,
        }
        # Indeks baris (ruang window) untuk tiap split — dipakai sanity check
        # dan pemetaan prediksi kembali ke timeline.
        result["rows"] = {
            "train": rows_of(split["train"]),  # type: ignore[arg-type]
            "validation": rows_of(split["validation"]),  # type: ignore[arg-type]
            "test": rows_of(split["test"]),  # type: ignore[arg-type]
        }

    if return_hurst:
        result["hurst_targets"] = {
            "train": take_hurst(split["train"]),  # type: ignore[arg-type]
            "validation": take_hurst(split["validation"]),  # type: ignore[arg-type]
            "test": take_hurst(split["test"]),  # type: ignore[arg-type]
        }

    return result

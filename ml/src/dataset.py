"""Pembentukan dataset training — titik paling rawan look-ahead bias."""

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
)
from app.services.order_flow import (  # noqa: E402
    ORDER_FLOW_CHANNELS,
    bars_to_return_space,
    build_order_flow_bars,
    prepare_order_flow_windows,
)
from app.services.splitting import bars_to_rows, split_indices  # noqa: E402


# Pembentukan fitur memakai fungsi yang sama dengan backend inference.
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
    threshold_source: str | None = None,
    timeframe: str | None = None,
    soft_consensus: bool = True,
    extra_train_symbols: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """Rakit X, Y, dan indeks split dari deret harga penutupan."""
    cfg = get_config()
    threshold_source = threshold_source or cfg.analysis.threshold_source
    target_classes: List[str] = list(classes) if classes else list(REGIME_CLASSES)
    log_ret = to_log_return(close)

    window = min(cfg.analysis.L, max(64, len(log_ret) // 4))
    if step is not None:
        stride_bars = max(1, int(step))
    elif timeframe == "4h" or (10000 <= len(close) <= 25000):
        # Khusus timeframe 4H gunakan stride = 2.
        stride_bars = 2
    else:
        stride_bars = max(1, cfg.analysis.stride_bars)

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
        soft_consensus=soft_consensus,
    )
    labels = labeled["regime"].tolist()
    positions = labeled["index"].astype(int).tolist()

    # h dinyatakan dalam bar; deret label bergerak per stride_bars bar.
    effective_h = h_bars if h_bars is not None else cfg.model.h
    h_windows = bars_to_rows(effective_h, stride_bars) if effective_h > 0 else 0
    targets = labels[:] if h_windows == 0 else build_targets(labels, h_windows)
    # Sampel hanya dipakai bila targetnya termasuk kelas yang diminta.
    mask = [t in target_classes for t in targets]

    # Target auxiliary untuk head regresi.
    hurst_series = labeled["hurst"].to_numpy(dtype=float)
    if h_windows == 0:
        hurst_targets = hurst_series.copy()
    else:
        shifted = np.full(hurst_series.shape, np.nan, dtype=float)
        if h_windows < hurst_series.size:
            shifted[: hurst_series.size - h_windows] = hurst_series[h_windows:]
        hurst_targets = shifted
    # NaN tidak boleh masuk ke loss.
    hurst_targets = np.nan_to_num(hurst_targets, nan=0.5)

    X_all = build_features(
        log_ret, positions, level=cfg.analysis.J, seq_len=seq_len, swt_window=window
    )
    F_all = (
        build_feature_matrix(log_ret, positions, window=window, swt_level=cfg.analysis.J)
        if with_structural
        else np.empty((len(positions), 0), dtype=float)
    )

    # Fitur multifraktal H(q).
    mf_names: List[str] = []
    if with_multifractal:
        MF_all = build_multifractal_matrix(log_ret, positions, window=window)
        mf_names = multifractal_names()
        F_all = np.hstack([F_all, MF_all]) if F_all.shape[1] else MF_all

    # Fitur order flow.
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

    # Purge gap harus mengikuti horizon yang benar-benar dipakai.
    purge_bars = (
        cfg.model.purge_gap
        if h_bars is None
        else min(cfg.analysis.L + effective_h, cfg.model.purge_gap)
    )
    # Pada tugas identifikasi.
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

    # Scaler dipasang HANYA pada rentang training, lalu diterapkan ke semua split.
    train_start, train_end = split["train"]  # type: ignore[misc]
    train_rows = [i for i in range(train_start, train_end) if mask[i]]
    scaler = fit_scaler(X_all[train_rows]) if train_rows else {"mean": [], "std": []}
    X_all = apply_scaler(X_all, scaler)

    # Fitur struktural dinormalisasi terpisah, dengan statistik dari training saja.
    if F_all.shape[1] and train_rows:
        f_mean = F_all[train_rows].mean(axis=0)
        f_std = F_all[train_rows].std(axis=0)
        f_std[f_std < 1e-12] = 1.0
        F_all = (F_all - f_mean) / f_std
        feature_scaler = {"mean": f_mean.tolist(), "std": f_std.tolist()}
    else:
        feature_scaler = {"mean": [], "std": []}

    # Branch order flow sekuensial.
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
        """Tuple (sekuens, fitur, target kelas)."""
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

    train_tuple = take(split["train"])  # type: ignore[arg-type]
    if extra_train_symbols:
        from app.db.repository import get_repository  # noqa: PLC0415

        repo = get_repository()
        tf_key = timeframe or ("4h" if 10000 <= len(close) <= 25000 else "1h")
        x_tr_list = [train_tuple[0]]
        f_tr_list = [train_tuple[1]]
        y_tr_list = [train_tuple[2]]
        # Batas indeks bar maksimal pada periode Train (sebelum purge_1)
        max_train_bar = int(positions[max(0, split["train"][1] - 1)]) + 1
        for sym in extra_train_symbols:
            try:
                ex_df = repo.get_ohlcv(sym, tf_key)
                ex_close = ex_df["close"].to_numpy(dtype=float)[:max_train_bar]
                if len(ex_close) <= window + 64:
                    continue
                ex_lr = to_log_return(ex_close)
                ex_met = rolling_hurst_dfa(ex_lr, window=window, step=stride_bars)
                ex_lab = label_series(
                    ex_met,
                    cfg.analysis.hurst_threshold,
                    cfg.analysis.dfa_threshold,
                    mode=cfg.analysis.threshold_mode,
                    quantiles=cfg.analysis.threshold_quantiles,
                    threshold_source="full_history",
                    soft_consensus=soft_consensus,
                )
                ex_pos = ex_lab["index"].astype(int).tolist()
                ex_targets = ex_lab["regime"].tolist()
                ex_sel = [idx_i for idx_i, t_val in enumerate(ex_targets) if t_val in target_classes]
                if not ex_sel:
                    continue
                ex_pos_sel = [ex_pos[idx_i] for idx_i in ex_sel]
                ex_X = build_features(ex_lr, ex_pos_sel, level=cfg.analysis.J, seq_len=seq_len, swt_window=window)
                ex_X = apply_scaler(ex_X, scaler)
                ex_F = (
                    build_feature_matrix(ex_lr, ex_pos_sel, window=window, swt_level=cfg.analysis.J)
                    if with_structural
                    else np.empty((len(ex_pos_sel), 0), dtype=float)
                )
                if with_multifractal:
                    ex_MF = build_multifractal_matrix(ex_lr, ex_pos_sel, window=window)
                    ex_F = np.hstack([ex_F, ex_MF]) if ex_F.shape[1] else ex_MF
                if ex_F.shape[1] and feature_scaler["mean"]:
                    ex_F = (ex_F - np.asarray(feature_scaler["mean"])) / np.asarray(feature_scaler["std"])
                ex_y = np.zeros((len(ex_sel), n_classes))
                for j_idx, idx_i in enumerate(ex_sel):
                    ex_y[j_idx, class_index[str(ex_targets[idx_i])]] = 1.0
                x_tr_list.append(ex_X)
                f_tr_list.append(ex_F)
                y_tr_list.append(ex_y)
            except Exception:  # noqa: BLE001
                continue
        train_tuple = (
            np.concatenate(x_tr_list, axis=0),
            np.concatenate(f_tr_list, axis=0),
            np.concatenate(y_tr_list, axis=0),
        )

    result: Dict[str, Any] = {
        "train": train_tuple,
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
        # Indeks baris (ruang window) untuk tiap split — dipakai sanity check.
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

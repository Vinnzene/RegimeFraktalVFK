"""Order flow sekuensial: OFI dan CVD per candle, diselaraskan ke rolling window."""

from __future__ import annotations

from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

EPSILON = 1e-12
TIMEFRAME_SECONDS = {"1h": 3600, "4h": 14400}
ORDER_FLOW_CHANNELS = ("ofi", "cvd")


def _to_seconds(ts: np.ndarray) -> np.ndarray:
    """Normalisasi timestamp ke detik. Binance memakai ms (trade) atau µs (2025+)."""
    ts = np.asarray(ts, dtype=np.int64)
    if ts.size == 0:
        return ts
    peak = int(np.max(ts))
    if peak > 10**15:
        return ts // 1_000_000
    if peak > 10**12:
        return ts // 1000
    return ts


def aggregate_trades_to_candles(
    trades: pd.DataFrame,
    timeframe: str,
    candle_times: Optional[Sequence[int]] = None,
) -> pd.DataFrame:
    """Agregasi trade mentah menjadi volume beli/jual per candle."""
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"timeframe '{timeframe}' tidak didukung")
    step = TIMEFRAME_SECONDS[timeframe]

    ts = _to_seconds(trades["timestamp"].to_numpy())
    qty = trades["quantity"].to_numpy(dtype=float)
    if "is_buyer_maker" in trades.columns:
        flag = trades["is_buyer_maker"]
        if flag.dtype == object:
            flag = flag.astype(str).str.lower().isin(["true", "1"])
        is_sell = np.asarray(flag, dtype=bool)
    elif "side" in trades.columns:
        is_sell = trades["side"].astype(str).str.lower().isin(["sell", "s", "ask"]).to_numpy()
    else:
        raise ValueError("data trade wajib memuat kolom `is_buyer_maker` atau `side`")

    bucket = (ts // step) * step
    frame = pd.DataFrame(
        {
            "time": bucket,
            "buy_volume": np.where(is_sell, 0.0, qty),
            "sell_volume": np.where(is_sell, qty, 0.0),
            "n_trades": 1,
        }
    )
    out = frame.groupby("time", sort=True).sum()
    if candle_times is not None:
        out = out.reindex(pd.Index(np.asarray(candle_times, dtype=np.int64), name="time"))
        out = out.fillna(0.0)
    return out.reset_index()


def buy_sell_from_klines(volume: np.ndarray, taker_buy: np.ndarray) -> Dict[str, np.ndarray]:
    """Pisahkan volume kline menjadi beli (taker buy) dan jual (sisanya)."""
    volume = np.asarray(volume, dtype=float)
    buy = np.clip(np.asarray(taker_buy, dtype=float), 0.0, None)
    sell = np.clip(volume - buy, 0.0, None)
    return {"buy": buy, "sell": sell}


def calculate_trade_ofi(
    buy_volume: np.ndarray, sell_volume: np.ndarray, epsilon: float = EPSILON
) -> np.ndarray:
    """OFI_t = (Buy_t − Sell_t) / (Buy_t + Sell_t + ε), dalam [−1, 1]."""
    buy = np.asarray(buy_volume, dtype=float)
    sell = np.asarray(sell_volume, dtype=float)
    ofi = (buy - sell) / (buy + sell + epsilon)
    return np.nan_to_num(ofi, nan=0.0, posinf=0.0, neginf=0.0)


def calculate_delta_volume(buy_volume: np.ndarray, sell_volume: np.ndarray) -> np.ndarray:
    """DeltaVolume_t = Buy_t − Sell_t."""
    return np.asarray(buy_volume, dtype=float) - np.asarray(sell_volume, dtype=float)


def calculate_cvd(buy_volume: np.ndarray, sell_volume: np.ndarray) -> np.ndarray:
    """CVD_t = CVD_{t−1} + DeltaVolume_t, CVD_{-1} = 0. Nilai absolut, belum dinormalisasi."""
    return np.cumsum(calculate_delta_volume(buy_volume, sell_volume))


def normalize_cvd(
    cvd: np.ndarray,
    window: int,
    method: str = "zscore",
    volume: Optional[np.ndarray] = None,
    epsilon: float = EPSILON,
    min_periods: Optional[int] = None,
) -> np.ndarray:
    """Normalisasi CVD secara KAUSAL terhadap rolling window [t−W+1, t]."""
    cvd = np.asarray(cvd, dtype=float)
    min_periods = min_periods or max(2, window // 4)
    s = pd.Series(cvd)
    if method == "zscore":
        roll = s.rolling(window, min_periods=min_periods)
        out = (s - roll.mean()) / (roll.std(ddof=0) + epsilon)
    elif method == "volume":
        if volume is None:
            raise ValueError("method='volume' memerlukan deret volume")
        vol = pd.Series(np.asarray(volume, dtype=float))
        net = s - s.shift(window).fillna(0.0)
        total = vol.rolling(window, min_periods=1).sum()
        out = net / (total + epsilon)
        out[: min_periods - 1] = np.nan
    else:
        raise ValueError(f"method '{method}' tidak dikenal")
    return np.nan_to_num(out.to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)


def build_order_flow_bars(
    ohlcv: pd.DataFrame,
    cvd_window: int,
    cvd_method: str = "zscore",
) -> pd.DataFrame:
    """Deret order flow per CANDLE dari OHLCV yang memuat `taker_buy_volume`."""
    if "taker_buy_volume" not in ohlcv.columns:
        raise ValueError("OHLCV tidak memuat kolom taker_buy_volume")
    bs = buy_sell_from_klines(ohlcv["volume"].to_numpy(), ohlcv["taker_buy_volume"].to_numpy())
    ofi = calculate_trade_ofi(bs["buy"], bs["sell"])
    delta = calculate_delta_volume(bs["buy"], bs["sell"])
    cvd = np.cumsum(delta)
    cvd_norm = normalize_cvd(
        cvd, window=cvd_window, method=cvd_method, volume=bs["buy"] + bs["sell"]
    )
    return pd.DataFrame(
        {
            "time": ohlcv["time"].to_numpy(),
            "buy_volume": bs["buy"],
            "sell_volume": bs["sell"],
            "ofi": ofi,
            "delta_volume": delta,
            "cvd": cvd,
            "cvd_norm": cvd_norm,
        }
    )


def coverage(ohlcv: pd.DataFrame) -> float:
    """Porsi candle bervolume yang kolom taker_buy-nya terisi."""
    if "taker_buy_volume" not in ohlcv.columns or len(ohlcv) == 0:
        return 0.0
    traded = ohlcv["volume"].to_numpy(dtype=float) > 0
    if not traded.any():
        return 0.0
    filled = ohlcv["taker_buy_volume"].to_numpy(dtype=float) > 0
    return float((filled & traded).sum() / traded.sum())


def prepare_order_flow_windows(
    series: np.ndarray,
    positions: Sequence[int],
    seq_len: int,
) -> np.ndarray:
    """Sekuens (N, seq_len, C) dengan indeks IDENTIK branch SWT."""
    arr = np.asarray(series, dtype=float)
    if arr.ndim == 1:
        arr = arr[:, None]
    pos = np.asarray(list(positions), dtype=int)
    if pos.size == 0:
        return np.empty((0, seq_len, arr.shape[1]), dtype=float)
    offsets = np.arange(seq_len) - (seq_len - 1)
    idx = pos[:, None] + offsets[None, :]
    valid = idx >= 0
    out = arr[np.clip(idx, 0, None)]
    out[~valid] = 0.0
    return out


def bars_to_return_space(bars: pd.DataFrame, columns: Sequence[str]) -> np.ndarray:
    """Buang bar pertama agar sejajar dengan deret log-return (n_bar − 1)."""
    return bars[list(columns)].to_numpy(dtype=float)[1:]

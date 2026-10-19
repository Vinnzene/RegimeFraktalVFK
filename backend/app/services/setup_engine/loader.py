"""Loader data untuk setup engine — read-only terhadap data existing.

Sumber (tidak ada yang ditulis ulang oleh modul ini):

    data/processed/ohlcv_btcusdt_{tf}.parquet
        time (epoch detik, open time UTC), open, high, low, close, volume,
        taker_buy_volume, n_trades. Tersedia: 1h, 4h.

    data/processed/ohlcv_btcusdt_{tf}.parquet untuk 30m / 5m
        BELUM ADA. Loader mendukungnya begitu file ada (format sama).

    ml/artifacts/orderflow_timeline_{tf}.parquet
        Prediksi regime model existing pada rentang OUT-OF-SAMPLE (test):
        time, close, hurst_dfa_regime, model_A..D, model_X_maxprob, ofi,
        cvd, cvd_norm, evaluated. Satu baris per window (stride 4 bar).

    data/processed/regime_btcusdt_{tf}.parquet
        Label referensi Hurst-DFA untuk SELURUH riwayat (bukan prediksi model).

OFI dan CVD dihitung ulang dari taker_buy_volume dengan fungsi existing
`app.services.order_flow` sehingga definisinya identik dengan eksperimen
order flow sebelumnya.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, cast

import numpy as np
import pandas as pd

from app.core.config import ARTIFACTS_DIR, PROCESSED_DIR
from app.services.order_flow import buy_sell_from_klines, calculate_trade_ofi
from app.services.setup_engine.config import SetupEngineConfig, timeframe_seconds
from app.services.setup_engine.data_contract import (
    CONTEXT_CONTRACT,
    MARKET_CONTRACT,
    REGIME_CONTRACT,
    DataContractError,
    choose_resolution_timeframe,
    to_utc_timestamp,
    validate_frame,
)

SYMBOL = "btcusdt"


def ohlcv_path(timeframe: str, base_dir: Optional[Path] = None) -> Path:
    return (base_dir or PROCESSED_DIR) / f"ohlcv_{SYMBOL}_{timeframe}.parquet"


def available_market_timeframes(base_dir: Optional[Path] = None) -> List[str]:
    base = base_dir or PROCESSED_DIR
    out = []
    for p in base.glob(f"ohlcv_{SYMBOL}_*.parquet"):
        tf = p.stem.split("_")[-1]
        try:
            timeframe_seconds(tf)
        except ValueError:
            continue
        out.append(tf)
    return sorted(out, key=timeframe_seconds)


def market_frame_from_ohlcv(raw: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Ubah OHLCV mentah project ke kontrak market (+OFI, +CVD).

    CVD = kumulatif (buy − sell) sejak bar pertama berkas. Nilai absolutnya
    bergantung titik awal; engine hanya boleh memakai SELISIH/kemiringannya.
    """
    if "taker_buy_volume" not in raw.columns:
        raise DataContractError(f"OHLCV {timeframe} tidak memuat taker_buy_volume")
    bs = buy_sell_from_klines(raw["volume"].to_numpy(), raw["taker_buy_volume"].to_numpy())
    delta = bs["buy"] - bs["sell"]
    frame = pd.DataFrame(
        {
            "timestamp": to_utc_timestamp(raw["time"], unit="s").to_numpy(),
            "timeframe": timeframe,
            "open": raw["open"].to_numpy(dtype=float),
            "high": raw["high"].to_numpy(dtype=float),
            "low": raw["low"].to_numpy(dtype=float),
            "close": raw["close"].to_numpy(dtype=float),
            "volume": raw["volume"].to_numpy(dtype=float),
            "buy_volume": bs["buy"],
            "sell_volume": bs["sell"],
            "delta_volume": delta,
            "ofi": calculate_trade_ofi(bs["buy"], bs["sell"]),
            "cvd": np.cumsum(delta),
        }
    )
    if "n_trades" in raw.columns:
        frame["n_trades"] = raw["n_trades"].to_numpy()
    return validate_frame(frame, MARKET_CONTRACT, timeframe)


def load_market(timeframe: str, base_dir: Optional[Path] = None) -> pd.DataFrame:
    path = ohlcv_path(timeframe, base_dir)
    if not path.exists():
        raise FileNotFoundError(f"data market {timeframe} tidak ada: {path}")
    raw = pd.read_parquet(path)
    coverage = float((raw["taker_buy_volume"] > 0).mean()) if "taker_buy_volume" in raw else 0.0
    if coverage < 0.99:
        raise DataContractError(
            f"cakupan order flow {timeframe} hanya {coverage:.1%}; "
            f"jalankan ml/src/prepare_order_flow.py --timeframe {timeframe}"
        )
    return market_frame_from_ohlcv(raw, timeframe)


def regime_frame_from_timeline(
    timeline: pd.DataFrame,
    timeframe: str,
    source: str = "model_A",
) -> pd.DataFrame:
    """Prediksi regime model existing -> kontrak regime.

    `time` pada timeline = open time bar TERAKHIR yang masuk window. Prediksi
    baru diketahui setelah bar itu close, jadi
        available_at = time + durasi(timeframe).
    """
    if source == "hurst_dfa":
        pred = timeline["hurst_dfa_regime"]
        conf = pd.Series(np.nan, index=timeline.index)
    else:
        if source not in timeline.columns:
            raise DataContractError(f"kolom prediksi {source} tidak ada di timeline {timeframe}")
        pred = timeline[source]
        conf = timeline.get(f"{source}_maxprob", pd.Series(np.nan, index=timeline.index))
    ts = to_utc_timestamp(timeline["time"], unit="s")
    frame = pd.DataFrame(
        {
            "timestamp": ts.to_numpy(),
            "timeframe": timeframe,
            "predicted_regime": pred.to_numpy(),
            "confidence": conf.to_numpy(dtype=float),
            "reference_regime": timeline["hurst_dfa_regime"].to_numpy(),
            "available_at": (ts + pd.Timedelta(seconds=timeframe_seconds(timeframe))).to_numpy(),
        }
    )
    if "evaluated" in timeline.columns:
        frame["evaluated"] = timeline["evaluated"].to_numpy(dtype=bool)
    return validate_frame(frame, REGIME_CONTRACT, timeframe)


def load_regime_predictions(
    timeframe: str,
    source: str = "model_A",
    artifacts_dir: Optional[Path] = None,
) -> pd.DataFrame:
    path = (artifacts_dir or ARTIFACTS_DIR) / f"orderflow_timeline_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"prediksi regime {timeframe} tidak ada: {path}. "
            f"Jalankan ml/src/train_orderflow_ablation.py --timeframe {timeframe}"
        )
    return regime_frame_from_timeline(pd.read_parquet(path), timeframe, source)


def attach_regime(
    market: pd.DataFrame,
    regime: pd.DataFrame,
    max_age: Optional[pd.Timedelta] = None,
) -> pd.DataFrame:
    """Lekatkan prediksi regime ke bar market timeframe yang SAMA, tanpa look-ahead.

    Prediksi berstride (satu tiap 4 bar). Setiap bar mendapat prediksi
    terakhir yang `available_at <= close_time` bar itu. Bar sebelum prediksi
    pertama mendapat NaN dan dibuang oleh pemanggil.

    `max_age` membatasi umur prediksi. Tanpa batas, prediksi terakhir akan
    terbawa ke seluruh bar sesudah rentang prediksi berakhir. Bawaan: jarak
    antar-prediksi yang paling sering (stride) — prediksi yang lebih tua dari
    itu berarti ada prediksi yang hilang, bukan regime yang bertahan.
    """
    if market["timeframe"].iloc[0] != regime["timeframe"].iloc[0]:
        raise DataContractError("timeframe market dan regime harus sama")
    if max_age is None:
        diffs = regime["available_at"].diff().dropna()
        max_age = cast(pd.Timedelta, diffs.mode().iloc[0]) if len(diffs) else pd.Timedelta(0)
    right = regime[["available_at", "predicted_regime", "confidence", "reference_regime"]].rename(
        columns={"available_at": "regime_available_at"}
    )
    merged = pd.merge_asof(
        market.sort_values("close_time"),
        right.sort_values("regime_available_at"),
        left_on="close_time",
        right_on="regime_available_at",
        direction="backward",
    )
    bad = merged["regime_available_at"].notna() & (merged["regime_available_at"] > merged["close_time"])
    if bad.any():
        raise DataContractError("prediksi regime dilekatkan sebelum tersedia")
    stale = merged["regime_available_at"].notna() & (
        merged["close_time"] - merged["regime_available_at"] >= max_age
    )
    if stale.any():
        cols = ["predicted_regime", "confidence", "reference_regime", "regime_available_at"]
        merged.loc[stale, cols] = np.nan
    return merged.reset_index(drop=True)


@dataclass
class EngineData:
    """Paket data siap pakai untuk tahap berikutnya."""

    regime_ctx: pd.DataFrame            # REGIME_TIMEFRAME, kontrak CONTEXT
    bias_ctx: pd.DataFrame              # BIAS_TIMEFRAME, kontrak CONTEXT
    setup: Optional[pd.DataFrame]       # SETUP_TIMEFRAME, kontrak MARKET
    resolution: Optional[pd.DataFrame]  # resolusi outcome, kontrak MARKET
    resolution_tf: str
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp
    warnings: List[str] = field(default_factory=list)


def load_engine_data(
    cfg: SetupEngineConfig,
    processed_dir: Optional[Path] = None,
    artifacts_dir: Optional[Path] = None,
) -> EngineData:
    """Muat & validasi seluruh timeframe sesuai config. Tidak ada penulisan."""
    tfs = cfg.timeframes
    warnings: List[str] = []
    avail = available_market_timeframes(processed_dir)

    ctx = {}
    for tf in (tfs.regime, tfs.bias):
        market = load_market(tf, processed_dir)
        reg = load_regime_predictions(tf, cfg.regime.source, artifacts_dir)
        joined = attach_regime(market, reg)
        joined = joined[joined["predicted_regime"].notna()].reset_index(drop=True)
        ctx[tf] = validate_frame(joined, CONTEXT_CONTRACT, tf)

    setup = None
    if tfs.setup in avail:
        setup = load_market(tfs.setup, processed_dir)
    else:
        warnings.append(
            f"Data {tfs.setup} (setup timeframe) belum tersedia di {processed_dir or PROCESSED_DIR}."
        )

    res_tf, msg = choose_resolution_timeframe(tfs.resolution, tfs.setup, avail)
    if msg:
        warnings.append(msg)
    resolution = load_market(res_tf, processed_dir) if res_tf in avail else None

    oos_start = max(ctx[tfs.regime]["regime_available_at"].min(), ctx[tfs.bias]["regime_available_at"].min())
    oos_end = min(ctx[tfs.regime]["close_time"].max(), ctx[tfs.bias]["close_time"].max())
    return EngineData(
        regime_ctx=ctx[tfs.regime],
        bias_ctx=ctx[tfs.bias],
        setup=setup,
        resolution=resolution,
        resolution_tf=res_tf,
        oos_start=oos_start,
        oos_end=oos_end,
        warnings=warnings,
    )

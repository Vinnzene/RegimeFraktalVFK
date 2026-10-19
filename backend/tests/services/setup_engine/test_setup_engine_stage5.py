"""Tahap 5 setup engine: deterministic setup engine 30M."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.setup_engine.config import SetupEngineConfig
from app.services.setup_engine.data_contract import DataContractError
from app.services.setup_engine.directional_bias_engine import Bias
from app.services.setup_engine.setup_engine import SetupRejectionReason, generate_setups


def make_market(n_bars: int) -> pd.DataFrame:
    ts = pd.date_range("2025-01-01 00:00", periods=n_bars, freq="30min", tz="UTC")
    df = pd.DataFrame({
        "timestamp": ts,
        "timeframe": "30m",
        "open": 100_000.0,
        "high": 100_500.0,
        "low": 99_500.0,
        "close": 100_000.0,
        "volume": 100.0,
        "ofi": 0.5,
        "cvd": 10.0
    })
    df["close_time"] = df["timestamp"] + pd.Timedelta(minutes=30)
    return df


def make_bias(market_df: pd.DataFrame, bias_val: str, reason: str = "OK") -> pd.DataFrame:
    # 1H bias stream
    b_ts = market_df["timestamp"].dt.floor("1h").unique()
    return pd.DataFrame({
        "timestamp": b_ts,
        "timestamp_bias": b_ts + pd.Timedelta(hours=1),
        "bias": bias_val,
        "bias_reason": reason
    })


def test_long_setup_flow():
    cfg = SetupEngineConfig()
    cfg.confirmation.required = False
    
    df = make_market(30)
    
    # Swing high di bar 4
    df.loc[4, "high"] = 101_000.0
    
    # Swing low di bar 10
    df.loc[10, "low"] = 99_000.0
    
    # Trigger di bar 18
    df.loc[18, "high"] = 101_500.0
    
    bias_df = make_bias(df, Bias.LONG_BIAS.value)
    
    setups = generate_setups(df, bias_df, cfg)
    
    assert not setups.empty
    valid_setups = setups[setups["setup_valid"] == True]
    assert len(valid_setups) >= 1
    
    setup = valid_setups.iloc[0]
    assert setup["direction"] == "LONG"
    assert setup["entry"] == 101_000.0
    assert setup["stop_loss"] == 99_000.0
    assert pd.notna(setup["take_profit"])


def test_setup_expiration():
    cfg = SetupEngineConfig()
    cfg.execution.max_setup_wait_bars = 2
    cfg.confirmation.required = False
    
    df = make_market(30)
    
    df.loc[4, "high"] = 101_000.0
    df.loc[10, "low"] = 99_000.0
    
    bias_df = make_bias(df, Bias.LONG_BIAS.value)
    
    setups = generate_setups(df, bias_df, cfg)
    assert not setups.empty
    
    expired = setups[setups["setup_rejection_reason"] == SetupRejectionReason.SETUP_EXPIRED.value]
    assert len(expired) >= 1


def test_ofi_cvd_rejection():
    cfg = SetupEngineConfig()
    cfg.confirmation.required = True
    cfg.confirmation.use_ofi = True
    cfg.confirmation.ofi_threshold = 0.8
    cfg.confirmation.ofi_lookback = 3
    
    df = make_market(30)
    df.loc[4, "high"] = 101_000.0
    df.loc[10, "low"] = 99_000.0
    df.loc[18, "high"] = 101_500.0
    
    bias_df = make_bias(df, Bias.LONG_BIAS.value)
    
    setups = generate_setups(df, bias_df, cfg)
    
    rejected = setups[setups["setup_rejection_reason"] == SetupRejectionReason.OFI_NOT_CONFIRMED.value]
    assert len(rejected) >= 1


def test_mode_a_vs_mode_b():
    cfg = SetupEngineConfig()
    
    df = make_market(30)
    df.loc[4, "high"] = 101_000.0
    df.loc[10, "low"] = 99_000.0
    df.loc[18, "high"] = 101_500.0
    bias_df = make_bias(df, Bias.LONG_BIAS.value)
    
    # Mode B: required=True, use_ofi=True
    cfg.confirmation.required = True
    cfg.confirmation.use_ofi = True
    cfg.confirmation.ofi_threshold = 0.9
    setups_b = generate_setups(df, bias_df, cfg)
    assert (setups_b["setup_valid"] == False).all()
    
    # Mode A: required=False, use_ofi=False
    cfg.confirmation.required = False
    cfg.confirmation.use_ofi = False
    setups_a = generate_setups(df, bias_df, cfg)
    assert (setups_a["setup_valid"] == True).any()


def test_bias_change_cancels_setup():
    cfg = SetupEngineConfig()
    df = make_market(30)
    
    df.loc[4, "high"] = 101_000.0
    df.loc[10, "low"] = 99_000.0
    
    bias_df = make_bias(df, Bias.LONG_BIAS.value)
    bias_df.loc[8:, "bias"] = Bias.NEUTRAL.value
    bias_df.loc[8:, "bias_reason"] = "CONFLICTING_REGIME"
    
    setups = generate_setups(df, bias_df, cfg)
    
    cancelled = setups[setups["setup_rejection_reason"] == "CONFLICTING_REGIME"]
    assert len(cancelled) >= 1


def test_no_look_ahead():
    cfg = SetupEngineConfig()
    cfg.confirmation.required = False
    
    df1 = make_market(30)
    df1.loc[4, "high"] = 101_000.0
    df1.loc[10, "low"] = 99_000.0
    df1.loc[18, "high"] = 101_500.0
    
    df2 = df1.copy()
    df2.loc[22, "high"] = 102_000.0
    df2.loc[22, "low"] = 10_000.0
    
    bias_df = make_bias(df1, Bias.LONG_BIAS.value)
    
    s1 = generate_setups(df1, bias_df, cfg)
    s2 = generate_setups(df2, bias_df, cfg)
    
    v1 = s1[s1["setup_valid"] == True].iloc[0]
    v2 = s2[s2["setup_valid"] == True].iloc[0]
    
    assert v1["timestamp_entry"] == v2["timestamp_entry"]
    assert v1["entry"] == v2["entry"]
    assert v1["stop_loss"] == v2["stop_loss"]


def test_mode_a_nan_orderflow():
    """T1.6: Pastikan Mode A menyetel kolom OFI/CVD bernilai NaN."""
    from app.services.setup_engine.setup_engine import generate_setups
    cfg = SetupEngineConfig()
    cfg.confirmation.required = False
    cfg.confirmation.use_ofi = False
    cfg.confirmation.use_cvd = False
    cfg.bias.use_ofi = False
    cfg.bias.use_cvd = False
    
    df = make_market(30)
    df.loc[4, "high"] = 101_000.0
    df.loc[10, "low"] = 99_000.0
    df.loc[18, "high"] = 101_500.0
    bias_df = make_bias(df, Bias.LONG_BIAS.value)
    
    setups = generate_setups(df, bias_df, cfg)
    assert not setups.empty
    valid_setups = setups[setups["setup_valid"] == True]
    assert not valid_setups.empty
    assert valid_setups["ofi_30m"].isna().all()
    assert valid_setups["cvd_30m"].isna().all()


def test_mode_b_raises_on_missing_orderflow():
    """T1.6: Mode B harus melempar ValueError eksplisit jika data orderflow tidak tersedia / 0.0."""
    from app.services.setup_engine.setup_engine import generate_setups
    cfg = SetupEngineConfig()
    cfg.confirmation.required = True
    cfg.confirmation.use_ofi = True
    
    df = make_market(30)
    df["ofi"] = 0.0
    df["cvd"] = 0.0
    bias_df = make_bias(df, Bias.LONG_BIAS.value)
    
    with pytest.raises(ValueError, match="Mode B memerlukan data orderflow nyata"):
        generate_setups(df, bias_df, cfg)

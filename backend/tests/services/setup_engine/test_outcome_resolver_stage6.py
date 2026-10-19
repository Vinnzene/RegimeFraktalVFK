"""Tahap 6: Unit tests for outcome resolver."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from app.services.setup_engine.config import SetupEngineConfig
from app.services.setup_engine.outcome_resolver import resolve_outcomes


def make_market(n_bars: int, freq: str) -> pd.DataFrame:
    ts = pd.date_range("2025-01-01 00:00", periods=n_bars, freq=freq, tz="UTC")
    df = pd.DataFrame({
        "timestamp": ts,
        "timeframe": freq,
        "open": 100_000.0,
        "high": 100_500.0,
        "low": 99_500.0,
        "close": 100_000.0,
        "volume": 100.0,
        "ofi": 0.5,
        "cvd": 10.0
    })
    step = pd.Timedelta(minutes=30) if freq == "30min" else pd.Timedelta(minutes=5)
    df["close_time"] = df["timestamp"] + step
    return df


def make_setups(direction: str, tp: float, sl: float, entry: float, risk: float, rr: float) -> pd.DataFrame:
    return pd.DataFrame([{
        "timestamp_entry": pd.Timestamp("2025-01-01 01:00:00", tz="UTC"),
        "entry": entry,
        "take_profit": tp,
        "stop_loss": sl,
        "direction": direction,
        "rr": rr,
        "risk": risk,
        "setup_valid": True
    }])


def test_tp_first_resolution_long():
    cfg = SetupEngineConfig()
    m30 = make_market(10, "30min")
    m5 = make_market(60, "5min")
    
    setups = make_setups("LONG", 102_000.0, 98_000.0, 100_000.0, 2_000.0, 2.0)
    
    # 01:00 is bar 2 in m30
    # Let's make bar 3 (01:30) hit TP
    m30.loc[3, "high"] = 103_000.0
    
    outcomes = resolve_outcomes(setups, m30, m5, cfg)
    
    assert len(outcomes) == 1
    assert outcomes.iloc[0]["outcome"] == "TP"
    assert outcomes.iloc[0]["r_gross"] == 2.0
    assert outcomes.iloc[0]["R_multiple"] == outcomes.iloc[0]["r_net"]
    assert outcomes.iloc[0]["r_net"] < outcomes.iloc[0]["r_gross"]


def test_sl_first_resolution_long():
    cfg = SetupEngineConfig()
    m30 = make_market(10, "30min")
    m5 = make_market(60, "5min")
    
    setups = make_setups("LONG", 102_000.0, 98_000.0, 100_000.0, 2_000.0, 2.0)
    
    # 01:00 is bar 2 in m30
    # Let's make bar 3 (01:30) hit SL
    m30.loc[3, "low"] = 97_000.0
    
    outcomes = resolve_outcomes(setups, m30, m5, cfg)
    
    assert outcomes.iloc[0]["outcome"] == "SL"
    assert outcomes.iloc[0]["r_gross"] == -1.0
    assert outcomes.iloc[0]["R_multiple"] == outcomes.iloc[0]["r_net"]
    assert outcomes.iloc[0]["r_net"] < outcomes.iloc[0]["r_gross"]


def test_ambiguous_30m_resolved_in_5m_tp_first():
    cfg = SetupEngineConfig()
    m30 = make_market(10, "30min")
    m5 = make_market(60, "5min")
    
    setups = make_setups("LONG", 102_000.0, 98_000.0, 100_000.0, 2_000.0, 2.0)
    
    # Bar 3 in 30M hits BOTH
    m30.loc[3, "high"] = 103_000.0
    m30.loc[3, "low"] = 97_000.0
    
    # 01:30 is index 18 in 5M (18*5 = 90 min)
    # TP first at 01:35 (index 19)
    m5.loc[19, "high"] = 103_000.0
    # SL later at 01:45 (index 21)
    m5.loc[21, "low"] = 97_000.0
    
    outcomes = resolve_outcomes(setups, m30, m5, cfg)
    
    assert outcomes.iloc[0]["outcome"] == "TP"
    assert outcomes.iloc[0]["r_gross"] == 2.0
    assert outcomes.iloc[0]["R_multiple"] == outcomes.iloc[0]["r_net"]
    assert outcomes.iloc[0]["r_net"] < outcomes.iloc[0]["r_gross"]


def test_ambiguous_30m_resolved_in_5m_sl_first():
    cfg = SetupEngineConfig()
    m30 = make_market(10, "30min")
    m5 = make_market(60, "5min")
    
    setups = make_setups("LONG", 102_000.0, 98_000.0, 100_000.0, 2_000.0, 2.0)
    
    # Bar 3 in 30M hits BOTH
    m30.loc[3, "high"] = 103_000.0
    m30.loc[3, "low"] = 97_000.0
    
    # SL first at 01:35 (index 19)
    m5.loc[19, "low"] = 97_000.0
    # TP later at 01:45 (index 21)
    m5.loc[21, "high"] = 103_000.0
    
    outcomes = resolve_outcomes(setups, m30, m5, cfg)
    
    assert outcomes.iloc[0]["outcome"] == "SL"
    assert outcomes.iloc[0]["r_gross"] == -1.0
    assert outcomes.iloc[0]["R_multiple"] == outcomes.iloc[0]["r_net"]
    assert outcomes.iloc[0]["r_net"] < outcomes.iloc[0]["r_gross"]


def test_ambiguous_5m():
    cfg = SetupEngineConfig()
    m30 = make_market(10, "30min")
    m5 = make_market(60, "5min")
    
    setups = make_setups("LONG", 102_000.0, 98_000.0, 100_000.0, 2_000.0, 2.0)
    
    # Bar 3 in 30M hits BOTH
    m30.loc[3, "high"] = 103_000.0
    m30.loc[3, "low"] = 97_000.0
    
    # Bar 19 in 5M hits BOTH
    m5.loc[19, "high"] = 103_000.0
    m5.loc[19, "low"] = 97_000.0
    
    outcomes = resolve_outcomes(setups, m30, m5, cfg)
    
    assert outcomes.iloc[0]["outcome"] == "AMBIGUOUS"
    assert pd.isna(outcomes.iloc[0]["R_multiple"])


def test_missing_5m_data_ambiguous(caplog):
    cfg = SetupEngineConfig()
    m30 = make_market(10, "30min")
    
    setups = make_setups("LONG", 102_000.0, 98_000.0, 100_000.0, 2_000.0, 2.0)
    
    # Bar 3 in 30M hits BOTH
    m30.loc[3, "high"] = 103_000.0
    m30.loc[3, "low"] = 97_000.0
    
    # Pass None for m5
    with caplog.at_level(logging.WARNING):
        outcomes = resolve_outcomes(setups, m30, None, cfg)
    
    assert outcomes.iloc[0]["outcome"] == "AMBIGUOUS"
    assert "Resolusi outcome lebih rendah" in caplog.text


def test_timeout():
    cfg = SetupEngineConfig()
    cfg.execution.max_holding_bars = 4
    
    m30 = make_market(10, "30min")
    m5 = make_market(60, "5min")
    
    setups = make_setups("LONG", 102_000.0, 98_000.0, 100_000.0, 2_000.0, 2.0)
    
    # Set close of the timeout bar to calculate R
    # Entry is at bar 2 (01:00)
    # Timeout at bar 2 + 4 = 6
    m30.loc[6, "close"] = 101_000.0
    
    outcomes = resolve_outcomes(setups, m30, m5, cfg)
    
    assert outcomes.iloc[0]["outcome"] == "TIMEOUT"
    assert outcomes.iloc[0]["r_gross"] == 0.5  # (101000 - 100000) / 2000
    assert outcomes.iloc[0]["R_multiple"] == outcomes.iloc[0]["r_net"]
    assert outcomes.iloc[0]["r_net"] < outcomes.iloc[0]["r_gross"]
    assert outcomes.iloc[0]["exit_price"] == 101_000.0


def test_short_tp_first():
    cfg = SetupEngineConfig()
    m30 = make_market(10, "30min")
    m5 = make_market(60, "5min")
    
    setups = make_setups("SHORT", 98_000.0, 102_000.0, 100_000.0, 2_000.0, 2.0)
    
    m30.loc[3, "low"] = 97_000.0
    
    outcomes = resolve_outcomes(setups, m30, m5, cfg)
    
    assert outcomes.iloc[0]["outcome"] == "TP"
    assert outcomes.iloc[0]["r_gross"] == 2.0
    assert outcomes.iloc[0]["R_multiple"] == outcomes.iloc[0]["r_net"]
    assert outcomes.iloc[0]["r_net"] < outcomes.iloc[0]["r_gross"]


def test_short_sl_first():
    cfg = SetupEngineConfig()
    m30 = make_market(10, "30min")
    m5 = make_market(60, "5min")
    
    setups = make_setups("SHORT", 98_000.0, 102_000.0, 100_000.0, 2_000.0, 2.0)
    
    m30.loc[3, "high"] = 103_000.0
    
    outcomes = resolve_outcomes(setups, m30, m5, cfg)
    
    assert outcomes.iloc[0]["outcome"] == "SL"
    assert outcomes.iloc[0]["r_gross"] == -1.0
    assert outcomes.iloc[0]["R_multiple"] == outcomes.iloc[0]["r_net"]
    assert outcomes.iloc[0]["r_net"] < outcomes.iloc[0]["r_gross"]


def test_short_timeout():
    cfg = SetupEngineConfig()
    cfg.execution.max_holding_bars = 4
    
    m30 = make_market(10, "30min")
    m5 = make_market(60, "5min")
    
    setups = make_setups("SHORT", 98_000.0, 102_000.0, 100_000.0, 2_000.0, 2.0)
    
    m30.loc[6, "close"] = 99_000.0
    
    outcomes = resolve_outcomes(setups, m30, m5, cfg)
    
    assert outcomes.iloc[0]["outcome"] == "TIMEOUT"
    assert outcomes.iloc[0]["r_gross"] == 0.5  # (100000 - 99000) / 2000
    assert outcomes.iloc[0]["R_multiple"] == outcomes.iloc[0]["r_net"]
    assert outcomes.iloc[0]["r_net"] < outcomes.iloc[0]["r_gross"]


def test_fee_slippage_zero_vs_realistic():
    """T1.5: Bandingkan trade tanpa biaya (0 fee, 0 slippage) vs dengan biaya realistis."""
    cfg_zero = SetupEngineConfig(execution={"taker_fee_pct": 0.0, "slippage_ticks": 0, "tick_size": 0.01})
    cfg_real = SetupEngineConfig(execution={"taker_fee_pct": 0.00075, "slippage_ticks": 1, "tick_size": 0.01})
    
    m30 = make_market(10, "30min")
    m5 = make_market(60, "5min")
    setups = make_setups("LONG", 102_000.0, 98_000.0, 100_000.0, 2_000.0, 2.0)
    m30.loc[3, "high"] = 103_000.0
    
    res_zero = resolve_outcomes(setups.copy(), m30.copy(), m5.copy(), cfg_zero)
    res_real = resolve_outcomes(setups.copy(), m30.copy(), m5.copy(), cfg_real)
    
    # Tanpa biaya: r_net == r_gross == 2.0
    assert res_zero.iloc[0]["r_gross"] == 2.0
    assert res_zero.iloc[0]["r_net"] == 2.0
    assert res_zero.iloc[0]["biaya_total"] == 0.0
    assert res_zero.iloc[0]["R_multiple"] == 2.0
    
    # Dengan biaya realistis: r_net < r_gross
    assert res_real.iloc[0]["r_gross"] == 2.0
    assert res_real.iloc[0]["r_net"] < 2.0
    assert res_real.iloc[0]["biaya_total"] > 0.0
    assert res_real.iloc[0]["R_multiple"] == res_real.iloc[0]["r_net"]
    assert res_real.iloc[0]["r_net"] < res_zero.iloc[0]["r_net"]

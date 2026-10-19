"""Tahap 7: Unit tests for walk-forward orchestrator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.setup_engine.config import SetupEngineConfig
from app.services.setup_engine.data_contract import LookAheadError, Regime
from app.services.setup_engine.walk_forward import generate_windows, run_walk_forward, validate_no_lookahead


def test_window_generator():
    cfg = SetupEngineConfig()
    cfg.walk_forward.train_period = "12M"
    cfg.walk_forward.validation_period = "3M"
    cfg.walk_forward.test_period = "1M"
    cfg.walk_forward.step_period = "1M"
    
    start = pd.Timestamp("2024-01-01", tz="UTC")
    end = pd.Timestamp("2025-06-01", tz="UTC")
    assert isinstance(start, pd.Timestamp) and isinstance(end, pd.Timestamp)
    
    windows = generate_windows(start, end, cfg)
    
    assert len(windows) > 0
    w1 = windows[0]
    assert w1["window_id"] == 1
    assert w1["train_end"] == start + pd.DateOffset(months=12)
    assert w1["val_end"] == w1["train_end"] + pd.DateOffset(months=3)
    assert w1["test_end"] == w1["val_end"] + pd.DateOffset(months=1)
    
    # Check chronologically
    for i in range(1, len(windows)):
        prev = windows[i-1]
        curr = windows[i]
        assert curr["window_id"] == prev["window_id"] + 1
        assert curr["train_start"] == prev["train_start"] + pd.DateOffset(months=1)
        assert curr["test_start"] == prev["test_start"] + pd.DateOffset(months=1)
        
    # Check non-overlap train/test within a window
    for w in windows:
        assert w["train_end"] <= w["val_start"]
        assert w["val_end"] <= w["test_start"]
        assert w["test_end"] > w["test_start"]


def make_market(n_bars: int, freq: str, start: str = "2024-01-01 00:00") -> pd.DataFrame:
    ts = pd.date_range(start, periods=n_bars, freq=freq, tz="UTC")
    df = pd.DataFrame({
        "timestamp": ts,
        "timeframe": freq.replace("min", "m"),
        "open": 100_000.0,
        "high": 100_500.0,
        "low": 99_500.0,
        "close": 100_000.0,
        "volume": 100.0,
        "ofi": 0.5,
        "cvd": 10.0
    })
    step = pd.Timedelta(freq.replace("min", "m"))
    df["close_time"] = df["timestamp"] + step
    df["available_at"] = df["close_time"]
    return df


def make_regime(n_bars: int, freq: str, start: str = "2024-01-01 00:00") -> pd.DataFrame:
    ts = pd.date_range(start, periods=n_bars, freq=freq, tz="UTC")
    df = pd.DataFrame({
        "timestamp": ts,
        "timeframe": freq.replace("min", "m"),
        "predicted_regime": Regime.PERSISTENT.value,
        "confidence": 0.8
    })
    step = pd.Timedelta(freq)
    df["close_time"] = df["timestamp"] + step
    df["available_at"] = df["close_time"]
    return df


def mock_compute_bias(m1h, r4, r1, cfg):
    from app.services.setup_engine.directional_bias_engine import Bias
    return pd.DataFrame({
        "timestamp": m1h["timestamp"],
        "close_time": m1h["close_time"],
        "available_at": m1h["close_time"],
        "timestamp_bias": m1h["close_time"],
        "bias": Bias.LONG_BIAS.value,
        "bias_reason": "OK",
        "regime_4h": "PERSISTENT",
        "regime_1h": "PERSISTENT",
        "structure_1h": 1,
        "ofi_1h": 0.5,
        "cvd_1h": 0.5,
        "transition_type": "NORMAL"
    })

def test_one_position_at_a_time(monkeypatch):
    import app.services.setup_engine.walk_forward
    monkeypatch.setattr(app.services.setup_engine.walk_forward, "compute_bias", mock_compute_bias)

    cfg = SetupEngineConfig()
    cfg.walk_forward.train_period = "1D"
    cfg.walk_forward.validation_period = "1D"
    cfg.walk_forward.test_period = "2D"
    cfg.walk_forward.step_period = "1D"
    cfg.confirmation.required = False
    
    start = "2024-01-01 00:00"
    m1h = make_market(120, "1h", start)
    m30 = make_market(240, "30min", start)
    m5 = make_market(24 * 60, "5min", start)
    r4 = make_regime(30, "4h", start)
    r1 = make_regime(120, "1h", start)
    
    # We want two setups to form close to each other.
    # W1 test starts at 2024-01-03 00:00 (index 48 in 1H, 96 in 30M).
    
    # Setup 1
    # Swing high at 96+4, low at 96+10, entry at 96+14
    i = 96
    m30.loc[i+4, "high"] = 101_000.0
    m30.loc[i+10, "low"] = 98_000.0
    m30.loc[i+14, "high"] = 102_000.0  # entry! (101_000)
    
    # Setup 2
    # Swing high at 96+15, low at 96+20, entry at 96+24
    m30.loc[i+15, "high"] = 103_000.0
    m30.loc[i+20, "low"] = 99_500.0
    m30.loc[i+24, "high"] = 104_000.0  # entry 2! (103_000)
    
    # Trade 1 will be held up to max_holding_bars (default 8) because no TP/SL is hit.
    # Entry 1 is at i+14. Exit will be at i+14+8 = i+22.
    # Entry 2 is at i+24.
    # Wait, if exit is at i+22, then at i+24 it's FREE! We want it to be REJECTED.
    # Let's make Setup 2 entry at i+18.
    m30.loc[i+15, "high"] = 100_500.0
    m30.loc[i+20, "low"] = 99_500.0
    m30.loc[i+24, "high"] = 100_500.0
    
    m30.loc[i+16, "low"] = 99_000.0
    m30.loc[i+20, "high"] = 102_500.0 # Entry 2 (102_000 from prev swing high at i+14)
    
    log = run_walk_forward(m1h, m30, m5, r4, r1, cfg)
    
    assert len(log) > 0
    # There should be at least 1 EXISTING_POSITION rejection
    rejections = log[log["setup_rejection_reason"] == "EXISTING_POSITION"]
    assert len(rejections) >= 1


def test_validate_no_lookahead_catches_leak():
    # Make a dummy log
    log = pd.DataFrame({
        "timestamp_bias": [pd.Timestamp("2024-01-01 02:00:00")],
        "timestamp_setup": [pd.Timestamp("2024-01-01 02:30:00")],
        "timestamp_entry": [pd.Timestamp("2024-01-01 01:30:00")],  # LEAK!
        "exit_timestamp": [pd.Timestamp("2024-01-01 03:00:00")],
    })
    with pytest.raises(LookAheadError, match="timestamp_entry mendahului timestamp_bias"):
        validate_no_lookahead(log)
        
    log2 = pd.DataFrame({
        "timestamp_bias": [pd.Timestamp("2024-01-01 02:00:00")],
        "timestamp_setup": [pd.Timestamp("2024-01-01 02:30:00")],
        "timestamp_entry": [pd.Timestamp("2024-01-01 02:30:00")],
        "exit_timestamp": [pd.Timestamp("2024-01-01 02:00:00")],  # LEAK!
    })
    with pytest.raises(LookAheadError, match="exit_timestamp mendahului timestamp_entry"):
        validate_no_lookahead(log2)


def test_setup_expiration_in_full_flow(monkeypatch):
    import app.services.setup_engine.walk_forward
    monkeypatch.setattr(app.services.setup_engine.walk_forward, "compute_bias", mock_compute_bias)
    cfg = SetupEngineConfig()
    cfg.walk_forward.train_period = "1D"
    cfg.walk_forward.validation_period = "1D"
    cfg.walk_forward.test_period = "2D"
    cfg.walk_forward.step_period = "1D"
    cfg.execution.max_setup_wait_bars = 2
    cfg.confirmation.required = False
    
    start = "2024-01-01 00:00"
    m1h = make_market(120, "1h", start)
    m30 = make_market(240, "30min", start)
    m5 = make_market(24 * 60, "5min", start)
    r4 = make_regime(30, "4h", start)
    r1 = make_regime(120, "1h", start)
    
    # W1 test starts at index 96 in 30M.
    i = 96
    m30.loc[i+4, "high"] = 101_000.0
    m30.loc[i+10, "low"] = 99_000.0
    # No entry trigger
    
    log = run_walk_forward(m1h, m30, m5, r4, r1, cfg)
    expired = log[log["setup_rejection_reason"] == "SETUP_EXPIRED"]
    assert len(expired) >= 1


def test_regime_transition_block_in_full_flow(monkeypatch):
    def mock_bias_transition(m1h, r4, r1, cfg):
        from app.services.setup_engine.directional_bias_engine import Bias
        
        b = np.full(len(m1h), Bias.LONG_BIAS.value, dtype=object)
        r = np.full(len(m1h), "OK", dtype=object)
        
        b[55:] = Bias.NEUTRAL.value
        r[55:] = "CONFLICTING_REGIME"
        
        return pd.DataFrame({
            "timestamp": m1h["timestamp"],
            "close_time": m1h["close_time"],
            "available_at": m1h["close_time"],
            "timestamp_bias": m1h["close_time"],
            "bias": b,
            "bias_reason": r,
            "regime_4h": "PERSISTENT",
            "regime_1h": "PERSISTENT",
            "structure_1h": 1,
            "ofi_1h": 0.5,
            "cvd_1h": 0.5,
            "transition_type": "BLOCK_ALL"
        })
        
    import app.services.setup_engine.walk_forward
    monkeypatch.setattr(app.services.setup_engine.walk_forward, "compute_bias", mock_bias_transition)
    cfg = SetupEngineConfig()
    cfg.walk_forward.train_period = "1D"
    cfg.walk_forward.validation_period = "1D"
    cfg.walk_forward.test_period = "2D"
    cfg.walk_forward.step_period = "1D"
    cfg.confirmation.required = False
    
    start = "2024-01-01 00:00"
    m1h = make_market(120, "1h", start)
    m30 = make_market(240, "30min", start)
    m5 = make_market(24 * 60, "5min", start)
    r4 = make_regime(30, "4h", start)
    r1 = make_regime(120, "1h", start)
    
    # Force regime to change
    # W1 test starts at index 48 in 1H (2024-01-03 00:00)
    # Let's change regime_4h to RANDOM_LIKE at index 13 (2024-01-03 04:00)
    r4.loc[13:, "predicted_regime"] = Regime.RANDOM_LIKE.value
    
    i = 96
    # Swing low at 96+10 (2024-01-03 05:00)
    m30.loc[i+4, "high"] = 101_000.0
    m30.loc[i+10, "low"] = 99_000.0
    
    log = run_walk_forward(m1h, m30, m5, r4, r1, cfg)
    
    # Karena 4H menjadi RANDOM_LIKE, 1H PERSISTENT, tabel konteks mengembalikan NEUTRAL
    # Tapi PERSISTENT -> RANDOM_LIKE transition akan menghasilkan BLOCK_ALL sementara waktu (karena perlu confirm)
    # Ini akan memblokir setup.
    blocked = log[log["setup_rejection_reason"] == "CONFLICTING_REGIME"]
    assert len(blocked) >= 1

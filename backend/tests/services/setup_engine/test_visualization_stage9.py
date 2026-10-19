"""Tahap 9: Visualization Tests"""

import pandas as pd
import numpy as np
import os
from app.services.setup_engine.visualization import (
    plot_setup, 
    plot_walk_forward_cumulative_r, 
    plot_regime_setup_distribution, 
    plot_setup_outcome_distribution
)

def test_visualization_smoke_test(tmp_path):
    # Synthetic market data
    ts = pd.date_range("2024-01-01 00:00:00", periods=100, freq="30min", tz="UTC")
    m30 = pd.DataFrame({
        "timestamp": ts,
        "open": np.random.randn(100).cumsum() + 100000,
        "high": np.nan,
        "low": np.nan,
        "close": np.nan,
        "ofi": np.random.randn(100),
        "cvd": np.random.randn(100).cumsum()
    })
    m30["high"] = m30["open"] + 100
    m30["low"] = m30["open"] - 100
    m30["close"] = m30["open"] + 50
    
    # Synthetic trade log
    trade = pd.Series({
        "timestamp_entry": ts[50],
        "exit_timestamp": ts[60],
        "timestamp_setup": ts[48],
        "entry": m30["open"].iloc[50],
        "stop_loss": m30["open"].iloc[50] - 500,
        "take_profit": m30["open"].iloc[50] + 1000,
        "exit_price": m30.loc[60, "close"],
        "direction": "LONG",
        "outcome": "TP",
        "R_multiple": 2.0,
        "RR": 2.0,
        "regime_4h": "PERSISTENT",
        "regime_1h": "PERSISTENT",
        "bias": "LONG_BIAS",
        "window_id": 1,
        "setup_valid": True
    })
    
    out_dir = str(tmp_path)
    
    # 1. Plot setup
    fig1 = plot_setup(trade, m30, output_dir=out_dir)
    assert fig1 is not None
    assert any(f.endswith(".html") for f in os.listdir(out_dir))
    
    # 2. Plot cumulative R
    log = pd.DataFrame([
        trade,
        trade.copy().replace({"timestamp_entry": ts[70], "R_multiple": -1.0, "outcome": "SL", "window_id": 2})
    ])
    fig2 = plot_walk_forward_cumulative_r(log, output_dir=out_dir)
    assert fig2 is not None
    assert "cumulative_R.html" in os.listdir(out_dir)
    
    # 3. Plot regime distribution
    fig3 = plot_regime_setup_distribution(log, output_dir=out_dir)
    assert fig3 is not None
    assert "regime_distribution.html" in os.listdir(out_dir)
    
    # 4. Plot outcome distribution
    fig4 = plot_setup_outcome_distribution(log, output_dir=out_dir)
    assert fig4 is not None
    assert "outcome_distribution.html" in os.listdir(out_dir)

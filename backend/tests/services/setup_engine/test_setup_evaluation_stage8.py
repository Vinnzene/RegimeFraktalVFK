"""Tahap 8: Setup Evaluation Tests"""

import pandas as pd
import numpy as np
from app.services.setup_engine.setup_evaluation import calculate_metrics, run_evaluation, compare_modes

def test_calculate_metrics_synthetic():
    # Synthetic trade log
    data = [
        {"setup_valid": True, "direction": "LONG", "outcome": "TP", "R_multiple": 2.0, "holding_time": pd.Timedelta(hours=4)},
        {"setup_valid": True, "direction": "SHORT", "outcome": "SL", "R_multiple": -1.0, "holding_time": pd.Timedelta(hours=2)},
        {"setup_valid": True, "direction": "LONG", "outcome": "SL", "R_multiple": -1.0, "holding_time": pd.Timedelta(hours=1)},
        {"setup_valid": True, "direction": "SHORT", "outcome": "SL", "R_multiple": -1.0, "holding_time": pd.Timedelta(hours=2)},
        {"setup_valid": True, "direction": "LONG", "outcome": "TP", "R_multiple": 3.0, "holding_time": pd.Timedelta(hours=12)},
        {"setup_valid": True, "direction": "SHORT", "outcome": "TP", "R_multiple": 1.5, "holding_time": pd.Timedelta(hours=3)},
        {"setup_valid": True, "direction": "LONG", "outcome": "TIMEOUT", "R_multiple": -0.5, "holding_time": pd.Timedelta(hours=8)},
        {"setup_valid": True, "direction": "LONG", "outcome": "SL", "R_multiple": -1.0, "holding_time": pd.Timedelta(hours=4)},
        {"setup_valid": True, "direction": "SHORT", "outcome": "AMBIGUOUS", "R_multiple": np.nan, "holding_time": pd.Timedelta(hours=1)},
        {"setup_valid": True, "direction": "LONG", "outcome": "AMBIGUOUS", "R_multiple": np.nan, "holding_time": pd.Timedelta(hours=1)},
    ]
    df = pd.DataFrame(data)
    metrics = calculate_metrics(df, duration_days=30.0)
    
    assert metrics["total_setup"] == 10
    assert metrics["total_long"] == 6
    assert metrics["total_short"] == 4
    
    assert metrics["tp"] == 3
    assert metrics["sl"] == 4
    assert metrics["timeout"] == 1
    assert metrics["ambiguous"] == 2
    
    # Win rate: TP / (TP+SL+TIMEOUT) = 3 / 8 = 0.375
    assert metrics["win_rate"] == 0.375
    
    # Total R = 2.0 - 1.0 - 1.0 - 1.0 + 3.0 + 1.5 - 0.5 - 1.0 = 2.0
    assert abs(metrics["total_r"] - 2.0) < 1e-5
    
    # Gross Profit = 2.0 + 3.0 + 1.5 = 6.5
    # Gross Loss = 1.0 + 1.0 + 1.0 + 0.5 + 1.0 = 4.5
    # PF = 6.5 / 4.5 = 1.444...
    assert abs(metrics["profit_factor"] - (6.5 / 4.5)) < 1e-5
    
    # Max DD:
    # Cum: 2.0 -> 1.0 -> 0.0 -> -1.0 -> 2.0 -> 3.5 -> 3.0 -> 2.0
    # Peaks: 2.0 -> 2.0 -> 2.0 -> 2.0 -> 2.0 -> 3.5 -> 3.5 -> 3.5
    # DDs:   0.0 -> 1.0 -> 2.0 -> 3.0 -> 0.0 -> 0.0 -> 0.5 -> 1.5
    # Max DD = 3.0
    assert abs(metrics["max_drawdown"] - 3.0) < 1e-5
    
    # Losing streak: 3 (SL, SL, SL)
    assert metrics["losing_streak"] == 3
    
    # Avg holding time: (4+2+1+2+12+3+8+4+1+1) / 10 = 38 / 10 = 3.8 hours
    assert "0 days 03:48:00" in metrics["average_holding_time"]

def test_compare_modes():
    log_a = pd.DataFrame([
        {"setup_valid": True, "outcome": "TP", "R_multiple": 2.0, "direction": "LONG", "holding_time": pd.Timedelta(hours=4)},
        {"setup_valid": True, "outcome": "SL", "R_multiple": -1.0, "direction": "LONG", "holding_time": pd.Timedelta(hours=2)},
    ])
    log_b = pd.DataFrame([
        {"setup_valid": True, "outcome": "TP", "R_multiple": 2.0, "direction": "LONG", "holding_time": pd.Timedelta(hours=4)},
    ])
    
    comp = compare_modes(log_a, log_b)
    assert len(comp) == 2
    assert comp.iloc[0]["total_setup"] == 2
    assert comp.iloc[1]["total_setup"] == 1
    assert comp.iloc[0]["profit_factor"] == 2.0
    assert comp.iloc[1]["profit_factor"] == np.inf

def test_run_evaluation():
    data = [
        {"timestamp_bias": pd.Timestamp("2024-01-01 00:00:00", tz="UTC"), "setup_valid": True, "outcome": "TP", "R_multiple": 2.0, "direction": "LONG", "holding_time": pd.Timedelta(hours=4), "window_id": 1, "regime_4h": "PERSISTENT", "setup_rejection_reason": "OK"},
        {"timestamp_bias": pd.Timestamp("2024-01-02 00:00:00", tz="UTC"), "setup_valid": True, "outcome": "SL", "R_multiple": -1.0, "direction": "LONG", "holding_time": pd.Timedelta(hours=2), "window_id": 1, "regime_4h": "RANDOM_LIKE", "setup_rejection_reason": "OK"},
        {"timestamp_bias": pd.Timestamp("2024-01-03 00:00:00", tz="UTC"), "setup_valid": False, "outcome": np.nan, "R_multiple": np.nan, "direction": "SHORT", "holding_time": pd.NaT, "window_id": 2, "regime_4h": "ANTI_PERSISTENT", "setup_rejection_reason": "EXISTING_POSITION"},
    ]
    df = pd.DataFrame(data)
    res = run_evaluation(df)
    
    assert "global_summary" in res
    assert "window_summary" in res
    assert "regime_summary" in res
    assert "bias_summary" in res
    assert "setup_type_summary" in res
    assert "rejections" in res
    
    assert len(res["window_summary"]) == 2 # 2 windows
    assert len(res["regime_summary"]) == 3 # 3 regimes
    
    # Verify rejection counting
    rej = res["rejections"]
    assert len(rej) == 2
    
    assert rej[rej["reason"] == "OK"]["count"].iloc[0] == 2
    assert rej[rej["reason"] == "EXISTING_POSITION"]["count"].iloc[0] == 1

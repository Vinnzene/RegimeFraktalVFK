"""Tahap 8: Setup Evaluation"""

from __future__ import annotations
import os
import pandas as pd
import numpy as np
from typing import Dict, Any, List, cast

def _wilson_score_interval(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    if trials == 0:
        return 0.0, 0.0
    z = 1.96 if confidence == 0.95 else 1.96
    p_hat = successes / trials
    denominator = 1 + z**2 / trials
    centre = (p_hat + z**2 / (2 * trials)) / denominator
    margin = (z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * trials)) / trials)) / denominator
    return max(0.0, float(centre - margin)), min(1.0, float(centre + margin))

def calculate_metrics(log: pd.DataFrame, duration_days: float = 30.0) -> Dict[str, Any]:
    if log.empty:
        return _empty_metrics()
        
    valid_log = log[log["setup_valid"] == True].copy()
    if valid_log.empty:
        return _empty_metrics()

    # Drop AMBIGUOUS for win rate and cumulative R, but count it
    trade_log = valid_log[valid_log["outcome"] != "AMBIGUOUS"].copy()
    
    total_setup = len(valid_log)
    total_long = len(valid_log[valid_log["direction"] == "LONG"])
    total_short = len(valid_log[valid_log["direction"] == "SHORT"])
    
    tp_count = len(valid_log[valid_log["outcome"] == "TP"])
    sl_count = len(valid_log[valid_log["outcome"] == "SL"])
    timeout_count = len(valid_log[valid_log["outcome"] == "TIMEOUT"])
    ambiguous_count = len(valid_log[valid_log["outcome"] == "AMBIGUOUS"])
    
    n_trades = len(trade_log)
    win_rate = tp_count / n_trades if n_trades > 0 else 0.0
    ci_lower, ci_upper = _wilson_score_interval(tp_count, n_trades)
    
    # Net R multiples
    if "r_net" in trade_log.columns and not trade_log["r_net"].isna().all():
        r_net = trade_log["r_net"].dropna()
    elif "R_multiple" in trade_log.columns and not trade_log["R_multiple"].isna().all():
        r_net = trade_log["R_multiple"].dropna()
    else:
        r_net = pd.Series(dtype=float)
        
    # Gross R multiples
    if "r_gross" in trade_log.columns and not trade_log["r_gross"].isna().all():
        r_gross = trade_log["r_gross"].dropna()
    else:
        r_gross = r_net.copy()
        
    total_r_net = float(r_net.sum()) if not r_net.empty else 0.0
    avg_r_net = float(r_net.mean()) if not r_net.empty else 0.0
    median_r_net = float(r_net.median()) if not r_net.empty else 0.0
    
    gross_profit_net = float(r_net[r_net > 0].sum()) if not r_net.empty else 0.0
    gross_loss_net = float(abs(r_net[r_net < 0].sum())) if not r_net.empty else 0.0
    profit_factor_net = gross_profit_net / gross_loss_net if gross_loss_net > 0 else (np.inf if gross_profit_net > 0 else 0.0)
    
    cumulative_r_net = r_net.cumsum() if not r_net.empty else pd.Series(dtype=float)
    max_dd_net = 0.0
    if not cumulative_r_net.empty:
        peak_net = cumulative_r_net.cummax()
        max_dd_net = float((peak_net - cumulative_r_net).max())

    total_r_gross = float(r_gross.sum()) if not r_gross.empty else 0.0
    avg_r_gross = float(r_gross.mean()) if not r_gross.empty else 0.0
    median_r_gross = float(r_gross.median()) if not r_gross.empty else 0.0
    
    gross_profit_gross = float(r_gross[r_gross > 0].sum()) if not r_gross.empty else 0.0
    gross_loss_gross = float(abs(r_gross[r_gross < 0].sum())) if not r_gross.empty else 0.0
    profit_factor_gross = gross_profit_gross / gross_loss_gross if gross_loss_gross > 0 else (np.inf if gross_profit_gross > 0 else 0.0)
    
    cumulative_r_gross = r_gross.cumsum() if not r_gross.empty else pd.Series(dtype=float)
    max_dd_gross = 0.0
    if not cumulative_r_gross.empty:
        peak_gross = cumulative_r_gross.cummax()
        max_dd_gross = float((peak_gross - cumulative_r_gross).max())
        
    total_biaya = float(trade_log["biaya_total"].sum()) if ("biaya_total" in trade_log.columns and not trade_log["biaya_total"].isna().all()) else 0.0
        
    losing_streak = 0
    current_streak = 0
    for r in r_net:
        if r < 0:
            current_streak += 1
            losing_streak = max(losing_streak, current_streak)
        else:
            current_streak = 0
            
    avg_holding = pd.Timedelta(0)
    holding_times = valid_log["holding_time"].dropna()
    if not holding_times.empty:
        holding_times = pd.to_timedelta(holding_times)
        avg_holding_sec = holding_times.dt.total_seconds().mean()
        avg_holding = pd.to_timedelta(avg_holding_sec, unit="s")
        
    setup_freq = total_setup / (duration_days / 30.0) if duration_days > 0 else total_setup
    
    return {
        "n": total_setup,
        "n_small_sample": total_setup < 30,
        "total_setup": total_setup,
        "total_long": total_long,
        "total_short": total_short,
        "tp": tp_count,
        "sl": sl_count,
        "timeout": timeout_count,
        "ambiguous": ambiguous_count,
        "win_rate": win_rate,
        "win_rate_ci_lower": ci_lower,
        "win_rate_ci_upper": ci_upper,
        "total_r": total_r_net,
        "average_r": avg_r_net,
        "median_r": median_r_net,
        "profit_factor": profit_factor_net,
        "max_drawdown": max_dd_net,
        "total_r_net": total_r_net,
        "average_r_net": avg_r_net,
        "median_r_net": median_r_net,
        "profit_factor_net": profit_factor_net,
        "max_drawdown_net": max_dd_net,
        "total_r_gross": total_r_gross,
        "average_r_gross": avg_r_gross,
        "median_r_gross": median_r_gross,
        "profit_factor_gross": profit_factor_gross,
        "max_drawdown_gross": max_dd_gross,
        "total_biaya": total_biaya,
        "losing_streak": losing_streak,
        "average_holding_time": str(avg_holding),
        "setup_frequency_per_month": setup_freq
    }

def _empty_metrics() -> Dict[str, Any]:
    return {
        "n": 0,
        "n_small_sample": True,
        "total_setup": 0,
        "total_long": 0,
        "total_short": 0,
        "tp": 0,
        "sl": 0,
        "timeout": 0,
        "ambiguous": 0,
        "win_rate": 0.0,
        "win_rate_ci_lower": 0.0,
        "win_rate_ci_upper": 0.0,
        "total_r": 0.0,
        "average_r": 0.0,
        "median_r": 0.0,
        "profit_factor": 0.0,
        "max_drawdown": 0.0,
        "total_r_net": 0.0,
        "average_r_net": 0.0,
        "median_r_net": 0.0,
        "profit_factor_net": 0.0,
        "max_drawdown_net": 0.0,
        "total_r_gross": 0.0,
        "average_r_gross": 0.0,
        "median_r_gross": 0.0,
        "profit_factor_gross": 0.0,
        "max_drawdown_gross": 0.0,
        "total_biaya": 0.0,
        "losing_streak": 0,
        "average_holding_time": "0 days",
        "setup_frequency_per_month": 0.0
    }

def run_evaluation(final_log: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    # Calculate duration
    duration_days = 30.0
    if not final_log.empty and "timestamp_bias" in final_log.columns and not final_log["timestamp_bias"].isna().all():
        start_t = final_log["timestamp_bias"].dropna().min()
        end_t = final_log["timestamp_bias"].dropna().max()
        if pd.notna(start_t) and pd.notna(end_t):
            duration_days = (end_t - start_t).total_seconds() / 86400.0
            if duration_days <= 0:
                duration_days = 30.0
        
    global_metrics = calculate_metrics(final_log, duration_days)
    
    # Per window
    windows = []
    if not final_log.empty and "window_id" in final_log.columns:
        for wid, wdf in final_log.groupby("window_id"):
            wm = calculate_metrics(wdf, duration_days)
            wm["window_id"] = wid
            windows.append(wm)
            
    # Regime conditioned
    regime_results = []
    if not final_log.empty and "regime_4h" in final_log.columns:
        for reg, rdf in final_log.groupby("regime_4h"):
            rm = calculate_metrics(rdf, duration_days)
            rm["regime"] = reg
            regime_results.append(rm)
            
    # Bias conditioned
    bias_results = []
    if not final_log.empty and "bias" in final_log.columns:
        for b, bdf in final_log.groupby("bias"):
            bm = calculate_metrics(bdf, duration_days)
            bm["bias"] = b
            bias_results.append(bm)
            
    # Structure/Setup type conditioned
    setup_type_results = []
    if not final_log.empty and "structure_30m" in final_log.columns:
        for s, sdf in final_log.groupby("structure_30m"):
            sm = calculate_metrics(sdf, duration_days)
            sm["structure_30m"] = s
            setup_type_results.append(sm)
            
    # Rejection reasons
    rejections = []
    if not final_log.empty and "setup_rejection_reason" in final_log.columns:
        vc = final_log["setup_rejection_reason"].value_counts(dropna=False)
        for reason, count in vc.items():
            rejections.append({"reason": reason if pd.notna(cast(Any, reason)) else "OK", "count": count})
            
    return {
        "global_summary": pd.DataFrame([global_metrics]),
        "window_summary": pd.DataFrame(windows),
        "regime_summary": pd.DataFrame(regime_results),
        "bias_summary": pd.DataFrame(bias_results),
        "setup_type_summary": pd.DataFrame(setup_type_results),
        "rejections": pd.DataFrame(rejections),
        "trade_log": final_log
    }

def export_csvs(eval_results: Dict[str, pd.DataFrame], output_dir: str = "."):
    os.makedirs(output_dir, exist_ok=True)
    
    if "trade_log" in eval_results:
        eval_results["trade_log"].to_csv(os.path.join(output_dir, "trade_log.csv"), index=False)
    if "global_summary" in eval_results:
        eval_results["global_summary"].to_csv(os.path.join(output_dir, "setup_summary.csv"), index=False)
    if "window_summary" in eval_results:
        eval_results["window_summary"].to_csv(os.path.join(output_dir, "walk_forward_summary.csv"), index=False)
    if "regime_summary" in eval_results:
        eval_results["regime_summary"].to_csv(os.path.join(output_dir, "regime_conditioned_results.csv"), index=False)
        
    # Cumulative R
    if "trade_log" in eval_results:
        log = eval_results["trade_log"]
        valid_log = log[(log["setup_valid"] == True) & (log["outcome"] != "AMBIGUOUS")].copy()
        if not valid_log.empty:
            valid_log = valid_log.sort_values("timestamp_entry")
            if "r_gross" in valid_log.columns:
                valid_log["cumulative_R_gross"] = valid_log["r_gross"].cumsum()
            if "r_net" in valid_log.columns:
                valid_log["cumulative_R_net"] = valid_log["r_net"].cumsum()
            if "R_multiple" in valid_log.columns:
                valid_log["cumulative_R"] = valid_log["R_multiple"].cumsum()
            elif "r_net" in valid_log.columns:
                valid_log["cumulative_R"] = valid_log["cumulative_R_net"]
            cols = [
                "timestamp_entry", "window_id", "regime_4h", "direction", "outcome",
                "r_gross", "cumulative_R_gross", "r_net", "cumulative_R_net", "biaya_total",
                "R_multiple", "cumulative_R"
            ]
            cols = [c for c in cols if c in valid_log.columns]
            valid_log[cols].to_csv(os.path.join(output_dir, "cumulative_R.csv"), index=False)

def compare_modes(log_mode_a: pd.DataFrame, log_mode_b: pd.DataFrame) -> pd.DataFrame:
    metrics_a = calculate_metrics(log_mode_a)
    metrics_b = calculate_metrics(log_mode_b)
    
    df = pd.DataFrame([metrics_a, metrics_b], index=["Mode A (Base)", "Mode B (OFI/CVD)"])
    return df

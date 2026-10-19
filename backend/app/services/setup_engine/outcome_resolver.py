"""Tahap 6: Outcome Resolver.

Menentukan hasil trade (TP / SL / TIMEOUT / AMBIGUOUS) setelah entry.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.services.setup_engine.config import SetupEngineConfig

logger = logging.getLogger(__name__)


def resolve_outcomes(
    setups: pd.DataFrame,
    market_30m: pd.DataFrame,
    market_5m: Optional[pd.DataFrame],
    cfg: SetupEngineConfig,
) -> pd.DataFrame:
    """Iterasi kronologis menentukan outcome per setup valid."""
    if setups.empty:
        return pd.DataFrame()
        
    outcomes: List[Dict[str, Any]] = []
    
    # Pastikan market sort by timestamp
    m30 = market_30m.sort_values("timestamp").reset_index(drop=True)
    m5 = market_5m.sort_values("timestamp").reset_index(drop=True) if market_5m is not None and not market_5m.empty else None
    
    if m5 is None:
        logger.warning("Data resolusi rendah (5M) tidak tersedia. Resolusi outcome lebih rendah dari yang direncanakan.")
        
    for _, setup in setups.iterrows():
        if not setup["setup_valid"]:
            continue
            
        entry_time = setup["timestamp_entry"]
        entry_price = setup["entry"]
        tp = setup["take_profit"]
        sl = setup["stop_loss"]
        is_long = setup["direction"] == "LONG"
        rr = setup["rr"]
        risk = setup["risk"]
        
        # Cari index bar entry di 30m
        idx_match = m30.index[m30["timestamp"] == entry_time].tolist()
        if not idx_match:
            # Tidak ada data market untuk entry ini, aneh tapi mungkin di ujung data
            outcomes.append(_build_ambiguous(setup, "MARKET_DATA_MISSING"))
            continue
            
        entry_idx = idx_match[0]
        max_idx = min(len(m30) - 1, entry_idx + cfg.execution.max_holding_bars)
        
        resolved = False
        
        for i in range(entry_idx, max_idx + 1):
            bar_30m = m30.iloc[i]
            
            if is_long:
                hit_tp = bar_30m["high"] >= tp
                hit_sl = bar_30m["low"] <= sl
            else:
                hit_tp = bar_30m["low"] <= tp
                hit_sl = bar_30m["high"] >= sl
                
            needs_drilldown = (hit_tp and hit_sl) or (i == entry_idx and (hit_tp or hit_sl))
            
            if needs_drilldown:
                if m5 is None:
                    outcomes.append(_build_ambiguous(setup, "AMBIGUOUS_OUTCOME"))
                    resolved = True
                    break
                    
                # Ambil sub bars
                sub_bars = m5[(m5["timestamp"] >= bar_30m["timestamp"]) & (m5["timestamp"] < bar_30m["close_time"])]
                if sub_bars.empty:
                    outcomes.append(_build_ambiguous(setup, "AMBIGUOUS_OUTCOME"))
                    resolved = True
                    break
                
                entry_triggered_in_sub = False if i == entry_idx else True
                
                for _, sub_bar in sub_bars.iterrows():
                    if not entry_triggered_in_sub:
                        if is_long and sub_bar["high"] >= entry_price:
                            entry_triggered_in_sub = True
                        elif not is_long and sub_bar["low"] <= entry_price:
                            entry_triggered_in_sub = True
                            
                        if entry_triggered_in_sub:
                            # Cek TP/SL di sub_bar yang sama dengan entry
                            sub_tp = (sub_bar["high"] >= tp) if is_long else (sub_bar["low"] <= tp)
                            sub_sl = (sub_bar["low"] <= sl) if is_long else (sub_bar["high"] >= sl)
                            if sub_tp or sub_sl:
                                outcomes.append(_build_ambiguous(setup, "AMBIGUOUS_OUTCOME"))
                                resolved = True
                                break
                    else:
                        sub_tp = (sub_bar["high"] >= tp) if is_long else (sub_bar["low"] <= tp)
                        sub_sl = (sub_bar["low"] <= sl) if is_long else (sub_bar["high"] >= sl)
                        
                        if sub_tp and sub_sl:
                            outcomes.append(_build_ambiguous(setup, "AMBIGUOUS_OUTCOME"))
                            resolved = True
                            break
                        elif sub_tp:
                            outcomes.append(_build_outcome(setup, "TP", sub_bar["timestamp"], tp, cfg))
                            resolved = True
                            break
                        elif sub_sl:
                            outcomes.append(_build_outcome(setup, "SL", sub_bar["timestamp"], sl, cfg))
                            resolved = True
                            break
                            
                if resolved:
                    break
                    
                # Jika i == entry_idx dan entry_triggered_in_sub == False, berarti entry tidak tercapai di 5m
                # Ini inkonsistensi data 30M vs 5M.
                if i == entry_idx and not entry_triggered_in_sub:
                    outcomes.append(_build_ambiguous(setup, "AMBIGUOUS_OUTCOME"))
                    resolved = True
                    break
                    
            else:
                if hit_tp:
                    outcomes.append(_build_outcome(setup, "TP", bar_30m["timestamp"], tp, cfg))
                    resolved = True
                    break
                elif hit_sl:
                    outcomes.append(_build_outcome(setup, "SL", bar_30m["timestamp"], sl, cfg))
                    resolved = True
                    break
                    
        if not resolved:
            last_bar = m30.iloc[max_idx]
            exit_price = float(last_bar["close"])
            outcomes.append(_build_outcome(setup, "TIMEOUT", last_bar["close_time"], exit_price, cfg))
            
    # Gabungkan hasil
    df_outcomes = pd.DataFrame(outcomes)
    
    # Gabungkan dengan setup asli menggunakan index atau tambahkan kolom
    if df_outcomes.empty:
        result = setups.copy()
        result["exit_timestamp"] = pd.NaT
        result["exit_price"] = np.nan
        result["outcome"] = np.nan
        result["R_multiple"] = np.nan
        result["r_gross"] = np.nan
        result["r_net"] = np.nan
        result["biaya_total"] = np.nan
        result["holding_time"] = pd.NaT
        return result
        
    result = setups.copy()
    valid_mask = result["setup_valid"] == True
    
    # Assign back safely
    for col in ["exit_timestamp", "exit_price", "outcome", "R_multiple", "r_gross", "r_net", "biaya_total", "holding_time"]:
        if col not in df_outcomes.columns:
            continue
        # Only assign to valid setups
        # Match by implicit order since we iterated over valid setups in order
        valid_indices = result[valid_mask].index
        if len(valid_indices) == len(df_outcomes):
            result.loc[valid_indices, col] = df_outcomes[col].values
            
    return result


def _calculate_costs_and_r(
    setup: pd.Series,
    exit_price: float,
    outcome_type: str,
    cfg: SetupEngineConfig,
) -> tuple[float, float, float]:
    """Menghitung r_gross, r_net, dan biaya_total (fee + slippage).

    Rumus T1.6:
    R_real = ((P_exit - P_entry) * direction - biaya_total) / risk_distance
    """
    entry_price = float(setup["entry"])
    is_long = setup["direction"] == "LONG"
    direction = 1.0 if is_long else -1.0
    risk = float(setup["risk"])
    rr = float(setup.get("rr", getattr(cfg.risk, "rr", 2.0)))

    # Gross R
    if outcome_type == "TP":
        r_gross = rr
    elif outcome_type == "SL":
        r_gross = -1.0
    else:  # TIMEOUT
        pnl_gross = (exit_price - entry_price) * direction
        r_gross = pnl_gross / risk if risk > 0 else 0.0

    # Fee and slippage calculation
    fee_pct = getattr(cfg.execution, "taker_fee_pct", 0.0)
    slip_ticks = getattr(cfg.execution, "slippage_ticks", 0)
    tick_sz = getattr(cfg.execution, "tick_size", 0.01)

    fee_entry = entry_price * fee_pct
    fee_exit = exit_price * fee_pct
    slippage_cost = 2 * slip_ticks * tick_sz
    biaya_total = fee_entry + fee_exit + slippage_cost

    if biaya_total == 0.0:
        r_net = r_gross
    else:
        pnl_gross = (exit_price - entry_price) * direction
        pnl_net = pnl_gross - biaya_total
        r_net = pnl_net / risk if risk > 0 else 0.0

    return r_gross, r_net, biaya_total


def _build_outcome(
    setup: pd.Series,
    outcome_type: str,
    exit_ts: pd.Timestamp,
    exit_price: float,
    cfg: SetupEngineConfig,
) -> Dict[str, Any]:
    ht = exit_ts - setup["timestamp_entry"]
    r_gross, r_net, biaya_total = _calculate_costs_and_r(setup, exit_price, outcome_type, cfg)
    return {
        "exit_timestamp": exit_ts,
        "exit_price": exit_price,
        "outcome": outcome_type,
        "R_multiple": r_net,
        "r_gross": r_gross,
        "r_net": r_net,
        "biaya_total": biaya_total,
        "holding_time": ht,
    }


def _build_ambiguous(setup: pd.Series, reason: str) -> Dict[str, Any]:
    return {
        "exit_timestamp": pd.NaT,
        "exit_price": np.nan,
        "outcome": "AMBIGUOUS",
        "R_multiple": np.nan,
        "r_gross": np.nan,
        "r_net": np.nan,
        "biaya_total": np.nan,
        "holding_time": pd.NaT,
        "ambiguous_reason": reason,
    }

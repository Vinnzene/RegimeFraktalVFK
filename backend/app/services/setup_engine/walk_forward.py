"""Tahap 7: Walk-forward Orchestrator.

Orkestrator simulasi kronologis. Membagi data menjadi jendela walk-forward
(train/val/test) dan menjalankan simulasi di setiap periode test secara sekuensial.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, cast

import numpy as np
import pandas as pd

from app.services.setup_engine.config import SetupEngineConfig, parse_period
from app.services.setup_engine.data_contract import LookAheadError
from app.services.setup_engine.directional_bias_engine import compute_bias
from app.services.setup_engine.outcome_resolver import resolve_outcomes
from app.services.setup_engine.setup_engine import generate_setups

logger = logging.getLogger(__name__)


def generate_windows(start_time: pd.Timestamp, end_time: pd.Timestamp, cfg: SetupEngineConfig) -> List[Dict[str, Any]]:
    """Membangkitkan jendela walk-forward dari konfigurasi."""
    train_off = parse_period(cfg.walk_forward.train_period)
    val_off = parse_period(cfg.walk_forward.validation_period)
    test_off = parse_period(cfg.walk_forward.test_period)
    step_off = parse_period(cfg.walk_forward.step_period)
    
    current_train_start = start_time
    windows = []
    window_id = 1
    
    while True:
        train_end = current_train_start + train_off
        val_end = train_end + val_off
        test_end = val_end + test_off
        
        if val_end >= end_time:
            break
            
        windows.append({
            "window_id": window_id,
            "train_start": current_train_start,
            "train_end": train_end,
            "val_start": train_end,
            "val_end": val_end,
            "test_start": val_end,
            "test_end": min(test_end, end_time)
        })
        
        current_train_start += step_off
        window_id += 1
        
        if val_end + test_off >= end_time:
            break
            
    return windows


def validate_no_lookahead(log: pd.DataFrame) -> None:
    """Memeriksa potensi look-ahead bias pada final trade log."""
    if log.empty:
        return
        
    # 1. timestamp_entry >= timestamp_bias
    mask_entry = log["timestamp_entry"].notna() & log["timestamp_bias"].notna()
    if mask_entry.any():
        if not (log.loc[mask_entry, "timestamp_entry"] >= log.loc[mask_entry, "timestamp_bias"]).all():
            bad = log.loc[mask_entry & (log["timestamp_entry"] < log["timestamp_bias"])]
            raise LookAheadError(f"Lookahead: timestamp_entry mendahului timestamp_bias\n{bad}")
        
    # 2. timestamp_setup >= timestamp_bias
    mask_setup = log["timestamp_setup"].notna() & log["timestamp_bias"].notna()
    if mask_setup.any():
        if not (log.loc[mask_setup, "timestamp_setup"] >= log.loc[mask_setup, "timestamp_bias"]).all():
            bad = log.loc[mask_setup & (log["timestamp_setup"] < log["timestamp_bias"])]
            raise LookAheadError(f"Lookahead: timestamp_setup mendahului timestamp_bias\n{bad}")
        
    # 3. exit_timestamp >= timestamp_entry
    mask_exit = log["exit_timestamp"].notna() & log["timestamp_entry"].notna()
    if mask_exit.any():
        if not (log.loc[mask_exit, "exit_timestamp"] >= log.loc[mask_exit, "timestamp_entry"]).all():
            bad = log.loc[mask_exit & (log["exit_timestamp"] < log["timestamp_entry"])]
            raise LookAheadError(f"Lookahead: exit_timestamp mendahului timestamp_entry\n{bad}")


def enrich_with_bias_columns(setups: pd.DataFrame, bias_df: pd.DataFrame) -> pd.DataFrame:
    """Menggabungkan kolom-kolom dari directional_bias_engine yang diperlukan untuk output."""
    cols_to_add = ["regime_4h", "regime_1h", "structure_1h", "ofi_1h", "cvd_1h", "transition_type"]
    
    # Pastikan bias_df memiliki kolom yang kita butuhkan
    available_cols = [c for c in cols_to_add if c in bias_df.columns]
    
    if not available_cols:
        return setups
        
    # Drop existing if any, to avoid collision
    for c in available_cols:
        if c in setups.columns:
            setups = setups.drop(columns=c)
            
    b = pd.DataFrame(bias_df[["timestamp_bias"] + available_cols]).drop_duplicates(subset=["timestamp_bias"])
    merged = pd.merge(setups, b, on="timestamp_bias", how="left")
    return merged


def run_walk_forward(
    market_1h: pd.DataFrame,
    market_30m: pd.DataFrame,
    market_5m: pd.DataFrame | None,
    regime_4h: pd.DataFrame,
    regime_1h: pd.DataFrame,
    cfg: SetupEngineConfig
) -> pd.DataFrame:
    """Menjalankan simulasi walk-forward penuh secara kronologis."""
    
    if cfg.confirmation.required:
        has_ofi = "ofi" in market_1h.columns and not bool(market_1h["ofi"].isna().all()) and bool((market_1h["ofi"].abs().sum() > 0))
        has_cvd = "cvd" in market_1h.columns and not bool(market_1h["cvd"].isna().all()) and bool((market_1h["cvd"].abs().sum() > 0))
        if not (has_ofi or has_cvd):
            raise ValueError(
                "Mode B (OFI/CVD confirmation) cannot run without valid order flow data. "
                "Binance spot book archives returned HTTP 404; use Mode A instead."
            )

    start_time = pd.Timestamp(cast(Any, market_1h["timestamp"].min()))
    end_time = pd.Timestamp(cast(Any, market_1h["timestamp"].max())) + pd.Timedelta(hours=1)
    assert isinstance(start_time, pd.Timestamp) and isinstance(end_time, pd.Timestamp)
    
    windows = generate_windows(start_time, end_time, cfg)
    all_logs = []
    
    free_time = pd.Timestamp.min.tz_localize("UTC")
    
    for w in windows:
        test_start = w["test_start"]
        test_end = w["test_end"]
        
        warmup = pd.Timedelta(days=7)
        slice_start = test_start - warmup
        extend_end = test_end + pd.Timedelta(minutes=30 * cfg.execution.max_holding_bars)
        
        m1h = pd.DataFrame(market_1h[(market_1h["timestamp"] >= slice_start) & (market_1h["timestamp"] < test_end)])
        m30m = pd.DataFrame(market_30m[(market_30m["timestamp"] >= slice_start) & (market_30m["timestamp"] <= extend_end)])
        m5m = pd.DataFrame(market_5m[(market_5m["timestamp"] >= slice_start) & (market_5m["timestamp"] <= extend_end)]) if market_5m is not None else None
        
        r4 = pd.DataFrame(regime_4h[(regime_4h["timestamp"] >= slice_start) & (regime_4h["timestamp"] <= test_end)])
        r1 = pd.DataFrame(regime_1h[(regime_1h["timestamp"] >= slice_start) & (regime_1h["timestamp"] <= test_end)])
        
        if len(m1h) == 0 or len(m30m) == 0:
            continue
            
        bias_df = compute_bias(m1h, r4, r1, cfg)
        setups = generate_setups(m30m, bias_df, cfg)
        
        if setups.empty:
            continue
            
        test_setups = pd.DataFrame(setups[(setups["timestamp_entry"] >= test_start) & (setups["timestamp_entry"] < test_end)].copy())
        
        if test_setups.empty:
            continue
            
        resolved = resolve_outcomes(test_setups, m30m, m5m, cfg)
        
        # Max open positions = 1 logic
        for idx, row in cast(Any, resolved.sort_values("timestamp_entry")).iterrows():
            if bool(pd.isna(row["timestamp_entry"])):
                continue
            
            t_entry = pd.Timestamp(cast(Any, row["timestamp_entry"]))
            t_free = pd.Timestamp(cast(Any, free_time))
            if t_entry.tz is not None:
                t_entry = t_entry.tz_convert("UTC").tz_localize(None)
            if t_free.tz is not None:
                t_free = t_free.tz_convert("UTC").tz_localize(None)

            if cast(Any, t_entry) < cast(Any, t_free):
                resolved.loc[idx, "setup_valid"] = False
                resolved.loc[idx, "setup_rejection_reason"] = "EXISTING_POSITION"
                for col in ["exit_timestamp", "exit_price", "outcome", "R_multiple", "r_gross", "r_net", "biaya_total", "holding_time"]:
                    if col in resolved.columns:
                        resolved.loc[idx, col] = pd.NaT if "timestamp" in col or "time" in col else np.nan
            else:
                if bool(row["setup_valid"]):
                    if bool(pd.notna(row["exit_timestamp"])):
                        free_time = row["exit_timestamp"]
                    
        resolved["window_id"] = w["window_id"]
        
        # Enrich dengan fitur bias (regime_4h, dll)
        resolved = enrich_with_bias_columns(resolved, bias_df)
        
        all_logs.append(resolved)
        
    if not all_logs:
        return pd.DataFrame()
        
    final_log = pd.concat(all_logs, ignore_index=True)
    
    # Standardize output columns
    expected_cols = [
        "timestamp_bias", "timestamp_setup", "timestamp_entry", 
        "regime_4h", "regime_1h", "bias", "direction", 
        "structure_1h", "structure_30m", "ofi_1h", "cvd_1h", "ofi_30m", "cvd_30m", 
        "entry", "stop_loss", "take_profit", "risk", "rr", 
        "exit_timestamp", "exit_price", "outcome", "R_multiple", "r_gross", "r_net", "biaya_total", "holding_time", 
        "setup_valid", "setup_rejection_reason", "window_id", "transition_type"
    ]
    
    # Rename rr to RR for consistency with spec if needed, but python uses rr internally.
    # We will rename 'rr' to 'RR' to match the spec
    if "rr" in final_log.columns and "RR" not in final_log.columns:
        final_log = final_log.rename(columns={"rr": "RR"})
        
    for c in expected_cols:
        if c not in final_log.columns:
            final_log[c] = pd.NA if "timestamp" in c or "time" in c else np.nan
            
    final_log = pd.DataFrame(final_log[expected_cols])
    
    for col in ["timestamp_bias", "timestamp_setup", "timestamp_entry", "exit_timestamp"]:
        if col in final_log.columns:
            final_log[col] = pd.to_datetime(final_log[col], utc=True)
    
    validate_no_lookahead(final_log)
    
    return final_log

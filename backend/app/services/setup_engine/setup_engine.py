"""Setup Engine: State machine deterministic pada timeframe 30M.

Menerima data market 30M dan stream bias 1H, lalu mencari setup berdasarkan
pullback dan Break of Structure (BOS), serta memvalidasi dengan OFI/CVD dan Risk.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from pandas._libs import NaTType

from app.services.setup_engine.config import SetupEngineConfig
from app.services.setup_engine.data_contract import DataContractError, align_htf_to_ltf
from app.services.setup_engine.directional_bias_engine import Bias, cvd_slope, rolling_ofi
from app.services.setup_engine.market_structure import MarketStructure
from app.services.setup_engine.risk_engine import Direction, build_risk_plan


class SetupRejectionReason(str, Enum):
    OK = "OK"
    NO_BIAS = "NO_BIAS"
    CONFLICTING_REGIME = "CONFLICTING_REGIME"
    STRUCTURE_NOT_CONFIRMED = "STRUCTURE_NOT_CONFIRMED"
    OFI_NOT_CONFIRMED = "OFI_NOT_CONFIRMED"
    CVD_NOT_CONFIRMED = "CVD_NOT_CONFIRMED"
    NO_ENTRY_TRIGGER = "NO_ENTRY_TRIGGER"
    SETUP_EXPIRED = "SETUP_EXPIRED"
    INVALID_STOP = "INVALID_STOP"
    EXISTING_POSITION = "EXISTING_POSITION"
    AMBIGUOUS_OUTCOME = "AMBIGUOUS_OUTCOME"


def generate_setups(
    market_30m: pd.DataFrame,
    bias_1h: pd.DataFrame,
    cfg: SetupEngineConfig,
) -> pd.DataFrame:
    """State machine penghasil kandidat setup."""
    if str(market_30m["timeframe"].iloc[0]) != cfg.timeframes.setup:
        raise DataContractError(f"market 30m harus timeframe {cfg.timeframes.setup}")
    
    for c in ("timestamp", "close_time", "high", "low", "close", "volume", "ofi", "cvd"):
        if c not in market_30m.columns:
            raise DataContractError(f"market 30m butuh kolom {c}")

    market_30m = market_30m.copy()
    if "available_at" not in market_30m.columns:
        market_30m["available_at"] = market_30m["close_time"]

    bias_1h = bias_1h.copy()
    if "available_at" not in bias_1h.columns:
        bias_1h["available_at"] = bias_1h["timestamp_bias"]
    if "close_time" not in bias_1h.columns:
        bias_1h["close_time"] = bias_1h["timestamp_bias"]
        
    aligned = align_htf_to_ltf(
        market_30m, 
        bias_1h, 
        columns=["bias", "bias_reason", "timestamp_bias"], 
        prefix="b_"
    )
    
    ms = MarketStructure.from_config(market_30m, cfg)
    timeline = ms.timeline()
    
    c_cfg = cfg.confirmation
    if c_cfg.required:
        has_real_ofi = "ofi" in market_30m.columns and not market_30m["ofi"].isna().all() and (market_30m["ofi"].abs().sum() > 0)
        has_real_cvd = "cvd" in market_30m.columns and not market_30m["cvd"].isna().all() and (market_30m["cvd"].abs().sum() > 0)
        if not (has_real_ofi or has_real_cvd):
            raise ValueError(
                "Mode B memerlukan data orderflow nyata. Jalankan scraper L2/trades terlebih dahulu atau gunakan Mode A."
            )

    if c_cfg.use_ofi and "ofi" in market_30m.columns:
        ofi_30m = rolling_ofi(market_30m["ofi"].to_numpy(), c_cfg.ofi_lookback)
    else:
        ofi_30m = np.full(len(market_30m), np.nan)

    if c_cfg.use_cvd and "cvd" in market_30m.columns:
        cvd_30m = cvd_slope(
            market_30m["cvd"].to_numpy(), 
            market_30m["volume"].to_numpy(), 
            c_cfg.cvd_lookback
        )
    else:
        cvd_30m = np.full(len(market_30m), np.nan)
    
    n_bars = len(market_30m)
    
    state = "NONE"
    current_bias = Bias.NEUTRAL.value
    start_n_swing = 0
    trigger_level = np.nan
    setup_timestamp = pd.NaT
    setup_timestamp_bias = pd.NaT
    wait_bars = 0
    
    setups: List[Dict[str, Any]] = []
    
    for j in range(n_bars):
        bar_bias = aligned["b_bias"].iloc[j]
        bias_reason = aligned["b_bias_reason"].iloc[j]
        if pd.isna(bar_bias):
            bar_bias = Bias.NEUTRAL.value
            bias_reason = "NO_BIAS"
            
        if bar_bias != current_bias:
            if state == "WAITING_TRIGGER":
                # Bias berubah membatalkan setup yang menunggu
                reason_str = str(bias_reason)
                # Map reason ke enum SetupRejectionReason sebisa mungkin
                if reason_str in SetupRejectionReason.__members__:
                    mapped_reason = reason_str
                else:
                    mapped_reason = SetupRejectionReason.NO_BIAS.value
                    
                setups.append(_build_row(
                    aligned, timeline, ofi_30m, cvd_30m, j,
                    bias=current_bias, 
                    direction="LONG" if current_bias == Bias.LONG_BIAS.value else "SHORT",
                    ts_bias=aligned["b_timestamp_bias"].iloc[j-1] if j > 0 else pd.NaT, 
                    ts_setup=setup_timestamp,
                    entry=trigger_level, 
                    valid=False, 
                    reason=mapped_reason
                ))
            current_bias = bar_bias
            if current_bias in (Bias.LONG_BIAS.value, Bias.SHORT_BIAS.value):
                state = "WAITING_PULLBACK"
                start_n_swing = timeline["n_swing_low"].iloc[j] if current_bias == Bias.LONG_BIAS.value else timeline["n_swing_high"].iloc[j]
            else:
                state = "NONE"
            continue
            
        if current_bias == Bias.NEUTRAL.value:
            continue
            
        is_long = (current_bias == Bias.LONG_BIAS.value)
        
        if state == "WAITING_PULLBACK":
            curr_n_swing = timeline["n_swing_low"].iloc[j] if is_long else timeline["n_swing_high"].iloc[j]
            if curr_n_swing > start_n_swing:
                state = "WAITING_TRIGGER"
                trigger_level = timeline["swing_high"].iloc[j] if is_long else timeline["swing_low"].iloc[j]
                setup_timestamp = market_30m["close_time"].iloc[j]
                setup_timestamp_bias = aligned["b_timestamp_bias"].iloc[j-1] if j > 0 else pd.NaT
                wait_bars = 0
                if np.isnan(trigger_level):
                    # No entry trigger available
                    setups.append(_build_row(
                        aligned, timeline, ofi_30m, cvd_30m, j,
                        bias=current_bias, 
                        direction="LONG" if is_long else "SHORT",
                        ts_bias=setup_timestamp_bias, 
                        ts_setup=setup_timestamp,
                        entry=trigger_level, 
                        valid=False, 
                        reason=SetupRejectionReason.NO_ENTRY_TRIGGER.value
                    ))
                    state = "WAITING_PULLBACK"
                    start_n_swing = curr_n_swing
                
        elif state == "WAITING_TRIGGER":
            wait_bars += 1
            
            high_j = market_30m["high"].iloc[j]
            low_j = market_30m["low"].iloc[j]
            
            triggered = False
            if is_long and high_j > trigger_level:
                triggered = True
            elif not is_long and low_j < trigger_level:
                triggered = True
                
            if triggered:
                reason = SetupRejectionReason.OK.value
                if c_cfg.required:
                    if c_cfg.use_ofi:
                        ofi_val = ofi_30m[j]
                        if not np.isfinite(ofi_val):
                            reason = SetupRejectionReason.OFI_NOT_CONFIRMED.value
                        elif is_long and ofi_val < c_cfg.ofi_threshold:
                            reason = SetupRejectionReason.OFI_NOT_CONFIRMED.value
                        elif not is_long and ofi_val > -c_cfg.ofi_threshold:
                            reason = SetupRejectionReason.OFI_NOT_CONFIRMED.value
                            
                    if reason == SetupRejectionReason.OK.value and c_cfg.use_cvd:
                        cvd_val = cvd_30m[j]
                        if not np.isfinite(cvd_val):
                            reason = SetupRejectionReason.CVD_NOT_CONFIRMED.value
                        elif is_long and cvd_val < c_cfg.cvd_slope_threshold:
                            reason = SetupRejectionReason.CVD_NOT_CONFIRMED.value
                        elif not is_long and cvd_val > -c_cfg.cvd_slope_threshold:
                            reason = SetupRejectionReason.CVD_NOT_CONFIRMED.value
                
                valid = (reason == SetupRejectionReason.OK.value)
                rp_dict = {}
                if valid:
                    swing = ms.get_last_confirmed_swing_low(market_30m["close_time"].iloc[j]) if is_long else ms.get_last_confirmed_swing_high(market_30m["close_time"].iloc[j])
                    
                    rp = build_risk_plan(
                        Direction.LONG if is_long else Direction.SHORT,
                        entry=trigger_level,
                        swing=swing,
                        entry_time=market_30m["close_time"].iloc[j],
                        cfg=cfg
                    )
                    
                    if not rp.valid:
                        valid = False
                        reason = SetupRejectionReason.INVALID_STOP.value
                    
                    rp_dict = rp.to_dict()
                
                setups.append(_build_row(
                    aligned, timeline, ofi_30m, cvd_30m, j,
                    bias=current_bias, 
                    direction="LONG" if is_long else "SHORT",
                    ts_bias=setup_timestamp_bias, 
                    ts_setup=setup_timestamp,
                    entry=trigger_level, 
                    valid=valid, 
                    reason=reason, 
                    rp_dict=rp_dict
                ))
                
                state = "WAITING_PULLBACK"
                start_n_swing = timeline["n_swing_low"].iloc[j] if is_long else timeline["n_swing_high"].iloc[j]
                
            else:
                if wait_bars >= cfg.execution.max_setup_wait_bars:
                    setups.append(_build_row(
                        aligned, timeline, ofi_30m, cvd_30m, j,
                        bias=current_bias, 
                        direction="LONG" if is_long else "SHORT",
                        ts_bias=setup_timestamp_bias, 
                        ts_setup=setup_timestamp,
                        entry=trigger_level, 
                        valid=False, 
                        reason=SetupRejectionReason.SETUP_EXPIRED.value
                    ))
                    state = "WAITING_PULLBACK"
                    start_n_swing = timeline["n_swing_low"].iloc[j] if is_long else timeline["n_swing_high"].iloc[j]
                    
    # Pastikan jika tidak ada setup sama sekali, kembalikan df kosong dengan kolom yang benar
    if not setups:
        return pd.DataFrame(columns=[
            "timestamp_bias", "timestamp_setup", "timestamp_entry", 
            "bias", "direction", "trigger_type", "timeframe",
            "structure_30m", "ofi_30m", "cvd_30m", "entry", 
            "stop_loss", "take_profit", "risk", "rr", "risk_pct",
            "setup_valid", "setup_rejection_reason"
        ])
    
    return pd.DataFrame(setups)


def _build_row(
    aligned: pd.DataFrame, 
    timeline: pd.DataFrame, 
    ofi_30m: np.ndarray, 
    cvd_30m: np.ndarray, 
    j: int,
    bias: str, 
    direction: str, 
    ts_bias: pd.Timestamp | NaTType, 
    ts_setup: pd.Timestamp | NaTType, 
    entry: float, 
    valid: bool, 
    reason: str, 
    rp_dict: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    rp = rp_dict or {}
    return {
        "timestamp_bias": ts_bias,
        "timestamp_setup": ts_setup,
        "timestamp_entry": aligned["timestamp"].iloc[j],
        "bias": bias,
        "direction": direction,
        "trigger_type": "BOS",
        "timeframe": "30m",
        "structure_30m": timeline["structure"].iloc[j],
        "ofi_30m": ofi_30m[j],
        "cvd_30m": cvd_30m[j],
        "entry": entry,
        "stop_loss": rp.get("stop_loss", np.nan),
        "take_profit": rp.get("take_profit", np.nan),
        "risk": rp.get("risk", np.nan),
        "rr": rp.get("rr", np.nan),
        "risk_pct": rp.get("risk_pct", np.nan),
        "setup_valid": valid,
        "setup_rejection_reason": reason if not valid else None
    }

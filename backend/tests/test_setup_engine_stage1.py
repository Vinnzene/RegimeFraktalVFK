"""Tahap 1 setup engine: config, data contract, alignment tanpa look-ahead."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.services.setup_engine.config import (
    SetupEngineConfig,
    load_setup_config,
    parse_period,
)
from app.services.setup_engine.data_contract import (
    MARKET_CONTRACT,
    REGIME_CONTRACT,
    DataContractError,
    LookAheadError,
    Regime,
    align_htf_to_ltf,
    choose_resolution_timeframe,
    detect_gaps,
    normalize_regime,
    resample_ohlcv,
    to_utc_timestamp,
    validate_frame,
)
from app.services.setup_engine.loader import (
    attach_regime,
    market_frame_from_ohlcv,
    regime_frame_from_timeline,
)

T0 = pd.Timestamp("2025-01-01 00:00", tz="UTC")


def market(tf: str, n: int, start: pd.Timestamp = T0, seed: int = 0) -> pd.DataFrame:
    step = pd.Timedelta(tf.replace("m", "min"))
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    open_ = np.concatenate([[100.0], close[:-1]])
    vol = rng.uniform(1, 10, n)
    buy = vol * rng.uniform(0, 1, n)
    df = pd.DataFrame(
        {
            "timestamp": [start + i * step for i in range(n)],
            "timeframe": tf,
            "open": open_,
            "high": np.maximum(open_, close) + 0.5,
            "low": np.minimum(open_, close) - 0.5,
            "close": close,
            "volume": vol,
            "buy_volume": buy,
            "sell_volume": vol - buy,
            "ofi": (2 * buy - vol) / vol,
            "cvd": np.cumsum(2 * buy - vol),
        }
    )
    return validate_frame(df, MARKET_CONTRACT, tf)


# ------------------------------------------------------------------ config


def test_default_config_matches_spec():
    f = SetupEngineConfig().flat()
    assert f["SETUP_TIMEFRAME"] == "30m"
    assert f["BIAS_TIMEFRAME"] == "1h"
    assert f["REGIME_TIMEFRAME"] == "4h"
    assert f["RESOLUTION_TIMEFRAME"] == "5m"
    assert f["RR"] == 2.0
    assert f["MAX_OPEN_POSITIONS"] == 1
    assert f["MAX_SETUP_WAIT_BARS"] == 6
    assert f["MAX_HOLDING_BARS"] == 8
    assert f["TAKER_FEE_PCT"] == 0.00075
    assert f["SLIPPAGE_TICKS"] == 1
    assert f["TICK_SIZE"] == 0.01
    assert f["USE_OFI_CONFIRMATION"] is False
    assert f["USE_CVD_CONFIRMATION"] is False
    assert f["CONFIRMATION_REQUIRED"] is False
    assert f["SWING_LOOKBACK"] == 3
    assert f["SL_BUFFER"] == 0
    assert f["ALLOW_ENTRY_DURING_TRANSITION"] is False


def test_project_yaml_loads_and_equals_defaults():
    cfg = load_setup_config()
    assert cfg.flat() == SetupEngineConfig().flat()


def test_setup_yaml_does_not_touch_model_config_hash():
    from app.core.config import load_config

    before = load_config().config_hash
    load_setup_config()
    assert load_config().config_hash == before


@pytest.mark.parametrize(
    "patch",
    [
        {"risk": {"rr": 0}},
        {"risk": {"sl_buffer": -1}},
        {"risk": {"min_risk_distance_pct": 0.1, "max_risk_distance_pct": 0.05}},
        {"execution": {"max_open_positions": 2}},
        {"execution": {"max_holding_bars": 0}},
        {"structure": {"swing_lookback": 0}},
        {"confirmation": {"ofi_threshold": 1.5}},
        {"timeframes": {"setup": "2h"}},
        {"timeframes": {"setup": "45m"}},
        {"regime": {"source": "model_Z"}},
        {"walk_forward": {"test_period": "1X"}},
        {"unknown_section": {}},
    ],
)
def test_invalid_config_rejected(patch):
    with pytest.raises(ValidationError):
        SetupEngineConfig(**patch)


def test_setup_hash_changes_with_parameter():
    assert SetupEngineConfig().setup_hash != SetupEngineConfig(risk={"rr": 3.0}).setup_hash


def test_parse_period_calendar_months():
    assert T0 + parse_period("1M") == pd.Timestamp("2025-02-01", tz="UTC")
    assert T0 + parse_period("12M") == pd.Timestamp("2026-01-01", tz="UTC")


def test_load_setup_config_from_file(tmp_path: Path):
    p = tmp_path / "s.yaml"
    p.write_text("risk:\n  rr: 3.0\nstructure:\n  swing_lookback: 2\n", encoding="utf-8")
    cfg = load_setup_config(p)
    assert cfg.risk.rr == 3.0 and cfg.structure.swing_lookback == 2


# ------------------------------------------------------------ data contract


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("persistent", Regime.PERSISTENT),
        ("Persistent", Regime.PERSISTENT),
        ("random_like", Regime.RANDOM_LIKE),
        ("Random-like", Regime.RANDOM_LIKE),
        ("ANTI_PERSISTENT", Regime.ANTI_PERSISTENT),
        ("anti-persistent", Regime.ANTI_PERSISTENT),
        ("uncertain_rule", Regime.UNCERTAIN),
        ("uncertain_lowconf", Regime.UNCERTAIN),
    ],
)
def test_normalize_regime(raw, expected):
    assert normalize_regime(raw) is expected


def test_normalize_regime_rejects_unknown():
    with pytest.raises(DataContractError):
        normalize_regime("bullish")


def test_missing_column_rejected():
    df = market("1h", 5).drop(columns=["ofi"])
    with pytest.raises(DataContractError, match="ofi"):
        validate_frame(df, MARKET_CONTRACT)


def test_naive_timestamp_rejected():
    with pytest.raises(DataContractError):
        to_utc_timestamp(pd.Series(pd.date_range("2025-01-01", periods=3, freq="h")))


def test_epoch_seconds_become_utc():
    s = to_utc_timestamp(pd.Series([1735689600]), unit="s")
    assert str(s.dt.tz) == "UTC" and s.iloc[0] == T0


def test_non_utc_converted_to_utc():
    df = market("1h", 3)
    df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Jakarta")
    out = validate_frame(df.drop(columns=["close_time", "available_at"]), MARKET_CONTRACT)
    assert str(out["timestamp"].dt.tz) == "UTC"
    assert out["timestamp"].iloc[0] == T0


def test_duplicate_and_unsorted_rejected():
    df = market("1h", 5).drop(columns=["close_time", "available_at"])
    with pytest.raises(DataContractError, match="duplikat"):
        validate_frame(pd.concat([df, df.iloc[[2]]]).sort_values("timestamp"), MARKET_CONTRACT)
    with pytest.raises(DataContractError, match="monoton"):
        validate_frame(df.iloc[::-1], MARKET_CONTRACT)


def test_bad_high_low_rejected():
    df = market("1h", 5).drop(columns=["close_time", "available_at"])
    df.loc[2, "high"] = df["low"].iloc[2] - 1
    with pytest.raises(DataContractError, match="high/low"):
        validate_frame(df, MARKET_CONTRACT)


def test_available_before_close_is_lookahead():
    df = market("1h", 3).drop(columns=["close_time"])
    df["available_at"] = df["timestamp"]
    with pytest.raises(LookAheadError):
        validate_frame(df, MARKET_CONTRACT)


def test_gap_detection():
    df = market("1h", 10)
    df = df.drop(index=[4, 5]).reset_index(drop=True)
    gaps = detect_gaps(df)
    assert len(gaps) == 1 and gaps["missing_bars"].iloc[0] == 2


# ----------------------------------------------------------------- alignment


def test_htf_alignment_uses_close_time_not_open_time():
    h4 = market("4h", 3, seed=1)
    m30 = market("30m", 24, seed=2)
    out = align_htf_to_ltf(m30, h4, ["close"], prefix="h4_")
    # Bar 30M pertama (close 00:30) belum boleh melihat bar 4H 00:00.
    assert out["h4_timestamp"].iloc[:7].isna().all()
    # Bar 30M 03:30-04:00 close 04:00 = saat bar 4H 00:00 close -> boleh.
    assert out["h4_timestamp"].iloc[7] == T0
    assert out["h4_close"].iloc[7] == h4["close"].iloc[0]
    # Bar 30M 04:00-04:30 masih melihat bar 4H 00:00, bukan 04:00.
    assert out["h4_timestamp"].iloc[8] == T0
    assert out["h4_timestamp"].iloc[15] == T0 + pd.Timedelta(hours=4)


def test_alignment_never_leaks_randomized():
    rng = np.random.default_rng(7)
    h1 = market("1h", 200, seed=3)
    m30 = market("30m", 400, seed=4)
    # Prediksi berstride dengan delay ketersediaan acak (≥ close).
    sel = np.sort(rng.choice(len(h1), 60, replace=False))
    reg = h1.iloc[sel].copy()
    reg["available_at"] = reg["close_time"] + pd.to_timedelta(rng.integers(0, 3, len(reg)), unit="h")
    reg = reg.sort_values("available_at").drop_duplicates("available_at", keep="last")
    out = align_htf_to_ltf(m30, reg, ["close"], prefix="h1_")
    have = out["h1_available_at"].notna()
    assert (out.loc[have, "h1_available_at"] <= out.loc[have, "close_time"]).all()
    # Dan selalu yang TERBARU yang tersedia.
    for i in np.where(have)[0][::17]:
        cands = reg[reg["available_at"] <= out["close_time"].iloc[i]]
        assert out["h1_available_at"].iloc[i] == cands["available_at"].max()


def test_alignment_unaffected_by_future_htf_changes():
    h4 = market("4h", 6, seed=5)
    m30 = market("30m", 48, seed=6)
    a = align_htf_to_ltf(m30, h4, ["close"], prefix="h4_")
    h4b = h4.copy()
    h4b.loc[3:, "close"] += 1_000
    b = align_htf_to_ltf(m30, h4b, ["close"], prefix="h4_")
    cutoff = h4["available_at"].iloc[3]
    early = a["close_time"] < cutoff
    pd.testing.assert_series_equal(a.loc[early, "h4_close"], b.loc[early, "h4_close"])
    assert not a.loc[~early, "h4_close"].equals(b.loc[~early, "h4_close"])


def test_alignment_guard_raises_on_tampered_result():
    from app.services.setup_engine.data_contract import assert_no_lookahead_alignment

    h4 = market("4h", 3)
    m30 = market("30m", 24)
    out = align_htf_to_ltf(m30, h4, ["close"], prefix="h4_")
    out.loc[0, "h4_available_at"] = out["close_time"].iloc[0] + pd.Timedelta(minutes=1)
    with pytest.raises(LookAheadError):
        assert_no_lookahead_alignment(out, "h4_")


def test_regime_prediction_available_after_window_bar_closes():
    tl = pd.DataFrame(
        {
            "time": [int(T0.timestamp()) + k * 4 * 3600 for k in range(3)],
            "hurst_dfa_regime": ["persistent", "uncertain_rule", "random_like"],
            "model_A": ["persistent", "anti_persistent", "random_like"],
            "model_A_maxprob": [0.4, 0.5, 0.6],
        }
    )
    reg = regime_frame_from_timeline(tl, "1h", "model_A")
    assert (reg["available_at"] == reg["timestamp"] + pd.Timedelta(hours=1)).all()
    assert reg["predicted_regime"].tolist() == ["PERSISTENT", "ANTI_PERSISTENT", "RANDOM_LIKE"]
    assert reg["reference_regime"].tolist()[1] == "UNCERTAIN"

    mkt = market("1h", 12)
    joined = attach_regime(mkt, reg)
    # Bar 00:00 close 01:00 = available_at prediksi pertama -> boleh.
    assert joined["predicted_regime"].iloc[0] == "PERSISTENT"
    # Bar 03:00 (close 04:00) belum boleh melihat prediksi bar 04:00.
    assert joined["predicted_regime"].iloc[3] == "PERSISTENT"
    assert joined["predicted_regime"].iloc[4] == "ANTI_PERSISTENT"


def test_regime_not_carried_past_last_prediction():
    tl = pd.DataFrame(
        {
            "time": [int(T0.timestamp()) + k * 4 * 3600 for k in range(2)],
            "hurst_dfa_regime": ["persistent", "persistent"],
            "model_A": ["persistent", "random_like"],
            "model_A_maxprob": [0.4, 0.5],
        }
    )
    reg = regime_frame_from_timeline(tl, "1h", "model_A")
    joined = attach_regime(market("1h", 20), reg)
    # Prediksi terakhir tersedia 05:00; stride 4 jam -> berlaku s.d. bar close < 09:00.
    assert joined["predicted_regime"].iloc[7] == "RANDOM_LIKE"
    assert joined["predicted_regime"].iloc[8:].isna().all()


def test_market_frame_from_project_ohlcv_schema():
    raw = pd.DataFrame(
        {
            "time": [int(T0.timestamp()) + k * 3600 for k in range(4)],
            "open": [1.0, 2, 3, 4],
            "high": [2.0, 3, 4, 5],
            "low": [0.5, 1, 2, 3],
            "close": [2.0, 3, 4, 5],
            "volume": [10.0, 10, 10, 0],
            "taker_buy_volume": [7.0, 2, 5, 0],
            "n_trades": [1, 1, 1, 0],
        }
    )
    m = market_frame_from_ohlcv(raw, "1h")
    assert np.allclose(m["ofi"], [0.4, -0.6, 0.0, 0.0])
    assert np.allclose(m["cvd"], [4.0, -2.0, -2.0, -2.0])
    assert (m["close_time"] - m["timestamp"] == pd.Timedelta(hours=1)).all()


# --------------------------------------------------------------- resolution


def test_resolution_fallback_and_warning():
    assert choose_resolution_timeframe("5m", "30m", ["5m", "30m", "1h"]) == ("5m", None)
    tf, msg = choose_resolution_timeframe("5m", "30m", ["15m", "30m"])
    assert tf == "15m" and msg is not None and "lebih rendah" in msg
    tf, msg = choose_resolution_timeframe("5m", "30m", ["30m", "1h"])
    assert tf == "30m" and msg is not None and "AMBIGUOUS" in msg


def test_resample_drops_incomplete_bars():
    m5 = market("5m", 14)
    out = resample_ohlcv(m5, "30m")
    assert len(out) == 2
    first = m5.iloc[:6]
    assert out["open"].iloc[0] == first["open"].iloc[0]
    assert out["high"].iloc[0] == first["high"].max()
    assert out["low"].iloc[0] == first["low"].min()
    assert out["close"].iloc[0] == first["close"].iloc[-1]
    assert np.isclose(out["volume"].iloc[0], first["volume"].sum())
    assert out["cvd"].iloc[0] == first["cvd"].iloc[-1]

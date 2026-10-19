"""Tahap 4 setup engine: risk engine (structural SL, RR tetap)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.services.setup_engine.config import SetupEngineConfig
from app.services.setup_engine.data_contract import LookAheadError
from app.services.setup_engine.market_structure import MarketStructure, Swing, SwingKind
from app.services.setup_engine.risk_engine import (
    INVALID_STOP,
    build_risk_plan,
    structural_stop,
    take_profit,
)

T0 = pd.Timestamp("2025-01-01 00:00", tz="UTC")
ENTRY_T = T0 + pd.Timedelta(hours=10)


def swing(kind: SwingKind, price: float, confirmed: pd.Timestamp = T0 + pd.Timedelta(hours=5)) -> Swing:
    return Swing(
        kind=kind,
        pivot_index=2,
        pivot_time=T0 + pd.Timedelta(hours=2),
        price=price,
        confirmation_index=5,
        confirmation_time=confirmed,
    )


def cfg(**risk) -> SetupEngineConfig:
    return SetupEngineConfig(risk=risk) if risk else SetupEngineConfig()


# ------------------------------------------------------- 1-2 structural SL


def test_long_structural_sl():
    p = build_risk_plan("LONG", 100_000.0, swing(SwingKind.LOW, 99_000.0), ENTRY_T, cfg())
    assert p.valid and p.rejection_reason is None
    assert p.stop_loss == 99_000.0
    assert p.risk == 1_000.0
    assert p.swing_price == 99_000.0


def test_short_structural_sl():
    p = build_risk_plan("SHORT", 100_000.0, swing(SwingKind.HIGH, 101_500.0), ENTRY_T, cfg())
    assert p.valid
    assert p.stop_loss == 101_500.0
    assert p.risk == 1_500.0


def test_sl_comes_from_confirmed_swing_of_market_structure():
    mids = 100_000 + np.array([0, -400, 200, -800, 600, -300, 900, 100, 1200, 500, 1500])
    ts = pd.Series([T0 + i * pd.Timedelta(hours=1) for i in range(mids.size)], dtype="datetime64[ns, UTC]")
    df = pd.DataFrame(
        {"timestamp": ts, "close_time": ts + pd.Timedelta(hours=1), "high": mids + 50, "low": mids - 50, "close": mids}
    )
    ms = MarketStructure(df, lookback=1)
    t = df["close_time"].iloc[-1]
    sw = ms.get_last_confirmed_swing_low(t)
    assert sw is not None
    entry = float(mids[-1])
    p = build_risk_plan("LONG", entry, sw, t, cfg())
    assert p.stop_loss == sw.price
    assert p.swing_confirmation_time <= t


def test_unconfirmed_swing_is_lookahead_error():
    late = swing(SwingKind.LOW, 99_000.0, confirmed=ENTRY_T + pd.Timedelta(minutes=1))
    with pytest.raises(LookAheadError):
        build_risk_plan("LONG", 100_000.0, late, ENTRY_T, cfg())


def test_swing_kind_must_match_direction():
    with pytest.raises(ValueError):
        build_risk_plan("LONG", 100_000.0, swing(SwingKind.HIGH, 101_000.0), ENTRY_T, cfg())
    with pytest.raises(ValueError):
        build_risk_plan("SHORT", 100_000.0, swing(SwingKind.LOW, 99_000.0), ENTRY_T, cfg())


# ------------------------------------------------------------ 3. RR 1:2


def test_rr_1_to_2_long():
    p = build_risk_plan("LONG", 100_000.0, swing(SwingKind.LOW, 99_000.0), ENTRY_T, cfg())
    assert p.rr == 2.0
    assert p.take_profit == 102_000.0
    assert p.reward == 2_000.0
    assert math.isclose(p.reward / p.risk, 2.0)


def test_rr_1_to_2_short():
    p = build_risk_plan("SHORT", 100_000.0, swing(SwingKind.HIGH, 101_000.0), ENTRY_T, cfg())
    assert p.take_profit == 98_000.0
    assert p.reward == 2_000.0
    assert math.isclose((p.entry - p.take_profit) / (p.stop_loss - p.entry), 2.0)


def test_rr_only_from_config():
    p = build_risk_plan("LONG", 100_000.0, swing(SwingKind.LOW, 99_000.0), ENTRY_T, cfg(rr=3.0))
    assert p.take_profit == 103_000.0 and p.rr == 3.0
    with pytest.raises(TypeError):
        build_risk_plan("LONG", 100_000.0, swing(SwingKind.LOW, 99_000.0), ENTRY_T, cfg(), rr=5.0)  # type: ignore[call-arg]


def test_helpers():
    assert structural_stop("LONG", 100.0, 1.0) == 99.0
    assert structural_stop("SHORT", 100.0, 1.0) == 101.0
    assert take_profit("LONG", 100.0, 5.0, 2.0) == 110.0
    assert take_profit("short", 100.0, 5.0, 2.0) == 90.0
    with pytest.raises(ValueError):
        structural_stop("FLAT", 100.0, 0.0)
    with pytest.raises(ValueError):
        structural_stop("LONG", 100.0, -1.0)


# ------------------------------------------------------- 4. INVALID_STOP


@pytest.mark.parametrize(
    "direction,entry,kind,price,detail",
    [
        ("LONG", 100_000.0, SwingKind.LOW, 100_500.0, "WRONG_SIDE"),
        ("SHORT", 100_000.0, SwingKind.HIGH, 99_500.0, "WRONG_SIDE"),
        ("LONG", 100_000.0, SwingKind.LOW, 100_000.0, "ZERO_RISK"),
        ("SHORT", 100_000.0, SwingKind.HIGH, 100_000.0, "ZERO_RISK"),
        ("LONG", 100_000.0, SwingKind.LOW, 99_950.0, "RISK_TOO_SMALL"),  # 0.05% < 0.1%
        ("SHORT", 100_000.0, SwingKind.HIGH, 100_050.0, "RISK_TOO_SMALL"),
        ("LONG", 100_000.0, SwingKind.LOW, 90_000.0, "RISK_TOO_LARGE"),  # 10% > 5%
    ],
)
def test_invalid_stop(direction, entry, kind, price, detail):
    p = build_risk_plan(direction, entry, swing(kind, price), ENTRY_T, cfg())
    assert not p.valid
    assert p.rejection_reason == INVALID_STOP
    assert p.invalid_detail == detail
    assert math.isnan(p.take_profit)


def test_missing_swing_and_bad_entry_are_invalid_stop():
    p = build_risk_plan("LONG", 100_000.0, None, ENTRY_T, cfg())
    assert p.rejection_reason == INVALID_STOP and p.invalid_detail == "NO_SWING"
    p = build_risk_plan("LONG", float("nan"), swing(SwingKind.LOW, 99_000.0), ENTRY_T, cfg())
    assert p.rejection_reason == INVALID_STOP and p.invalid_detail == "INVALID_ENTRY"


def test_min_risk_boundary_is_inclusive():
    p = build_risk_plan("LONG", 100_000.0, swing(SwingKind.LOW, 99_900.0), ENTRY_T, cfg())
    assert p.valid and math.isclose(p.risk_pct, 0.001)


# --------------------------------------------------------- 5. SL_BUFFER


def test_sl_buffer_long_widens_stop_and_moves_tp():
    base = build_risk_plan("LONG", 100_000.0, swing(SwingKind.LOW, 99_000.0), ENTRY_T, cfg())
    buf = build_risk_plan("LONG", 100_000.0, swing(SwingKind.LOW, 99_000.0), ENTRY_T, cfg(sl_buffer=100.0))
    assert buf.stop_loss == 98_900.0
    assert buf.risk == base.risk + 100.0
    assert buf.take_profit == 100_000.0 + 2 * 1_100.0


def test_sl_buffer_short_widens_stop_and_moves_tp():
    buf = build_risk_plan("SHORT", 100_000.0, swing(SwingKind.HIGH, 101_000.0), ENTRY_T, cfg(sl_buffer=100.0))
    assert buf.stop_loss == 101_100.0
    assert buf.risk == 1_100.0
    assert buf.take_profit == 100_000.0 - 2 * 1_100.0


def test_sl_buffer_can_rescue_too_small_risk():
    tight = swing(SwingKind.LOW, 99_950.0)
    assert not build_risk_plan("LONG", 100_000.0, tight, ENTRY_T, cfg()).valid
    assert build_risk_plan("LONG", 100_000.0, tight, ENTRY_T, cfg(sl_buffer=100.0)).valid


# -------------------------------------------------------------- purity


def test_pure_and_deterministic():
    sw = swing(SwingKind.LOW, 99_000.0)
    c = cfg()
    before = c.canonical()
    a = build_risk_plan("LONG", 100_000.0, sw, ENTRY_T, c)
    b = build_risk_plan("LONG", 100_000.0, sw, ENTRY_T, c)
    assert a == b
    assert c.canonical() == before
    assert sw.price == 99_000.0
    assert set(a.to_dict()) >= {"entry", "stop_loss", "take_profit", "risk", "reward", "rr", "valid", "rejection_reason"}

"""Tahap 2 setup engine: market structure (swing, HH/HL, BOS) tanpa look-ahead."""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd
import pytest

from app.services.setup_engine.config import SetupEngineConfig
from app.services.setup_engine.data_contract import DataContractError
from app.services.setup_engine.market_structure import (
    MarketStructure,
    Structure,
    classify_structure,
    detect_pivots,
)

T0 = pd.Timestamp("2025-01-01 00:00", tz="UTC")
H = pd.Timedelta(hours=1)


def frame(
    mids: Sequence[float] | np.ndarray,
    half: float = 0.5,
    close: Optional[Sequence[float]] = None,
    tf: str = "1h",
) -> pd.DataFrame:
    price = np.asarray(mids, dtype=float)
    step = pd.Timedelta(tf.replace("m", "min"))
    ts = pd.Series([T0 + i * step for i in range(price.size)], dtype="datetime64[ns, UTC]")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "close_time": ts + step,
            "timeframe": tf,
            "open": price,
            "high": price + half,
            "low": price - half,
            "close": price if close is None else np.asarray(close, dtype=float),
        }
    )


def hl_frame(high: Sequence[float], low: Sequence[float]) -> pd.DataFrame:
    hi = np.asarray(high, dtype=float)
    lo = np.asarray(low, dtype=float)
    ts = pd.Series([T0 + i * H for i in range(hi.size)])
    return pd.DataFrame(
        {"timestamp": ts, "close_time": ts + H, "high": hi, "low": lo, "close": (hi + lo) / 2}
    )


UP = [10, 12, 11, 13, 12, 14, 13, 15, 14]
DOWN = [20, 18, 19, 17, 18, 16, 17, 15, 16]
EXPAND = [10, 12, 9, 13, 8, 14, 7, 15, 6]
CONTRACT = [10, 16, 6, 15, 7, 14, 8, 13, 9]


# ------------------------------------------------------------ classification


@pytest.mark.parametrize(
    "mids,expected",
    [(UP, Structure.BULLISH), (DOWN, Structure.BEARISH), (EXPAND, Structure.NEUTRAL), (CONTRACT, Structure.NEUTRAL)],
)
def test_structure_label_patterns(mids, expected):
    ms = MarketStructure(frame(mids), lookback=1)
    end = ms.structure_series()["close_time"].iloc[-1]
    st = ms.structure_at(end)
    assert st.label is expected
    assert ms.structure_series()["structure"].iloc[-1] == expected.value


def test_bullish_swings_are_hh_hl():
    ms = MarketStructure(frame(UP), lookback=1)
    st = ms.structure_at(ms.structure_series()["close_time"].iloc[-1])
    assert st.last_high is not None and st.prev_high is not None
    assert st.last_low is not None and st.prev_low is not None
    assert st.last_high.price > st.prev_high.price
    assert st.last_low.price > st.prev_low.price


def test_classify_structure_rules():
    assert classify_structure(2, 1, 2, 1) is Structure.BULLISH
    assert classify_structure(1, 2, 1, 2) is Structure.BEARISH
    assert classify_structure(2, 1, 1, 2) is Structure.NEUTRAL
    assert classify_structure(1, 1, 2, 1) is Structure.NEUTRAL  # equal high -> bukan HH
    assert classify_structure(None, 1, 2, 1) is Structure.NEUTRAL


def test_structure_with_lookback_3():
    mids = []
    base = 100.0
    for _ in range(6):
        mids += [base, base + 2, base + 4, base + 6, base + 4, base + 2, base + 1]
        base += 3
    ms = MarketStructure(frame(mids), lookback=3)
    labels = ms.structure_series()["structure"]
    assert labels.iloc[-1] == "BULLISH"
    assert (labels.iloc[:10] == "NEUTRAL").all()


# -------------------------------------------------------------- confirmation


def test_swing_not_visible_before_confirmation_time():
    k = 3
    ms = MarketStructure(frame([1, 2, 3, 9, 3, 2, 1, 0, 0, 0]), lookback=k)
    sf = ms.swings_frame()
    sh = sf[sf["kind"] == "HIGH"].iloc[0]
    assert sh["pivot_index"] == 3
    assert sh["confirmation_index"] == 3 + k
    assert sh["confirmation_time"] == T0 + (3 + k + 1) * H  # close bar i+k
    just_before = sh["confirmation_time"] - pd.Timedelta(1, unit="ns")
    assert ms.get_last_confirmed_swing_high(just_before) is None
    got = ms.get_last_confirmed_swing_high(sh["confirmation_time"])
    assert got is not None and got.pivot_index == 3 and got.price == 9.5
    assert ms.confirmed_swings(just_before).empty


def test_series_only_uses_confirmed_swings():
    ms = MarketStructure(frame(UP), lookback=1)
    s = ms.structure_series()
    sf = ms.swings_frame()
    for j in range(len(s)):
        t = s["close_time"].iloc[j]
        n_hi = int(((sf["kind"] == "HIGH") & (sf["confirmation_time"] <= t)).sum())
        assert s["n_swing_high"].iloc[j] == n_hi
        if n_hi:
            got = ms.get_last_confirmed_swing_high(t)
            assert got is not None and got.pivot_time == s["swing_high_time"].iloc[j]


def test_last_k_bars_never_confirm():
    k = 3
    ms = MarketStructure(frame([1, 2, 3, 4, 5, 6, 7, 20, 7, 6]), lookback=k)
    # Puncak di bar 7 butuh bar 8..10; bar 10 belum ada.
    assert ms.swings_frame().empty


# ----------------------------------------------------------- future invariance


@pytest.mark.parametrize("cut", [10, 25, 40])
def test_appending_or_changing_future_does_not_change_past(cut):
    rng = np.random.default_rng(cut)
    mids = 100 + np.cumsum(rng.normal(0, 1, 60))
    full = frame(mids)
    ms_full = MarketStructure(full, lookback=3)

    truncated = MarketStructure(full.iloc[:cut].copy(), lookback=3)
    tampered = full.copy()
    tampered.loc[cut:, ["open", "high", "low", "close"]] += rng.normal(0, 50, (60 - cut, 1))
    tampered["high"] = np.maximum(tampered["high"], tampered[["open", "close"]].max(axis=1))
    tampered["low"] = np.minimum(tampered["low"], tampered[["open", "close"]].min(axis=1))
    ms_tamp = MarketStructure(tampered, lookback=3)

    a = ms_full.timeline().iloc[:cut].reset_index(drop=True)
    for other in (truncated.timeline().iloc[:cut], ms_tamp.timeline().iloc[:cut]):
        pd.testing.assert_frame_equal(a, other.reset_index(drop=True))

    t = full["close_time"].iloc[cut - 1]
    assert ms_full.structure_at(t).label == ms_tamp.structure_at(t).label
    for get in ("get_last_confirmed_swing_high", "get_last_confirmed_swing_low"):
        assert getattr(ms_full, get)(t) == getattr(ms_tamp, get)(t)


# ----------------------------------------------------------------------- BOS


def test_bullish_bos_after_confirmation_only_once():
    # k=1. Swing high di bar 1 (11.5), terkonfirmasi di close bar 2.
    mids = [10, 11, 10, 10.5, 12, 13, 14]
    ms = MarketStructure(frame(mids), lookback=1)
    bos = ms.bos_series("close")
    assert bos["bos_bullish"].tolist() == [False, False, False, False, True, False, False]
    assert bos["bos_bullish_level"].iloc[4] == 11.5
    assert bos["bos_bullish_swing_time"].iloc[4] == T0 + H


def test_bar_that_breaks_level_invalidates_pivot_instead():
    # k=1. Bar 2 menembus high bar 1 -> bar 1 BUKAN pivot (syarat kanan gagal),
    # jadi "swing terkonfirmasi lalu langsung ditembus bar yang sama" mustahil.
    df = hl_frame([10, 12, 12.6, 13], [9, 11, 10, 12])
    df["close"] = [9.5, 11.5, 12.5, 12.8]
    ms = MarketStructure(df, lookback=1)
    sw = ms.swings_frame()
    assert 1 not in sw[sw["kind"] == "HIGH"]["pivot_index"].tolist()
    assert not ms.bos_series("close")["bos_bullish"].any()


@pytest.mark.parametrize("mode", ["close", "wick"])
def test_bos_level_was_confirmed_before_bar_opened(mode):
    rng = np.random.default_rng(11)
    ms = MarketStructure(frame(100 + np.cumsum(rng.normal(0, 1, 400))), lookback=3)
    bos = ms.bos_series(mode)
    sf = ms.swings_frame()
    for side, kind in (("bullish", "HIGH"), ("bearish", "LOW")):
        hits = bos[bos[f"bos_{side}"]]
        assert len(hits) > 5
        for _, row in hits.iterrows():
            sw = sf[(sf["kind"] == kind) & (sf["pivot_time"] == row[f"bos_{side}_swing_time"])].iloc[0]
            assert sw["confirmation_time"] <= row["timestamp"]
            assert sw["price"] == row[f"bos_{side}_level"]
        # Setiap swing ditembus paling banyak sekali.
        assert not hits[f"bos_{side}_swing_time"].duplicated().any()


def test_bearish_bos_and_wick_mode():
    mids = [20, 19, 20, 19.6, 18.6, 18]
    ms = MarketStructure(frame(mids), lookback=1)
    # Swing low bar 1 = 18.5, konfirmasi close bar 2.
    close_bos = ms.bos_series("close")["bos_bearish"].tolist()
    wick_bos = ms.bos_series("wick")["bos_bearish"].tolist()
    assert close_bos == [False, False, False, False, False, True]
    assert wick_bos == [False, False, False, False, True, False]


def test_close_equal_to_level_is_not_break():
    df = hl_frame([10, 12, 11, 12.5], [9, 11, 10, 11])
    df["close"] = [9.5, 11.5, 10.5, 12.0]
    ms = MarketStructure(df, lookback=1)
    assert not ms.bos_series("close")["bos_bullish"].any()


# ---------------------------------------------------------------- edge cases


def test_too_short_data_is_neutral_without_swings():
    for n in (0, 1, 2, 6):
        ms = MarketStructure(frame(list(range(n))), lookback=3)
        assert ms.swings_frame().empty
        s = ms.structure_series()
        assert len(s) == n and (s["structure"] == "NEUTRAL").all()
        if n:
            assert ms.structure_at(s["close_time"].iloc[-1]).label is Structure.NEUTRAL
            assert not ms.bos_series()["bos_bullish"].any()


def test_equal_highs_plateau_takes_first_bar():
    high = [10, 12, 12, 11, 10]
    low = [9, 10, 10, 9.5, 9]
    hi, _ = detect_pivots(np.array(high), np.array(low), 1)
    assert hi.tolist() == [1]


def test_equal_lows_plateau_takes_first_bar():
    high = [12, 11, 11, 11.5, 12]
    low = [10, 8, 8, 9, 10]
    _, lo = detect_pivots(np.array(high), np.array(low), 1)
    assert lo.tolist() == [1]


def test_equal_swing_highs_give_neutral():
    # High pivot sama persis (12.5) dua kali, low naik -> bukan HH -> NEUTRAL.
    mids = [10, 12, 10, 12, 11, 12.5]
    high = [10.5, 12.5, 10.5, 12.5, 11.5, 13]
    low = [9.5, 11.5, 9.0, 11.5, 10.0, 12]
    ms = MarketStructure(hl_frame(high, low), lookback=1)
    st = ms.structure_at(ms.structure_series()["close_time"].iloc[-1])
    assert st.last_high is not None and st.prev_high is not None
    assert st.last_high.price == st.prev_high.price == 12.5
    assert st.label is Structure.NEUTRAL


def test_outside_bar_can_be_both_high_and_low():
    high = [10, 15, 10]
    low = [9, 5, 9]
    hi, lo = detect_pivots(np.array(high), np.array(low), 1)
    assert hi.tolist() == [1] and lo.tolist() == [1]


def test_input_validation():
    df = frame(UP)
    with pytest.raises(DataContractError):
        MarketStructure(df.drop(columns=["high"]))
    with pytest.raises(DataContractError):
        MarketStructure(df.iloc[::-1].reset_index(drop=True))
    naive = df.copy()
    naive["timestamp"] = naive["timestamp"].dt.tz_localize(None)
    with pytest.raises(DataContractError):
        MarketStructure(naive)
    ms = MarketStructure(df, lookback=1)
    with pytest.raises(DataContractError):
        ms.structure_at(pd.Timestamp("2025-01-01 05:00"))
    with pytest.raises(ValueError):
        ms.bos_series("body")


def test_works_on_30m_and_uses_config_lookback():
    cfg = SetupEngineConfig(structure={"swing_lookback": 2})
    df = frame(UP, tf="30m").drop(columns=["close_time"])
    ms = MarketStructure.from_config(df, cfg)
    assert ms.lookback == 2
    s = ms.structure_series()
    assert (s["close_time"] - s["timestamp"] == pd.Timedelta(minutes=30)).all()

"""Tahap 3 setup engine: regime context, filter transisi, directional bias."""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.services.setup_engine.config import SetupEngineConfig, load_setup_config
from app.services.setup_engine.data_contract import LookAheadError
from app.services.setup_engine.directional_bias_engine import (
    compute_bias,
    cvd_slope,
    rolling_ofi,
    validate_bias_no_lookahead,
)
from app.services.setup_engine.regime_context import (
    context_table_frame,
    direction_blocked,
    regime_context,
    strictest,
    track_transitions,
)

T0 = pd.Timestamp("2025-01-01 00:00", tz="UTC")
H = pd.Timedelta(hours=1)
P, R, A, U = "PERSISTENT", "RANDOM_LIKE", "ANTI_PERSISTENT", "UNCERTAIN"

# ------------------------------------------------------------------ helpers

UP_SEG = [0, 2, 1, 3, 2, 4, 3, 5, 4, 6]
DOWN_SEG = [0, -2, -1, -3, -2, -4, -3, -5, -4, -6]


def cfg(**kw) -> SetupEngineConfig:
    base = {"structure": {"swing_lookback": 1}, "transition": {"confirm_predictions": 1}}
    for k, v in kw.items():
        base[k] = {**base.get(k, {}), **v}
    return SetupEngineConfig(**base)


def market_1h(
    mids: Sequence[float] | np.ndarray, ofi: float | Sequence[float] | np.ndarray = 0.2
) -> pd.DataFrame:
    price = 100 + np.asarray(mids, dtype=float)
    n = price.size
    ts = pd.Series([T0 + i * H for i in range(n)], dtype="datetime64[ns, UTC]")
    ofi_arr = np.broadcast_to(np.asarray(ofi, dtype=float), (n,)).copy()
    vol = np.full(n, 10.0)
    delta = ofi_arr * vol
    return pd.DataFrame(
        {
            "timestamp": ts,
            "close_time": ts + H,
            "timeframe": "1h",
            "open": price,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": vol,
            "ofi": ofi_arr,
            "cvd": np.cumsum(delta),
        }
    )


def preds(regimes: Sequence[str], every_h: int = 1, conf: Optional[Sequence[float]] = None) -> pd.DataFrame:
    n = len(regimes)
    return pd.DataFrame(
        {
            "available_at": [T0 + (i * every_h + 1) * H for i in range(n)],
            "predicted_regime": list(regimes),
            "confidence": list(conf) if conf is not None else [0.6] * n,
        }
    )


def run(mids, r4, r1, ofi=0.2, c: Optional[SetupEngineConfig] = None) -> pd.DataFrame:
    m = market_1h(mids, ofi)
    return compute_bias(m, preds(r4), preds(r1), c or cfg())


# -------------------------------------------------------------- A. context


def test_context_table_spec_rows():
    c = SetupEngineConfig()
    assert regime_context(P, P, c).value == "SUPPORTIVE"
    assert regime_context(P, R, c).value == "NEUTRAL"
    assert regime_context(P, A, c).value == "CONFLICT"


def test_context_table_full_and_symmetric_conflict():
    c = SetupEngineConfig()
    t = context_table_frame(c)
    assert t.shape == (4, 4)
    assert (t == "SUPPORTIVE").sum().sum() == 1
    assert t.loc[A, P] == "CONFLICT" and t.loc[P, A] == "CONFLICT"
    assert set(t.loc[U]) == {"NEUTRAL"} and set(t[U]) == {"NEUTRAL"}


def test_context_accepts_raw_labels_and_unknown_is_neutral():
    c = SetupEngineConfig()
    assert regime_context("persistent", "Persistent", c).value == "SUPPORTIVE"
    assert regime_context(None, "persistent", c).value == "NEUTRAL"


def test_context_table_configurable_and_validated():
    t = SetupEngineConfig().context.table
    t[R][R] = "SUPPORTIVE"
    c = SetupEngineConfig(context={"table": t})
    assert regime_context(R, R, c).value == "SUPPORTIVE"
    bad = {k: dict(v) for k, v in t.items()}
    bad[P][P] = "BULLISH"
    with pytest.raises(ValidationError):
        SetupEngineConfig(context={"table": bad})
    with pytest.raises(ValidationError):
        SetupEngineConfig(context={"table": {P: t[P]}})
    with pytest.raises(ValidationError):
        SetupEngineConfig(context={"bias_allowed_contexts": ["CONFLICT"]})


def test_yaml_matches_defaults():
    assert load_setup_config().canonical() == SetupEngineConfig().canonical()


# ----------------------------------------------------------- B. transition


def test_transition_rules_from_spec():
    r = SetupEngineConfig().transition.rules
    assert r["PERSISTENT->RANDOM_LIKE"] == "BLOCK_ALL"
    assert r["PERSISTENT->ANTI_PERSISTENT"] == "BLOCK_LONG"
    assert r["ANTI_PERSISTENT->PERSISTENT"] == "WAIT_NEW_BIAS"


def test_transition_tracking_with_confirmation():
    c = SetupEngineConfig()  # confirm_predictions = 2
    regs = [P, P, R, P, A, A, A]
    tr = track_transitions(regs, [T0 + i * H for i in range(len(regs))], c)
    assert tr["stable_regime"].tolist() == ["NONE", P, P, P, P, A, A]
    # Kedipan R satu kali: transisi tercatat lalu batal.
    assert tr["transition_type"].iloc[2] == "PERSISTENT->RANDOM_LIKE"
    assert tr["transition_status"].iloc[2] == "BLOCK_ALL"
    assert tr["transition_type"].iloc[3] == ""
    # P -> A: pending satu prediksi, lalu terkonfirmasi.
    assert tr["transition_type"].iloc[4] == "PERSISTENT->ANTI_PERSISTENT"
    assert tr["transition_status"].iloc[4] == "BLOCK_LONG"
    assert tr["last_transition_type"].iloc[5] == "PERSISTENT->ANTI_PERSISTENT"
    assert tr["transition_status"].iloc[5] == "NORMAL"


def test_transition_tracking_is_causal():
    c = SetupEngineConfig()
    rng = np.random.default_rng(3)
    regs = list(rng.choice([P, R, A], 50))
    times = [T0 + i * H for i in range(50)]
    full = track_transitions(regs, times, c)
    head = track_transitions(regs[:30], times[:30], c)
    pd.testing.assert_frame_equal(full.iloc[:30].reset_index(drop=True), head)


@pytest.mark.parametrize(
    "status,direction,blocked",
    [
        ("NORMAL", "LONG", False),
        ("BLOCK_ALL", "SHORT", True),
        ("BLOCK_LONG", "LONG", True),
        ("BLOCK_LONG", "SHORT", False),
        ("BLOCK_SHORT", "SHORT", True),
        ("WAIT_NEW_BIAS", "LONG", True),
    ],
)
def test_direction_blocked(status, direction, blocked):
    assert direction_blocked(status, direction, SetupEngineConfig()) is blocked
    allow = SetupEngineConfig(regime={"allow_entry_during_transition": True})
    assert direction_blocked(status, direction, allow) is False


def test_strictest_status():
    assert strictest("NORMAL", "BLOCK_LONG") == "BLOCK_LONG"
    assert strictest("BLOCK_LONG", "BLOCK_SHORT") == "BLOCK_ALL"
    assert strictest("WAIT_NEW_BIAS", "BLOCK_ALL") == "BLOCK_ALL"


def test_incomplete_transition_rules_rejected():
    r = dict(SetupEngineConfig().transition.rules)
    r.pop("PERSISTENT->RANDOM_LIKE")
    with pytest.raises(ValidationError):
        SetupEngineConfig(transition={"rules": r})


# --------------------------------------------------------------- C. bias


def test_long_bias_supportive_bullish_orderflow_ok():
    b = run(UP_SEG, [P] * 10, [P] * 10, ofi=0.2)
    last = b.iloc[-1]
    assert last["structure_1h"] == "BULLISH"
    assert last["regime_context"] == "SUPPORTIVE"
    assert last["bias"] == "LONG_BIAS" and last["bias_reason"] == "OK"
    assert last["timestamp_bias"] == last["timestamp"] + H


def test_short_bias_is_symmetric():
    b = run(DOWN_SEG, [P] * 10, [P] * 10, ofi=-0.2)
    assert b["bias"].iloc[-1] == "SHORT_BIAS"


def test_regime_alone_never_gives_direction():
    # Regime persistent penuh tetapi struktur datar -> NEUTRAL.
    b = run([0] * 10, [P] * 10, [P] * 10)
    assert (b["bias"] == "NEUTRAL").all()
    assert (b["bias_reason"] == "STRUCTURE_NOT_CONFIRMED").all()


def test_anti_persistent_does_not_imply_short():
    # Regime anti-persistent + struktur bearish: context NEUTRAL -> tidak SHORT.
    b = run(DOWN_SEG, [A] * 10, [A] * 10, ofi=-0.2)
    assert (b["bias"] == "NEUTRAL").all()
    assert b["bias_reason"].iloc[-1] == "CONTEXT_NOT_SUPPORTIVE"


def test_conflicting_regime_gives_neutral():
    b = run(UP_SEG, [P] * 10, [A] * 10)
    assert b["regime_context"].iloc[-1] == "CONFLICT"
    assert b["bias"].iloc[-1] == "NEUTRAL"
    assert b["bias_reason"].iloc[-1] == "CONFLICTING_REGIME"


def test_neutral_context_gives_neutral_unless_allowed():
    b = run(UP_SEG, [P] * 10, [R] * 10)
    assert b["bias_reason"].iloc[-1] == "CONTEXT_NOT_SUPPORTIVE"
    b2 = run(UP_SEG, [P] * 10, [R] * 10, c=cfg(context={"bias_allowed_contexts": ["SUPPORTIVE", "NEUTRAL"]}))
    assert b2["bias"].iloc[-1] == "LONG_BIAS"


def test_ofi_against_gives_neutral():
    b = run(UP_SEG, [P] * 10, [P] * 10, ofi=-0.3, c=cfg(bias={"use_ofi": True}))
    assert b["bias_reason"].iloc[-1] == "OFI_AGAINST"
    b2 = run(UP_SEG, [P] * 10, [P] * 10, ofi=-0.3, c=cfg(bias={"use_ofi": False, "use_cvd": False}))
    assert b2["bias"].iloc[-1] == "LONG_BIAS"


def test_ofi_threshold_tolerates_small_opposite_flow():
    c = cfg(confirmation={"ofi_threshold": 0.1, "cvd_slope_threshold": 0.1}, bias={"use_ofi": True})
    b = run(UP_SEG, [P] * 10, [P] * 10, ofi=-0.05, c=c)
    assert b["bias"].iloc[-1] == "LONG_BIAS"


def test_cvd_against_gives_neutral():
    m = market_1h(UP_SEG, ofi=0.2)
    m["cvd"] = -np.arange(len(m)) * 5.0  # tekanan jual kuat
    b = compute_bias(m, preds([P] * 10), preds([P] * 10), cfg(bias={"use_cvd": True}))
    assert b["bias_reason"].iloc[-1] == "CVD_AGAINST"


def test_low_confidence_and_missing_regime():
    c = cfg(regime={"min_confidence": 0.5})
    m = market_1h(UP_SEG)
    b = compute_bias(m, preds([P] * 10, conf=[0.4] * 10), preds([P] * 10), c)
    assert b["bias_reason"].iloc[-1] == "LOW_CONFIDENCE"
    m2 = market_1h(UP_SEG)
    b2 = compute_bias(m2, preds([P] * 2), preds([P] * 10), cfg())
    assert b2["bias_reason"].iloc[-1] == "REGIME_MISSING"


def test_transition_blocks_long_and_is_recorded():
    c = cfg(transition={"confirm_predictions": 3})
    # 1H: P stabil, lalu mulai beralih ke A di prediksi 7 (pending).
    r1 = [P] * 7 + [A] * 3
    b = compute_bias(market_1h(UP_SEG), preds([P] * 10), preds(r1), c)
    blocked = b.iloc[8]
    assert blocked["transition_type"] == "1H:PERSISTENT->ANTI_PERSISTENT"
    assert blocked["transition_status"] == "BLOCK_LONG"
    assert blocked["bias"] == "NEUTRAL"
    assert blocked["bias_reason"] in {"TRANSITION_BLOCKED", "CONFLICTING_REGIME"}
    assert (b["transition_type"] != "").any()


def test_transition_block_lifted_by_parameter_but_still_recorded():
    base = {"transition": {"confirm_predictions": 3}, "context": {"bias_allowed_contexts": ["SUPPORTIVE", "NEUTRAL"]}}
    r1 = [P] * 7 + [R] * 3
    blk = compute_bias(market_1h(UP_SEG), preds([P] * 10), preds(r1), cfg(**base))
    allow = compute_bias(
        market_1h(UP_SEG),
        preds([P] * 10),
        preds(r1),
        cfg(**base, regime={"allow_entry_during_transition": True}),
    )
    assert blk["bias_reason"].iloc[8] == "TRANSITION_BLOCKED"
    assert allow["bias"].iloc[8] == "LONG_BIAS"
    assert allow["transition_type"].iloc[8] == "1H:PERSISTENT->RANDOM_LIKE"
    assert allow["transition_status"].iloc[8] == "BLOCK_ALL"


def test_wait_new_bias_after_anti_to_persistent():
    c = cfg(transition={"confirm_predictions": 1})
    mids = [0, -2, -1, -3, -2, -4] + [-3, -1, -2, 0, -1, 1, 0, 2, 1, 3]
    n = len(mids)
    # 4H tetap P. 1H: P..., lalu A, kemudian kembali P (ANTI->PERSISTENT = WAIT_NEW_BIAS).
    r1 = [P] * 3 + [A] * 3 + [P] * (n - 6)
    c = cfg(transition={"confirm_predictions": 1}, bias={"use_ofi": False, "use_cvd": False})
    b = compute_bias(market_1h(mids, ofi=0.2), preds([P] * n), preds(r1), c)
    done = b["timestamp_bias"].iloc[6]  # prediksi P pertama setelah A tersedia di close bar 6
    after = b.iloc[6:]
    longs = after[after["bias"] == "LONG_BIAS"]
    assert len(longs) > 0
    # Setiap LONG setelah transisi berasal dari struktur yang terbentuk SETELAH transisi.
    assert (longs["candidate_since"] > done).all()


def test_wait_new_bias_blocks_old_candidate():
    c = cfg(transition={"confirm_predictions": 1})
    n = 10
    r1 = [P] * 7 + [A] + [P] * 2  # A -> P selesai di prediksi 8
    b = compute_bias(market_1h(UP_SEG, ofi=0.2), preds([P] * n), preds(r1), c)
    # Struktur bullish sudah ada sebelum transisi selesai -> bukan bias baru.
    assert b["bias_reason"].iloc[8] == "WAITING_NEW_BIAS"
    assert b["bias"].iloc[8] == "NEUTRAL"
    assert bool(b["waiting_new_bias"].iloc[9])


# ------------------------------------------------------------- lookahead


def test_bias_uses_only_available_predictions():
    b = run(UP_SEG, [P] * 10, [P] * 10)
    assert (b["regime_1h_available_at"] <= b["timestamp_bias"]).all()
    assert (b["regime_4h_available_at"] <= b["timestamp_bias"]).all()


def test_bias_unchanged_when_future_data_changes():
    rng = np.random.default_rng(5)
    n = 120
    mids = np.cumsum(rng.normal(0, 1, n))
    ofi = rng.uniform(-0.4, 0.4, n)
    r4 = list(rng.choice([P, P, R, A], n))
    r1 = list(rng.choice([P, P, R, A], n))
    c = cfg(transition={"confirm_predictions": 2})
    full = compute_bias(market_1h(mids, ofi), preds(r4), preds(r1), c)

    cut = 70
    m2 = market_1h(mids, ofi)
    m2.loc[cut:, ["open", "high", "low", "close"]] += 500
    m2.loc[cut:, "ofi"] = -m2.loc[cut:, "ofi"]
    m2["cvd"] = np.cumsum(m2["ofi"] * m2["volume"])
    r1b = r1[:cut] + [A] * (n - cut)
    tampered = compute_bias(m2, preds(r4), preds(r1b), c)
    pd.testing.assert_frame_equal(full.iloc[:cut], tampered.iloc[:cut])

    head = compute_bias(market_1h(mids[:cut], ofi[:cut]), preds(r4[:cut]), preds(r1[:cut]), c)
    pd.testing.assert_frame_equal(full.iloc[:cut].reset_index(drop=True), head)


def test_validate_bias_no_lookahead_raises():
    b = run(UP_SEG, [P] * 10, [P] * 10)
    b.loc[3, "regime_1h_available_at"] = b["timestamp_bias"].iloc[3] + pd.Timedelta(minutes=1)
    with pytest.raises(LookAheadError):
        validate_bias_no_lookahead(b)


def test_orderflow_helpers():
    assert np.isnan(rolling_ofi(np.array([0.1, 0.2, 0.3]), 3)[1])
    assert np.isclose(rolling_ofi(np.array([0.1, 0.2, 0.3]), 3)[2], 0.2)
    s = cvd_slope(np.array([0.0, 5.0, 10.0, 0.0]), np.array([10.0, 10.0, 10.0, 10.0]), 2)
    assert np.isnan(s[1])
    assert np.isclose(s[2], 0.5) and np.isclose(s[3], -0.25)

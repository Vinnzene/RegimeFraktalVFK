"""Uji fungsi order flow: rumus OFI/CVD, agregasi trade, dan kausalitas."""

import numpy as np
import pandas as pd

from app.services.order_flow import (
    aggregate_trades_to_candles,
    build_order_flow_bars,
    calculate_cvd,
    calculate_trade_ofi,
    normalize_cvd,
    prepare_order_flow_windows,
)


def test_ofi_formula_and_range():
    buy = np.array([10.0, 0.0, 5.0, 0.0])
    sell = np.array([0.0, 10.0, 5.0, 0.0])
    ofi = calculate_trade_ofi(buy, sell)
    assert np.allclose(ofi, [1.0, -1.0, 0.0, 0.0], atol=1e-9)
    assert np.isfinite(ofi).all()


def test_cvd_is_cumulative_delta():
    buy = np.array([3.0, 1.0, 2.0])
    sell = np.array([1.0, 2.0, 2.0])
    assert np.allclose(calculate_cvd(buy, sell), [2.0, 1.0, 1.0])


def test_cvd_zscore_is_shift_invariant_and_causal():
    rng = np.random.default_rng(0)
    cvd = np.cumsum(rng.normal(size=400))
    a = normalize_cvd(cvd, window=50)
    b = normalize_cvd(cvd + 1e6, window=50)
    assert np.allclose(a, b, atol=1e-6)
    tampered = cvd.copy()
    tampered[300:] += rng.normal(size=100) * 100
    c = normalize_cvd(tampered, window=50)
    assert np.array_equal(a[:300], c[:300])


def test_aggregate_trades_buyer_maker_means_sell():
    base_ms = 1_678_838_400_000  # 2023-03-15 00:00 UTC
    trades = pd.DataFrame(
        {
            "timestamp": [base_ms, base_ms + 1_000, base_ms + 3_599_999, base_ms + 3_600_000],
            "quantity": [1.0, 2.0, 4.0, 8.0],
            "is_buyer_maker": [False, True, False, True],
        }
    )
    out = aggregate_trades_to_candles(trades, "1h")
    base_s = base_ms // 1000
    assert out["time"].tolist() == [base_s, base_s + 3600]
    assert out["buy_volume"].tolist() == [5.0, 0.0]
    assert out["sell_volume"].tolist() == [2.0, 8.0]


def test_windows_never_touch_future():
    series = np.arange(100, dtype=float)[:, None]
    w = prepare_order_flow_windows(series, [10, 50], seq_len=5)
    assert w.shape == (2, 5, 1)
    assert w[0, :, 0].tolist() == [6, 7, 8, 9, 10]
    assert w[1, -1, 0] == 50
    early = prepare_order_flow_windows(series, [2], seq_len=5)
    assert early[0, :, 0].tolist() == [0, 0, 0, 1, 2]


def test_bars_unchanged_by_future_tampering():
    rng = np.random.default_rng(1)
    n = 300
    vol = rng.uniform(1, 10, n)
    df = pd.DataFrame(
        {"time": np.arange(n) * 3600, "close": np.ones(n), "volume": vol,
         "taker_buy_volume": vol * rng.uniform(0, 1, n)}
    )
    a = build_order_flow_bars(df, cvd_window=40)
    df2 = df.copy()
    df2.loc[200:, "taker_buy_volume"] = df2.loc[200:, "volume"] * 0.99
    b = build_order_flow_bars(df2, cvd_window=40)
    for col in ("ofi", "cvd", "cvd_norm"):
        assert np.array_equal(a[col].to_numpy()[:200], b[col].to_numpy()[:200])

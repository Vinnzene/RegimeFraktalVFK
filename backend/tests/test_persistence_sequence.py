"""Sekuens statistik persistensi: kebenaran nilai, rentang, dan kausalitas."""

import numpy as np
import pytest

from app.services.persistence_sequence import (
    PS_CHANNELS,
    build_persistence_sequences,
    channel_series,
    step_offsets,
)
from app.services.structural_features import variance_ratio


def _naive(seg: np.ndarray) -> dict:
    def ac(a, lag):
        return float(np.corrcoef(a[:-lag], a[lag:])[0, 1])

    out = {}
    for q in (2, 4, 8, 16):
        m = seg.size // q
        blocks = seg[seg.size - m * q :].reshape(m, q).sum(axis=1)
        out[f"vr_{q}"] = blocks.var() / (q * seg.var())
    for lag in (1, 2, 3, 5):
        out[f"ac_{lag}"] = ac(seg, lag)
    out["acabs_1"] = ac(np.abs(seg), 1)
    out["sign_flip"] = float(((seg[1:] * seg[:-1]) < 0).mean())
    out["log_vol"] = float(np.log(seg.std() + 1e-12))
    return out


def test_vectorized_matches_naive():
    rng = np.random.default_rng(0)
    x = rng.standard_t(4, 900) * 0.01
    W = 128
    s = channel_series(x, W)
    for e in (W - 1, 300, 899):
        ref = _naive(x[e - W + 1 : e + 1])
        for c in PS_CHANNELS:
            assert s[c][e] == pytest.approx(ref[c], rel=1e-6, abs=1e-9), (c, e)
    assert np.isnan(s["vr_2"][W - 2])


def test_vr_matches_existing_definition_when_aligned():
    rng = np.random.default_rng(1)
    seg = rng.normal(size=128)
    s = channel_series(seg, 128)
    assert s["vr_4"][127] == pytest.approx(variance_ratio(seg, 4), rel=1e-9)


def test_step_offsets_cover_label_window():
    offs = step_offsets(500, 128, 32)
    assert offs[-1] == 0 and offs[0] == -(500 - 128)
    assert np.all(np.diff(offs) == 12)
    with pytest.raises(ValueError):
        step_offsets(500, 100, 32)


def test_shape_and_window_bounds():
    rng = np.random.default_rng(2)
    x = rng.normal(size=2000) * 0.01
    pos = [600, 1200, 1999]
    X = build_persistence_sequences(x, pos, window=500)
    assert X.shape == (3, 32, len(PS_CHANNELS))
    assert np.isfinite(X).all()
    # Langkah pertama memakai bar t-499..t-372: semua di dalam window label.
    s = channel_series(x, 128)
    assert X[0, 0, PS_CHANNELS.index("ac_1")] == pytest.approx(s["ac_1"][600 - 372])


def test_causal_future_changes_do_not_matter():
    rng = np.random.default_rng(3)
    x = rng.normal(size=1500) * 0.01
    a = build_persistence_sequences(x, [800, 1000], window=500)
    y = x.copy()
    y[1001:] = rng.normal(size=y.size - 1001) * 5
    b = build_persistence_sequences(y, [800, 1000], window=500)
    np.testing.assert_array_equal(a, b)


def test_bars_before_label_window_do_not_matter():
    rng = np.random.default_rng(4)
    x = rng.normal(size=1500) * 0.01
    t = 1200
    a = build_persistence_sequences(x, [t], window=500)
    y = x.copy()
    y[: t - 499] = rng.normal(size=t - 499) * 7
    b = build_persistence_sequences(y, [t], window=500)
    # Selisih hanya pembulatan cumsum (nilai lama dibuat 700x lebih besar);
    # perubahan informasi nyata akan berukuran ~1e-1.
    np.testing.assert_allclose(a, b, rtol=0, atol=1e-7)


def test_short_history_is_zero_padded():
    x = np.random.default_rng(5).normal(size=400) * 0.01
    X = build_persistence_sequences(x, [200], window=500)
    # Langkah k berakhir di 200 - (31-k)*12; butuh >= 127 -> k >= 26.
    assert (X[0, :25] == 0).all()
    assert (X[0, 26:] != 0).any()
    assert np.isfinite(X).all()

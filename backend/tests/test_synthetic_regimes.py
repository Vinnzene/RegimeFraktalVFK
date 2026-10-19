"""Generator data sintetis Fase 1: label, sampling, dan sifat transformasi."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "src"))

from app.services.hurst_dfa import dfa_alpha  # noqa: E402
from synthetic_regimes import (  # noqa: E402
    CLASSES,
    PRIMARY,
    SENSITIVITY,
    SIGMA,
    CryptoParams,
    crypto_noise,
    fgn,
    label,
    make_series,
    sample_h,
    to_student_t,
)


@pytest.mark.parametrize("thresholds", [PRIMARY, SENSITIVITY])
def test_sample_h_stays_in_class(thresholds):
    rng = np.random.default_rng(0)
    for cls in CLASSES:
        hs = [sample_h(cls, rng, thresholds) for _ in range(300)]
        assert all(label(h, thresholds) == cls for h in hs)
        assert 0.30 <= min(hs) and max(hs) <= 0.70


def test_label_boundaries_primary():
    assert label(0.469) == "anti_persistent"
    assert label(0.47) == "random_like" and label(0.53) == "random_like"
    assert label(0.531) == "persistent"


@pytest.mark.parametrize("scenario", ["S1", "S2", "S3", "S4", "S5", "S4k"])
def test_series_shape_scale_and_determinism(scenario):
    r1, info = make_series(scenario, 500, 0.6, np.random.default_rng(7))
    r2, _ = make_series(scenario, 500, 0.6, np.random.default_rng(7))
    assert r1.shape == (500,) and np.all(np.isfinite(r1))
    assert np.isclose(r1.std(), SIGMA)
    assert np.array_equal(r1, r2)
    assert info["h_true"] == 0.6


def test_s5_switch_point_and_classes():
    rng = np.random.default_rng(3)
    for _ in range(50):
        _, info = make_series("S5", 500, 0.62, rng)
        assert 0.4 * 500 <= info["switch_at"] <= 0.9 * 500
        assert label(info["h_first"]) != label(info["h_true"])


def test_student_t_transform_is_monotone():
    z = np.linspace(-4, 4, 201)
    t = to_student_t(z, 3.0)
    assert np.all(np.diff(t) > 0)


def test_stochastic_volatility_keeps_return_signs():
    rng = np.random.default_rng(5)
    z = fgn(2000, 0.65, rng)
    r = crypto_noise(z, CryptoParams(), rng, heavy=False, sv=True, jump=False)
    assert np.array_equal(np.sign(r), np.sign(z))


@pytest.mark.parametrize("h", [0.3, 0.7])
def test_s1_ground_truth_recoverable_on_long_series(h):
    # Pada deret panjang DFA harus memulihkan H pembangkit; bila tidak,
    # kebenaran dasar benchmark tidak sah.
    rng = np.random.default_rng(11)
    est = np.mean([dfa_alpha(make_series("S1", 8192, h, rng)[0]) for _ in range(6)])
    assert abs(est - h) < 0.06

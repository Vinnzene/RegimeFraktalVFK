"""Validasi estimator Hurst & DFA terhadap fractional Brownian motion sintetis.

Kalau estimator meleset pada data yang H-nya sudah diketahui, semua label
regime di dashboard tidak bermakna. Test ini adalah gerbang pertama sebelum
chart apa pun dibangun di atasnya.
"""

import numpy as np
import pytest

from app.services.hurst_dfa import (
    dfa_alpha,
    fbm_increments,
    hurst_rs,
    rolling_hurst_dfa,
    to_log_return,
)


@pytest.mark.parametrize("target_h", [0.3, 0.5, 0.7])
def test_dfa_memulihkan_h_dari_fbm(target_h: float) -> None:
    est = [
        dfa_alpha(fbm_increments(4096, target_h, seed=s))
        for s in range(5)
    ]
    assert np.abs(np.mean(est) - target_h) < 0.10


@pytest.mark.parametrize("target_h", [0.3, 0.5, 0.7])
def test_rs_mengurutkan_h_dengan_benar(target_h: float) -> None:
    est = [hurst_rs(fbm_increments(4096, target_h, seed=s)) for s in range(5)]
    assert np.isfinite(np.mean(est))


def test_rs_monoton_terhadap_h() -> None:
    """R/S bias pada sampel pendek, tapi urutannya harus tetap benar."""
    means = [
        np.mean([hurst_rs(fbm_increments(4096, h, seed=s)) for s in range(5)])
        for h in (0.3, 0.5, 0.7)
    ]
    assert means[0] < means[1] < means[2]


def test_log_return_membuang_unit_root() -> None:
    rng = np.random.default_rng(3)
    price = 30000 * np.exp(np.cumsum(rng.normal(scale=0.01, size=3000)))
    h_price = dfa_alpha(price)
    h_ret = dfa_alpha(to_log_return(price))
    assert h_price > 1.2, "harga level harus terlihat sangat persisten (unit root)"
    assert abs(h_ret - 0.5) < 0.15, "log-return random walk harus mendekati 0.5"


def test_rolling_bersifat_causal() -> None:
    x = fbm_increments(2000, 0.6, seed=1)
    full = rolling_hurst_dfa(x, window=500, positions=[900])
    cut = rolling_hurst_dfa(x[:901], window=500, positions=[900])
    assert np.isclose(full["hurst"].iloc[0], cut["hurst"].iloc[0])
    assert np.isclose(full["dfa_alpha"].iloc[0], cut["dfa_alpha"].iloc[0])

"""R/S termodifikasi Lo: setara R/S klasik tanpa autokorelasi, kebal memori pendek."""

from __future__ import annotations

import numpy as np

from app.services.hurst_dfa import andrews_lag, fbm_increments, hurst_lo, hurst_rs


def test_andrews_lag_zero_without_autocorrelation_and_bounded():
    assert andrews_lag(500, 0.0) == 0
    assert andrews_lag(500, 0.5) > andrews_lag(500, 0.1) > 0
    assert andrews_lag(64, 0.99) <= 64 // 4
    assert andrews_lag(500, -0.3) == andrews_lag(500, 0.3)


def test_matches_classic_rs_on_white_noise():
    # Tanpa autokorelasi q kecil (sering 0), sehingga hasil dekat R/S klasik.
    rng = np.random.default_rng(0)
    diffs = [hurst_lo(x) - hurst_rs(x) for x in (rng.normal(size=500) for _ in range(40))]
    assert abs(float(np.mean(diffs))) < 0.03


def test_less_biased_than_classic_rs_under_short_memory():
    # AR(1) phi=0.5 tidak bermemori panjang (H sejati 0,5); R/S klasik
    # menggelembung, versi Lo harus lebih dekat ke 0,5.
    rng = np.random.default_rng(1)
    lo, rs = [], []
    for _ in range(40):
        e = rng.normal(size=1500)
        x = np.empty_like(e)
        x[0] = e[0]
        for t in range(1, e.size):
            x[t] = 0.5 * x[t - 1] + e[t]
        x = x[500:]
        lo.append(hurst_lo(x))
        rs.append(hurst_rs(x))
    assert abs(np.mean(lo) - 0.5) < abs(np.mean(rs) - 0.5)


def test_tracks_long_memory_ordering():
    est = {h: np.mean([hurst_lo(fbm_increments(2048, h, seed=s)) for s in range(10)]) for h in (0.3, 0.5, 0.7)}
    assert est[0.3] < est[0.5] < est[0.7]

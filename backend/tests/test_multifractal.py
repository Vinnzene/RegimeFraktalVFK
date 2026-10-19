"""Validasi generalized Hurst H(q) — flow.md langkah 2 & 5.

Tiga hal yang harus benar sebelum H(q) boleh dipakai sebagai fitur:

1. Pada fBm dengan H diketahui, H(q) harus memulihkan nilai itu untuk setiap q.
2. fBm bersifat MONOFRAKTAL: H(q) harus hampir konstan terhadap q, sehingga
   lebar spektrum mendekati nol. Kalau estimator melaporkan lebar besar pada
   data monofraktal, seluruh klaim multifraktalitas pada BTC tidak bermakna.
3. Perhitungan wajib causal.
"""

import numpy as np
import pytest

from app.services.hurst_dfa import fbm_increments
from app.services.multifractal import (
    FEATURE_DIM,
    build_feature_matrix,
    compute_features,
    feature_names,
    generalized_hurst,
    hq_spectrum,
)


@pytest.mark.parametrize("target_h", [0.3, 0.5, 0.7])
def test_hq_memulihkan_h_dari_fbm(target_h: float) -> None:
    est = [
        generalized_hurst(fbm_increments(4096, target_h, seed=s), q=2.0)
        for s in range(5)
    ]
    assert np.abs(np.mean(est) - target_h) < 0.10


def test_fbm_monofraktal_lebar_spektrum_kecil() -> None:
    """fBm monofraktal: H(1), H(2), H(4) harus berdekatan."""
    widths = []
    for s in range(5):
        spec = hq_spectrum(fbm_increments(4096, 0.6, seed=s))
        vals = [spec[1.0], spec[2.0], spec[4.0]]
        assert all(np.isfinite(v) for v in vals)
        widths.append(max(vals) - min(vals))
    assert np.mean(widths) < 0.12, "fBm monofraktal tidak boleh tampak multifraktal"


def test_hq_membedakan_deret_multifraktal() -> None:
    """Deret dengan volatilitas berlompat harus punya spektrum lebih lebar.

    Kontrol positif: tanpa uji ini, lebar spektrum yang selalu kecil bisa saja
    berarti estimatornya memang tidak peka terhadap apa pun.
    """
    rng = np.random.default_rng(7)
    base = fbm_increments(4096, 0.6, seed=1)
    # Volatilitas berganda bergantian — sumber multifraktalitas paling umum
    # pada data keuangan.
    vol = np.where(rng.random(base.size) < 0.1, 8.0, 1.0)
    multi = base * vol

    w_mono = abs(
        hq_spectrum(base)[1.0] - hq_spectrum(base)[4.0]
    )
    w_multi = abs(
        hq_spectrum(multi)[1.0] - hq_spectrum(multi)[4.0]
    )
    assert w_multi > w_mono


def test_bersifat_causal() -> None:
    x = fbm_increments(2000, 0.6, seed=1)
    penuh = compute_features(x, t=900, window=500)
    dipotong = compute_features(x[:901], t=900, window=500)
    assert np.allclose(penuh, dipotong)


def test_dimensi_fitur_konsisten() -> None:
    x = fbm_increments(1024, 0.55, seed=2)
    feats = compute_features(x, t=800, window=500)
    assert len(feats) == FEATURE_DIM == len(feature_names())
    assert all(np.isfinite(v) for v in feats)


def test_matriks_fitur_bentuknya_benar() -> None:
    x = fbm_increments(2000, 0.55, seed=3)
    positions = [700, 900, 1100]
    mat = build_feature_matrix(x, positions, window=500)
    assert mat.shape == (len(positions), FEATURE_DIM)
    assert np.isfinite(mat).all()


def test_segmen_terlalu_pendek_mengembalikan_nol() -> None:
    x = fbm_increments(128, 0.5, seed=4)
    assert compute_features(x, t=10, window=500) == [0.0] * FEATURE_DIM

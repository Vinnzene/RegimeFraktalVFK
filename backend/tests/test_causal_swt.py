"""Bukti kausalitas SWT.

Uji inti: potong deret di t, hitung ulang SWT, koefisien pada t-1 harus
identik dengan hasil dari deret yang lebih panjang. Kalau test ini gagal,
fitur model menyerap data masa depan (look-ahead bias) dan seluruh hasil
identifikasi regime tidak sah.
"""

import numpy as np
import pytest

from app.services.swt import causal_swt_at, swt_decompose


@pytest.fixture
def series() -> np.ndarray:
    rng = np.random.default_rng(7)
    return np.cumsum(rng.normal(scale=0.01, size=600))


def test_causal_swt_tidak_berubah_saat_data_masa_depan_ditambah(series: np.ndarray) -> None:
    t = 400
    window = 256
    short = causal_swt_at(series[: t + 1], t, level=4, window=window)
    long = causal_swt_at(series, t, level=4, window=window)
    assert short.keys() == long.keys()
    for key in short:
        assert np.isclose(short[key], long[key], rtol=1e-9, atol=1e-12), key


def test_koefisien_t_minus_1_stabil_setelah_pemotongan(series: np.ndarray) -> None:
    t = 350
    window = 256
    cut = series[:t]
    full_prev = causal_swt_at(series, t - 1, level=4, window=window)
    cut_prev = causal_swt_at(cut, t - 1, level=4, window=window)
    for key in full_prev:
        assert np.isclose(full_prev[key], cut_prev[key], rtol=1e-9, atol=1e-12), key


def test_swt_naif_pada_seluruh_deret_memang_bocor(series: np.ndarray) -> None:
    """Kontrol negatif: mendokumentasikan kenapa pendekatan naif ditolak."""
    t = 300
    full = swt_decompose(series, level=4)["detail_1"][t]
    truncated = swt_decompose(series[: t + 1], level=4)["detail_1"][t]
    assert not np.isclose(full, truncated, rtol=1e-6)


def test_causal_swt_menolak_indeks_di_luar_rentang(series: np.ndarray) -> None:
    with pytest.raises(IndexError):
        causal_swt_at(series, len(series), level=4, window=128)

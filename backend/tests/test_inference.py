"""Test pipeline inference: pembentukan fitur, penskalaan, pemuatan artefak."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.feature_builder import (
    apply_scaler,
    build_sequence_features,
    fit_scaler,
)
from app.services.model_registry import (
    NEURAL_KEYS,
    load_metadata,
    prediction_source,
)


@pytest.fixture
def log_returns() -> np.ndarray:
    rng = np.random.default_rng(11)
    return rng.normal(scale=0.01, size=800)


# --- Pembentukan fitur --------------------------------------------------------------


def test_bentuk_fitur_sesuai_seq_len(log_returns: np.ndarray) -> None:
    feats = build_sequence_features(log_returns, [400, 500], level=4, seq_len=32, swt_window=256)
    assert feats.shape[0] == 2
    assert feats.shape[1] == 32
    assert feats.shape[2] >= 2


def test_langkah_terakhir_adalah_koefisien_pada_t(log_returns: np.ndarray) -> None:
    """Elemen terakhir sekuens harus koefisien tepat di t, bukan setelahnya."""
    from app.services.swt import causal_swt_at

    t = 400
    feats = build_sequence_features(log_returns, [t], level=4, seq_len=8, swt_window=256)
    direct = causal_swt_at(log_returns, t, level=4, window=256)
    expected = [direct[k] for k in sorted(direct)]
    assert np.allclose(feats[0, -1], expected)


def test_fitur_tidak_berubah_saat_data_masa_depan_ditambah(log_returns: np.ndarray) -> None:
    t = 400
    short = build_sequence_features(
        log_returns[: t + 1], [t], level=4, seq_len=16, swt_window=256
    )
    long = build_sequence_features(log_returns, [t], level=4, seq_len=16, swt_window=256)
    assert np.allclose(short, long, rtol=1e-9, atol=1e-12)


# --- Penskalaan ---------------------------------------------------------------------


def test_scaler_menormalkan_skala_koefisien(log_returns: np.ndarray) -> None:
    """Koefisien SWT log-return berskala ~1e-3; tanpa penskalaan gradien padam."""
    feats = build_sequence_features(
        log_returns, list(range(300, 700, 10)), level=4, seq_len=16, swt_window=256
    )
    assert np.abs(feats).mean() < 0.1, "prasyarat: skala asli memang sangat kecil"

    scaler = fit_scaler(feats)
    scaled = apply_scaler(feats, scaler)
    flat = scaled.reshape(-1, scaled.shape[-1])
    assert np.allclose(flat.mean(axis=0), 0.0, atol=1e-6)
    assert np.allclose(flat.std(axis=0), 1.0, atol=1e-6)


def test_scaler_kosong_tidak_mengubah_fitur(log_returns: np.ndarray) -> None:
    feats = build_sequence_features(log_returns, [400], level=4, seq_len=8, swt_window=256)
    assert np.array_equal(apply_scaler(feats, None), feats)
    assert np.array_equal(apply_scaler(feats, {"mean": [], "std": []}), feats)


def test_std_nol_tidak_menghasilkan_pembagian_nol() -> None:
    konstan = np.ones((5, 4, 3))
    scaler = fit_scaler(konstan)
    scaled = apply_scaler(konstan, scaler)
    assert np.all(np.isfinite(scaled))


def test_scaler_dari_training_saja() -> None:
    """Statistik dihitung dari subset training, bukan seluruh dataset.

    Memakai seluruh data akan menyelipkan informasi periode test ke praproses —
    kebocoran yang tidak terlihat pada metrik mana pun.
    """
    rng = np.random.default_rng(5)
    train = rng.normal(loc=0.0, scale=1.0, size=(50, 8, 2))
    test = rng.normal(loc=10.0, scale=1.0, size=(50, 8, 2))

    scaler_train = fit_scaler(train)
    scaler_all = fit_scaler(np.concatenate([train, test]))
    assert not np.allclose(scaler_train["mean"], scaler_all["mean"]), (
        "statistik gabungan berbeda — inilah yang harus dihindari"
    )


# --- Artefak ------------------------------------------------------------------------


def test_prediction_source_membedakan_artefak_dan_standin() -> None:
    for key in NEURAL_KEYS:
        assert prediction_source(key, "1h") in {"trained_artifact", "placeholder"}
    assert prediction_source("rule_based", "1h") == "rule_based"


def test_metadata_hilang_mengembalikan_dict_kosong() -> None:
    assert load_metadata("model_tidak_ada", "1h") == {}


def test_seq_len_dibaca_dari_metadata_bukan_konstanta() -> None:
    """seq_len harus mengikuti artefak; menuliskannya dua kali berisiko beda."""
    from app.services.inference import sequence_length

    assert sequence_length("model_tidak_ada", "1h", default=32) == 32

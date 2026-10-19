"""Jembatan antara data regime tersimpan dan model terlatih.

Satu tempat yang menyiapkan fitur SWT lalu menjalankan inference, dipakai
bersama oleh /model/compare, /model/raw-probabilities, /model/predict, dan
/backtest. Menyalin logika ini ke tiap router pernah membuat backtest dan panel
perbandingan memakai fitur yang berbeda untuk model yang sama.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.config import REGIME_CLASSES, get_config
from app.db.repository import get_repository
from app.services.feature_builder import apply_scaler, build_sequence_features
from app.services.hurst_dfa import to_log_return
from app.services.model_registry import (
    NEURAL_KEYS,
    load_metadata,
    predict_proba,
    predict_sequences,
)

# Fitur mahal dihitung sekali per (symbol, timeframe, config_hash, seq_len).
_FEATURE_CACHE: Dict[Tuple[str, str, str, int, int], np.ndarray] = {}
# Probabilitas dikunci pula pada jumlah baris: hasil dari deret yang lebih
# pendek tidak boleh terpakai untuk deret penuh.
_PROBA_CACHE: Dict[Tuple[str, str, str, str, int], np.ndarray] = {}


def clear_inference_cache(symbol: Optional[str] = None, timeframe: Optional[str] = None) -> None:
    caches: Tuple[Dict[Any, np.ndarray], ...] = (_FEATURE_CACHE, _PROBA_CACHE)
    for cache in caches:
        keys = [
            k
            for k in cache
            if (symbol is None or k[0] == symbol) and (timeframe is None or k[1] == timeframe)
        ]
        for k in keys:
            cache.pop(k, None)


def sequence_length(model_key: str, timeframe: str, default: int = 32) -> int:
    """Panjang sekuens diambil dari metadata artefak, bukan ditulis ulang.

    Menuliskannya sebagai konstanta di dua tempat berisiko: begitu training
    memakai seq_len berbeda, inference tetap berjalan tetapi memberi model
    bentuk masukan yang salah.
    """
    meta = load_metadata(model_key, timeframe)
    value = meta.get("seq_len")
    return value if isinstance(value, int) and value > 0 else default


def scaled_features_for(
    symbol: str,
    timeframe: str,
    regime_df: pd.DataFrame,
    model_key: str = "swt_attention_bilstm",
) -> np.ndarray:
    """Fitur yang siap disuapkan ke model: sudah memakai seq_len dan scaler artefak."""
    seq_len = sequence_length(model_key, timeframe)
    features = build_features_for(symbol, timeframe, regime_df, seq_len)
    meta = load_metadata(model_key, timeframe)
    return apply_scaler(features, meta.get("scaler"))


def build_features_for(
    symbol: str,
    timeframe: str,
    regime_df: pd.DataFrame,
    seq_len: int,
) -> np.ndarray:
    """Fitur SWT causal untuk setiap window pada deret regime."""
    cfg = get_config()
    # Jumlah baris ikut menjadi kunci, sama seperti pada cache probabilitas.
    key = (symbol, timeframe, cfg.config_hash, seq_len, len(regime_df))
    if key in _FEATURE_CACHE:
        return _FEATURE_CACHE[key]

    ohlcv = get_repository().get_ohlcv(symbol, timeframe)
    log_ret = to_log_return(ohlcv["close"].to_numpy())
    positions = regime_df["index"].astype(int).tolist()
    window = (
        int(regime_df["effective_window"].iloc[0]) if len(regime_df) else cfg.analysis.L
    )

    features = build_sequence_features(
        log_ret,
        positions,
        level=cfg.analysis.J,
        seq_len=seq_len,
        swt_window=window,
    )
    _FEATURE_CACHE[key] = features
    return features


def probabilities_for(
    symbol: str,
    timeframe: str,
    regime_df: pd.DataFrame,
    model_key: str,
) -> Tuple[np.ndarray, str]:
    """Matriks probabilitas (n_window, 3) beserta asal angkanya.

    Mengembalikan ("trained_artifact") bila model terlatih dipakai, atau
    ("placeholder") bila jatuh ke stand-in deterministik.
    """
    cfg = get_config()
    n = len(regime_df)
    if n == 0:
        return np.empty((0, 3)), "placeholder"

    # Jumlah baris ikut menjadi kunci cache. Tanpa itu, hasil dari DataFrame
    # yang lebih pendek dapat terpakai untuk deret penuh, dan pengindeksan
    # baris terakhir melampaui batas matriks.
    cache_key = (symbol, timeframe, model_key, cfg.config_hash, n)
    if cache_key in _PROBA_CACHE:
        cached = _PROBA_CACHE[cache_key]
        source = (
            "trained_artifact"
            if model_key in NEURAL_KEYS and cached.shape[0] > 0
            else "placeholder"
        )
        return cached, _cached_source(symbol, timeframe, model_key, source)

    if model_key in NEURAL_KEYS:
        seq_len = sequence_length(model_key, timeframe)
        features = build_features_for(symbol, timeframe, regime_df, seq_len)
        # Statistik penskalaan diambil dari artefak, bukan dihitung ulang di
        # sini: menghitung ulang dari data terkini akan memakai periode test.
        meta = load_metadata(model_key, timeframe)
        features = apply_scaler(features, meta.get("scaler"))
        probs = predict_sequences(model_key, timeframe, features)
        if probs is not None and len(probs) == n:
            _PROBA_CACHE[cache_key] = probs
            _SOURCE[(symbol, timeframe, model_key)] = "trained_artifact"
            return probs, "trained_artifact"

    # Stand-in deterministik: dipakai untuk rule_based dan saat artefak absen.
    rows = []
    for i, (h_val, a_val) in enumerate(
        zip(regime_df["hurst"].fillna(0.0), regime_df["dfa_alpha"].fillna(0.0))
    ):
        p = predict_proba(model_key, [float(h_val), float(a_val)], seed=cfg.model.seed + i)
        rows.append([p[c] for c in REGIME_CLASSES])
    probs = np.asarray(rows, dtype=float)
    _PROBA_CACHE[cache_key] = probs
    source = "rule_based" if model_key == "rule_based" else "placeholder"
    _SOURCE[(symbol, timeframe, model_key)] = source
    return probs, source


_SOURCE: Dict[Tuple[str, str, str], str] = {}


def _cached_source(symbol: str, timeframe: str, model_key: str, fallback: str) -> str:
    return _SOURCE.get((symbol, timeframe, model_key), fallback)


def to_dicts(probs: np.ndarray) -> List[Dict[str, float]]:
    """Ubah matriks probabilitas menjadi daftar dict per kelas."""
    return [
        {cls: float(round(v, 4)) for cls, v in zip(REGIME_CLASSES, row)} for row in probs
    ]

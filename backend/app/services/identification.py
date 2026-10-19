"""Inference tugas identifikasi + laporan konsistensi terhadap Hurst-DFA.

Modul ini memuat artefak hasil `ml/src/train_identification.py`, menjalankan
prediksi pada rentang test, lalu membandingkan hasilnya dengan label Hurst-DFA
pada empat lapis konsistensi (lihat app/services/consistency.py).

Perhitungan berat di-cache per (symbol, timeframe, mode, config_hash) karena
hasilnya deterministik: artefak tidak berubah kecuali dilatih ulang, dan
perubahan konfigurasi selalu menggeser config_hash.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from app.core.config import REGIME_CLASSES, get_config
from app.db.repository import get_repository
from app.services import disk_cache
from app.services.consistency import full_consistency
from app.services.feature_builder import apply_scaler, build_sequence_features
from app.services.hurst_dfa import to_log_return
from app.services.model_registry import load_identification_model, load_metadata
from app.services.splitting import bars_to_rows, split_indices
from app.services.structural_features import build_feature_matrix

BINARY_CLASSES = ["persistent", "anti_persistent"]

_CACHE: Dict[Tuple[str, str, str, str], dict] = {}


def clear_identification_cache(symbol: Optional[str] = None, timeframe: Optional[str] = None) -> None:
    keys = [
        k
        for k in _CACHE
        if (symbol is None or k[0] == symbol) and (timeframe is None or k[1] == timeframe)
    ]
    for k in keys:
        _CACHE.pop(k, None)


def _apply_feature_scaler(features: np.ndarray, scaler: Optional[dict]) -> np.ndarray:
    """Penskalaan fitur struktural memakai statistik dari artefak.

    Statistik wajib berasal dari artefak, bukan dihitung ulang dari data
    terkini — menghitung ulang akan memakai periode test.
    """
    if not scaler or not scaler.get("mean"):
        return features
    mean = np.asarray(scaler["mean"], dtype=float)
    std = np.asarray(scaler["std"], dtype=float)
    if features.size == 0 or features.shape[1] != mean.shape[0]:
        return features
    return (features - mean) / std


def consistency_report(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    mode: str = "multiclass",
    model_key: str = "hybrid_attention_bilstm",
) -> dict:
    """Laporan konsistensi model identifikasi terhadap label Hurst-DFA."""
    cfg = get_config()
    cache_key = (symbol, timeframe, mode, cfg.config_hash)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    # Cache disk: perhitungan memerlukan ~4,5 detik karena menjalankan
    # inference atas seluruh rentang test. Menyimpannya ke disk membuat waktu
    # itu tidak terulang setiap backend dimulai ulang.
    disk_key = disk_cache.cache_key(
        "consistency", symbol=symbol, tf=timeframe, mode=mode, model=model_key
    )
    cached = disk_cache.read(disk_key)
    if cached is not None:
        _CACHE[cache_key] = cached
        return cached

    meta = load_metadata(f"{model_key}_{mode}", timeframe)
    if not meta:
        return {
            "available": False,
            "reason": "Artefak identifikasi belum ada.",
            "perintah": (
                f"python ml/src/train_identification.py --timeframe {timeframe}"
                + (" --binary" if mode == "binary" else "")
            ),
        }

    model = load_identification_model(model_key, mode, timeframe)
    if model is None:
        return {"available": False, "reason": "Artefak gagal dimuat."}

    classes: List[str] = meta.get("classes") or list(REGIME_CLASSES)
    repo = get_repository()
    df = repo.get_regime(symbol, timeframe)
    ohlcv = repo.get_ohlcv(symbol, timeframe)
    log_ret = to_log_return(ohlcv["close"].to_numpy())

    labels = df["regime"].tolist()
    positions = df["index"].astype(int).tolist()
    window = int(meta.get("effective_window") or cfg.analysis.L)
    seq_len = int(meta.get("seq_len") or 32)
    stride = int(meta.get("stride_bars") or cfg.analysis.stride_bars)

    # Evaluasi hanya pada rentang test — konsistensi harus diukur di data yang
    # tidak pernah dilihat model.
    split = split_indices(
        len(positions), cfg.split.ratios, bars_to_rows(cfg.analysis.L, stride)
    )
    lo, hi = split["test"]  # type: ignore[misc]
    rows = [i for i in range(lo, hi) if labels[i] in classes]
    if len(rows) < 30:
        return {"available": False, "reason": "Rentang test terlalu pendek."}

    pos_subset = [positions[i] for i in rows]
    seq = build_sequence_features(
        log_ret, pos_subset, level=cfg.analysis.J, seq_len=seq_len, swt_window=window
    )
    seq = apply_scaler(seq, meta.get("scaler"))
    feat = build_feature_matrix(log_ret, pos_subset, window=window, swt_level=cfg.analysis.J)
    feat = _apply_feature_scaler(feat, meta.get("feature_scaler"))

    try:
        inputs = feat if model_key == "structural_mlp" else [seq, feat]
        probs = np.asarray(model.predict(inputs, batch_size=256, verbose=0))
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"Inference gagal: {exc}"[:200]}

    pred = [classes[i] for i in probs.argmax(axis=1)]
    true = [labels[i] for i in rows]
    hurst = df["hurst"].to_numpy()[rows]
    dfa = df["dfa_alpha"].to_numpy()[rows]

    report = full_consistency(true, pred, hurst, dfa, classes)
    report.update(
        {
            "available": True,
            "timeframe": timeframe,
            "mode": mode,
            "model": model_key,
            "classes": classes,
            "config_hash": cfg.config_hash,
            "config_matches": meta.get("config_hash") == cfg.config_hash,
            "segment": "test",
            "mean_max_prob": round(float(probs.max(axis=1).mean()), 4),
        }
    )
    _CACHE[cache_key] = report
    disk_cache.write(disk_key, report)
    return report

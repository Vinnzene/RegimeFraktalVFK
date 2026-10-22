"""Detektor regime resmi sistem: Hybrid PS (Attention-BiLSTM) latih-sintetis.

Model dan statistik normalisasinya dibangun oleh `ml/src/train_detector.py`
(praregistrasi Fase 1 adendum 3): dilatih pada deret sintetis dengan eksponen
Hurst yang diketahui, lalu dibekukan. Inference di sini harus sama persis
dengan uji generalisasi (`ml/src/generalization_study.py`):

- window 500 return, titik deteksi tiap 4 bar mulai dari return ke-500;
- return tiap window diskalakan ke `sigma_per_bar` sebelum fitur dihitung,
  karena data latih sintetis dinormalisasi ke angka itu;
- 50 fitur struktural (termasuk 12 rasio energi SWT) + sekuens PS 32 × 11.

Featurisasi ±60 ms per window, sehingga riwayat penuh BTC 1H (±17 ribu
window) memakan beberapa menit. Hasil disimpan di cache disk dan diperbarui
bertahap: hanya titik deteksi baru yang dihitung.
"""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.config import ARTIFACTS_DIR, PROCESSED_DIR

META_PATH = ARTIFACTS_DIR / "detector_meta.json"
CACHE_DIR = PROCESSED_DIR / "cache"
STRIDE = 4
# Di atas jumlah ini, permintaan API tidak menunggu; pembangunan dijalankan di
# latar belakang dan endpoint memberi tahu bahwa cache sedang dibangun.
MAX_SYNC_WINDOWS = 1500
# Ambang abstain: τ terkecil dengan BA tercakup ≥ 0,90 pada validasi sintetis
# (praregistrasi Fase 1 adendum 5, `ml/artifacts/regime_change_study.md`).
# Di bawahnya label dianggap tidak pasti (uncertain_lowconf).
ABSTAIN_TAU = 0.75

_lock = threading.Lock()
_building: Dict[str, bool] = {}
_model: Any = None


class DetectorUnavailable(RuntimeError):
    """Artefak detektor belum ada (jalankan `ml/src/train_detector.py`)."""


class CacheBuilding(RuntimeError):
    """Cache deteksi sedang dibangun di latar belakang."""


def meta() -> Dict[str, Any]:
    if not META_PATH.exists():
        raise DetectorUnavailable("detector_meta.json tidak ditemukan")
    return json.loads(META_PATH.read_text(encoding="utf-8"))["d_sintetis"]


def _fingerprint(m: Dict[str, Any]) -> str:
    """Sidik jari model + normalisasi: cache gugur bila detektor dilatih ulang."""
    path = ARTIFACTS_DIR / m["file"]
    blob = json.dumps({"mtime": int(path.stat().st_mtime), "mean": m["feature_mean"][:5], "sigma": m["sigma_per_bar"]})
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _load_model(m: Dict[str, Any]) -> Any:
    global _model
    if _model is None:
        path = ARTIFACTS_DIR / m["file"]
        if not path.exists():
            raise DetectorUnavailable(f"{m['file']} tidak ditemukan")
        import tensorflow as tf  # noqa: PLC0415

        from ml_layers import AttentionPooling  # noqa: PLC0415

        _model = tf.keras.models.load_model(path, custom_objects={"AttentionPooling": AttentionPooling})
    return _model


def window_features(w: np.ndarray, m: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """Fitur satu window, sama dengan `generalization_study._window_features`."""
    from app.services.multifractal import build_feature_matrix as build_mf  # noqa: PLC0415
    from app.services.persistence_sequence import build_persistence_sequences  # noqa: PLC0415
    from app.services.structural_features import build_feature_matrix  # noqa: PLC0415

    L = int(m["window"])
    sd = w.std()
    wn = w * (m["sigma_per_bar"] / sd) if sd > 0 else w
    t = len(wn) - 1
    return {
        "feat": np.concatenate([build_feature_matrix(wn, [t], L, 4)[0], build_mf(wn, [t], L)[0]]),
        "ps": build_persistence_sequences(wn, [t], L, int(m["sub_window"]), int(m["seq_len"]))[0].astype(np.float32),
    }


def predict_proba(feat: np.ndarray, ps: np.ndarray, m: Dict[str, Any]) -> np.ndarray:
    from app.services.feature_builder import apply_scaler  # noqa: PLC0415

    model = _load_model(m)
    F = (np.nan_to_num(feat) - np.array(m["feature_mean"])) / np.array(m["feature_std"])
    S = apply_scaler(ps, m["ps_scaler"])
    return model.predict([S, F], batch_size=1024, verbose=0)


def _featurize(r: np.ndarray, pos: np.ndarray, m: Dict[str, Any], jobs: int) -> Dict[str, np.ndarray]:
    L = int(m["window"])
    if jobs == 1 or len(pos) < 200:
        rows = [window_features(r[t - L + 1 : t + 1], m) for t in pos]
    else:
        from joblib import Parallel, delayed  # noqa: PLC0415

        rows = Parallel(n_jobs=jobs, batch_size=32)(delayed(window_features)(r[t - L + 1 : t + 1], m) for t in pos)
    return {"feat": np.stack([x["feat"] for x in rows]), "ps": np.stack([x["ps"] for x in rows])}


def _cache_path(symbol: str, tf: str):
    return CACHE_DIR / f"ai_regime_{symbol.lower()}_{tf}.npz"


def update_cache(symbol: str, tf: str, jobs: int = -1, max_new: Optional[int] = None) -> pd.DataFrame:
    """Hitung probabilitas untuk titik deteksi yang belum ada di cache.

    Titik deteksi mengikuti grid uji generalisasi (return ke-500, lalu tiap 4
    bar). Bila jumlah titik baru melebihi `max_new`, `CacheBuilding` dilempar
    dan pembangunan dijalankan di thread latar belakang.
    """
    from app.db.repository import get_repository  # noqa: PLC0415

    m = meta()
    fp = _fingerprint(m)
    L = int(m["window"])
    ohlcv = get_repository().get_ohlcv(symbol, tf)
    ohlcv = ohlcv[ohlcv["close"] > 0].reset_index(drop=True)
    close = ohlcv["close"].to_numpy(dtype=float)
    times = ohlcv["time"].to_numpy()
    r = np.diff(np.log(close))
    grid = np.arange(L - 1, len(r), STRIDE)

    path = _cache_path(symbol, tf)
    cached_pos = np.empty(0, dtype=np.int64)
    cached_proba = np.empty((0, 3))
    if path.exists():
        with np.load(path) as z:
            # Grid dihitung dari bar pertama; data yang awalnya berubah membuat grid lama tidak sah.
            if str(z["fingerprint"]) == fp and int(z["first_time"]) == int(times[0]) and int(z["n_bars"]) <= len(close):
                cached_pos, cached_proba = z["pos"], z["proba"]

    new = np.setdiff1d(grid, cached_pos)
    if max_new is not None and len(new) > max_new:
        key = f"{symbol}_{tf}"
        if not _building.get(key):
            _building[key] = True

            def run() -> None:
                try:
                    update_cache(symbol, tf, jobs=jobs)
                finally:
                    _building[key] = False

            threading.Thread(target=run, daemon=True, name=f"ai-detector-{key}").start()
        raise CacheBuilding(f"{len(new)} window baru sedang dihitung")

    with _lock:
        if len(new):
            f = _featurize(r, new, m, jobs)
            proba = predict_proba(f["feat"], f["ps"], m)
            cached_pos = np.concatenate([cached_pos, new])
            cached_proba = np.concatenate([cached_proba, proba])
            order = np.argsort(cached_pos)
            cached_pos, cached_proba = cached_pos[order], cached_proba[order]
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path, pos=cached_pos, proba=cached_proba, fingerprint=fp,
                                n_bars=len(close), first_time=int(times[0]))

    # return r[t] = log(close[t+1] / close[t]); window berakhir pada bar t+1.
    classes: List[str] = list(m["classes"])
    df = pd.DataFrame({
        "time": times[cached_pos + 1].astype(np.int64),
        "close": close[cached_pos + 1],
        "regime": np.array(classes)[cached_proba.argmax(axis=1)],
        "confidence": cached_proba.max(axis=1),
    })
    for i, c in enumerate(classes):
        df[f"p_{c}"] = cached_proba[:, i]
    return df


def with_abstain(df: pd.DataFrame, tau: float = ABSTAIN_TAU) -> pd.DataFrame:
    """Salinan deret dengan label berkeyakinan rendah diganti `uncertain_lowconf`.

    Dipakai untuk notifikasi: label ragu memutus rentetan konfirmasi, sehingga
    salah alarm turun (0,91 → 0,30 per 1.000 bar pada uji sintetis).
    """
    out = df.copy()
    out.loc[out["confidence"] < tau, "regime"] = "uncertain_lowconf"
    return out


def series(symbol: str, tf: str) -> pd.DataFrame:
    """Deret deteksi untuk API; tidak menunggu bila cache masih kosong."""
    return update_cache(symbol, tf, max_new=MAX_SYNC_WINDOWS)


def building(symbol: str, tf: str) -> bool:
    return bool(_building.get(f"{symbol}_{tf}"))


if __name__ == "__main__":
    # python -m app.services.ai_detector BTCUSDT 1h 4h   (dari folder backend)
    import sys
    import time

    sym, *tfs = sys.argv[1:] or ["BTCUSDT", "1h", "4h"]
    for tf_ in tfs:
        t0 = time.time()
        out = update_cache(sym, tf_)
        print(f"{sym} {tf_}: {len(out)} titik, {time.time() - t0:.0f}s, terakhir {out['regime'].iloc[-1]}", flush=True)

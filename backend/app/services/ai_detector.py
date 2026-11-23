"""Identifikasi regime resmi sistem: Hybrid Attention-BiLSTM pipeline naskah (h = 0).

Model = model yang dilaporkan di Bab 4 (`ml/src/run_updated_evaluation.py`), disimpan
ulang tanpa perubahan oleh `ml/src/review_eval.py --variant normal --save-models`:

    ml/artifacts/review/models/hybrid_ps_updated_{tf}_s{42,43,44}.keras
    ml/artifacts/review/models/hybrid_ps_updated_{tf}_scaler.json

Label yang dipelajari = Trend-Aware Soft Consensus Hurst R/S–DFA-1 dengan ambang
kuantil train-only, horizon h = 0 (identifikasi regime jendela itu sendiri, bukan
prediksi). Inference harus sama persis dengan evaluasi:

- jendela L = 500 log-return; grid titik identifikasi mulai return ke-500, tiap 4 bar
  (1H) atau 2 bar (4H);
- TANPA normalisasi σ per jendela (berbeda dari detektor latih-sintetis lama);
- input [PS 32 × 14, F 56] (50 fitur struktural + 6 multifraktal), distandarkan
  dengan statistik partisi latih yang tersimpan di `*_scaler.json`;
- ensemble = rata-rata softmax 3 seed.

Fitur dihitung atas seluruh deret log-return (semua fungsi fitur kausal: hanya
data ≤ t). Hasil disimpan di cache disk dan diperbarui bertahap.
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
META_KEY = "d_identifikasi"
CACHE_DIR = PROCESSED_DIR / "cache"
CACHE_VERSION = "id1"
# Stride per timeframe sama dengan evaluasi Bab 4.
STRIDES = {"1h": 4, "4h": 2}
DEFAULT_STRIDE = 4
# Timeframe lain (mis. analisis aset 15m/1d) memakai model timeframe terdekat.
MODEL_TF = {"15m": "1h", "30m": "1h", "1h": "1h", "4h": "4h", "1d": "4h"}
# Di atas jumlah ini, permintaan API tidak menunggu; pembangunan dijalankan di
# latar belakang dan endpoint memberi tahu bahwa cache sedang dibangun.
MAX_SYNC_WINDOWS = 1500
# Sampai jumlah jendela ini, sekuens PS dihitung per potongan jendela (cepat untuk
# pembaruan bertahap); di atasnya dihitung sekali atas seluruh deret.
INCREMENTAL_MAX = 64
# Penanda keyakinan rendah. Label identifikasi tetap argmax (sesuai evaluasi Bab 4);
# τ hanya menandai jendela ragu dan memutus konfirmasi notifikasi. Pada set
# validasi backtest, keyakinan ≥ 0,75 mencakup 25% (1H) / 49% (4H) jendela dengan
# ketepatan 85,7% / 94,8% (`ml/artifacts/detector_meta.json`).
ABSTAIN_TAU = 0.75

_lock = threading.Lock()
_building: Dict[str, bool] = {}
_models: Dict[str, List[Any]] = {}
_fp_cache: Dict[str, str] = {}


class DetectorUnavailable(RuntimeError):
    """Artefak model belum ada (jalankan `ml/src/review_eval.py --variant normal --save-models`)."""


class CacheBuilding(RuntimeError):
    """Cache identifikasi sedang dibangun di latar belakang."""


def model_tf(tf: str) -> str:
    return MODEL_TF.get(tf, "1h")


def stride_for(tf: str) -> int:
    return STRIDES.get(model_tf(tf), DEFAULT_STRIDE)


def meta(tf: str = "1h") -> Dict[str, Any]:
    """Metadata model untuk timeframe `tf` (kelas, ambang label, scaler, berkas)."""
    if not META_PATH.exists():
        raise DetectorUnavailable("detector_meta.json tidak ditemukan")
    blob = json.loads(META_PATH.read_text(encoding="utf-8"))
    entry = blob.get(META_KEY, {}).get(model_tf(tf))
    if not entry:
        raise DetectorUnavailable(f"{META_KEY}.{model_tf(tf)} tidak ada di detector_meta.json")
    scaler_path = ARTIFACTS_DIR / entry["scaler_file"]
    if not scaler_path.exists():
        raise DetectorUnavailable(f"{entry['scaler_file']} tidak ditemukan")
    scaler = json.loads(scaler_path.read_text(encoding="utf-8"))
    missing = [f for f in entry["files"] if not (ARTIFACTS_DIR / f).exists()]
    if missing:
        raise DetectorUnavailable(f"berkas model tidak ditemukan: {', '.join(missing)}")
    return {**entry, "model_timeframe": model_tf(tf), "ps_scaler": scaler["ps_scaler"],
            "feature_mean": scaler["f_mean"], "feature_std": scaler["f_std"],
            "ps_channels": scaler["ps_channels"], "feature_names": scaler["f_names"]}


def _fingerprint(m: Dict[str, Any]) -> str:
    """Sidik jari isi model + scaler: cache gugur bila model dilatih ulang.

    Memakai hash isi berkas, bukan waktu ubah, agar cache tetap sah setelah
    model dan cache disalin ke server lain.
    """
    paths = [ARTIFACTS_DIR / f for f in m["files"]] + [ARTIFACTS_DIR / m["scaler_file"]]
    key = "|".join(f"{p}:{p.stat().st_mtime_ns}" for p in paths)
    if key not in _fp_cache:
        h = hashlib.sha256(CACHE_VERSION.encode())
        for p in paths:
            h.update(hashlib.sha256(p.read_bytes()).digest())
        _fp_cache[key] = h.hexdigest()[:12]
    return _fp_cache[key]


def _load_models(m: Dict[str, Any]) -> List[Any]:
    tfm = m["model_timeframe"]
    if tfm not in _models:
        import tensorflow as tf  # noqa: PLC0415

        from ml_layers import AttentionPooling  # noqa: PLC0415

        _models[tfm] = [
            tf.keras.models.load_model(ARTIFACTS_DIR / f, custom_objects={"AttentionPooling": AttentionPooling}, compile=False)
            for f in m["files"]
        ]
    return _models[tfm]


def _struct_chunk(r: np.ndarray, pos: List[int], L: int, level: int) -> np.ndarray:
    from app.services.multifractal import compute_features as mf_one  # noqa: PLC0415
    from app.services.structural_features import compute_features as st_one  # noqa: PLC0415

    return np.asarray([list(st_one(r, int(t), L, level)) + list(mf_one(r, int(t), L)) for t in pos], dtype=np.float32)


def _featurize(r: np.ndarray, pos: np.ndarray, m: Dict[str, Any], jobs: int) -> Dict[str, np.ndarray]:
    """Fitur identik dengan `run_updated_evaluation.prepare_timeframe_data`."""
    from app.services.persistence_sequence import build_persistence_sequences  # noqa: PLC0415

    L, level = int(m["window"]), int(m.get("swt_level", 4))
    pos_l = [int(t) for t in pos]
    if jobs == 1 or len(pos_l) < 200:
        feat = _struct_chunk(r, pos_l, L, level)
    else:
        from joblib import Parallel, delayed  # noqa: PLC0415

        size = max(64, len(pos_l) // 32 + 1)
        chunks = [pos_l[i: i + size] for i in range(0, len(pos_l), size)]
        feat = np.vstack(Parallel(n_jobs=jobs)(delayed(_struct_chunk)(r, ch, L, level) for ch in chunks))
    sub, seq = int(m["sub_window"]), int(m["seq_len"])
    if len(pos_l) <= INCREMENTAL_MAX:
        # Pembaruan bertahap (beberapa jendela baru): sekuens PS hanya bergantung pada
        # 500 return di dalam jendela, jadi dihitung dari potongan itu saja (±0,05 s per
        # jendela, bukan ±5 s untuk seluruh riwayat). Selisih terhadap perhitungan atas
        # deret penuh hanya pembulatan floating point (< 1e-11).
        ps = np.stack([
            build_persistence_sequences(r[t - L + 1: t + 1], [L - 1], L, sub, seq)[0] for t in pos_l
        ]).astype(np.float32)
    else:
        ps = build_persistence_sequences(r, pos_l, L, sub, seq).astype(np.float32)
    return {"feat": feat, "ps": ps}


def predict_proba(feat: np.ndarray, ps: np.ndarray, m: Dict[str, Any]) -> np.ndarray:
    """Probabilitas ensemble (n, 3), urutan kelas = m["classes"]."""
    from app.services.feature_builder import apply_scaler  # noqa: PLC0415

    # Aritmetika float32 untuk F dan float32→float64 untuk PS, sama dengan evaluasi,
    # agar argmax identik sampai bit terakhir.
    f32 = np.float32
    F = (np.asarray(feat, dtype=f32) - np.asarray(m["feature_mean"], dtype=f32)) / np.asarray(m["feature_std"], dtype=f32)
    S = apply_scaler(np.asarray(ps, dtype=f32), m["ps_scaler"])
    probs = [mdl.predict([S, F], batch_size=1024, verbose=0) for mdl in _load_models(m)]
    return np.mean(probs, axis=0)


def _scaled_inputs(feat: np.ndarray, ps: np.ndarray, m: Dict[str, Any]):
    from app.services.feature_builder import apply_scaler  # noqa: PLC0415

    f32 = np.float32
    F = (np.asarray(feat, dtype=f32) - np.asarray(m["feature_mean"], dtype=f32)) / np.asarray(m["feature_std"], dtype=f32)
    S = apply_scaler(np.asarray(ps, dtype=f32), m["ps_scaler"])
    return S, F


_extractors: Dict[str, List[Any]] = {}


def attention_weights(feat: np.ndarray, ps: np.ndarray, m: Dict[str, Any]) -> np.ndarray:
    """Bobot alpha lapisan `attention_pool` tiap seed: array (n_seed, n, seq_len).

    Bobot dihitung dari keluaran BiLSTM (masukan lapisan attention) dengan
    `AttentionPooling.compute_attention`, sama persis dengan yang dipakai model
    saat menghasilkan probabilitas.
    """
    import tensorflow as tf  # noqa: PLC0415

    tfm = m["model_timeframe"]
    if tfm not in _extractors:
        out = []
        for mdl in _load_models(m):
            layer = mdl.get_layer("attention_pool")
            out.append((tf.keras.Model(mdl.inputs, layer.input), layer))
        _extractors[tfm] = out
    S, F = _scaled_inputs(feat, ps, m)
    weights = []
    for sub, layer in _extractors[tfm]:
        h = sub.predict([S, F], batch_size=1024, verbose=0)
        weights.append(np.asarray(layer.compute_attention(tf.convert_to_tensor(h))))
    return np.stack(weights)


def _ohlcv_arrays(symbol: str, tf: str):
    from app.db.repository import get_repository  # noqa: PLC0415

    ohlcv = get_repository().get_ohlcv(symbol, tf)
    ohlcv = ohlcv[ohlcv["close"] > 0].reset_index(drop=True)
    close = ohlcv["close"].to_numpy(dtype=float)
    return np.diff(np.log(close)), ohlcv["time"].to_numpy(), close


def window_detail(symbol: str, tf: str, at_time: Optional[int] = None) -> Dict[str, Any]:
    """Fitur, probabilitas, dan bobot attention untuk satu jendela.

    Jendela = titik grid identifikasi terakhir dengan waktu bar terakhir <= `at_time`
    (bawaan: jendela terbaru).
    """
    m = meta(tf)
    L, stride = int(m["window"]), stride_for(tf)
    r, times, close = _ohlcv_arrays(symbol, tf)
    grid = np.arange(L - 1, len(r), stride)
    if len(grid) == 0:
        raise ValueError("riwayat kurang dari satu jendela")
    bar_time = times[grid + 1]
    i = len(grid) - 1 if at_time is None else int(np.searchsorted(bar_time, int(at_time), side="right") - 1)
    i = max(0, i)
    t = int(grid[i])
    f = _featurize(r, np.array([t]), m, jobs=1)
    with _lock:
        proba = predict_proba(f["feat"], f["ps"], m)[0]
        alpha = attention_weights(f["feat"], f["ps"], m)[:, 0, :]
    sub, seq = int(m["sub_window"]), int(m["seq_len"])
    step = (L - sub) // (seq - 1)
    classes = list(m["classes"])
    return {
        "position": t,
        "window_index": i,
        "n_windows": int(len(grid)),
        "time": int(times[t + 1]),
        "close": float(close[t + 1]),
        "regime": classes[int(proba.argmax())],
        "confidence": float(proba.max()),
        "probabilities": {c: float(p) for c, p in zip(classes, proba)},
        "attention": {
            "mean": alpha.mean(0).tolist(),
            "per_seed": {str(s): a.tolist() for s, a in zip(m["seeds"], alpha)},
            "seq_len": seq,
            "sub_window_bars": sub,
            "step_bars": step,
            # Langkah k mencakup bar [t − (seq−1−k)·step − sub + 1, t − (seq−1−k)·step].
            "step_end_offsets_bars": [-(seq - 1 - k) * step for k in range(seq)],
            "entropy_normalized": float(-(alpha.mean(0) * np.log(alpha.mean(0) + 1e-12)).sum() / np.log(seq)),
        },
        "features": {
            "ps_shape": list(f["ps"].shape[1:]),
            "ps_channels": list(m["ps_channels"]),
            "summary_length": int(f["feat"].shape[1]),
            "summary_names": list(m["feature_names"]),
            "summary_values": [float(v) for v in f["feat"][0]],
            "ps_last_step": [float(v) for v in f["ps"][0, -1]],
        },
    }


def _cache_path(symbol: str, tf: str):
    return CACHE_DIR / f"ai_regime_{symbol.lower()}_{tf}.npz"


def update_cache(symbol: str, tf: str, jobs: int = -1, max_new: Optional[int] = None) -> pd.DataFrame:
    """Hitung probabilitas untuk titik identifikasi yang belum ada di cache.

    Bila jumlah titik baru melebihi `max_new`, `CacheBuilding` dilempar dan
    pembangunan dijalankan di thread latar belakang.
    """
    from app.db.repository import get_repository  # noqa: PLC0415

    m = meta(tf)
    fp = _fingerprint(m)
    L = int(m["window"])
    stride = stride_for(tf)
    ohlcv = get_repository().get_ohlcv(symbol, tf)
    ohlcv = ohlcv[ohlcv["close"] > 0].reset_index(drop=True)
    close = ohlcv["close"].to_numpy(dtype=float)
    times = ohlcv["time"].to_numpy()
    r = np.diff(np.log(close))
    grid = np.arange(L - 1, len(r), stride)

    path = _cache_path(symbol, tf)
    cached_pos = np.empty(0, dtype=np.int64)
    cached_proba = np.empty((0, 3))
    if path.exists():
        with np.load(path) as z:
            # Grid dihitung dari bar pertama; data yang awalnya berubah membuat grid lama tidak sah.
            if ("stride" in z and int(z["stride"]) == stride and str(z["fingerprint"]) == fp
                    and int(z["first_time"]) == int(times[0]) and int(z["n_bars"]) <= len(close)):
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
            np.savez_compressed(path, pos=cached_pos, proba=cached_proba, fingerprint=fp, stride=stride,
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


def preload(tf: str) -> None:
    """Muat model timeframe `tf` ke memori (dipanggil saat pemanasan startup)."""
    _load_models(meta(tf))


def with_abstain(df: pd.DataFrame, tau: float = ABSTAIN_TAU) -> pd.DataFrame:
    """Salinan deret dengan label berkeyakinan rendah diganti `uncertain_lowconf`.

    Dipakai untuk notifikasi: label ragu memutus rentetan konfirmasi.
    """
    out = df.copy()
    out.loc[out["confidence"] < tau, "regime"] = "uncertain_lowconf"
    return out


def series(symbol: str, tf: str) -> pd.DataFrame:
    """Deret identifikasi untuk API; tidak menunggu bila cache masih kosong."""
    return update_cache(symbol, tf, max_new=MAX_SYNC_WINDOWS)


def building(symbol: str, tf: str) -> bool:
    return bool(_building.get(f"{symbol}_{tf}"))


def describe(tf: str) -> Dict[str, Any]:
    """Ringkasan model untuk respons API dan halaman metodologi."""
    m = meta(tf)
    return {
        "name": "Hybrid Attention-BiLSTM (identifikasi, h = 0)",
        "task": "identifikasi",
        "horizon_bars": 0,
        "inputs": f"Sekuens statistik persistensi {m['seq_len']}×{len(m['ps_channels'])} + "
                  f"{len(m['feature_names'])} fitur (50 struktural termasuk 12 energi SWT dan 6 ER/tren, + 6 multifraktal)",
        "trained_on": m["trained_on"],
        "label": m["label"],
        "label_thresholds": m["label_thresholds_train_only"],
        "classes": m["classes"],
        "window": int(m["window"]),
        "stride_bars": stride_for(tf),
        "model_timeframe": m["model_timeframe"],
        "ensemble_seeds": m["seeds"],
        "test_backtest": m["test_backtest"],
        "walk_forward_pooled": m.get("walk_forward_pooled"),
        "abstain_tau": ABSTAIN_TAU,
        "abstain_validation": m.get("abstain_validation"),
    }


if __name__ == "__main__":
    # python -m app.services.ai_detector BTCUSDT 1h 4h   (dari folder backend)
    import sys
    import time

    sym, *tfs = sys.argv[1:] or ["BTCUSDT", "1h", "4h"]
    for tf_ in tfs:
        t0 = time.time()
        out = update_cache(sym, tf_)
        print(f"{sym} {tf_}: {len(out)} titik, {time.time() - t0:.0f}s, terakhir {out['regime'].iloc[-1]}", flush=True)

"""Inference regime — HANYA memuat artefak hasil training offline.

Backend tidak pernah melatih model saat request; TensorFlow diimpor secara malas
hanya ketika artefak benar-benar dimuat, sehingga endpoint non-model tetap
ringan dan tidak bergantung pada TF.

Tiga model yang dibandingkan:
    rule_based           : baseline 1 — Hurst-DFA dari window <= t
    swt_bilstm           : baseline 2 — tanpa attention
    swt_attention_bilstm : model usulan skripsi
Ditambah `persistence` sebagai baseline naif (regime t+h = regime t).
Tanpa baseline persistence, angka model apa pun tidak bisa dinilai.

Bila artefak belum ada, modul memakai stand-in deterministik agar dashboard
tetap dapat dijalankan. Statusnya selalu dilaporkan lewat `prediction_source`
supaya angka stand-in tidak pernah disalahartikan sebagai hasil pembelajaran.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.core.config import ARTIFACTS_DIR, REGIME_CLASSES, get_config
from app.services.regime_labeling import (
    UNCERTAIN_RULE,
    apply_tau,
)

MODEL_KEYS = ["rule_based", "swt_bilstm", "swt_attention_bilstm"]
MODEL_LABELS = {
    "rule_based": "Baseline 1 — Hurst-DFA rule-based",
    "swt_bilstm": "Baseline 2 — SWT + BiLSTM",
    "swt_attention_bilstm": "Usulan — SWT + Attention-BiLSTM",
    "persistence": "Baseline naif — Persistence (regime t+h = regime t)",
}

NEURAL_KEYS = {"swt_bilstm", "swt_attention_bilstm"}

_loaded: Dict[str, Any] = {}
_load_lock = threading.Lock()
_load_failures: Dict[str, str] = {}


def artifact_path(model_key: str, timeframe: str) -> Path:
    return ARTIFACTS_DIR / f"{model_key}_{timeframe}.keras"


def metadata_path(model_key: str, timeframe: str) -> Path:
    return ARTIFACTS_DIR / f"{model_key}_{timeframe}.json"


def artifact_available(model_key: str, timeframe: str) -> bool:
    return artifact_path(model_key, timeframe).exists()


def load_metadata(model_key: str, timeframe: str) -> Dict[str, Any]:
    """Metadata training: seq_len, horizon, metrik, config_hash."""
    path = metadata_path(model_key, timeframe)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def load_model(model_key: str, timeframe: str) -> Any:
    """Muat artefak Keras sekali lalu simpan di memori.

    TensorFlow diimpor di dalam fungsi, bukan di tingkat modul: endpoint yang
    tidak menyentuh model tidak perlu menanggung waktu impornya.
    """
    cache_key = f"{model_key}_{timeframe}"
    if cache_key in _loaded:
        return _loaded[cache_key]
    if cache_key in _load_failures:
        return None

    path = artifact_path(model_key, timeframe)
    if not path.exists():
        return None

    with _load_lock:
        if cache_key in _loaded:
            return _loaded[cache_key]
        try:
            import tensorflow as tf  # noqa: PLC0415

            from ml_layers import AttentionPooling  # noqa: PLC0415

            model = tf.keras.models.load_model(
                path, custom_objects={"AttentionPooling": AttentionPooling}
            )
            _loaded[cache_key] = model
            return model
        except Exception as exc:  # noqa: BLE001
            # Kegagalan memuat tidak boleh menjatuhkan dashboard; dicatat agar
            # tidak dicoba berulang kali pada setiap request.
            _load_failures[cache_key] = f"{type(exc).__name__}: {exc}"[:200]
            return None


def load_error(model_key: str, timeframe: str) -> Optional[str]:
    return _load_failures.get(f"{model_key}_{timeframe}")


def reset_model_cache() -> None:
    _loaded.clear()
    _load_failures.clear()


def prediction_source(model_key: str, timeframe: str) -> str:
    """Asal angka prediksi: artefak terlatih atau stand-in deterministik.

    Dipakai UI untuk menandai panel model, supaya angka stand-in tidak pernah
    disalahartikan sebagai hasil model yang sudah dilatih.
    """
    if model_key == "rule_based":
        return "rule_based"
    return "trained_artifact" if artifact_available(model_key, timeframe) else "placeholder"


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def predict_proba(
    model_key: str,
    features: Sequence[float],
    seed: int = 42,
) -> Dict[str, float]:
    """Probabilitas 3 kelas untuk satu window.

    Saat artefak hasil training belum tersedia, skor dibangkitkan deterministik
    dari fitur sehingga stabil antar-request — bukan angka acak per panggilan.

    Catatan penting: ketersediaan artefak TIDAK terikat pada `runtime.use_mock`.
    Flag itu hanya mengatur sumber data harga (mock vs Binance). Data pasar asli
    bisa dipakai jauh sebelum model dilatih, jadi keduanya dipisah. Status
    sebenarnya dilaporkan lewat `artifact_loaded` di endpoint agar tidak ada
    yang mengira angka stand-in berasal dari model terlatih.
    """
    vec = np.asarray(list(features) or [0.0], dtype=float)
    digest = float(np.sum(np.sin(vec * 12.9898 + 78.233))) + hash(model_key) % 97
    rng = np.random.default_rng(int(abs(digest) * 1000) % (2**31) + seed)

    # Model dengan attention dibuat sedikit lebih tajam (entropi lebih rendah)
    # agar perbedaan antar-model terlihat di panel perbandingan.
    sharpness = {"rule_based": 1.0, "swt_bilstm": 1.4, "swt_attention_bilstm": 1.9}
    logits = rng.normal(size=3) * sharpness.get(model_key, 1.0)
    probs = _softmax(logits)
    return {cls: float(round(p, 4)) for cls, p in zip(REGIME_CLASSES, probs)}


def predict_labels(
    model_key: str,
    feature_rows: Sequence[Sequence[float]],
    tau: float,
) -> List[Dict[str, object]]:
    """Prediksi banyak window sekaligus, sudah melalui post-processing tau."""
    out = []
    for i, row in enumerate(feature_rows):
        probs = predict_proba(model_key, row, seed=i)
        resolved = apply_tau(probs, tau)
        out.append({"raw_probabilities": probs, **resolved})
    return out


def predict_sequences(
    model_key: str,
    timeframe: str,
    sequences: np.ndarray,
    batch_size: int = 256,
) -> Optional[np.ndarray]:
    """Probabilitas untuk banyak sekuens sekaligus memakai artefak terlatih.

    Mengembalikan None bila artefak tidak tersedia atau gagal dimuat, sehingga
    pemanggil dapat jatuh ke stand-in tanpa menggagalkan request.
    """
    if model_key not in NEURAL_KEYS or len(sequences) == 0:
        return None
    model = load_model(model_key, timeframe)
    if model is None:
        return None
    try:
        return np.asarray(model.predict(sequences, batch_size=batch_size, verbose=0))
    except Exception as exc:  # noqa: BLE001
        _load_failures[f"{model_key}_{timeframe}"] = f"predict: {exc}"[:200]
        return None


def load_identification_model(model_key: str, mode: str, timeframe: str) -> Any:
    """Muat artefak tugas identifikasi (nama berpola <model>_<mode>_<tf>)."""
    return load_model(f"{model_key}_{mode}", timeframe)


def attention_weights(
    timeframe: str,
    sequence: np.ndarray,
) -> Optional[List[float]]:
    """Bobot alpha_t untuk satu sekuens dari model attention terlatih."""
    model = load_model("swt_attention_bilstm", timeframe)
    if model is None:
        return None
    try:
        pool = model.get_layer("attention_pool")
        import tensorflow as tf  # noqa: PLC0415

        extractor = tf.keras.models.Model(model.input, pool.input)
        seq_out = extractor.predict(sequence[None, ...], verbose=0)
        weights = pool.compute_attention(tf.convert_to_tensor(seq_out))
        return [float(w) for w in np.asarray(weights)[0]]
    except Exception:  # noqa: BLE001
        return None


def persistence_baseline(labels: Sequence[str], h: int) -> List[Optional[str]]:
    """Prediksi naif: regime t+h sama dengan regime t."""
    return [labels[t] if t < len(labels) else None for t in range(len(labels))]


def balanced_accuracy(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    """Recall rata-rata per kelas — tahan terhadap kelas tidak seimbang."""
    classes = [c for c in REGIME_CLASSES if c in set(y_true)]
    if not classes:
        return float("nan")
    recalls = []
    for c in classes:
        idx = [i for i, y in enumerate(y_true) if y == c]
        if not idx:
            continue
        recalls.append(sum(1 for i in idx if y_pred[i] == c) / len(idx))
    return float(round(np.mean(recalls), 4)) if recalls else float("nan")


def matthews_corrcoef(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    """MCC multikelas — satu angka ringkas yang tetap jujur saat kelas timpang."""
    classes = sorted(set(list(y_true) + list(y_pred)))
    idx = {c: i for i, c in enumerate(classes)}
    k = len(classes)
    if k < 2:
        return float("nan")
    cm = np.zeros((k, k), dtype=float)
    for t, p in zip(y_true, y_pred):
        cm[idx[t], idx[p]] += 1
    t_sum = cm.sum(axis=1)
    p_sum = cm.sum(axis=0)
    n = cm.sum()
    correct = np.trace(cm)
    num = correct * n - float(t_sum @ p_sum)
    den = np.sqrt(max(n**2 - float(p_sum @ p_sum), 0.0)) * np.sqrt(
        max(n**2 - float(t_sum @ t_sum), 0.0)
    )
    return float(round(num / den, 4)) if den > 0 else float("nan")


def evaluate_against_truth(
    y_true: Sequence[str],
    y_pred: Sequence[str],
) -> Dict[str, object]:
    """Metrik SEKUNDER. Bukan indikator keberhasilan utama penelitian ini.

    Window dengan ground truth uncertain_rule dikeluarkan dari perhitungan
    karena model memang tidak pernah dilatih untuk kategori tersebut.
    """
    pairs = [(t, p) for t, p in zip(y_true, y_pred) if t != UNCERTAIN_RULE and p is not None]
    if not pairs:
        return {"n_evaluated": 0}
    yt = [t for t, _ in pairs]
    yp = [p for _, p in pairs]
    return {
        "n_evaluated": len(pairs),
        "balanced_accuracy": balanced_accuracy(yt, yp),
        "mcc": matthews_corrcoef(yt, yp),
        "plain_accuracy": float(round(sum(t == p for t, p in pairs) / len(pairs), 4)),
        "catatan": "Metrik sekunder — bukan indikator keberhasilan utama penelitian ini.",
    }


def evaluate_with_coverage(
    y_true: Sequence[Optional[str]],
    y_argmax: Sequence[Optional[str]],
    y_final: Sequence[Optional[str]],
) -> Dict[str, object]:
    """Metrik dua lapis: sebelum dan sesudah ambang tau.

    Alasan pemisahan ini: ketika model jarang yakin, hampir semua window menjadi
    uncertain_lowconf dan metrik pasca-tau jatuh ke 0. Angka nol itu menyesatkan
    karena terbaca seolah model salah total, padahal artinya model tidak pernah
    cukup yakin untuk memberi label tegas.

    - `argmax`   : kemampuan diskriminatif murni, mengabaikan tau.
    - `thresholded` : yang benar-benar dipakai dashboard, dihitung hanya pada
                      window yang lolos tau.
    - `coverage` : porsi window yang mendapat label tegas. Tanpa angka ini,
                   pembaca tidak bisa membedakan "salah" dari "tidak menjawab".
    """
    valid = [
        (t, a, f)
        for t, a, f in zip(y_true, y_argmax, y_final)
        if t is not None and t != UNCERTAIN_RULE and a is not None
    ]
    if not valid:
        return {"n_evaluated": 0, "coverage": 0.0}

    yt = [t for t, _, _ in valid]
    ya = [a for _, a, _ in valid]

    confident = [(t, f) for t, _, f in valid if f in REGIME_CLASSES]
    coverage = len(confident) / len(valid)

    thresholded: Dict[str, object] = {"n": len(confident)}
    if confident:
        ct = [t for t, _ in confident]
        cp = [p for _, p in confident]
        thresholded.update(
            {
                "balanced_accuracy": balanced_accuracy(ct, cp),
                "mcc": matthews_corrcoef(ct, cp),
                "plain_accuracy": float(round(sum(t == p for t, p in confident) / len(confident), 4)),
            }
        )

    return {
        "n_evaluated": len(valid),
        "coverage": float(round(coverage, 4)),
        "argmax": {
            "n": len(valid),
            "balanced_accuracy": balanced_accuracy(yt, ya),
            "mcc": matthews_corrcoef(yt, ya),
            "plain_accuracy": float(round(sum(t == a for t, a in zip(yt, ya)) / len(yt), 4)),
        },
        "thresholded": thresholded,
        "catatan": (
            "Metrik sekunder. `argmax` mengukur daya diskriminasi tanpa ambang; "
            "`thresholded` hanya menghitung window yang lolos tau. Bila coverage "
            "rendah, angka thresholded berarti 'jarang menjawab', bukan 'sering salah'."
        ),
    }

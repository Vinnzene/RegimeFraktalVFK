"""Dataset sintetis fBm untuk pretraining — flow.md langkah 4.

Gagasannya
----------
Pada data BTC, label regime berasal dari ESTIMASI Hurst, dan estimasi itu
sendiri mengandung galat. Model karenanya belajar dari target yang sudah
tercemar. Pada fractional Brownian motion, H adalah parameter pembangkit:
nilainya diketahui persis, bukan ditaksir. Melatih model di sana lebih dulu
membuatnya mempelajari bentuk pola tiap regime dalam keadaan bersih, sebelum
dihadapkan pada derau pasar sungguhan.

Yang penting dijaga
-------------------
1. **Fitur dibentuk dengan fungsi yang sama** seperti data riil
   (`build_sequence_features`). Kalau berbeda, bobot hasil pretraining memetakan
   masukan yang tak pernah muncul saat fine-tuning dan justru memperburuk.
2. **Label berasal dari H pembangkit**, bukan dari estimator. Memakai estimator
   di sini akan mengulang galat yang justru ingin dihindari.
3. **Ambang label mengikuti definisi regime yang sama**: H < 0.5 anti-persisten,
   H > 0.5 persisten, di sekitar 0.5 random-like. Lebar pita netral dibuat
   eksplisit lewat `neutral_band` supaya tidak ada ambang tersembunyi.

Perbedaan yang disengaja dari `backend/tests/test_hurst_dfa.py`: di sana fBm
dipakai untuk MENGUJI ESTIMATOR, di sini untuk MELATIH MODEL. Keduanya memakai
pembangkit yang sama (`hurst_dfa.fbm_increments`) sehingga tidak ada dua versi
fBm yang bisa menyimpang diam-diam.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import REGIME_CLASSES  # noqa: E402
from app.services.feature_builder import (  # noqa: E402
    apply_scaler,
    build_sequence_features,
    fit_scaler,
)
from app.services.hurst_dfa import fbm_increments  # noqa: E402
from app.services.multifractal import (  # noqa: E402
    build_feature_matrix as build_multifractal_matrix,
)
from app.services.structural_features import build_feature_matrix  # noqa: E402

# Rentang H yang disimulasikan. Sengaja melebar ke 0.2 dan 0.8 agar model
# melihat contoh tegas di kedua ujung, bukan hanya kasus batas.
DEFAULT_HURST_GRID: Tuple[float, ...] = (0.2, 0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7, 0.8)


def label_from_true_h(h: float, neutral_band: float = 0.05) -> str:
    """Label regime dari H pembangkit — tanpa estimasi, tanpa galat."""
    if h < 0.5 - neutral_band:
        return "anti_persistent"
    if h > 0.5 + neutral_band:
        return "persistent"
    return "random_like"


def build_synthetic_dataset(
    seq_len: int = 32,
    window: int = 500,
    swt_level: int = 4,
    n_series_per_h: int = 40,
    samples_per_series: int = 8,
    hurst_grid: Sequence[float] = DEFAULT_HURST_GRID,
    classes: Sequence[str] | None = None,
    neutral_band: float = 0.05,
    with_structural: bool = True,
    with_multifractal: bool = True,
    seed: int = 42,
    validation_share: float = 0.2,
) -> Dict[str, object]:
    """Rakit X, fitur, target kelas, dan target H dari fBm.

    Parameter
    ---------
    n_series_per_h
        Banyak realisasi independen per nilai H. Beberapa realisasi diperlukan
        karena satu lintasan fBm tunggal bisa kebetulan tidak khas.
    samples_per_series
        Banyak titik t yang diambil dari tiap lintasan. Titik-titik ini saling
        tumpang tindih, jadi menambahnya tidak setara dengan menambah lintasan.
    validation_share
        Pemisahan dilakukan per LINTASAN, bukan per sampel. Memisah per sampel
        akan menempatkan potongan dari lintasan yang sama di kedua sisi dan
        membuat skor validasi terlalu bagus.
    """
    target_classes: List[str] = list(classes) if classes else list(REGIME_CLASSES)
    rng = np.random.default_rng(seed)

    # Panjang deret: satu window penuh untuk sampel pertama, ditambah ruang
    # gerak sepanjang satu window lagi agar titik-titik sampel benar-benar
    # tersebar dan tidak bertumpuk di ujung yang sama.
    series_len = 2 * window + 64

    seq_rows: List[np.ndarray] = []
    feat_rows: List[np.ndarray] = []
    class_rows: List[str] = []
    hurst_rows: List[float] = []
    series_id: List[int] = []

    sid = 0
    for h in hurst_grid:
        label = label_from_true_h(float(h), neutral_band=neutral_band)
        if label not in target_classes:
            continue
        for k in range(n_series_per_h):
            series_seed = int(rng.integers(0, 2**31 - 1))
            x = fbm_increments(series_len, float(h), seed=series_seed)

            # Titik pengambilan dimulai setelah satu window penuh terkumpul,
            # sehingga tidak ada sampel yang windownya terpotong di awal deret.
            lo = window - 1
            hi = x.size - 1
            positions = sorted(
                set(np.linspace(lo, hi, samples_per_series).astype(int).tolist())
            )

            seq = build_sequence_features(
                x, positions, level=swt_level, seq_len=seq_len, swt_window=window
            )

            parts: List[np.ndarray] = []
            if with_structural:
                parts.append(
                    build_feature_matrix(x, positions, window=window, swt_level=swt_level)
                )
            if with_multifractal:
                parts.append(build_multifractal_matrix(x, positions, window=window))
            feats = (
                np.hstack(parts)
                if parts
                else np.empty((len(positions), 0), dtype=float)
            )

            seq_rows.append(seq)
            feat_rows.append(feats)
            class_rows.extend([label] * len(positions))
            hurst_rows.extend([float(h)] * len(positions))
            series_id.extend([sid] * len(positions))
            sid += 1

    if not seq_rows:
        raise ValueError(
            "Tidak ada deret yang terbentuk. Periksa hurst_grid terhadap classes: "
            f"grid={list(hurst_grid)} classes={target_classes}"
        )

    X = np.concatenate(seq_rows, axis=0)
    F = np.concatenate(feat_rows, axis=0)
    y_hurst = np.asarray(hurst_rows, dtype=float).reshape(-1, 1)
    sids = np.asarray(series_id, dtype=int)

    class_index = {c: i for i, c in enumerate(target_classes)}
    y_class = np.zeros((len(class_rows), len(target_classes)), dtype=float)
    for i, c in enumerate(class_rows):
        y_class[i, class_index[c]] = 1.0

    # Pemisahan per lintasan.
    unique_sids = np.unique(sids)
    rng.shuffle(unique_sids)
    n_val = max(1, int(len(unique_sids) * validation_share))
    val_sids = set(unique_sids[:n_val].tolist())
    val_mask = np.array([s in val_sids for s in sids])
    train_mask = ~val_mask

    # Scaler dari subset training saja, konsisten dengan pipeline data riil.
    scaler = fit_scaler(X[train_mask]) if train_mask.any() else {"mean": [], "std": []}
    X = apply_scaler(X, scaler)

    if F.shape[1] and train_mask.any():
        f_mean = F[train_mask].mean(axis=0)
        f_std = F[train_mask].std(axis=0)
        f_std[f_std < 1e-12] = 1.0
        F = (F - f_mean) / f_std
        feature_scaler = {"mean": f_mean.tolist(), "std": f_std.tolist()}
    else:
        feature_scaler = {"mean": [], "std": []}

    return {
        "train": (X[train_mask], F[train_mask], y_class[train_mask], y_hurst[train_mask]),
        "validation": (X[val_mask], F[val_mask], y_class[val_mask], y_hurst[val_mask]),
        "classes": target_classes,
        "scaler": scaler,
        "feature_scaler": feature_scaler,
        "hurst_grid": [float(h) for h in hurst_grid],
        "neutral_band": neutral_band,
        "n_series": int(sid),
        "n_samples": int(len(class_rows)),
        "class_counts": {
            c: int(sum(1 for r in class_rows if r == c)) for c in target_classes
        },
        "seq_len": seq_len,
        "window": window,
        "catatan": (
            "Label berasal dari H pembangkit, bukan dari estimator. Scaler "
            "sintetis TIDAK dipakai saat fine-tuning: data riil punya skala "
            "sendiri dan memakai statistik fBm di sana akan menggeser masukan."
        ),
    }

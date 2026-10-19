"""Pelabelan regime fraktal — 4 kategori, dua sumber ketidakpastian.

Kategori:
    persistent        : H > upper DAN alpha > upper
    random_like       : keduanya di dalam pita [lower, upper]
    anti_persistent   : H < lower DAN alpha < lower
    uncertain_rule    : Hurst dan DFA TIDAK konsisten (ground truth, Bab 3.3.3)
    uncertain_lowconf : max(P) < tau pada output model (post-processing)

Dua jenis uncertain sengaja DIPISAH di seluruh sistem. `uncertain_rule` adalah
pernyataan tentang datanya (dua estimator tidak sepakat); `uncertain_lowconf`
adalah pernyataan tentang modelnya (model ragu). Menggabungkannya akan membuat
penguji tidak bisa membedakan "data ambigu" dari "model lemah".
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple, cast

import numpy as np
import pandas as pd

from app.core.config import REGIME_CATEGORIES, REGIME_CLASSES

PERSISTENT = "persistent"
RANDOM_LIKE = "random_like"
ANTI_PERSISTENT = "anti_persistent"
UNCERTAIN_RULE = "uncertain_rule"
UNCERTAIN_LOWCONF = "uncertain_lowconf"


def _bucket(value: float, lower: float, upper: float) -> Optional[str]:
    """Petakan satu nilai eksponen ke salah satu dari 3 kelas dasar."""
    if not np.isfinite(value):
        return None
    if value < lower:
        return ANTI_PERSISTENT
    if value > upper:
        return PERSISTENT
    return RANDOM_LIKE


def calibrate_thresholds(
    values: Iterable[float],
    quantiles: Sequence[float] = (1 / 3, 2 / 3),
) -> List[float]:
    """Ambang empiris dari distribusi estimator itu sendiri.

    Alasan keberadaannya: R/S dan DFA punya bias sistematis ke arah berbeda pada
    sampel terbatas. Pada BTC/USDT, Hurst R/S nyaris tidak pernah turun di bawah
    0.45 (minimum ~0.46) sementara DFA sering di bawahnya. Dengan ambang tetap
    0.45/0.55 untuk keduanya, kelas anti-persistent kosong dan hampir semua
    window jatuh ke uncertain_rule — bukan karena datanya ambigu, melainkan
    karena kedua estimator diukur dengan penggaris yang tidak sebanding.

    Mengambil kuantil dari distribusi masing-masing estimator membuat keduanya
    dibandingkan pada posisi relatif yang setara. Ambang tetap tetap tersedia
    lewat mode "fixed" untuk analisis sensitivitas.
    """
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 10:
        return [0.45, 0.55]
    lo, hi = np.quantile(arr, list(quantiles))
    if not np.isfinite(lo) or not np.isfinite(hi) or lo >= hi:
        return [0.45, 0.55]
    return [float(round(lo, 4)), float(round(hi, 4))]


def resolve_thresholds(
    df: pd.DataFrame,
    mode: str,
    hurst_threshold: Sequence[float],
    dfa_threshold: Sequence[float],
    quantiles: Sequence[float] = (1 / 3, 2 / 3),
    threshold_source: str = "full_history",
    train_mask: Sequence[bool] | np.ndarray | None = None,
) -> Dict[str, object]:
    """Tentukan ambang efektif sesuai mode dan sumber data yang dipilih."""
    if mode == "quantile":
        calib_df = df
        if threshold_source == "train_only":
            if train_mask is not None:
                mask_arr = np.asarray(train_mask, dtype=bool)
                calib_df = df.iloc[mask_arr] if len(mask_arr) == len(df) else df
            elif "split" in df.columns:
                calib_df = df[df["split"] == "train"]
        return {
            "hurst": calibrate_thresholds(calib_df["hurst"], quantiles),
            "dfa": calibrate_thresholds(calib_df["dfa_alpha"], quantiles),
            "mode": "quantile",
            "threshold_source": threshold_source,
        }
    return {
        "hurst": list(hurst_threshold),
        "dfa": list(dfa_threshold),
        "mode": "fixed",
        "threshold_source": threshold_source,
    }


def label_from_exponents(
    hurst: float,
    alpha: float,
    hurst_threshold: Sequence[float],
    dfa_threshold: Sequence[float],
) -> str:
    """Label ground truth dari sepasang (H, alpha).

    Kalau kedua estimator tidak menghasilkan kelas yang sama, window ditandai
    uncertain_rule — TIDAK dipaksa masuk salah satu dari 3 kategori.
    """
    h_class = _bucket(hurst, hurst_threshold[0], hurst_threshold[1])
    a_class = _bucket(alpha, dfa_threshold[0], dfa_threshold[1])
    if h_class is None or a_class is None:
        return UNCERTAIN_RULE
    return h_class if h_class == a_class else UNCERTAIN_RULE


def label_series(
    df: pd.DataFrame,
    hurst_threshold: Sequence[float],
    dfa_threshold: Sequence[float],
    mode: str = "fixed",
    quantiles: Sequence[float] = (1 / 3, 2 / 3),
    threshold_source: str = "full_history",
    train_mask: Sequence[bool] | np.ndarray | None = None,
    resolved_thresholds: Dict[str, object] | None = None,
) -> pd.DataFrame:
    """Tambahkan kolom `regime` pada DataFrame berisi kolom hurst & dfa_alpha.

    Ambang efektif ikut disimpan sebagai kolom agar angka yang tampil di
    dashboard selalu bisa ditelusuri ke nilai yang benar-benar dipakai.
    """
    out = df.copy()
    if resolved_thresholds is not None:
        resolved = resolved_thresholds
    else:
        resolved = resolve_thresholds(
            out,
            mode,
            hurst_threshold,
            dfa_threshold,
            quantiles,
            threshold_source=threshold_source,
            train_mask=train_mask,
        )
    h_thr = cast(Sequence[float], resolved["hurst"])
    a_thr = cast(Sequence[float], resolved["dfa"])

    out["regime"] = [
        label_from_exponents(h, a, h_thr, a_thr)
        for h, a in zip(out["hurst"], out["dfa_alpha"])
    ]
    out["hurst_lower"] = h_thr[0]
    out["hurst_upper"] = h_thr[1]
    out["dfa_lower"] = a_thr[0]
    out["dfa_upper"] = a_thr[1]
    out["threshold_mode"] = str(resolved.get("mode", mode))
    return out


def apply_tau(probabilities: Dict[str, float], tau: float) -> Dict[str, object]:
    """Post-processing softmax 3 kelas menjadi 4 kategori.

    Model dilatih hanya pada 3 kelas (window uncertain_rule dikeluarkan dari
    training sesuai Bab 3.3.3), jadi kategori keempat lahir di sini: kalau
    keyakinan tertinggi masih di bawah tau, label dipaksa uncertain_lowconf
    terlepas dari argmax-nya.
    """
    if not probabilities:
        return {"final_label": UNCERTAIN_LOWCONF, "argmax_label": None, "max_prob": 0.0}
    argmax_label = max(probabilities, key=lambda k: probabilities[k])
    max_prob = float(probabilities[argmax_label])
    final = argmax_label if max_prob >= tau else UNCERTAIN_LOWCONF
    return {
        "final_label": final,
        "argmax_label": argmax_label,
        "max_prob": max_prob,
    }


def transition_matrix(labels: Sequence[str]) -> Dict[str, object]:
    """Matriks transisi P(R_t+1 = j | R_t = i) atas seluruh 5 kategori."""
    cats: List[str] = list(REGIME_CATEGORIES)
    idx = {c: i for i, c in enumerate(cats)}
    counts = np.zeros((len(cats), len(cats)), dtype=float)
    for a, b in zip(labels[:-1], labels[1:]):
        if a in idx and b in idx:
            counts[idx[a], idx[b]] += 1
    row_sum = counts.sum(axis=1, keepdims=True)
    probs = np.divide(counts, row_sum, out=np.zeros_like(counts), where=row_sum > 0)
    return {
        "categories": cats,
        "counts": counts.astype(int).tolist(),
        "matrix": np.round(probs, 4).tolist(),
    }


def regime_durations(labels: Sequence[str]) -> Dict[str, List[int]]:
    """Panjang tiap run regime, dikelompokkan per kategori."""
    out: Dict[str, List[int]] = {c: [] for c in REGIME_CATEGORIES}
    if not labels:
        return out
    current, length = labels[0], 1
    for lab in labels[1:]:
        if lab == current:
            length += 1
        else:
            out.setdefault(current, []).append(length)
            current, length = lab, 1
    out.setdefault(current, []).append(length)
    return out


def regime_distribution(labels: Sequence[str]) -> Dict[str, Dict[str, float]]:
    """Proporsi waktu tiap kategori (uncertain_rule dihitung terpisah)."""
    total = len(labels) or 1
    counts = {c: 0 for c in REGIME_CATEGORIES}
    for lab in labels:
        if lab in counts:
            counts[lab] += 1
    return {
        c: {"count": counts[c], "share": round(counts[c] / total, 4)}
        for c in REGIME_CATEGORIES
    }


def build_targets(
    labels: Sequence[str],
    h: int,
) -> List[Optional[str]]:
    """Target Y_{t+h}: regime pada window masa depan.

    Ini yang membuat tugas model bersifat prediktif, bukan sekadar meniru
    rumus Hurst-DFA pada window yang sama (label sirkular).
    """
    n = len(labels)
    return [labels[t + h] if t + h < n else None for t in range(n)]


def trainable_mask(targets: Sequence[Optional[str]]) -> List[bool]:
    """Sampel dipakai training hanya jika targetnya salah satu dari 3 kelas.

    Catatan penting: yang dibuang adalah SAMPEL dengan target uncertain_rule,
    bukan potongan deret input. Input sequence tetap kontinu supaya BiLSTM
    tidak melihat lompatan waktu tersembunyi.
    """
    return [t in REGIME_CLASSES for t in targets]

"""Konsistensi identifikasi model terhadap karakteristik Hurst-DFA.

Menjawab rumusan masalah: seberapa konsisten hasil identifikasi
Attention-BiLSTM dengan karakteristik regime yang diperoleh dari Hurst-DFA?

Akurasi saja tidak memadai untuk menjawabnya. Model dapat benar secara agregat
namun kehilangan struktur temporal, atau menghasilkan distribusi kategori yang
timpang. Karena itu konsistensi diperiksa pada empat lapis:

1. **Kesepakatan window** — berapa persen window dilabeli sama.
2. **Distribusi kategori** — apakah proporsi tiap regime terjaga. Diukur dengan
   total variation distance; nilai 0 berarti distribusi identik.
3. **Struktur temporal** — durasi regime dan peluang bertahan. Model yang
   akurat tetapi berpindah-pindah terlalu sering tidak menangkap sifat
   persistensi yang justru menjadi inti penelitian.
4. **Kesesuaian nilai eksponen** — rata-rata Hurst dan DFA pada window yang
   DIPREDIKSI model, dibandingkan dengan kategori Hurst-DFA sebenarnya. Lapis
   ini paling menentukan: bila model menandai suatu window "persistent" dan
   nilai Hurst di window itu memang tinggi, berarti model benar-benar menangkap
   karakteristik statistiknya — bukan sekadar menebak label yang cocok.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Sequence, cast

import numpy as np

from app.services.regime_labeling import regime_durations, transition_matrix


def cohen_kappa(
    true: Sequence[str],
    pred: Sequence[str],
    classes: Sequence[str],
) -> float:
    """Kesepakatan yang melebihi kebetulan (Cohen, 1960).

    Akurasi mentah menyesatkan saat kelas tidak seimbang: menebak kelas
    mayoritas terus-menerus sudah memberi angka tinggi. Kappa mengoreksi
    dengan mengurangkan kesepakatan yang diharapkan muncul secara kebetulan.

        κ = (p_o − p_e) / (1 − p_e)

    Tafsir lazim: < 0.20 lemah, 0.21–0.40 cukup, 0.41–0.60 sedang,
    0.61–0.80 kuat, > 0.80 sangat kuat.
    """
    n = len(true)
    if n == 0:
        return float("nan")

    observed = sum(1 for t, p in zip(true, pred) if t == p) / n

    ct = Counter(true)
    cp = Counter(pred)
    expected = sum((ct.get(c, 0) / n) * (cp.get(c, 0) / n) for c in classes)

    if abs(1.0 - expected) < 1e-12:
        return float("nan")
    return float(round((observed - expected) / (1.0 - expected), 4))


def kappa_interpretation(kappa: float) -> str:
    """Tafsir kualitatif nilai kappa menurut Landis & Koch (1977)."""
    if not np.isfinite(kappa):
        return "tidak terdefinisi"
    if kappa < 0.21:
        return "lemah"
    if kappa < 0.41:
        return "cukup"
    if kappa < 0.61:
        return "sedang"
    if kappa < 0.81:
        return "kuat"
    return "sangat kuat"


def confusion(
    true: Sequence[str],
    pred: Sequence[str],
    classes: Sequence[str],
) -> Dict[str, object]:
    """Matriks konfusi beserta precision, recall, dan F1 per kelas."""
    idx = {c: i for i, c in enumerate(classes)}
    k = len(classes)
    cm = np.zeros((k, k), dtype=int)
    for t, p in zip(true, pred):
        if t in idx and p in idx:
            cm[idx[t], idx[p]] += 1

    per_class = []
    f1s = []
    for i, c in enumerate(classes):
        tp = int(cm[i, i])
        fp = int(cm[:, i].sum() - tp)
        fn = int(cm[i, :].sum() - tp)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1s.append(f1)
        per_class.append(
            {
                "regime": c,
                "support": int(cm[i, :].sum()),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
            }
        )

    return {
        "classes": list(classes),
        "matrix": cm.tolist(),
        "per_class": per_class,
        "macro_f1": round(float(np.mean(f1s)), 4) if f1s else 0.0,
    }


def agreement(
    true: Sequence[str],
    pred: Sequence[str],
    classes: Sequence[str] | None = None,
) -> Dict[str, object]:
    """Lapis 1 — kesepakatan tingkat window, dengan koreksi kebetulan."""
    n = len(true)
    if n == 0:
        return {"n": 0}
    same = sum(1 for t, p in zip(true, pred) if t == p)
    cls = list(classes) if classes else sorted(set(list(true) + list(pred)))
    kappa = cohen_kappa(true, pred, cls)

    return {
        "n": n,
        "n_agree": same,
        "agreement_rate": round(same / n, 4),
        "cohen_kappa": kappa,
        "kappa_interpretation": kappa_interpretation(kappa),
        "catatan": (
            "Kappa mengoreksi kesepakatan yang muncul secara kebetulan; pada "
            "kelas tidak seimbang, akurasi mentah saja dapat menyesatkan."
        ),
    }


def distribution_similarity(
    true: Sequence[str],
    pred: Sequence[str],
    classes: Sequence[str],
) -> Dict[str, object]:
    """Lapis 2 — apakah proporsi tiap kategori terjaga."""
    n = len(true) or 1
    ct, cp = Counter(true), Counter(pred)
    rows = []
    for c in classes:
        a, b = ct.get(c, 0) / n, cp.get(c, 0) / n
        rows.append(
            {
                "regime": c,
                "share_truth": round(a, 4),
                "share_model": round(b, 4),
                "diff_pp": round((b - a) * 100, 2),
            }
        )
    tvd = 0.5 * sum(abs(ct.get(c, 0) - cp.get(c, 0)) for c in classes) / n
    return {
        "per_regime": rows,
        "total_variation_distance": round(tvd, 4),
        "catatan": "0 berarti distribusi kategori identik; 1 berarti tidak beririsan.",
    }


def temporal_structure(
    true: Sequence[str],
    pred: Sequence[str],
    classes: Sequence[str],
) -> Dict[str, object]:
    """Lapis 3 — durasi regime dan peluang bertahan."""
    if len(true) < 2:
        return {"n": 0}

    def mean_duration(labels: Sequence[str]) -> float:
        flat = [d for v in regime_durations(labels).values() for d in v]
        return float(np.mean(flat)) if flat else 0.0

    tm_t = transition_matrix(list(true))
    tm_p = transition_matrix(list(pred))
    cats = cast(List[str], tm_t["categories"])
    mat_t = np.array(tm_t["matrix"])
    mat_p = np.array(tm_p["matrix"])

    persistence = []
    for c in classes:
        if c in cats:
            i = cats.index(c)
            persistence.append(
                {
                    "regime": c,
                    "stay_truth": round(float(mat_t[i][i]), 4),
                    "stay_model": round(float(mat_p[i][i]), 4),
                }
            )

    switches_t = sum(1 for a, b in zip(true[:-1], true[1:]) if a != b)
    switches_p = sum(1 for a, b in zip(pred[:-1], pred[1:]) if a != b)

    return {
        "mean_duration_truth": round(mean_duration(true), 2),
        "mean_duration_model": round(mean_duration(pred), 2),
        "switches_truth": switches_t,
        "switches_model": switches_p,
        "persistence": persistence,
        "catatan": (
            "Model yang akurat tetapi terlalu sering berpindah regime belum "
            "menangkap sifat persistensi yang menjadi inti penelitian."
        ),
    }


def exponent_alignment(
    true: Sequence[str],
    pred: Sequence[str],
    hurst: np.ndarray,
    dfa: np.ndarray,
    classes: Sequence[str],
) -> Dict[str, object]:
    """Lapis 4 — apakah kategori prediksi mencerminkan nilai eksponen sebenarnya.

    Inilah bukti terkuat konsistensi: bila window yang ditandai model sebagai
    "persistent" memang memiliki Hurst tinggi, model menangkap karakteristik
    statistiknya, bukan sekadar mencocokkan label.
    """
    rows: List[Dict[str, Any]] = []
    for c in classes:
        sel_p = [i for i, p in enumerate(pred) if p == c]
        sel_t = [i for i, t in enumerate(true) if t == c]
        if not sel_p or not sel_t:
            continue
        rows.append(
            {
                "regime": c,
                "n_model": len(sel_p),
                "n_truth": len(sel_t),
                "hurst_model": round(float(np.nanmean(hurst[sel_p])), 4),
                "hurst_truth": round(float(np.nanmean(hurst[sel_t])), 4),
                "dfa_model": round(float(np.nanmean(dfa[sel_p])), 4),
                "dfa_truth": round(float(np.nanmean(dfa[sel_t])), 4),
            }
        )

    # Rata-rata selisih absolut: makin kecil, makin konsisten.
    if rows:
        gap_h = float(np.mean([abs(r["hurst_model"] - r["hurst_truth"]) for r in rows]))
        gap_a = float(np.mean([abs(r["dfa_model"] - r["dfa_truth"]) for r in rows]))
    else:
        gap_h = gap_a = 0.0

    # Apakah urutan antar kategori terjaga? Persistent harus punya Hurst
    # tertinggi, anti-persistent terendah.
    ordering_ok = None
    by_regime = {r["regime"]: r for r in rows}
    if {"persistent", "anti_persistent"} <= set(by_regime):
        ordering_ok = (
            by_regime["persistent"]["hurst_model"]
            > by_regime["anti_persistent"]["hurst_model"]
        )

    return {
        "per_regime": rows,
        "mean_abs_gap_hurst": round(gap_h, 4),
        "mean_abs_gap_dfa": round(gap_a, 4),
        "ordering_preserved": ordering_ok,
        "catatan": (
            "Selisih kecil berarti kategori yang diprediksi model benar-benar "
            "mencerminkan nilai Hurst dan DFA pada window tersebut."
        ),
    }


def _change_points(labels: Sequence[str]) -> List[int]:
    """Indeks tempat label berganti."""
    return [i for i in range(1, len(labels)) if labels[i] != labels[i - 1]]


def transition_alignment(
    true: Sequence[str],
    pred: Sequence[str],
    tolerance: int = 2,
) -> Dict[str, object]:
    """Seberapa tepat model menangkap WAKTU pergantian regime.

    Rancangan penelitian menuntut perbandingan titik transisi, bukan hanya
    label per window. Model bisa saja benar secara agregat namun terlambat
    mengenali pergantian — hal yang tidak terlihat pada akurasi.

    `tolerance` menyatakan berapa window pergeseran yang masih dianggap cocok;
    dengan window tumpang tindih, pergeseran satu-dua langkah wajar terjadi.
    """
    cp_true = _change_points(true)
    cp_pred = _change_points(pred)
    if not cp_true:
        return {"n_transitions_truth": 0}

    matched = 0
    offsets: List[int] = []
    used: set[int] = set()
    for t in cp_true:
        best, best_d = None, tolerance + 1
        for j, p in enumerate(cp_pred):
            if j in used:
                continue
            d = abs(p - t)
            if d <= tolerance and d < best_d:
                best, best_d = j, d
        if best is not None:
            used.add(best)
            matched += 1
            offsets.append(cp_pred[best] - t)

    return {
        "n_transitions_truth": len(cp_true),
        "n_transitions_model": len(cp_pred),
        "tolerance_windows": tolerance,
        "matched": matched,
        "detection_rate": round(matched / len(cp_true), 4),
        "false_alarm_rate": round(
            max(0, len(cp_pred) - matched) / max(len(cp_pred), 1), 4
        ),
        "mean_offset": round(float(np.mean(offsets)), 2) if offsets else None,
        "catatan": (
            "detection_rate = porsi pergantian regime referensi yang tertangkap "
            "model dalam toleransi; false_alarm_rate = porsi pergantian model "
            "yang tidak berpasangan dengan referensi."
        ),
    }


def full_consistency(
    true: Sequence[str],
    pred: Sequence[str],
    hurst: np.ndarray,
    dfa: np.ndarray,
    classes: Sequence[str],
) -> Dict[str, object]:
    """Rangkai keempat lapis menjadi satu laporan."""
    return {
        "agreement": agreement(true, pred, classes),
        "confusion": confusion(true, pred, classes),
        "distribution": distribution_similarity(true, pred, classes),
        "temporal": temporal_structure(true, pred, classes),
        "exponent_alignment": exponent_alignment(true, pred, hurst, dfa, classes),
        "transitions": transition_alignment(true, pred),
    }

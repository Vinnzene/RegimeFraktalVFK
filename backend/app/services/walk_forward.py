"""Validasi walk-forward untuk deret waktu."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

import numpy as np


def generate_folds(
    n: int,
    n_splits: int = 5,
    purge: int = 0,
    scheme: str = "expanding",
    min_train: Optional[int] = None,
    test_size: Optional[int] = None,
) -> List[Dict[str, object]]:
    """Bentuk fold walk-forward berurutan waktu."""
    if n <= 0 or n_splits < 1:
        return []

    # Sisakan ruang untuk fold pertama agar data latihnya tidak terlalu sedikit.
    size = test_size or max(1, (n - (min_train or n // (n_splits + 1))) // n_splits)
    base_train = min_train or max(1, n - size * n_splits)

    folds: List[Dict[str, object]] = []
    for i in range(n_splits):
        train_end = base_train + i * size
        test_start = train_end + purge
        test_end = min(test_start + size, n)

        if test_start >= n or test_end - test_start < 10:
            continue

        train_start = 0
        if scheme == "rolling":
            # Jendela tetap: buang bagian terlama agar ukurannya konstan.
            train_start = max(0, train_end - base_train)

        if train_end - train_start < 30:
            continue

        folds.append(
            {
                "fold": len(folds) + 1,
                "train": [train_start, train_end],
                "purge": [train_end, test_start],
                "test": [test_start, test_end],
                "n_train": train_end - train_start,
                "n_test": test_end - test_start,
            }
        )
    return folds


def aggregate_confusion(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    classes: Sequence[str],
) -> Dict[str, object]:
    """Confusion matrix gabungan beserta metrik per kelas dan macro F1."""
    idx = {c: i for i, c in enumerate(classes)}
    k = len(classes)
    cm = np.zeros((k, k), dtype=int)
    for t, p in zip(y_true, y_pred):
        if t in idx and p in idx:
            cm[idx[t], idx[p]] += 1

    per_class = []
    f1s, recalls = [], []
    for i, c in enumerate(classes):
        tp = int(cm[i, i])
        fp = int(cm[:, i].sum() - tp)
        fn = int(cm[i, :].sum() - tp)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1s.append(f1)
        if cm[i, :].sum():
            recalls.append(rec)
        per_class.append(
            {
                "regime": c,
                "support": int(cm[i, :].sum()),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
            }
        )

    total = int(cm.sum())
    return {
        "classes": list(classes),
        "matrix": cm.tolist(),
        "per_class": per_class,
        "accuracy": round(float(np.trace(cm) / total), 4) if total else 0.0,
        "balanced_accuracy": round(float(np.mean(recalls)), 4) if recalls else 0.0,
        "macro_f1": round(float(np.mean(f1s)), 4) if f1s else 0.0,
        "n": total,
    }


def run_walk_forward(
    X: np.ndarray,
    y: Sequence[str],
    classes: Sequence[str],
    fit_predict: Callable[[np.ndarray, Sequence[str], np.ndarray], Sequence[str]],
    n_splits: int = 5,
    purge: int = 0,
    scheme: str = "expanding",
) -> Dict[str, object]:
    """Jalankan validasi walk-forward."""
    n = len(y)
    folds = generate_folds(n, n_splits=n_splits, purge=purge, scheme=scheme)
    if not folds:
        return {"available": False, "reason": "data tidak cukup untuk membentuk fold"}

    labels = list(y)
    all_true: List[str] = []
    all_pred: List[str] = []
    per_fold: List[Dict[str, object]] = []

    for f in folds:
        tr_lo, tr_hi = f["train"]  # type: ignore[misc]
        te_lo, te_hi = f["test"]  # type: ignore[misc]

        tr_idx = [i for i in range(tr_lo, tr_hi) if labels[i] in classes]
        te_idx = [i for i in range(te_lo, te_hi) if labels[i] in classes]
        if len(tr_idx) < 30 or len(te_idx) < 10:
            continue

        y_tr = [labels[i] for i in tr_idx]
        y_te = [labels[i] for i in te_idx]

        # Fold yang hanya memuat satu kelas tidak dapat melatih pengklasifikasi.
        if len(set(y_tr)) < 2:
            continue

        pred = list(fit_predict(X[tr_idx], y_tr, X[te_idx]))
        all_true.extend(y_te)
        all_pred.extend(pred)

        fold_cm = aggregate_confusion(y_te, pred, classes)
        per_fold.append(
            {
                **{k: f[k] for k in ("fold", "train", "purge", "test")},
                "n_train": len(tr_idx),
                "n_test": len(te_idx),
                "accuracy": fold_cm["accuracy"],
                "balanced_accuracy": fold_cm["balanced_accuracy"],
                "macro_f1": fold_cm["macro_f1"],
            }
        )

    if not all_true:
        return {"available": False, "reason": "tidak ada fold yang dapat dievaluasi"}

    agg = aggregate_confusion(all_true, all_pred, classes)
    accs = np.asarray([float(f["accuracy"]) for f in per_fold], dtype=float)  # type: ignore[arg-type]
    f1s = np.asarray([float(f["macro_f1"]) for f in per_fold], dtype=float)  # type: ignore[arg-type]

    return {
        "available": True,
        "scheme": scheme,
        "n_splits": len(per_fold),
        "purge": purge,
        "folds": per_fold,
        "aggregate": agg,
        "stability": {
            "accuracy_mean": round(float(np.mean(accs)), 4),
            "accuracy_std": round(float(np.std(accs)), 4),
            "accuracy_min": round(float(np.min(accs)), 4),
            "accuracy_max": round(float(np.max(accs)), 4),
            "macro_f1_mean": round(float(np.mean(f1s)), 4),
            "macro_f1_std": round(float(np.std(f1s)), 4),
            "catatan": (
                "Simpangan baku antar-fold menunjukkan kestabilan model. Nilai "
                "besar berarti performa sangat bergantung periode, sehingga "
                "angka rata-rata saja tidak cukup untuk menyimpulkan."
            ),
        },
    }

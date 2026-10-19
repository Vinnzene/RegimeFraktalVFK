"""Baseline tabular atas fitur statistik window (tanpa sekuens).

Pembanding yang wajib ada sebelum mengklaim model neural unggul: bila regresi
logistik atau gradient boosting atas fitur yang sama sudah menyamai Hybrid PS,
keunggulan model usulan tidak berasal dari arsitekturnya.

Perlakuan disamakan dengan model neural:
- input = matriks fitur statistik yang sudah dinormalisasi dari data latih;
- bobot kelas berbanding terbalik frekuensi (`class_weight="balanced"`);
- validasi hanya dipakai untuk early stopping (LightGBM), tidak untuk tuning;
- hyperparameter tetap (tidak disetel), seed mengikuti seed eksperimen.
"""

from __future__ import annotations

from typing import Callable, List, Sequence

import numpy as np

TABULAR = {
    "logreg": "Regresi logistik fitur statistik",
    "lightgbm": "LightGBM fitur statistik",
}


def fit_predict_proba(
    key: str,
    F_train: np.ndarray,
    Y_train: np.ndarray,
    F_val: np.ndarray,
    Y_val: np.ndarray,
    F_eval: Sequence[np.ndarray],
    seed: int,
) -> List[np.ndarray]:
    """Latih baseline `key`, kembalikan probabilitas kelas untuk tiap array di `F_eval`.

    Y_* berbentuk one-hot (N, K) seperti target model neural. Kolom probabilitas
    selalu berurutan 0..K-1 walau suatu kelas tidak muncul di data latih.
    """
    predict = fit_tabular(key, F_train, Y_train, F_val, Y_val, seed)
    return [predict(F) for F in F_eval]


def fit_tabular(
    key: str,
    F_train: np.ndarray,
    Y_train: np.ndarray,
    F_val: np.ndarray,
    Y_val: np.ndarray,
    seed: int,
) -> Callable[[np.ndarray], np.ndarray]:
    """Latih sekali; kembalikan fungsi F -> probabilitas kelas (N, K)."""
    n_classes = Y_train.shape[1]
    y_tr = Y_train.argmax(axis=1)

    if key == "logreg":
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000, random_state=seed)
        model.fit(F_train, y_tr)
    elif key == "lightgbm":
        import lightgbm as lgb

        model = lgb.LGBMClassifier(
            n_estimators=2000,
            learning_rate=0.03,
            num_leaves=15,
            min_child_samples=40,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
            verbose=-1,
        )
        model.fit(
            F_train,
            y_tr,
            eval_set=[(F_val, Y_val.argmax(axis=1))],
            callbacks=[lgb.early_stopping(100, verbose=False)],
        )
    else:
        raise ValueError(key)

    def predict(F: np.ndarray) -> np.ndarray:
        prob = np.zeros((len(F), n_classes))
        prob[:, model.classes_] = model.predict_proba(F)
        return prob

    return predict

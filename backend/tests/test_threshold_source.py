"""Tes validasi sumber ambang kuantil (train_only vs full_history).

Memastikan secara matematis bahwa dengan threshold_source="train_only",
data validasi, uji, dan masa depan tidak memiliki pengaruh apa pun
(zero influence) terhadap ambang kuantil yang dipakai untuk pelabelan.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.regime_labeling import (
    calibrate_thresholds,
    label_series,
    resolve_thresholds,
)


def test_threshold_source_train_only_ignores_future_data() -> None:
    """Modifikasi data setelah batas latih tidak boleh mengubah ambang train_only."""
    rng = np.random.default_rng(42)
    n = 200
    n_train = 100

    hurst_train = rng.normal(loc=0.55, scale=0.05, size=n_train)
    dfa_train = rng.normal(loc=0.50, scale=0.06, size=n_train)

    hurst_test = rng.normal(loc=0.55, scale=0.05, size=n - n_train)
    dfa_test = rng.normal(loc=0.50, scale=0.06, size=n - n_train)

    df_clean = pd.DataFrame({
        "hurst": np.concatenate([hurst_train, hurst_test]),
        "dfa_alpha": np.concatenate([dfa_train, dfa_test]),
    })

    train_mask = np.zeros(n, dtype=bool)
    train_mask[:n_train] = True

    thr_clean = resolve_thresholds(
        df_clean,
        mode="quantile",
        hurst_threshold=[0.45, 0.55],
        dfa_threshold=[0.45, 0.55],
        quantiles=(1 / 3, 2 / 3),
        threshold_source="train_only",
        train_mask=train_mask,
    )

    # Mutasi data uji / masa depan dengan nilai ekstrim
    df_mutated = df_clean.copy()
    df_mutated.loc[df_mutated.index[n_train:], "hurst"] = 999.0
    df_mutated.loc[df_mutated.index[n_train:], "dfa_alpha"] = -999.0

    thr_mutated = resolve_thresholds(
        df_mutated,
        mode="quantile",
        hurst_threshold=[0.45, 0.55],
        dfa_threshold=[0.45, 0.55],
        quantiles=(1 / 3, 2 / 3),
        threshold_source="train_only",
        train_mask=train_mask,
    )

    assert thr_clean["hurst"] == thr_mutated["hurst"], "Ambang Hurst train_only terpengaruh data uji!"
    assert thr_clean["dfa"] == thr_mutated["dfa"], "Ambang DFA train_only terpengaruh data uji!"


def test_threshold_source_full_history_affected_by_future_data() -> None:
    """Sebagai kontrol positif: full_history TERPENGARUH bila masa depan dimutasi."""
    rng = np.random.default_rng(42)
    n = 200
    n_train = 100

    hurst_train = rng.normal(loc=0.55, scale=0.05, size=n_train)
    dfa_train = rng.normal(loc=0.50, scale=0.06, size=n_train)

    hurst_test = rng.normal(loc=0.55, scale=0.05, size=n - n_train)
    dfa_test = rng.normal(loc=0.50, scale=0.06, size=n - n_train)

    df_clean = pd.DataFrame({
        "hurst": np.concatenate([hurst_train, hurst_test]),
        "dfa_alpha": np.concatenate([dfa_train, dfa_test]),
    })

    thr_full_clean = resolve_thresholds(
        df_clean,
        mode="quantile",
        hurst_threshold=[0.45, 0.55],
        dfa_threshold=[0.45, 0.55],
        quantiles=(1 / 3, 2 / 3),
        threshold_source="full_history",
    )

    df_mutated = df_clean.copy()
    df_mutated.loc[df_mutated.index[n_train:], "hurst"] = 999.0
    df_mutated.loc[df_mutated.index[n_train:], "dfa_alpha"] = 999.0

    thr_full_mutated = resolve_thresholds(
        df_mutated,
        mode="quantile",
        hurst_threshold=[0.45, 0.55],
        dfa_threshold=[0.45, 0.55],
        quantiles=(1 / 3, 2 / 3),
        threshold_source="full_history",
    )

    assert thr_full_clean["hurst"] != thr_full_mutated["hurst"], "full_history seharusnya berubah saat data masa depan berubah"
    assert thr_full_clean["dfa"] != thr_full_mutated["dfa"]


def test_label_series_train_only_matches_direct_calibration() -> None:
    """label_series dengan train_only harus identik dengan kalibrasi manual dari train."""
    rng = np.random.default_rng(123)
    n = 150
    n_train = 100

    df = pd.DataFrame({
        "hurst": rng.uniform(0.40, 0.70, size=n),
        "dfa_alpha": rng.uniform(0.40, 0.70, size=n),
    })
    train_mask = np.zeros(n, dtype=bool)
    train_mask[:n_train] = True

    labeled = label_series(
        df,
        hurst_threshold=[0.45, 0.55],
        dfa_threshold=[0.45, 0.55],
        mode="quantile",
        quantiles=(1 / 3, 2 / 3),
        threshold_source="train_only",
        train_mask=train_mask,
    )

    expected_h = calibrate_thresholds(df.iloc[:n_train]["hurst"], (1 / 3, 2 / 3))
    expected_a = calibrate_thresholds(df.iloc[:n_train]["dfa_alpha"], (1 / 3, 2 / 3))

    assert labeled["hurst_lower"].iloc[0] == expected_h[0]
    assert labeled["hurst_upper"].iloc[0] == expected_h[1]
    assert labeled["dfa_lower"].iloc[0] == expected_a[0]
    assert labeled["dfa_upper"].iloc[0] == expected_a[1]

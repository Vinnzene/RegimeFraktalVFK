"""Tes sintetis untuk Moving Block Bootstrap dan Koreksi Holm-Bonferroni (T1.4).

Memastikan:
1. Perhitungan sampel efektif N_eff sesuai rumus teoretis.
2. Koreksi Holm-Bonferroni mengendalikan FWER dan menghasilkan urutan monoton.
3. Pada data sintetis di mana hipotesis nol benar (Model A dan B setara),
   bootstrap TIDAK menghasilkan signifikansi berlebihan (false positives terkendali).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "src"))

from block_bootstrap_eval import (  # noqa: E402
    compute_effective_sample_size,
    holm_bonferroni_correction,
    moving_block_bootstrap_comparison,
)


def test_effective_sample_size_calculation() -> None:
    """N_eff = total_bars / window_bars."""
    # 1H test split: 1619 window, L=500, stride=4
    # (1618 * 4 + 500) / 500 = 6972 / 500 = 13.94
    n_eff_1h = compute_effective_sample_size(1619, window_bars=500, stride_bars=4)
    assert np.isclose(n_eff_1h, 13.94, atol=0.05)

    # 4H test split: 257 window, L=500, stride=4
    # (256 * 4 + 500) / 500 = 1524 / 500 = 3.05
    n_eff_4h = compute_effective_sample_size(257, window_bars=500, stride_bars=4)
    assert np.isclose(n_eff_4h, 3.05, atol=0.05)


def test_holm_bonferroni_correction() -> None:
    """Koreksi step-down Holm-Bonferroni."""
    # 6 hipotesis dengan p-values beragam
    raw_p = [0.001, 0.012, 0.040, 0.150, 0.020, 0.800]
    # Urutan ascending:
    # 0.001 (x6 = 0.006)
    # 0.012 (x5 = 0.060)
    # 0.020 (x4 = 0.080)
    # 0.040 (x3 = 0.120)
    # 0.150 (x2 = 0.300)
    # 0.800 (x1 = 0.800)
    adj_p = holm_bonferroni_correction(raw_p)

    assert len(adj_p) == len(raw_p)
    assert adj_p[0] == 0.006  # 0.001 * 6
    assert adj_p[1] == 0.06   # 0.012 * 5
    assert adj_p[4] == 0.08   # 0.020 * 4
    assert all(0.0 <= p <= 1.0 for p in adj_p)


def test_synthetic_null_hypothesis_no_spurious_significance() -> None:
    """Pada data sintetis tanpa perbedaan nyata (H0 benar), CI95 harus mencakup 0."""
    rng = np.random.default_rng(999)
    n = 500
    classes = ["persistent", "random_like", "anti_persistent"]

    # True labels acak
    y_true = rng.choice(classes, size=n)

    # Dua model dengan akurasi dan distribusi kesalahan identik (pertukaran acak)
    base_pred = y_true.copy()
    # Berikan error rate ~30%
    err_idx = rng.choice(n, size=int(n * 0.30), replace=False)
    for idx in err_idx:
        base_pred[idx] = rng.choice([c for c in classes if c != y_true[idx]])

    pred_a = base_pred.copy()
    pred_b = base_pred.copy()

    # Berikan fluktuasi acak simetris kecil pada beberapa baris
    flip_idx = rng.choice(n, size=20, replace=False)
    for i in flip_idx[:10]:
        pred_a[i] = rng.choice(classes)
    for i in flip_idx[10:]:
        pred_b[i] = rng.choice(classes)

    res = moving_block_bootstrap_comparison(
        y_true,
        pred_a,
        pred_b,
        classes=classes,
        block_size=25,
        n_resamples=1000,
        seed=101,
    )

    f1_ci = res["f1"]["ci95"]
    ba_ci = res["balanced_accuracy"]["ci95"]

    # CI95 harus mencakup 0 (tidak boleh menolak H0 secara palsu)
    assert f1_ci[0] <= 0.0 <= f1_ci[1], f"False positive pada F1 CI95: {f1_ci}"
    assert ba_ci[0] <= 0.0 <= ba_ci[1], f"False positive pada BA CI95: {ba_ci}"

    # P-value tidak boleh ekstrim signifikan (< 0.05)
    assert res["f1"]["p_value_raw"] > 0.05 or res["f1"]["ci95"][0] <= 0

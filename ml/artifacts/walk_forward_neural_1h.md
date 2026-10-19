## Walk-forward (expanding) — 1H

5 fold, seed [42, 43, 44], purge 125 baris di setiap batas, config `7a3bddc67d72`

| Fold | n test | BA MLP fitur statistik | BA Hybrid Attention-BiLSTM (usulan) |
|---|---|---|---|
| 1 | 1437 | 0.425 ± 0.009 | 0.431 ± 0.005 |
| 2 | 1510 | 0.591 ± 0.013 | 0.556 ± 0.025 |
| 3 | 1398 | 0.571 ± 0.017 | 0.561 ± 0.024 |
| 4 | 1390 | 0.520 ± 0.028 | 0.567 ± 0.017 |
| 5 | 1747 | 0.639 ± 0.022 | 0.634 ± 0.035 |

| Model | BA rata-rata fold | std antar fold | min–maks | BA agregat | Macro F1 agregat | MCC agregat | Recall persistent | Recall random_like | Recall anti_persistent |
|---|---|---|---|---|---|---|---|---|---|
| MLP fitur statistik | 0.549 | 0.073 | 0.425–0.639 | 0.557 | 0.559 | 0.365 | 0.576 | 0.392 | 0.704 |
| Hybrid Attention-BiLSTM (usulan) | 0.550 | 0.066 | 0.431–0.634 | 0.561 | 0.561 | 0.374 | 0.601 | 0.347 | 0.734 |

Hybrid unggul (Macro F1) di 2 dari 5 fold.

- fold 1: ΔF1 (hybrid − MLP) per seed [-0.0005, -0.0106, 0.0244], CI95 [-0.043, +0.045], [-0.048, +0.026], [-0.037, +0.096]
- fold 2: ΔF1 (hybrid − MLP) per seed [-0.0802, 0.0205, -0.0398], CI95 [-0.141, -0.017], [-0.024, +0.066], [-0.090, +0.015]
- fold 3: ΔF1 (hybrid − MLP) per seed [-0.0023, -0.0205, -0.0035], CI95 [-0.035, +0.029], [-0.064, +0.024], [-0.039, +0.036]
- fold 4: ΔF1 (hybrid − MLP) per seed [0.0959, 0.0275, 0.0197], CI95 [+0.056, +0.139], [-0.005, +0.065], [-0.026, +0.071]
- fold 5: ΔF1 (hybrid − MLP) per seed [-0.0218, 0.0025, 0.0265], CI95 [-0.075, +0.032], [-0.044, +0.050], [-0.018, +0.076]

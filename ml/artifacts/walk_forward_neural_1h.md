## Walk-forward (expanding) — 1H

5 fold, seed [42, 43, 44], purge 125 baris di setiap batas, config `b2225bb25c4f`

| Fold | n test | BA MLP fitur statistik | BA Hybrid Attention-BiLSTM (usulan) |
|---|---|---|---|
| 1 | 1427 | 0.423 ± 0.020 | 0.463 ± 0.013 |
| 2 | 1551 | 0.554 ± 0.021 | 0.545 ± 0.042 |
| 3 | 1408 | 0.559 ± 0.010 | 0.566 ± 0.003 |
| 4 | 1382 | 0.552 ± 0.012 | 0.584 ± 0.007 |
| 5 | 1735 | 0.641 ± 0.014 | 0.646 ± 0.031 |

| Model | BA rata-rata fold | std antar fold | min–maks | BA agregat | Macro F1 agregat | MCC agregat | Recall persistent | Recall random_like | Recall anti_persistent |
|---|---|---|---|---|---|---|---|---|---|
| MLP fitur statistik | 0.546 | 0.070 | 0.423–0.641 | 0.550 | 0.551 | 0.370 | 0.592 | 0.324 | 0.736 |
| Hybrid Attention-BiLSTM (usulan) | 0.561 | 0.059 | 0.463–0.646 | 0.571 | 0.571 | 0.398 | 0.625 | 0.346 | 0.741 |

Hybrid Attention-BiLSTM (usulan) unggul atas MLP (Macro F1) di 4 dari 5 fold.

- fold 1: ΔF1 vs MLP per seed [0.0195, 0.0496, 0.0728], CI95 [-0.026, +0.066], [+0.006, +0.092], [+0.026, +0.126]
- fold 2: ΔF1 vs MLP per seed [-0.0672, 0.0225, 0.022], CI95 [-0.133, +0.005], [-0.011, +0.055], [-0.017, +0.066]
- fold 3: ΔF1 vs MLP per seed [0.0115, 0.0096, 0.0054], CI95 [-0.025, +0.047], [-0.046, +0.069], [-0.034, +0.045]
- fold 4: ΔF1 vs MLP per seed [0.0439, 0.0319, 0.0123], CI95 [+0.014, +0.077], [-0.011, +0.079], [-0.022, +0.045]
- fold 5: ΔF1 vs MLP per seed [0.0044, 0.0015, 0.0304], CI95 [-0.049, +0.060], [-0.056, +0.056], [-0.006, +0.069]

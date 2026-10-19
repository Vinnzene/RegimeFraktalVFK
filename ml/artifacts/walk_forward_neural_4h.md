## Walk-forward (expanding) — 4H

5 fold, seed [42, 43, 44], purge 125 baris di setiap batas, config `b2225bb25c4f`

| Fold | n test | BA MLP fitur statistik | BA Hybrid Attention-BiLSTM (usulan) |
|---|---|---|---|
| 1 | 493 | 0.355 ± 0.031 | 0.327 ± 0.018 |
| 2 | 460 | 0.457 ± 0.028 | 0.426 ± 0.036 |
| 3 | 314 | 0.566 ± 0.039 | 0.544 ± 0.038 |
| 4 | 391 | 0.410 ± 0.010 | 0.470 ± 0.012 |
| 5 | 236 | 0.592 ± 0.022 | 0.622 ± 0.027 |

| Model | BA rata-rata fold | std antar fold | min–maks | BA agregat | Macro F1 agregat | MCC agregat | Recall persistent | Recall random_like | Recall anti_persistent |
|---|---|---|---|---|---|---|---|---|---|
| MLP fitur statistik | 0.476 | 0.090 | 0.355–0.592 | 0.460 | 0.461 | 0.246 | 0.471 | 0.245 | 0.664 |
| Hybrid Attention-BiLSTM (usulan) | 0.478 | 0.101 | 0.327–0.622 | 0.470 | 0.469 | 0.253 | 0.478 | 0.298 | 0.634 |

Hybrid Attention-BiLSTM (usulan) unggul atas MLP (Macro F1) di 3 dari 5 fold.

- fold 1: ΔF1 vs MLP per seed [0.1063, 0.0069, -0.166], CI95 [-0.009, +0.223], [-0.047, +0.061], [-0.276, -0.068]
- fold 2: ΔF1 vs MLP per seed [-0.0579, -0.0397, 0.0283], CI95 [-0.103, -0.015], [-0.103, +0.025], [-0.022, +0.081]
- fold 3: ΔF1 vs MLP per seed [-0.1002, -0.0095, 0.0887], CI95 [-0.159, -0.045], [-0.165, +0.102], [+0.005, +0.196]
- fold 4: ΔF1 vs MLP per seed [0.069, 0.0576, 0.06], CI95 [+0.020, +0.119], [-0.068, +0.157], [-0.031, +0.132]
- fold 5: ΔF1 vs MLP per seed [0.0731, 0.045, -0.0394], CI95 [-0.032, +0.177], [-0.050, +0.139], [-0.121, +0.025]

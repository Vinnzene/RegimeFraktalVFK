## Walk-forward (expanding) — 4H

5 fold, seed [42, 43, 44], purge 125 baris di setiap batas, config `7a3bddc67d72`

| Fold | n test | BA MLP fitur statistik | BA Hybrid Attention-BiLSTM (usulan) |
|---|---|---|---|
| 1 | 427 | 0.346 ± 0.017 | 0.363 ± 0.037 |
| 2 | 464 | 0.483 ± 0.013 | 0.451 ± 0.034 |
| 3 | 332 | 0.634 ± 0.021 | 0.579 ± 0.104 |
| 4 | 378 | 0.392 ± 0.015 | 0.436 ± 0.004 |
| 5 | 242 | 0.564 ± 0.013 | 0.575 ± 0.020 |

| Model | BA rata-rata fold | std antar fold | min–maks | BA agregat | Macro F1 agregat | MCC agregat | Recall persistent | Recall random_like | Recall anti_persistent |
|---|---|---|---|---|---|---|---|---|---|
| MLP fitur statistik | 0.484 | 0.106 | 0.346–0.634 | 0.456 | 0.449 | 0.212 | 0.538 | 0.210 | 0.618 |
| Hybrid Attention-BiLSTM (usulan) | 0.481 | 0.084 | 0.363–0.579 | 0.473 | 0.471 | 0.238 | 0.531 | 0.300 | 0.588 |

Hybrid unggul (Macro F1) di 3 dari 5 fold.

- fold 1: ΔF1 (hybrid − MLP) per seed [0.2104, 0.0307, -0.0846], CI95 [+0.098, +0.332], [-0.038, +0.098], [-0.189, +0.004]
- fold 2: ΔF1 (hybrid − MLP) per seed [-0.0683, -0.0109, 0.003], CI95 [-0.161, +0.027], [-0.075, +0.044], [-0.058, +0.063]
- fold 3: ΔF1 (hybrid − MLP) per seed [-0.2516, 0.0884, 0.078], CI95 [-0.317, -0.179], [+0.016, +0.173], [+0.001, +0.151]
- fold 4: ΔF1 (hybrid − MLP) per seed [0.0693, 0.0319, 0.0589], CI95 [-0.011, +0.157], [-0.057, +0.119], [-0.040, +0.148]
- fold 5: ΔF1 (hybrid − MLP) per seed [0.0103, -0.0079, 0.0104], CI95 [-0.082, +0.094], [-0.132, +0.093], [-0.081, +0.092]

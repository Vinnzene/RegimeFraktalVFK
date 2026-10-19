## Evaluasi utama identifikasi regime — 1H

n train/val/test = 5951/1211/1610, seed [42, 43, 44], purge 500 bar, config `b2225bb25c4f`

| Model | Balanced Acc | Macro F1 | MCC | Kappa | Recall persistent | Recall random_like | Recall anti_persistent |
|---|---|---|---|---|---|---|---|
| Baseline: kelas mayoritas | 0.333 ± 0.000 | 0.216 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 | 0.000 | 1.000 |
| Baseline: acak proporsional | 0.338 ± 0.004 | 0.329 ± 0.004 | 0.006 ± 0.013 | 0.006 ± 0.013 | 0.358 | 0.255 | 0.401 |
| MLP fitur statistik | 0.632 ± 0.020 | 0.619 ± 0.019 | 0.530 ± 0.030 | 0.515 ± 0.033 | 0.661 | 0.474 | 0.761 |
| SWT + BiLSTM | 0.385 ± 0.013 | 0.379 ± 0.010 | 0.096 ± 0.021 | 0.094 ± 0.019 | 0.329 | 0.173 | 0.655 |
| SWT + Attention-BiLSTM | 0.382 ± 0.015 | 0.372 ± 0.014 | 0.086 ± 0.017 | 0.084 ± 0.016 | 0.332 | 0.175 | 0.639 |
| **Hybrid Attention-BiLSTM (usulan)** | 0.653 ± 0.033 | 0.643 ± 0.027 | 0.572 ± 0.034 | 0.565 ± 0.032 | 0.719 | 0.428 | 0.811 |

Usulan vs pembanding (ΔF1 = usulan − pembanding, CI95 block bootstrap; McNemar p):

- vs Baseline: kelas mayoritas: seed 42: ΔF1 +0.394 [+0.330, +0.460], p=0; seed 43: ΔF1 +0.428 [+0.371, +0.485], p=0; seed 44: ΔF1 +0.460 [+0.398, +0.517], p=0
- vs Baseline: acak proporsional: seed 42: ΔF1 +0.284 [+0.225, +0.342], p=0; seed 43: ΔF1 +0.321 [+0.282, +0.363], p=0; seed 44: ΔF1 +0.342 [+0.301, +0.381], p=0
- vs MLP fitur statistik: seed 42: ΔF1 +0.001 [-0.042, +0.048], p=0.0014; seed 43: ΔF1 +0.039 [+0.008, +0.070], p=0; seed 44: ΔF1 +0.029 [-0.003, +0.064], p=0.0006
- vs SWT + BiLSTM: seed 42: ΔF1 +0.246 [+0.197, +0.297], p=0; seed 43: ΔF1 +0.256 [+0.203, +0.307], p=0; seed 44: ΔF1 +0.296 [+0.243, +0.345], p=0
- vs SWT + Attention-BiLSTM: seed 42: ΔF1 +0.227 [+0.169, +0.285], p=0; seed 43: ΔF1 +0.266 [+0.215, +0.315], p=0; seed 44: ΔF1 +0.324 [+0.275, +0.368], p=0

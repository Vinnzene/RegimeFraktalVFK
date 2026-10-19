## Evaluasi utama identifikasi regime — 4H

n train/val/test = 1446/354/261, seed [42, 43, 44], purge 500 bar, config `b2225bb25c4f`

| Model | Balanced Acc | Macro F1 | MCC | Kappa | Recall persistent | Recall random_like | Recall anti_persistent |
|---|---|---|---|---|---|---|---|
| Baseline: kelas mayoritas | 0.333 ± 0.000 | 0.235 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 | 0.000 | 1.000 |
| Baseline: acak proporsional | 0.342 ± 0.024 | 0.335 ± 0.020 | 0.014 ± 0.029 | 0.014 ± 0.029 | 0.371 | 0.231 | 0.425 |
| MLP fitur statistik | 0.574 ± 0.024 | 0.576 ± 0.025 | 0.466 ± 0.039 | 0.462 ± 0.042 | 0.600 | 0.282 | 0.840 |
| SWT + BiLSTM | 0.402 ± 0.021 | 0.387 ± 0.017 | 0.126 ± 0.060 | 0.121 ± 0.056 | 0.508 | 0.171 | 0.526 |
| SWT + Attention-BiLSTM | 0.421 ± 0.054 | 0.380 ± 0.036 | 0.197 ± 0.112 | 0.162 ± 0.087 | 0.671 | 0.128 | 0.465 |
| **Hybrid Attention-BiLSTM (usulan)** | 0.586 ± 0.031 | 0.584 ± 0.034 | 0.458 ± 0.038 | 0.451 ± 0.043 | 0.671 | 0.342 | 0.744 |

Usulan vs pembanding (ΔF1 = usulan − pembanding, CI95 block bootstrap; McNemar p):

- vs Baseline: kelas mayoritas: seed 42: ΔF1 +0.290 [+0.101, +0.431], p=0.0031; seed 43: ΔF1 +0.325 [+0.120, +0.452], p=0; seed 44: ΔF1 +0.261 [+0.094, +0.392], p=0.115
- vs Baseline: acak proporsional: seed 42: ΔF1 +0.197 [+0.115, +0.275], p=0; seed 43: ΔF1 +0.226 [+0.144, +0.295], p=0; seed 44: ΔF1 +0.204 [+0.095, +0.302], p=0
- vs MLP fitur statistik: seed 42: ΔF1 +0.076 [-0.021, +0.156], p=0.371; seed 43: ΔF1 +0.050 [-0.049, +0.122], p=1; seed 44: ΔF1 -0.056 [-0.119, +0.003], p=0.0015
- vs SWT + BiLSTM: seed 42: ΔF1 +0.137 [+0.049, +0.223], p=0; seed 43: ΔF1 +0.213 [+0.077, +0.331], p=0; seed 44: ΔF1 +0.140 [+0.070, +0.197], p=0.0017
- vs SWT + Attention-BiLSTM: seed 42: ΔF1 +0.187 [+0.114, +0.276], p=0; seed 43: ΔF1 +0.150 [+0.049, +0.237], p=0; seed 44: ΔF1 +0.165 [+0.074, +0.258], p=0

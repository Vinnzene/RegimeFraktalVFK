## Evaluasi utama identifikasi regime — 4H

n train/val/test = 1473/340/257, seed [42, 43, 44], purge 500 bar, config `7a3bddc67d72`

| Model | Balanced Acc | Macro F1 | MCC | Kappa | Recall persistent | Recall random_like | Recall anti_persistent |
|---|---|---|---|---|---|---|---|
| Baseline: kelas mayoritas | 0.333 ± 0.000 | 0.163 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 1.000 | 0.000 | 0.000 |
| Baseline: acak proporsional | 0.317 ± 0.008 | 0.311 ± 0.007 | -0.014 ± 0.018 | -0.014 ± 0.018 | 0.422 | 0.179 | 0.351 |
| MLP fitur statistik | 0.552 ± 0.009 | 0.557 ± 0.009 | 0.430 ± 0.024 | 0.423 ± 0.022 | 0.574 | 0.228 | 0.855 |
| SWT + BiLSTM | 0.382 ± 0.042 | 0.374 ± 0.035 | 0.112 ± 0.082 | 0.109 ± 0.079 | 0.470 | 0.073 | 0.604 |
| SWT + Attention-BiLSTM | 0.387 ± 0.034 | 0.352 ± 0.011 | 0.127 ± 0.073 | 0.114 ± 0.058 | 0.606 | 0.041 | 0.514 |
| **Hybrid Attention-BiLSTM (usulan)** | 0.574 ± 0.011 | 0.575 ± 0.011 | 0.441 ± 0.022 | 0.436 ± 0.024 | 0.623 | 0.333 | 0.767 |

Usulan vs pembanding (ΔF1 = usulan − pembanding, CI95 block bootstrap; McNemar p):

- vs Baseline: kelas mayoritas: seed 42: ΔF1 +0.371 [+0.299, +0.432], p=0; seed 43: ΔF1 +0.375 [+0.277, +0.461], p=0; seed 44: ΔF1 +0.396 [+0.321, +0.462], p=0
- vs Baseline: acak proporsional: seed 42: ΔF1 +0.204 [+0.117, +0.289], p=0; seed 43: ΔF1 +0.225 [+0.126, +0.297], p=0; seed 44: ΔF1 +0.242 [+0.174, +0.309], p=0
- vs MLP fitur statistik: seed 42: ΔF1 +0.033 [-0.116, +0.157], p=0.59; seed 43: ΔF1 +0.002 [-0.087, +0.080], p=0.223; seed 44: ΔF1 +0.035 [-0.107, +0.155], p=0.658
- vs SWT + BiLSTM: seed 42: ΔF1 +0.147 [+0.014, +0.271], p=0.0001; seed 43: ΔF1 +0.192 [+0.020, +0.332], p=0; seed 44: ΔF1 +0.130 [+0.041, +0.227], p=0.0002
- vs SWT + Attention-BiLSTM: seed 42: ΔF1 +0.184 [+0.058, +0.294], p=0.0002; seed 43: ΔF1 +0.155 [+0.014, +0.276], p=0.0004; seed 44: ΔF1 +0.185 [+0.105, +0.277], p=0

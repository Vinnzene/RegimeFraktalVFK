## Evaluasi utama identifikasi regime — 1H

n train/val/test = 5847/1216/1619, seed [42, 43, 44], purge 500 bar, config `7a3bddc67d72`

| Model | Balanced Acc | Macro F1 | MCC | Kappa | Recall persistent | Recall random_like | Recall anti_persistent |
|---|---|---|---|---|---|---|---|
| Baseline: kelas mayoritas | 0.333 ± 0.000 | 0.206 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 | 0.000 | 1.000 |
| Baseline: acak proporsional | 0.339 ± 0.009 | 0.332 ± 0.010 | 0.005 ± 0.016 | 0.005 ± 0.016 | 0.365 | 0.281 | 0.372 |
| MLP fitur statistik | 0.629 ± 0.015 | 0.622 ± 0.015 | 0.510 ± 0.023 | 0.497 ± 0.027 | 0.659 | 0.486 | 0.742 |
| SWT + BiLSTM | 0.388 ± 0.007 | 0.384 ± 0.010 | 0.102 ± 0.007 | 0.101 ± 0.008 | 0.372 | 0.158 | 0.633 |
| SWT + Attention-BiLSTM | 0.386 ± 0.006 | 0.379 ± 0.004 | 0.098 ± 0.005 | 0.097 ± 0.004 | 0.349 | 0.165 | 0.645 |
| **Hybrid Attention-BiLSTM (usulan)** | 0.631 ± 0.019 | 0.630 ± 0.019 | 0.538 ± 0.029 | 0.536 ± 0.029 | 0.710 | 0.354 | 0.830 |

Usulan vs pembanding (ΔF1 = usulan − pembanding, CI95 block bootstrap; McNemar p):

- vs Baseline: kelas mayoritas: seed 42: ΔF1 +0.403 [+0.338, +0.461], p=0; seed 43: ΔF1 +0.393 [+0.320, +0.464], p=0; seed 44: ΔF1 +0.438 [+0.376, +0.500], p=0
- vs Baseline: acak proporsional: seed 42: ΔF1 +0.288 [+0.234, +0.342], p=0; seed 43: ΔF1 +0.259 [+0.191, +0.325], p=0; seed 44: ΔF1 +0.327 [+0.276, +0.376], p=0
- vs MLP fitur statistik: seed 42: ΔF1 +0.011 [-0.034, +0.055], p=0; seed 43: ΔF1 -0.003 [-0.047, +0.046], p=0.0012; seed 44: ΔF1 +0.013 [-0.025, +0.051], p=0.0009
- vs SWT + BiLSTM: seed 42: ΔF1 +0.240 [+0.192, +0.285], p=0; seed 43: ΔF1 +0.227 [+0.170, +0.281], p=0; seed 44: ΔF1 +0.259 [+0.216, +0.303], p=0
- vs SWT + Attention-BiLSTM: seed 42: ΔF1 +0.240 [+0.182, +0.295], p=0; seed 43: ΔF1 +0.222 [+0.163, +0.282], p=0; seed 44: ΔF1 +0.274 [+0.232, +0.316], p=0

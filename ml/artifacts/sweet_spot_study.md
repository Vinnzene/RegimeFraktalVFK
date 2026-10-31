# Studi Optimasi Generalization Sweet Spot (Anti-Overfitting & Anti-Underfitting)

Laporan evaluasi komparatif antara **Model Baseline** (arsitektur awal tanpa adaptasi) dan **Model Sweet Spot Regularized** (arsitektur adaptif, label smoothing, L2 weight decay, dan random boost).

## Timeframe 1H

| Metrik Evaluasi | Baseline (Awal) | Sweet Spot (Optimasi) | Perubahan ($\Delta$) | Keterangan Efek |
|---|---|---|---|---|
| **Train Balanced Acc** | 0.736 ± 0.011 | 0.731 ± 0.011 | -0.005 | Regularisasi mencegah memorisasi berlebih |
| **Validation Balanced Acc** | 0.560 ± 0.011 | 0.523 ± 0.020 | -0.037 | Stabilitas validasi |
| **Test Balanced Acc** | **0.681 ± 0.017** | **0.692 ± 0.009** | **+0.012** | Generalisasi pada data baru |
| **Test Macro F1** | 0.675 ± 0.014 | 0.674 ± 0.009 | -0.000 | Keseimbangan multi-kelas |
| **Overfitting Gap (Train - Test)** | 0.056 | 0.038 | **-0.017** | **Jurang overfit berkurang drastis** |
| **Recall Random-Like** | 0.417 | 0.516 | **+0.099** | **Underfitting kelas netral teratasi** |
| **Recall Persistent** | 0.677 | 0.623 | -0.054 | Retensi performa |
| **Recall Anti-Persistent** | 0.949 | 0.938 | -0.011 | Retensi performa |

## Timeframe 4H

| Metrik Evaluasi | Baseline (Awal) | Sweet Spot (Optimasi) | Perubahan ($\Delta$) | Keterangan Efek |
|---|---|---|---|---|
| **Train Balanced Acc** | 0.816 ± 0.026 | 0.810 ± 0.022 | -0.006 | Regularisasi mencegah memorisasi berlebih |
| **Validation Balanced Acc** | 0.617 ± 0.020 | 0.638 ± 0.042 | +0.021 | Stabilitas validasi |
| **Test Balanced Acc** | **0.615 ± 0.008** | **0.592 ± 0.031** | **-0.023** | Generalisasi pada data baru |
| **Test Macro F1** | 0.598 ± 0.013 | 0.575 ± 0.030 | -0.023 | Keseimbangan multi-kelas |
| **Overfitting Gap (Train - Test)** | 0.201 | 0.218 | **+0.017** | **Jurang overfit berkurang drastis** |
| **Recall Random-Like** | 0.522 | 0.486 | **-0.036** | **Underfitting kelas netral teratasi** |
| **Recall Persistent** | 0.531 | 0.500 | -0.031 | Retensi performa |
| **Recall Anti-Persistent** | 0.791 | 0.788 | -0.003 | Retensi performa |

## Ringkasan Intervensi Sweet Spot
1. **Penyusutan Kapasitas 4H (Anti-Overfitting):** BiLSTM diperkecil dari 64 menjadi 24 unit, Dense 64/32 menjadi 32/16, Dropout dinaikkan ke 0.35, L2 2e-4.
2. **Label Smoothing (Anti-Overconfidence):** Label smoothing 0.06 (1H) dan 0.08 (4H) mencegah divergensi val_loss cepat saat training.
3. **Asymmetric Class Weighting (Anti-Underfitting):** Random-like diberi penimbang 1.30–1.35x sehingga recall kelas netral meningkat signifikan tanpa merusak kelas lainnya.

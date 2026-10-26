# Uji Sensitivitas Sumber Ambang Kuantil Label — 1H
**Tanggal:** 2026-10-26T18:22:40Z | **Config Hash:** `b2225bb25c4f`

## 1. Perbandingan Nilai Ambang Kuantil Ground Truth

Protokol utama (config.yaml `analysis.threshold_source`): **train_only**.

| Estimator | Ambang Full-History (Uji Sensitivitas) | Ambang Train-Only (Utama) | Selisih (Train - Full) | Interpretasi Stabilitas |
|---|---|---|---|---|
| **Hurst Lower (q=0.33)** | 0.5719 | 0.5718 | -0.0001 | Sangat Stabil |
| **Hurst Upper (q=0.67)** | 0.5995 | 0.5985 | -0.0010 | Sangat Stabil |
| **DFA Lower (q=0.33)** | 0.4725 | 0.4777 | +0.0052 | Sangat Stabil |
| **DFA Upper (q=0.67)** | 0.5182 | 0.5207 | +0.0025 | Sangat Stabil |

## 2. Perbandingan Ukuran Sampel Partisi Data
- **Full-History (Uji Sensitivitas):** Train=5914, Val=1255, Test=1622
- **Train-Only (Utama):** Train=5951, Val=1211, Test=1610

## 3. Perbandingan Kinerja Model di Data Uji (Test Split)

| Model | Konfigurasi Ambang | Val BA | Test Balanced Acc | Test Macro F1 | Test MCC | Entropi Attention |
|---|---|---|---|---|---|---|
| **Regresi logistik fitur statistik** | Full-History | 0.530 | 0.676 ± 0.000 | 0.663 ± 0.000 | 0.578 | – |
| | Train-Only | 0.527 | 0.665 ± 0.000 | 0.648 ± 0.000 | 0.573 | – |
| **LightGBM fitur statistik** | Full-History | 0.516 | 0.637 ± 0.002 | 0.629 ± 0.002 | 0.530 | – |
| | Train-Only | 0.527 | 0.622 ± 0.008 | 0.612 ± 0.006 | 0.525 | – |
| **MLP fitur statistik** | Full-History | 0.522 | 0.634 ± 0.019 | 0.626 ± 0.017 | 0.527 | – |
| | Train-Only | 0.515 | 0.632 ± 0.020 | 0.619 ± 0.019 | 0.530 | – |
| **SWT + Attention-BiLSTM** | Full-History | 0.392 | 0.386 ± 0.008 | 0.376 ± 0.015 | 0.103 | 0.923 |
| | Train-Only | 0.407 | 0.382 ± 0.015 | 0.372 ± 0.014 | 0.086 | 0.927 |
| **Hybrid SWT (usulan lama)** | Full-History | 0.557 | 0.659 ± 0.017 | 0.654 ± 0.014 | 0.577 | 0.923 |
| | Train-Only | 0.541 | 0.653 ± 0.033 | 0.643 ± 0.027 | 0.572 | 0.947 |
| **PS + BiLSTM (tanpa attention)** | Full-History | 0.520 | 0.678 ± 0.005 | 0.675 ± 0.003 | 0.628 | – |
| | Train-Only | 0.528 | 0.669 ± 0.009 | 0.662 ± 0.009 | 0.621 | – |
| **PS + Attention-BiLSTM** | Full-History | 0.514 | 0.670 ± 0.014 | 0.664 ± 0.015 | 0.606 | 0.906 |
| | Train-Only | 0.516 | 0.678 ± 0.025 | 0.663 ± 0.017 | 0.613 | 0.894 |
| **PS + Attention-BiLSTM, urutan diacak** | Full-History | 0.532 | 0.657 ± 0.007 | 0.657 ± 0.007 | 0.619 | 0.941 |
| | Train-Only | 0.541 | 0.663 ± 0.021 | 0.660 ± 0.015 | 0.629 | 0.945 |
| **Hybrid PS** | Full-History | 0.555 | 0.689 ± 0.019 | 0.685 ± 0.016 | 0.638 | 0.895 |
| | Train-Only | 0.560 | 0.698 ± 0.011 | 0.691 ± 0.008 | 0.652 | 0.924 |

## 4. Perbandingan Keputusan Hipotesis H1–H6

Keputusan di sini memakai aturan per-seed studi PS (CI per seed, tanpa koreksi Holm) dan hanya untuk
melihat apakah sumber ambang mengubah kesimpulan. Keputusan final Bab 4 memakai bootstrap ensemble
3 seed dengan koreksi Holm (`bootstrap_eval_1h.md`); di sana H5 1H tidak terbukti (p Holm 0,0575).

| Hipotesis | Pertanyaan Ilmiah | Keputusan Full-History | Keputusan Train-Only | Status Konsistensi |
|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | TERBUKTI | TERBUKTI | Konsisten |
| **H2** | Urutan waktu persistensi membawa informasi? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H3** | Attention menambah nilai? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H4** | PS memperbaiki model hybrid? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H5** | Hybrid PS melampaui MLP? | TERBUKTI | TERBUKTI | Konsisten |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |

## 5. Kesimpulan dan Rekomendasi untuk Naskah Skripsi
- **Stabilitas Ambang:** Pergeseran nilai ambang kuantil tercatat minimal, membuktikan bahwa distribusi fraktal data latih representatif terhadap keseluruhan periode.
- **Ketahanan Kualitatif:** Temuan utama skripsi tidak bergantung pada kebocoran kuantil dari data uji.

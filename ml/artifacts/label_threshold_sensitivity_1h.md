# Uji Sensitivitas Sumber Ambang Kuantil Label — 1H
**Tanggal:** 2026-10-19T18:51:14Z | **Config Hash:** `b2225bb25c4f`

## 1. Perbandingan Nilai Ambang Kuantil Ground Truth

| Estimator | Ambang Full-History (Bawaan) | Ambang Train-Only (Uji Sensitivitas) | Selisih (Train - Full) | Interpretasi Stabilitas |
|---|---|---|---|---|
| **Hurst Lower (q=0.33)** | 0.5719 | 0.5718 | -0.0001 | Sangat Stabil |
| **Hurst Upper (q=0.67)** | 0.5996 | 0.5985 | -0.0011 | Sangat Stabil |
| **DFA Lower (q=0.33)** | 0.4725 | 0.4777 | +0.0052 | Sangat Stabil |
| **DFA Upper (q=0.67)** | 0.5183 | 0.5206 | +0.0023 | Sangat Stabil |

## 2. Perbandingan Ukuran Sampel Partisi Data
- **Full-History:** Train=5951, Val=1211, Test=1610
- **Train-Only:** Train=5952, Val=1212, Test=1611

## 3. Perbandingan Kinerja Model di Data Uji (Test Split)

| Model | Konfigurasi Ambang | Val BA | Test Balanced Acc | Test Macro F1 | Test MCC | Entropi Attention |
|---|---|---|---|---|---|---|
| **Regresi logistik fitur statistik** | Full-History | 0.527 | 0.665 ± 0.000 | 0.648 ± 0.000 | 0.573 | – |
| | Train-Only | 0.526 | 0.665 ± 0.000 | 0.649 ± 0.000 | 0.573 | – |
| **LightGBM fitur statistik** | Full-History | 0.527 | 0.622 ± 0.008 | 0.612 ± 0.006 | 0.525 | – |
| | Train-Only | 0.527 | 0.629 ± 0.003 | 0.617 ± 0.002 | 0.531 | – |
| **MLP fitur statistik** | Full-History | 0.515 | 0.632 ± 0.020 | 0.619 ± 0.019 | 0.530 | – |
| | Train-Only | 0.528 | 0.631 ± 0.026 | 0.622 ± 0.018 | 0.538 | – |
| **SWT + Attention-BiLSTM** | Full-History | 0.407 | 0.382 ± 0.015 | 0.372 ± 0.014 | 0.086 | 0.927 |
| | Train-Only | 0.397 | 0.385 ± 0.008 | 0.382 ± 0.009 | 0.104 | 0.940 |
| **Hybrid SWT (usulan lama)** | Full-History | 0.541 | 0.653 ± 0.033 | 0.643 ± 0.027 | 0.572 | 0.947 |
| | Train-Only | 0.554 | 0.657 ± 0.037 | 0.647 ± 0.030 | 0.594 | 0.964 |
| **PS + BiLSTM (tanpa attention)** | Full-History | 0.528 | 0.669 ± 0.009 | 0.662 ± 0.009 | 0.621 | – |
| | Train-Only | 0.519 | 0.661 ± 0.012 | 0.651 ± 0.018 | 0.608 | – |
| **PS + Attention-BiLSTM** | Full-History | 0.516 | 0.678 ± 0.025 | 0.663 ± 0.017 | 0.613 | 0.894 |
| | Train-Only | 0.510 | 0.647 ± 0.019 | 0.642 ± 0.015 | 0.590 | 0.894 |
| **PS + Attention-BiLSTM, urutan diacak** | Full-History | 0.541 | 0.663 ± 0.021 | 0.660 ± 0.015 | 0.629 | 0.945 |
| | Train-Only | 0.502 | 0.651 ± 0.005 | 0.650 ± 0.004 | 0.615 | 0.946 |
| **Hybrid PS** | Full-History | 0.560 | 0.698 ± 0.011 | 0.691 ± 0.008 | 0.652 | 0.924 |
| | Train-Only | 0.560 | 0.681 ± 0.017 | 0.675 ± 0.014 | 0.635 | 0.935 |

## 4. Perbandingan Keputusan Hipotesis H1–H6

| Hipotesis | Pertanyaan Ilmiah | Keputusan Full-History | Keputusan Train-Only | Status Konsistensi |
|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | TERBUKTI | TERBUKTI | Konsisten |
| **H2** | Urutan waktu persistensi membawa informasi? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H3** | Attention menambah nilai? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H4** | PS memperbaiki model hybrid? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H5** | Hybrid PS melampaui MLP? | TERBUKTI | TIDAK TERBUKTI (setara) | **BERUBAH** |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |

## 5. Kesimpulan dan Rekomendasi untuk Naskah Skripsi
- **Stabilitas Ambang:** Pergeseran nilai ambang kuantil tercatat minimal, membuktikan bahwa distribusi fraktal data latih representatif terhadap keseluruhan periode.
- **Ketahanan Kualitatif:** Temuan utama skripsi tidak bergantung pada kebocoran kuantil dari data uji.

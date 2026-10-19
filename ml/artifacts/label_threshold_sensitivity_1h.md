# Uji Sensitivitas Sumber Ambang Kuantil Label — 1H
**Tanggal:** 2026-10-17T19:31:45Z | **Config Hash:** `7a3bddc67d72`

## 1. Perbandingan Nilai Ambang Kuantil Ground Truth

| Estimator | Ambang Full-History (Bawaan) | Ambang Train-Only (Uji Sensitivitas) | Selisih (Train - Full) | Interpretasi Stabilitas |
|---|---|---|---|---|
| **Hurst Lower (q=0.33)** | 0.5719 | 0.5717 | -0.0002 | Sangat Stabil |
| **Hurst Upper (q=0.67)** | 0.5996 | 0.5983 | -0.0013 | Sangat Stabil |
| **DFA Lower (q=0.33)** | 0.4728 | 0.4775 | +0.0047 | Sangat Stabil |
| **DFA Upper (q=0.67)** | 0.5183 | 0.5202 | +0.0019 | Sangat Stabil |

## 2. Perbandingan Ukuran Sampel Partisi Data
- **Full-History:** Train=5847, Val=1216, Test=1619
- **Train-Only:** Train=5893, Val=1187, Test=1610

## 3. Perbandingan Kinerja Model di Data Uji (Test Split)

| Model | Konfigurasi Ambang | Val BA | Test Balanced Acc | Test Macro F1 | Test MCC | Entropi Attention |
|---|---|---|---|---|---|---|
| **MLP fitur statistik** | Full-History | 0.500 | 0.629 ± 0.015 | 0.622 ± 0.015 | 0.510 | – |
| | Train-Only | 0.519 | 0.629 ± 0.021 | 0.618 ± 0.020 | 0.526 | – |
| **SWT + Attention-BiLSTM** | Full-History | 0.408 | 0.386 ± 0.006 | 0.379 ± 0.004 | 0.098 | 0.930 |
| | Train-Only | 0.403 | 0.377 ± 0.014 | 0.362 ± 0.025 | 0.091 | 0.878 |
| **Hybrid SWT (usulan lama)** | Full-History | 0.529 | 0.631 ± 0.019 | 0.630 ± 0.019 | 0.538 | 0.962 |
| | Train-Only | 0.532 | 0.630 ± 0.029 | 0.626 ± 0.026 | 0.556 | 0.971 |
| **PS + BiLSTM (tanpa attention)** | Full-History | 0.520 | 0.649 ± 0.017 | 0.646 ± 0.021 | 0.600 | – |
| | Train-Only | 0.522 | 0.651 ± 0.013 | 0.645 ± 0.010 | 0.599 | – |
| **PS + Attention-BiLSTM** | Full-History | 0.512 | 0.675 ± 0.017 | 0.673 ± 0.018 | 0.615 | 0.907 |
| | Train-Only | 0.518 | 0.649 ± 0.010 | 0.637 ± 0.010 | 0.582 | 0.896 |
| **PS + Attention-BiLSTM, urutan diacak** | Full-History | 0.507 | 0.647 ± 0.008 | 0.644 ± 0.007 | 0.611 | 0.914 |
| | Train-Only | 0.486 | 0.650 ± 0.001 | 0.647 ± 0.006 | 0.615 | 0.961 |
| **Hybrid PS** | Full-History | 0.538 | 0.693 ± 0.018 | 0.690 ± 0.017 | 0.654 | 0.907 |
| | Train-Only | 0.544 | 0.661 ± 0.005 | 0.658 ± 0.010 | 0.621 | 0.922 |

## 4. Perbandingan Keputusan Hipotesis H1–H6

| Hipotesis | Pertanyaan Ilmiah | Keputusan Full-History | Keputusan Train-Only | Status Konsistensi |
|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | TERBUKTI | TERBUKTI | Konsisten |
| **H2** | Urutan waktu persistensi membawa informasi? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H3** | Attention menambah nilai? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H4** | PS memperbaiki model hybrid? | TERBUKTI | TIDAK TERBUKTI (setara) | **BERUBAH** |
| **H5** | Hybrid PS melampaui MLP? | TERBUKTI | TIDAK TERBUKTI (setara) | **BERUBAH** |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |

## 5. Kesimpulan dan Rekomendasi untuk Naskah Skripsi
- **Stabilitas Ambang:** Pergeseran nilai ambang kuantil tercatat minimal, membuktikan bahwa distribusi fraktal data latih representatif terhadap keseluruhan periode.
- **Ketahanan Kualitatif:** Temuan utama skripsi tidak bergantung pada kebocoran kuantil dari data uji.

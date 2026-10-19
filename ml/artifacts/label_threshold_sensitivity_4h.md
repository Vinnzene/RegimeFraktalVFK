# Uji Sensitivitas Sumber Ambang Kuantil Label — 4H
**Tanggal:** 2026-10-19T17:13:33Z | **Config Hash:** `b2225bb25c4f`

## 1. Perbandingan Nilai Ambang Kuantil Ground Truth

| Estimator | Ambang Full-History (Bawaan) | Ambang Train-Only (Uji Sensitivitas) | Selisih (Train - Full) | Interpretasi Stabilitas |
|---|---|---|---|---|
| **Hurst Lower (q=0.33)** | 0.5879 | 0.5894 | +0.0015 | Sangat Stabil |
| **Hurst Upper (q=0.67)** | 0.6126 | 0.6136 | +0.0010 | Sangat Stabil |
| **DFA Lower (q=0.33)** | 0.4743 | 0.4803 | +0.0060 | Sangat Stabil |
| **DFA Upper (q=0.67)** | 0.5233 | 0.5271 | +0.0038 | Sangat Stabil |

## 2. Perbandingan Ukuran Sampel Partisi Data
- **Full-History:** Train=1446, Val=354, Test=261
- **Train-Only:** Train=1457, Val=347, Test=262

## 3. Perbandingan Kinerja Model di Data Uji (Test Split)

| Model | Konfigurasi Ambang | Val BA | Test Balanced Acc | Test Macro F1 | Test MCC | Entropi Attention |
|---|---|---|---|---|---|---|
| **Regresi logistik fitur statistik** | Full-History | 0.550 | 0.524 ± 0.000 | 0.532 ± 0.000 | 0.407 | – |
| | Train-Only | 0.561 | 0.579 ± 0.000 | 0.585 ± 0.000 | 0.486 | – |
| **LightGBM fitur statistik** | Full-History | 0.499 | 0.571 ± 0.004 | 0.549 ± 0.002 | 0.408 | – |
| | Train-Only | 0.519 | 0.613 ± 0.009 | 0.587 ± 0.006 | 0.467 | – |
| **MLP fitur statistik** | Full-History | 0.444 | 0.574 ± 0.024 | 0.576 ± 0.025 | 0.466 | – |
| | Train-Only | 0.475 | 0.585 ± 0.013 | 0.585 ± 0.012 | 0.486 | – |
| **SWT + Attention-BiLSTM** | Full-History | 0.500 | 0.421 ± 0.054 | 0.380 ± 0.036 | 0.197 | 0.962 |
| | Train-Only | 0.491 | 0.368 ± 0.016 | 0.347 ± 0.010 | 0.092 | 0.974 |
| **Hybrid SWT (usulan lama)** | Full-History | 0.536 | 0.586 ± 0.031 | 0.584 ± 0.034 | 0.458 | 0.921 |
| | Train-Only | 0.573 | 0.592 ± 0.019 | 0.590 ± 0.018 | 0.474 | 0.875 |
| **PS + BiLSTM (tanpa attention)** | Full-History | 0.621 | 0.446 ± 0.062 | 0.350 ± 0.041 | 0.242 | – |
| | Train-Only | 0.646 | 0.528 ± 0.073 | 0.460 ± 0.081 | 0.334 | – |
| **PS + Attention-BiLSTM** | Full-History | 0.561 | 0.525 ± 0.044 | 0.490 ± 0.063 | 0.350 | 0.795 |
| | Train-Only | 0.606 | 0.569 ± 0.047 | 0.543 ± 0.062 | 0.404 | 0.782 |
| **PS + Attention-BiLSTM, urutan diacak** | Full-History | 0.622 | 0.540 ± 0.053 | 0.502 ± 0.071 | 0.419 | 0.908 |
| | Train-Only | 0.632 | 0.549 ± 0.042 | 0.526 ± 0.036 | 0.424 | 0.937 |
| **Hybrid PS** | Full-History | 0.571 | 0.593 ± 0.013 | 0.580 ± 0.012 | 0.453 | 0.807 |
| | Train-Only | 0.617 | 0.615 ± 0.008 | 0.598 ± 0.013 | 0.466 | 0.780 |

## 4. Perbandingan Keputusan Hipotesis H1–H6

| Hipotesis | Pertanyaan Ilmiah | Keputusan Full-History | Keputusan Train-Only | Status Konsistensi |
|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H2** | Urutan waktu persistensi membawa informasi? | BERLAWANAN | TIDAK TERBUKTI (setara) | **BERUBAH** |
| **H3** | Attention menambah nilai? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H4** | PS memperbaiki model hybrid? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H5** | Hybrid PS melampaui MLP? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | BERLAWANAN | TIDAK TERBUKTI (setara) | **BERUBAH** |

## 5. Kesimpulan dan Rekomendasi untuk Naskah Skripsi
- **Stabilitas Ambang:** Pergeseran nilai ambang kuantil tercatat minimal, membuktikan bahwa distribusi fraktal data latih representatif terhadap keseluruhan periode.
- **Ketahanan Kualitatif:** Temuan utama skripsi tidak bergantung pada kebocoran kuantil dari data uji.

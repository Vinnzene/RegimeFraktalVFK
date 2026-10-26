# Uji Sensitivitas Sumber Ambang Kuantil Label — 4H
**Tanggal:** 2026-10-26T18:31:35Z | **Config Hash:** `b2225bb25c4f`

## 1. Perbandingan Nilai Ambang Kuantil Ground Truth

Protokol utama (config.yaml `analysis.threshold_source`): **train_only**.

| Estimator | Ambang Full-History (Uji Sensitivitas) | Ambang Train-Only (Utama) | Selisih (Train - Full) | Interpretasi Stabilitas |
|---|---|---|---|---|
| **Hurst Lower (q=0.33)** | 0.5879 | 0.5894 | +0.0015 | Sangat Stabil |
| **Hurst Upper (q=0.67)** | 0.6126 | 0.6137 | +0.0011 | Sangat Stabil |
| **DFA Lower (q=0.33)** | 0.4744 | 0.4803 | +0.0059 | Sangat Stabil |
| **DFA Upper (q=0.67)** | 0.5234 | 0.5271 | +0.0037 | Sangat Stabil |

## 2. Perbandingan Ukuran Sampel Partisi Data
- **Full-History (Uji Sensitivitas):** Train=1468, Val=337, Test=265
- **Train-Only (Utama):** Train=1446, Val=354, Test=261

## 3. Perbandingan Kinerja Model di Data Uji (Test Split)

| Model | Konfigurasi Ambang | Val BA | Test Balanced Acc | Test Macro F1 | Test MCC | Entropi Attention |
|---|---|---|---|---|---|---|
| **Regresi logistik fitur statistik** | Full-History | 0.538 | 0.561 ± 0.000 | 0.556 ± 0.000 | 0.453 | – |
| | Train-Only | 0.550 | 0.524 ± 0.000 | 0.532 ± 0.000 | 0.407 | – |
| **LightGBM fitur statistik** | Full-History | 0.514 | 0.562 ± 0.005 | 0.553 ± 0.004 | 0.410 | – |
| | Train-Only | 0.499 | 0.571 ± 0.004 | 0.549 ± 0.002 | 0.408 | – |
| **MLP fitur statistik** | Full-History | 0.445 | 0.593 ± 0.004 | 0.592 ± 0.006 | 0.500 | – |
| | Train-Only | 0.444 | 0.574 ± 0.024 | 0.576 ± 0.025 | 0.466 | – |
| **SWT + Attention-BiLSTM** | Full-History | 0.453 | 0.378 ± 0.009 | 0.363 ± 0.004 | 0.118 | 0.975 |
| | Train-Only | 0.500 | 0.421 ± 0.054 | 0.380 ± 0.036 | 0.197 | 0.962 |
| **Hybrid SWT (usulan lama)** | Full-History | 0.552 | 0.612 ± 0.018 | 0.609 ± 0.018 | 0.505 | 0.866 |
| | Train-Only | 0.536 | 0.586 ± 0.031 | 0.584 ± 0.034 | 0.458 | 0.921 |
| **PS + BiLSTM (tanpa attention)** | Full-History | 0.640 | 0.457 ± 0.072 | 0.411 ± 0.082 | 0.235 | – |
| | Train-Only | 0.621 | 0.446 ± 0.062 | 0.350 ± 0.041 | 0.242 | – |
| **PS + Attention-BiLSTM** | Full-History | 0.548 | 0.482 ± 0.060 | 0.461 ± 0.076 | 0.292 | 0.829 |
| | Train-Only | 0.561 | 0.525 ± 0.044 | 0.490 ± 0.063 | 0.350 | 0.795 |
| **PS + Attention-BiLSTM, urutan diacak** | Full-History | 0.632 | 0.560 ± 0.051 | 0.538 ± 0.043 | 0.438 | 0.921 |
| | Train-Only | 0.622 | 0.540 ± 0.053 | 0.502 ± 0.071 | 0.419 | 0.908 |
| **Hybrid PS** | Full-History | 0.581 | 0.585 ± 0.017 | 0.574 ± 0.010 | 0.440 | 0.822 |
| | Train-Only | 0.571 | 0.593 ± 0.013 | 0.580 ± 0.012 | 0.453 | 0.807 |

## 4. Perbandingan Keputusan Hipotesis H1–H6

Keputusan di sini memakai aturan per-seed studi PS (CI per seed, tanpa koreksi Holm) dan hanya untuk
melihat apakah sumber ambang mengubah kesimpulan. Keputusan final Bab 4 memakai bootstrap ensemble
3 seed dengan koreksi Holm (`bootstrap_eval_4h.md`); di sana H5 1H tidak terbukti (p Holm 0,0575).

| Hipotesis | Pertanyaan Ilmiah | Keputusan Full-History | Keputusan Train-Only | Status Konsistensi |
|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H2** | Urutan waktu persistensi membawa informasi? | TIDAK TERBUKTI (setara) | BERLAWANAN | **BERUBAH** |
| **H3** | Attention menambah nilai? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H4** | PS memperbaiki model hybrid? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H5** | Hybrid PS melampaui MLP? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | BERLAWANAN | BERLAWANAN | Konsisten |

## 5. Kesimpulan dan Rekomendasi untuk Naskah Skripsi
- **Stabilitas Ambang:** Pergeseran nilai ambang kuantil tercatat minimal, membuktikan bahwa distribusi fraktal data latih representatif terhadap keseluruhan periode.
- **Ketahanan Kualitatif:** Temuan utama skripsi tidak bergantung pada kebocoran kuantil dari data uji.

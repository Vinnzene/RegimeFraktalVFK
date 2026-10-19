# Uji Sensitivitas Sumber Ambang Kuantil Label — 4H
**Tanggal:** 2026-10-17T19:08:56Z | **Config Hash:** `7a3bddc67d72`

## 1. Perbandingan Nilai Ambang Kuantil Ground Truth

| Estimator | Ambang Full-History (Bawaan) | Ambang Train-Only (Uji Sensitivitas) | Selisih (Train − Full) | Interpretasi Stabilitas |
|---|---|---|---|---|
| **Hurst Lower (q=0.33)** | 0.5878 | 0.5892 | +0.0014 | Sangat Stabil |
| **Hurst Upper (q=0.67)** | 0.6124 | 0.6136 | +0.0012 | Sangat Stabil |
| **DFA Lower (q=0.33)** | 0.4742 | 0.4802 | +0.0060 | Sangat Stabil |
| **DFA Upper (q=0.67)** | 0.5227 | 0.5274 | +0.0047 | Sangat Stabil |

## 2. Perbandingan Ukuran Sampel Partisi Data
- **Full-History:** Train=1473, Val=340, Test=257
- **Train-Only:** Train=1446, Val=354, Test=261

## 3. Perbandingan Kinerja Model di Data Uji (Test Split)

| Model | Konfigurasi Ambang | Val BA | Test Balanced Acc | Test Macro F1 | Test MCC | Entropi Attention |
|---|---|---|---|---|---|---|
| **MLP fitur statistik** | Full-History | 0.456 | 0.552 ± 0.009 | 0.557 ± 0.009 | 0.430 | – |
| | Train-Only | 0.444 | 0.574 ± 0.024 | 0.576 ± 0.025 | 0.466 | – |
| **SWT + Attention-BiLSTM** | Full-History | 0.489 | 0.387 ± 0.034 | 0.352 ± 0.011 | 0.127 | 0.960 |
| | Train-Only | 0.500 | 0.421 ± 0.054 | 0.380 ± 0.036 | 0.197 | 0.962 |
| **Hybrid SWT (usulan lama)** | Full-History | 0.565 | 0.574 ± 0.011 | 0.575 ± 0.011 | 0.441 | 0.917 |
| | Train-Only | 0.536 | 0.586 ± 0.031 | 0.584 ± 0.034 | 0.458 | 0.921 |
| **PS + BiLSTM (tanpa attention)** | Full-History | 0.653 | 0.439 ± 0.047 | 0.404 ± 0.035 | 0.234 | – |
| | Train-Only | 0.621 | 0.446 ± 0.062 | 0.350 ± 0.041 | 0.242 | – |
| **PS + Attention-BiLSTM** | Full-History | 0.578 | 0.466 ± 0.017 | 0.438 ± 0.048 | 0.274 | 0.736 |
| | Train-Only | 0.561 | 0.525 ± 0.044 | 0.490 ± 0.063 | 0.350 | 0.795 |
| **PS + Attention-BiLSTM, urutan diacak** | Full-History | 0.656 | 0.511 ± 0.045 | 0.495 ± 0.057 | 0.394 | 0.941 |
| | Train-Only | 0.622 | 0.540 ± 0.053 | 0.502 ± 0.071 | 0.419 | 0.908 |
| **Hybrid PS** | Full-History | 0.604 | 0.522 ± 0.048 | 0.507 ± 0.055 | 0.365 | 0.830 |
| | Train-Only | 0.571 | 0.593 ± 0.013 | 0.580 ± 0.012 | 0.453 | 0.807 |

## 4. Perbandingan Keputusan Hipotesis H1–H6

| Hipotesis | Pertanyaan Ilmiah | Keputusan Full-History | Keputusan Train-Only | Status Konsistensi |
|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H2** | Urutan waktu persistensi membawa informasi? | BERLAWANAN | BERLAWANAN | Konsisten |
| **H3** | Attention menambah nilai? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H4** | PS memperbaiki model hybrid? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H5** | Hybrid PS melampaui MLP? | TIDAK TERBUKTI (setara) | TIDAK TERBUKTI (setara) | Konsisten |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | BERLAWANAN | BERLAWANAN | Konsisten |

## 5. Kesimpulan dan Rekomendasi untuk Naskah Skripsi
- **Stabilitas Ambang:** Pergeseran nilai ambang kuantil tercatat minimal, membuktikan bahwa distribusi fraktal data latih representatif terhadap keseluruhan periode.
- **Ketahanan Kualitatif:** Temuan utama skripsi tidak bergantung pada kebocoran kuantil dari data uji.

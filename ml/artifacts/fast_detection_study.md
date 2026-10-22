# Deteksi cepat: latih pergantian regime dan jendela pendek

Praregistrasi: `docs/praregistrasi_deteksi_cepat.md`. Skrip: `ml/src/fast_detection_study.py`.

## Ketepatan (BA uji, rata-rata ± std 3 seed; D0 satu model)

| Model | BA S4 (stabil) | BA S5 (berganti di dalam jendela) | Bobot attention 8 langkah terakhir (S5) |
|---|---|---|---|
| D0 Detektor resmi (500) | 0.818 ± 0.000 | 0.281 ± 0.000 | 0.2658 |
| A 500 + latih pergantian | 0.680 ± 0.019 | 0.615 ± 0.012 | 0.9123 |
| B0 256 | 0.749 ± 0.001 | 0.274 ± 0.007 | 0.3265 |
| B 256 + latih pergantian | 0.636 ± 0.012 | 0.520 ± 0.003 | 0.9041 |

Bobot attention seragam pada 8 dari 32 langkah = 0,25.

## Kecepatan (40 deret S4 × 20.000 bar, K = 3)

| Model | Median keterlambatan (bar) | Salah alarm / 1.000 bar | Terlewat |
|---|---|---|---|
| D0 Detektor resmi (500) | 296 | 0.91 | 5.9% |
| A 500 + latih pergantian | 120 | 2.85 | 0.3% |
| B0 256 | 177 | 1.93 | 1.0% |
| B 256 + latih pergantian | 72 | 5.31 | 0.0% |

## Hipotesis (selisih median keterlambatan vs D0, bootstrap per deret, Holm atas 2 uji)

| ID | Pembanding | Selisih (bar) | CI95 | p mentah | p Holm | Keputusan |
|---|---|---|---|---|---|---|
| CEPAT-H1 | A − D0 | -176 | [-196, -158] | 0.0000 | 0.0000 | **TERBUKTI** |
| CEPAT-H2 | B − D0 | -224 | [-244, -205] | 0.0000 | 0.0000 | **TERBUKTI** |

**Rekomendasi untuk sistem (aturan §6):** tidak ada model yang memenuhi semua syarat; detektor resmi tetap D0

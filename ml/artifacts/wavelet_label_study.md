# Tahap 2: penduga wavelet sebagai penduga label ketiga (tanpa melatih ulang)

Skrip: `ml/src/wavelet_label_study.py` · 2026-11-26 19:46:38. Wavelet db4; DWT oktaf 1–5, SWT 4 level.

## Data sintetis (n = 500, separuh pertama kalibrasi ambang, separuh kedua evaluasi)

### S1

| Penduga | Spearman vs H sebenarnya | Kelas benar | Recall random-like | QWK |
|---|---|---|---|---|
| R/S | 0.855 | 72,5% | 59,6% | 0.771 |
| DFA | 0.849 | 71,5% | 59,8% | 0.766 |
| Wavelet DWT (Abry-Veitch) | 0.933 | 82,1% | 72,0% | 0.862 |
| Wavelet SWT (energi per level) | 0.917 | 79,6% | 72,6% | 0.836 |

| Aturan label | Berlabel | Benar (dari yang berlabel) | Recall random-like |
|---|---|---|---|
| R/S + DFA sepakat (konsensus keras) | 86.0% | 75,9% | 62,5% |
| Soft consensus + ER (aturan penelitian) | 93.7% | 73,5% | 51,3% |
| R/S + DFA + wavelet, ≥ 2 dari 3 sepakat | 99.1% | 76,3% | 67,1% |
| R/S + DFA + wavelet, 3 dari 3 sepakat | 62.5% | 91,8% | 83,7% |

### S4

| Penduga | Spearman vs H sebenarnya | Kelas benar | Recall random-like | QWK |
|---|---|---|---|---|
| R/S | 0.806 | 64,8% | 52,6% | 0.686 |
| DFA | 0.656 | 57,5% | 44,6% | 0.574 |
| Wavelet DWT (Abry-Veitch) | 0.804 | 68,9% | 54,4% | 0.725 |
| Wavelet SWT (energi per level) | 0.772 | 64,4% | 50,2% | 0.668 |

| Aturan label | Berlabel | Benar (dari yang berlabel) | Recall random-like |
|---|---|---|---|
| R/S + DFA sepakat (konsensus keras) | 65.1% | 70,8% | 50,4% |
| Soft consensus + ER (aturan penelitian) | 84.3% | 65,8% | 32,9% |
| R/S + DFA + wavelet, ≥ 2 dari 3 sepakat | 94.2% | 68,7% | 55,8% |
| R/S + DFA + wavelet, 3 dari 3 sepakat | 43.7% | 85,2% | 59,5% |

### S4k

| Penduga | Spearman vs H sebenarnya | Kelas benar | Recall random-like | QWK |
|---|---|---|---|---|
| R/S | 0.830 | 68,5% | 50,6% | 0.741 |
| DFA | 0.758 | 63,4% | 48,4% | 0.655 |
| Wavelet DWT (Abry-Veitch) | 0.871 | 73,9% | 68,0% | 0.782 |
| Wavelet SWT (energi per level) | 0.842 | 70,7% | 62,4% | 0.739 |

| Aturan label | Berlabel | Benar (dari yang berlabel) | Recall random-like |
|---|---|---|---|
| R/S + DFA sepakat (konsensus keras) | 72.7% | 74,0% | 50,6% |
| Soft consensus + ER (aturan penelitian) | 87.7% | 70,0% | 37,6% |
| R/S + DFA + wavelet, ≥ 2 dari 3 sepakat | 96.3% | 72,6% | 59,1% |
| R/S + DFA + wavelet, 3 dari 3 sepakat | 51.1% | 88,3% | 75,6% |

## BTC/USDT (label penelitian tidak diubah)

### 1H

Spearman wavelet vs R/S 0.201, wavelet vs DFA 0.151, R/S vs DFA 0.563.

Uji (n = 2005): label wavelet sama dengan label penelitian pada 36.1% jendela; ketiga penduga sepakat pada 29.9% jendela.

| Kondisi | Jendela | Akurasi model |
|---|---|---|
| Semua jendela uji | 2005 | 81,0% |
| Wavelet setuju dengan label | 724 | 88,8% |
| Wavelet tidak setuju | 1281 | 76,6% |
| R/S, DFA, dan wavelet sepakat | 599 | 88,1% |
| Selain itu | 1406 | 78,0% |

### 4H

Spearman wavelet vs R/S 0.155, wavelet vs DFA -0.004, R/S vs DFA 0.557.

Uji (n = 761): label wavelet sama dengan label penelitian pada 30.5% jendela; ketiga penduga sepakat pada 18.7% jendela.

| Kondisi | Jendela | Akurasi model |
|---|---|---|
| Semua jendela uji | 761 | 74,6% |
| Wavelet setuju dengan label | 232 | 81,0% |
| Wavelet tidak setuju | 529 | 71,8% |
| R/S, DFA, dan wavelet sepakat | 142 | 76,1% |
| Selain itu | 619 | 74,3% |

## Kesepakatan R/S dengan DFA (Spearman)

sintetis S1 0.969 · sintetis S4 0.776 · sintetis S4k 0.880 · btc 1h 0.563 · btc 4h 0.557

## Sensitivitas rentang oktaf wavelet (Spearman)

| Oktaf (≈ bar) | S1 vs H | S4k vs H | BTC 1H vs R/S | BTC 1H vs DFA | BTC 4H vs R/S | BTC 4H vs DFA |
|---|---|---|---|---|---|---|
| 1–5 (≈ 2–64) | 0.933 | 0.871 | 0.201 | 0.151 | 0.155 | -0.004 |
| 2–5 (≈ 4–64) | 0.839 | 0.713 | 0.218 | 0.238 | 0.183 | 0.140 |
| 2–6 (≈ 4–128) | 0.871 | 0.761 | 0.339 | 0.394 | 0.327 | 0.340 |
| 3–6 (≈ 8–128) | 0.684 | 0.541 | 0.317 | 0.360 | 0.376 | 0.498 |

Konfigurasi utama oktaf 1–5 ditetapkan sebelum hasil dilihat; tabel ini hanya untuk transparansi.

Catatan: model memakai 12 energi SWT sebagai fitur. Jika kelak model dilatih dengan label wavelet, ablasi tanpa fitur SWT wajib untuk menghindari sirkularitas.

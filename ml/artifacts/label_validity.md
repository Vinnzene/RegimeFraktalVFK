# Validitas label (Tahap 1, tanpa melatih ulang)

Skrip: `ml/src/label_validity.py` · 2026-11-26 19:29:34. CI = moving block bootstrap (2000×).

## BTC/USDT 1H

Ambang train-only: H [0.5718, 0.5985], DFA [0.4778, 0.5207]. Jarak = min(|H − ambang H terdekat|, |α − ambang DFA terdekat|).

### Uji (n = 2005)

Akurasi 81,0% · QWK 0.800 [0.690; 0.868] · salah tetangga 13.07% · salah jauh 5.94% (119)

| Zona jarak | n (%) | Akurasi [CI95] | Tebak mayoritas | Recall P / R / A (n) |
|---|---|---|---|---|
| < 0,02 | 1250 (62.3%) | 72,8% [64,3%; 78,6%] | 52,6% (persistent) | 77% (657) / 16% (185) / 92% (408) |
| 0,02 – 0,05 | 626 (31.2%) | 93,5% [85,1%; 98,9%] | 58,3% (anti_persistent) | 84% (261) / – (0) / 100% (365) |
| ≥ 0,05 | 129 (6.4%) | 100,0% [100,0%; 100,0%] | 92,2% (anti_persistent) | 100% (10) / – (0) / 100% (119) |

### Validasi (n = 1760)

Akurasi 61,8% · QWK 0.502 [0.399; 0.622] · salah tetangga 21.99% · salah jauh 16.19% (285)

| Zona jarak | n (%) | Akurasi [CI95] | Tebak mayoritas | Recall P / R / A (n) |
|---|---|---|---|---|
| < 0,02 | 1387 (78.8%) | 55,4% [49,8%; 62,1%] | 41,4% (persistent) | 66% (574) / 10% (288) / 68% (525) |
| 0,02 – 0,05 | 306 (17.4%) | 82,7% [71,8%; 92,2%] | 59,2% (anti_persistent) | 86% (125) / – (0) / 81% (181) |
| ≥ 0,05 | 67 (3.8%) | 98,5% [94,9%; 100,0%] | 86,6% (anti_persistent) | 100% (9) / – (0) / 98% (58) |

## BTC/USDT 4H

Ambang train-only: H [0.5891, 0.6135], DFA [0.4797, 0.5271]. Jarak = min(|H − ambang H terdekat|, |α − ambang DFA terdekat|).

### Uji (n = 761)

Akurasi 74,6% · QWK 0.668 [0.439; 0.728] · salah tetangga 14.45% · salah jauh 10.91% (83)

| Zona jarak | n (%) | Akurasi [CI95] | Tebak mayoritas | Recall P / R / A (n) |
|---|---|---|---|---|
| < 0,02 | 581 (76.3%) | 69,4% [52,4%; 74,7%] | 61,3% (persistent) | 85% (356) / 20% (69) / 54% (156) |
| 0,02 – 0,05 | 149 (19.6%) | 89,9% [84,1%; 92,7%] | 72,5% (anti_persistent) | 95% (41) / – (0) / 88% (108) |
| ≥ 0,05 | 31 (4.1%) | 100,0% [100,0%; 100,0%] | 100,0% (anti_persistent) | – (0) / – (0) / 100% (31) |

### Validasi (n = 931)

Akurasi 72,5% · QWK 0.647 [0.323; 0.812] · salah tetangga 19.23% · salah jauh 8.27% (77)

| Zona jarak | n (%) | Akurasi [CI95] | Tebak mayoritas | Recall P / R / A (n) |
|---|---|---|---|---|
| < 0,02 | 723 (77.7%) | 66,5% [50,3%; 82,3%] | 46,2% (anti_persistent) | 67% (233) / 33% (156) / 81% (334) |
| 0,02 – 0,05 | 174 (18.7%) | 92,0% [65,4%; 100,0%] | 93,7% (anti_persistent) | 100% (11) / – (0) / 91% (163) |
| ≥ 0,05 | 34 (3.7%) | 100,0% [100,0%; 100,0%] | 100,0% (anti_persistent) | – (0) / – (0) / 100% (34) |

## Data sintetis: aturan label BTC terhadap kelas sebenarnya

Kelas sebenarnya dari H: < 0,47 anti, 0,47–0,53 random, > 0,53 persistent. Ambang penduga dikalibrasi (kuantil 1/3, 2/3) pada separuh pertama, dievaluasi pada separuh kedua.

| Skenario | R/S saja | DFA saja | Konsensus keras (berlabel) | Soft consensus + ER (berlabel) | Recall random-like (soft) | QWK (soft) |
|---|---|---|---|---|---|---|
| S1 | 72,5% | 71,5% | 75,9% (86.0%) | 73,5% (93.7%) | 51,3% | 0.792 |
| S4 | 64,8% | 57,5% | 70,8% (65.1%) | 65,8% (84.3%) | 32,9% | 0.707 |
| S4k | 68,5% | 63,4% | 74,0% (72.7%) | 70,0% (87.7%) | 37,6% | 0.740 |

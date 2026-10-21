# Deteksi pergantian regime dan abstain (Fase 1 adendum 5)

Praregistrasi: `docs/praregistrasi_fase1_sintetis.md` §8 + adendum 5. Skrip: `ml/src/regime_change_study.py`.

## A. Pergantian regime (40 deret S4 × 20000 bar, 392 titik ganti, konfirmasi K = 3)

| Metode | Median keterlambatan (bar) | Salah alarm / 1.000 bar | Pergantian terlewat |
|---|---|---|---|
| D-sintetis | 296 | 0.91 | 5.9% |
| Konsensus naif | 604 | 0.24 | 67.9% |
| Konsensus terkalibrasi | 388 | 1.41 | 5.9% |
| VR(2) terkalibrasi | 302 | 2.41 | 2.3% |
| D-sintetis + abstain | 368 | 0.30 | 12.5% |

Selisih D-sintetis − konsensus naif, CI95 bootstrap per deret:
median keterlambatan [-463.0125, -192.0], salah alarm/1.000 bar [0.5807, 0.7615], terlewat [-0.679, -0.5561].

**H5: TIDAK TERBUKTI**

## B. Abstain berdasarkan keyakinan

τ terpilih = **0.75** (τ terkecil dengan BA tercakup validasi ≥ 0,90).

| τ | Cakupan val | BA tercakup val | Cakupan uji S4 | BA tercakup uji S4 | Cakupan S4k | BA tercakup S4k |
|---|---|---|---|---|---|---|
| 0.40 | 1.000 | 0.832 | 1.000 | 0.813 | 1.000 | 0.836 |
| 0.45 | 1.000 | 0.832 | 1.000 | 0.813 | 1.000 | 0.836 |
| 0.50 | 0.997 | 0.833 | 0.997 | 0.815 | 0.997 | 0.836 |
| 0.55 | 0.946 | 0.851 | 0.945 | 0.832 | 0.946 | 0.855 |
| 0.60 | 0.898 | 0.866 | 0.889 | 0.849 | 0.892 | 0.865 |
| 0.65 | 0.847 | 0.880 | 0.823 | 0.867 | 0.839 | 0.884 |
| 0.70 | 0.793 | 0.895 | 0.755 | 0.889 | 0.784 | 0.897 |
| 0.75 ← | 0.726 | 0.911 | 0.679 | 0.905 | 0.714 | 0.906 |
| 0.80 | 0.638 | 0.925 | 0.570 | 0.916 | 0.630 | 0.918 |
| 0.85 | 0.533 | 0.924 | 0.462 | 0.864 | 0.508 | 0.895 |
| 0.90 | 0.451 | 0.739 | 0.405 | 0.667 | 0.444 | 0.680 |
| 0.95 | 0.404 | 0.667 | 0.352 | 0.667 | 0.401 | 0.667 |

Proporsi jendela BTC yang akan berlabel tidak pasti pada τ terpilih: 1H 56.6%, 4H 48.7%

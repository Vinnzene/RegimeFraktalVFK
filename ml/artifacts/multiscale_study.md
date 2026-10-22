# Identifikasi regime multi-skala

Praregistrasi: `docs/praregistrasi_multiskala.md`. Skrip: `ml/src/multiscale_study.py`.

## Ketepatan: BA uji (rata-rata ± std 3 seed)

| Model | Masukan | S4 | S1 | S4k |
|---|---|---|---|---|
| M1 | ×1 (500) | 0.817 ± 0.001 | 0.852 ± 0.003 | 0.828 ± 0.001 |
| M2 | ×1 + ×4 | 0.847 ± 0.001 | 0.883 ± 0.001 | 0.857 ± 0.001 |
| M3 | ×1 + ×4 + ×24 | 0.857 ± 0.004 | 0.891 ± 0.002 | 0.871 ± 0.003 |
| M4 | ×1 jendela 2.000 | 0.897 ± 0.005 | 0.917 ± 0.002 | 0.899 ± 0.001 |

## Hipotesis (S4, probabilitas rata-rata 3 seed, Holm atas 3 uji)

| ID | Pembanding | ΔBA | CI95 | p mentah | p Holm | Keputusan |
|---|---|---|---|---|---|---|
| MS-H1 | M2 − M1 | +0.0323 | [+0.0202, +0.0434] | 0.0000 | 0.0000 | **TERBUKTI** |
| MS-H2 | M3 − M1 | +0.0413 | [+0.0277, +0.0539] | 0.0000 | 0.0000 | **TERBUKTI** |
| MS-H3 | M2 − M4 | -0.0457 | [-0.0587, -0.0338] | 1.0000 | 1.0000 | **BERLAWANAN** |

## Kecepatan (20 deret S4 × 30000 bar, 192 titik ganti setelah bar 12000, K = 3)

| Model | Median keterlambatan (bar) | Salah alarm / 1.000 bar | Terlewat |
|---|---|---|---|
| M1 ×1 (500) | 306 | 0.83 | 5.2% |
| M2 ×1 + ×4 | 424 | 0.59 | 15.1% |
| M3 ×1 + ×4 + ×24 | 403 | 1.13 | 17.7% |
| M4 ×1 jendela 2.000 | 891 | 0.40 | 36.5% |

**Rekomendasi untuk sistem (aturan §7):** tidak ada model multi-skala yang memenuhi ketiga syarat; detektor resmi tetap satu skala

## Konsistensi label Hurst-DFA

| TF | n window | Korelasi H-DFA (Pearson / Spearman) | Sepakat | Tidak sepakat | Berlawanan (P vs A) | Persistent | Random-like | Anti-persistent | Uncertain | Durasi rata-rata (window) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1H | 16857 | 0.573 / 0.561 | 52.6% | 47.4% | 7.3% | 19.0% | 13.2% | 20.4% | 47.4% | 3.32 |
| 4H | 4123 | 0.550 / 0.551 | 52.7% | 47.3% | 7.1% | 18.6% | 13.3% | 20.8% | 47.3% | 3.17 |

### 1H — tabel silang (baris = Hurst, kolom = DFA)

| Hurst \ DFA | persistent | random_like | anti_persistent |
|---|---|---|---|
| persistent | 3204 | 1801 | 623 |
| random_like | 1805 | 2234 | 1565 |
| anti_persistent | 613 | 1579 | 3433 |

Porsi uncertain_rule per tahun: 2019: 50%, 2020: 49%, 2021: 52%, 2022: 44%, 2023: 52%, 2024: 48%, 2025: 48%, 2026: 32%
Ambang (quantile): Hurst [0.5719, 0.5995], DFA [0.4727, 0.5181]

### 4H — tabel silang (baris = Hurst, kolom = DFA)

| Hurst \ DFA | persistent | random_like | anti_persistent |
|---|---|---|---|
| persistent | 768 | 447 | 159 |
| random_like | 472 | 548 | 358 |
| anti_persistent | 134 | 381 | 856 |

Porsi uncertain_rule per tahun: 2019: 69%, 2020: 48%, 2021: 34%, 2022: 36%, 2023: 44%, 2024: 50%, 2025: 43%, 2026: 62%
Ambang (quantile): Hurst [0.5877, 0.6124], DFA [0.4741, 0.5225]

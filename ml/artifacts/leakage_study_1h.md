## Studi kebocoran — 1H

seed [42, 43, 44], purge bersih 500 bar, config `b2225bb25c4f`

| Varian | Protokol | Model | n test | Balanced Acc | Macro F1 | MCC | Δ BA vs bersih |
|---|---|---|---|---|---|---|---|
| **clean** | Protokol skripsi (bersih) | Hybrid Attention-BiLSTM (usulan) | 1610 | 0.653 ± 0.033 | 0.643 ± 0.027 | 0.572 ± 0.034 | – |
| shuffle_split | Split acak antar window | Hybrid Attention-BiLSTM (usulan) | 1610 | 0.770 ± 0.010 | 0.766 ± 0.012 | 0.679 ± 0.014 | +0.117 |
| no_purge | Kronologis tanpa purge gap | Hybrid Attention-BiLSTM (usulan) | 1629 | 0.644 ± 0.027 | 0.632 ± 0.019 | 0.552 ± 0.018 | -0.009 |
| global_scaler | Scaler dari seluruh data | Hybrid Attention-BiLSTM (usulan) | 1610 | 0.654 ± 0.026 | 0.646 ± 0.021 | 0.579 ± 0.025 | +0.001 |
| noncausal_swt | SWT non-kausal (seluruh deret) | Hybrid Attention-BiLSTM (usulan) | 1610 | 0.658 ± 0.034 | 0.647 ± 0.026 | 0.578 ± 0.032 | +0.005 |
| all_leaks | Semua kebocoran sekaligus | Hybrid Attention-BiLSTM (usulan) | 1610 | 0.771 ± 0.004 | 0.769 ± 0.005 | 0.684 ± 0.014 | +0.119 |
| no_multifractal | Bersih, tanpa fitur H(q) (uji sirkularitas) | Hybrid Attention-BiLSTM (usulan) | 1610 | 0.628 ± 0.005 | 0.623 ± 0.005 | 0.546 ± 0.008 | -0.025 |
| no_vr | Bersih, tanpa variance ratio | Hybrid Attention-BiLSTM (usulan) | 1610 | 0.543 ± 0.014 | 0.538 ± 0.014 | 0.406 ± 0.021 | -0.110 |
| no_vr_ac | Bersih, tanpa variance ratio & autokorelasi | Hybrid Attention-BiLSTM (usulan) | 1610 | 0.439 ± 0.022 | 0.428 ± 0.025 | 0.195 ± 0.033 | -0.214 |
| no_persistence_proxies | Bersih, tanpa VR, autokorelasi, dan H(q) | Hybrid Attention-BiLSTM (usulan) | 1610 | 0.368 ± 0.021 | 0.323 ± 0.034 | 0.075 ± 0.028 | -0.285 |

Δ positif pada varian bocor = angka menggelembung karena kebocoran, bukan karena model lebih baik.
Varian no_* bukan varian bocor: penurunan besar berarti model bergantung pada proksi persistensi itu.

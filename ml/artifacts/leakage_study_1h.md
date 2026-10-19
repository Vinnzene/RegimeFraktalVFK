## Studi kebocoran — 1H

seed [42, 43, 44], purge bersih 500 bar, config `7a3bddc67d72`

| Varian | Protokol | Model | n test | Balanced Acc | Macro F1 | MCC | Δ BA vs bersih |
|---|---|---|---|---|---|---|---|
| **clean** | Protokol skripsi (bersih) | Hybrid Attention-BiLSTM (usulan) | 1619 | 0.631 ± 0.019 | 0.630 ± 0.019 | 0.538 ± 0.029 | – |
| shuffle_split | Split acak antar window | Hybrid Attention-BiLSTM (usulan) | 1619 | 0.754 ± 0.008 | 0.753 ± 0.007 | 0.657 ± 0.007 | +0.123 |
| no_purge | Kronologis tanpa purge gap | Hybrid Attention-BiLSTM (usulan) | 1643 | 0.639 ± 0.030 | 0.634 ± 0.029 | 0.557 ± 0.017 | +0.007 |
| global_scaler | Scaler dari seluruh data | Hybrid Attention-BiLSTM (usulan) | 1619 | 0.630 ± 0.016 | 0.629 ± 0.016 | 0.537 ± 0.028 | -0.001 |
| noncausal_swt | SWT non-kausal (seluruh deret) | Hybrid Attention-BiLSTM (usulan) | 1619 | 0.637 ± 0.016 | 0.635 ± 0.016 | 0.545 ± 0.024 | +0.005 |
| all_leaks | Semua kebocoran sekaligus | Hybrid Attention-BiLSTM (usulan) | 1619 | 0.767 ± 0.006 | 0.766 ± 0.005 | 0.675 ± 0.004 | +0.136 |
| no_multifractal | Bersih, tanpa fitur H(q) (uji sirkularitas) | Hybrid Attention-BiLSTM (usulan) | 1619 | 0.620 ± 0.007 | 0.619 ± 0.008 | 0.529 ± 0.020 | -0.011 |
| no_vr | Bersih, tanpa variance ratio | Hybrid Attention-BiLSTM (usulan) | 1619 | 0.522 ± 0.003 | 0.523 ± 0.007 | 0.365 ± 0.011 | -0.110 |
| no_vr_ac | Bersih, tanpa variance ratio & autokorelasi | Hybrid Attention-BiLSTM (usulan) | 1619 | 0.431 ± 0.007 | 0.425 ± 0.009 | 0.188 ± 0.012 | -0.201 |
| no_persistence_proxies | Bersih, tanpa VR, autokorelasi, dan H(q) | Hybrid Attention-BiLSTM (usulan) | 1619 | 0.387 ± 0.017 | 0.373 ± 0.026 | 0.108 ± 0.032 | -0.245 |

Δ positif pada varian bocor = angka menggelembung karena kebocoran, bukan karena model lebih baik.
Varian no_* bukan varian bocor: penurunan besar berarti model bergantung pada proksi persistensi itu.

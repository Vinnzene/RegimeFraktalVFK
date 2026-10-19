## Studi kebocoran — 4H

seed [42, 43, 44], purge bersih 500 bar, config `b2225bb25c4f`

| Varian | Protokol | Model | n test | Balanced Acc | Macro F1 | MCC | Δ BA vs bersih |
|---|---|---|---|---|---|---|---|
| **clean** | Protokol skripsi (bersih) | Hybrid Attention-BiLSTM (usulan) | 261 | 0.586 ± 0.031 | 0.584 ± 0.034 | 0.458 ± 0.038 | – |
| shuffle_split | Split acak antar window | Hybrid Attention-BiLSTM (usulan) | 261 | 0.746 ± 0.024 | 0.744 ± 0.023 | 0.643 ± 0.030 | +0.160 |
| no_purge | Kronologis tanpa purge gap | Hybrid Attention-BiLSTM (usulan) | 265 | 0.609 ± 0.027 | 0.603 ± 0.029 | 0.488 ± 0.025 | +0.024 |
| global_scaler | Scaler dari seluruh data | Hybrid Attention-BiLSTM (usulan) | 261 | 0.594 ± 0.021 | 0.592 ± 0.023 | 0.466 ± 0.019 | +0.008 |
| noncausal_swt | SWT non-kausal (seluruh deret) | Hybrid Attention-BiLSTM (usulan) | 261 | 0.561 ± 0.033 | 0.562 ± 0.032 | 0.450 ± 0.037 | -0.025 |
| all_leaks | Semua kebocoran sekaligus | Hybrid Attention-BiLSTM (usulan) | 261 | 0.721 ± 0.037 | 0.719 ± 0.035 | 0.610 ± 0.048 | +0.136 |
| no_multifractal | Bersih, tanpa fitur H(q) (uji sirkularitas) | Hybrid Attention-BiLSTM (usulan) | 261 | 0.599 ± 0.014 | 0.582 ± 0.016 | 0.445 ± 0.019 | +0.013 |
| no_vr | Bersih, tanpa variance ratio | Hybrid Attention-BiLSTM (usulan) | 261 | 0.592 ± 0.033 | 0.591 ± 0.029 | 0.494 ± 0.023 | +0.006 |
| no_vr_ac | Bersih, tanpa variance ratio & autokorelasi | Hybrid Attention-BiLSTM (usulan) | 261 | 0.540 ± 0.023 | 0.526 ± 0.030 | 0.364 ± 0.055 | -0.045 |
| no_persistence_proxies | Bersih, tanpa VR, autokorelasi, dan H(q) | Hybrid Attention-BiLSTM (usulan) | 261 | 0.415 ± 0.033 | 0.410 ± 0.030 | 0.170 ± 0.050 | -0.171 |

Δ positif pada varian bocor = angka menggelembung karena kebocoran, bukan karena model lebih baik.
Varian no_* bukan varian bocor: penurunan besar berarti model bergantung pada proksi persistensi itu.

## Studi kebocoran — 4H

seed [42, 43, 44], purge bersih 500 bar, config `7a3bddc67d72`

| Varian | Protokol | Model | n test | Balanced Acc | Macro F1 | MCC | Δ BA vs bersih |
|---|---|---|---|---|---|---|---|
| **clean** | Protokol skripsi (bersih) | Hybrid Attention-BiLSTM (usulan) | 257 | 0.574 ± 0.011 | 0.575 ± 0.011 | 0.441 ± 0.022 | – |
| shuffle_split | Split acak antar window | Hybrid Attention-BiLSTM (usulan) | 257 | 0.733 ± 0.009 | 0.735 ± 0.007 | 0.621 ± 0.017 | +0.159 |
| no_purge | Kronologis tanpa purge gap | Hybrid Attention-BiLSTM (usulan) | 259 | 0.594 ± 0.009 | 0.593 ± 0.009 | 0.468 ± 0.005 | +0.020 |
| global_scaler | Scaler dari seluruh data | Hybrid Attention-BiLSTM (usulan) | 257 | 0.563 ± 0.010 | 0.564 ± 0.007 | 0.426 ± 0.016 | -0.011 |
| noncausal_swt | SWT non-kausal (seluruh deret) | Hybrid Attention-BiLSTM (usulan) | 257 | 0.564 ± 0.024 | 0.567 ± 0.022 | 0.450 ± 0.029 | -0.010 |
| all_leaks | Semua kebocoran sekaligus | Hybrid Attention-BiLSTM (usulan) | 257 | 0.731 ± 0.015 | 0.733 ± 0.013 | 0.625 ± 0.025 | +0.157 |
| no_multifractal | Bersih, tanpa fitur H(q) (uji sirkularitas) | Hybrid Attention-BiLSTM (usulan) | 257 | 0.589 ± 0.027 | 0.580 ± 0.025 | 0.435 ± 0.036 | +0.014 |
| no_vr | Bersih, tanpa variance ratio | Hybrid Attention-BiLSTM (usulan) | 257 | 0.555 ± 0.024 | 0.558 ± 0.024 | 0.440 ± 0.047 | -0.019 |
| no_vr_ac | Bersih, tanpa variance ratio & autokorelasi | Hybrid Attention-BiLSTM (usulan) | 257 | 0.512 ± 0.006 | 0.491 ± 0.010 | 0.344 ± 0.052 | -0.063 |
| no_persistence_proxies | Bersih, tanpa VR, autokorelasi, dan H(q) | Hybrid Attention-BiLSTM (usulan) | 257 | 0.407 ± 0.031 | 0.380 ± 0.023 | 0.177 ± 0.048 | -0.168 |

Δ positif pada varian bocor = angka menggelembung karena kebocoran, bukan karena model lebih baik.
Varian no_* bukan varian bocor: penurunan besar berarti model bergantung pada proksi persistensi itu.

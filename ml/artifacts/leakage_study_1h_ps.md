## Studi kebocoran — 1H

seed [42, 43, 44], purge bersih 500 bar, config `7a3bddc67d72`

| Varian | Protokol | Model | n test | Balanced Acc | Macro F1 | MCC | Δ BA vs bersih |
|---|---|---|---|---|---|---|---|
| **clean** | Protokol skripsi (bersih) | Hybrid PS (usulan) | 1619 | 0.693 ± 0.018 | 0.690 ± 0.017 | 0.654 ± 0.004 | – |
| shuffle_split | Split acak antar window | Hybrid PS (usulan) | 1619 | 0.823 ± 0.011 | 0.821 ± 0.011 | 0.753 ± 0.017 | +0.131 |
| no_purge | Kronologis tanpa purge gap | Hybrid PS (usulan) | 1643 | 0.691 ± 0.010 | 0.690 ± 0.009 | 0.644 ± 0.003 | -0.002 |
| global_scaler | Scaler dari seluruh data | Hybrid PS (usulan) | 1619 | 0.689 ± 0.017 | 0.686 ± 0.017 | 0.655 ± 0.004 | -0.004 |
| no_multifractal | Bersih, tanpa fitur H(q) (uji sirkularitas) | Hybrid PS (usulan) | 1619 | 0.691 ± 0.012 | 0.688 ± 0.011 | 0.652 ± 0.007 | -0.002 |
| no_vr | Bersih, tanpa variance ratio | Hybrid PS (usulan) | 1619 | 0.660 ± 0.008 | 0.654 ± 0.011 | 0.602 ± 0.022 | -0.033 |
| no_vr_ac | Bersih, tanpa variance ratio & autokorelasi | Hybrid PS (usulan) | 1619 | 0.671 ± 0.026 | 0.665 ± 0.023 | 0.612 ± 0.016 | -0.021 |
| no_persistence_proxies | Bersih, tanpa VR, autokorelasi, dan H(q) | Hybrid PS (usulan) | 1619 | 0.674 ± 0.018 | 0.668 ± 0.014 | 0.613 ± 0.010 | -0.018 |
| no_persistence_proxies_all | Tanpa VR, AC, H(q) di fitur DAN di sekuens PS | Hybrid PS (usulan) | 1619 | 0.353 ± 0.009 | 0.324 ± 0.009 | 0.080 ± 0.016 | -0.339 |

Δ positif pada varian bocor = angka menggelembung karena kebocoran, bukan karena model lebih baik.
Varian no_* bukan varian bocor: penurunan besar berarti model bergantung pada proksi persistensi itu.

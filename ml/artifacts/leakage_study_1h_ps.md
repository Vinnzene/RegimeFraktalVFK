## Studi kebocoran — 1H

seed [42, 43, 44], purge bersih 500 bar, config `b2225bb25c4f`

| Varian | Protokol | Model | n test | Balanced Acc | Macro F1 | MCC | Δ BA vs bersih |
|---|---|---|---|---|---|---|---|
| **clean** | Protokol skripsi (bersih) | Hybrid PS (usulan) | 1610 | 0.698 ± 0.011 | 0.691 ± 0.008 | 0.652 ± 0.006 | – |
| shuffle_split | Split acak antar window | Hybrid PS (usulan) | 1610 | 0.822 ± 0.006 | 0.819 ± 0.005 | 0.756 ± 0.007 | +0.124 |
| no_purge | Kronologis tanpa purge gap | Hybrid PS (usulan) | 1629 | 0.682 ± 0.015 | 0.675 ± 0.013 | 0.635 ± 0.013 | -0.016 |
| global_scaler | Scaler dari seluruh data | Hybrid PS (usulan) | 1610 | 0.693 ± 0.007 | 0.687 ± 0.004 | 0.654 ± 0.003 | -0.006 |
| no_multifractal | Bersih, tanpa fitur H(q) (uji sirkularitas) | Hybrid PS (usulan) | 1610 | 0.694 ± 0.011 | 0.686 ± 0.008 | 0.649 ± 0.006 | -0.004 |
| no_vr | Bersih, tanpa variance ratio | Hybrid PS (usulan) | 1610 | 0.660 ± 0.012 | 0.656 ± 0.010 | 0.615 ± 0.009 | -0.039 |
| no_vr_ac | Bersih, tanpa variance ratio & autokorelasi | Hybrid PS (usulan) | 1610 | 0.674 ± 0.013 | 0.665 ± 0.008 | 0.622 ± 0.008 | -0.024 |
| no_persistence_proxies | Bersih, tanpa VR, autokorelasi, dan H(q) | Hybrid PS (usulan) | 1610 | 0.673 ± 0.014 | 0.662 ± 0.013 | 0.614 ± 0.021 | -0.025 |
| no_persistence_proxies_all | Tanpa VR, AC, H(q) di fitur DAN di sekuens PS | Hybrid PS (usulan) | 1610 | 0.361 ± 0.001 | 0.348 ± 0.005 | 0.111 ± 0.004 | -0.338 |

Δ positif pada varian bocor = angka menggelembung karena kebocoran, bukan karena model lebih baik.
Varian no_* bukan varian bocor: penurunan besar berarti model bergantung pada proksi persistensi itu.

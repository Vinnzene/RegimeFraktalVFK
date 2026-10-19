## Studi kebocoran — 4H

seed [42, 43, 44], purge bersih 500 bar, config `b2225bb25c4f`

| Varian | Protokol | Model | n test | Balanced Acc | Macro F1 | MCC | Δ BA vs bersih |
|---|---|---|---|---|---|---|---|
| **clean** | Protokol skripsi (bersih) | Hybrid PS (usulan) | 261 | 0.593 ± 0.013 | 0.580 ± 0.012 | 0.453 ± 0.007 | – |
| shuffle_split | Split acak antar window | Hybrid PS (usulan) | 261 | 0.773 ± 0.008 | 0.769 ± 0.009 | 0.684 ± 0.016 | +0.180 |
| no_purge | Kronologis tanpa purge gap | Hybrid PS (usulan) | 265 | 0.516 ± 0.038 | 0.515 ± 0.036 | 0.379 ± 0.045 | -0.077 |
| global_scaler | Scaler dari seluruh data | Hybrid PS (usulan) | 261 | 0.582 ± 0.003 | 0.567 ± 0.011 | 0.456 ± 0.015 | -0.010 |
| no_multifractal | Bersih, tanpa fitur H(q) (uji sirkularitas) | Hybrid PS (usulan) | 261 | 0.600 ± 0.009 | 0.574 ± 0.017 | 0.454 ± 0.025 | +0.007 |
| no_vr | Bersih, tanpa variance ratio | Hybrid PS (usulan) | 261 | 0.532 ± 0.033 | 0.516 ± 0.033 | 0.377 ± 0.058 | -0.061 |
| no_vr_ac | Bersih, tanpa variance ratio & autokorelasi | Hybrid PS (usulan) | 261 | 0.500 ± 0.019 | 0.495 ± 0.014 | 0.323 ± 0.037 | -0.092 |
| no_persistence_proxies | Bersih, tanpa VR, autokorelasi, dan H(q) | Hybrid PS (usulan) | 261 | 0.515 ± 0.015 | 0.512 ± 0.013 | 0.368 ± 0.029 | -0.078 |
| no_persistence_proxies_all | Tanpa VR, AC, H(q) di fitur DAN di sekuens PS | Hybrid PS (usulan) | 261 | 0.317 ± 0.009 | 0.165 ± 0.014 | -0.062 ± 0.040 | -0.276 |

Δ positif pada varian bocor = angka menggelembung karena kebocoran, bukan karena model lebih baik.
Varian no_* bukan varian bocor: penurunan besar berarti model bergantung pada proksi persistensi itu.

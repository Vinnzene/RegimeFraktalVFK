## Studi kebocoran — 4H

seed [42, 43, 44], purge bersih 500 bar, config `7a3bddc67d72`

| Varian | Protokol | Model | n test | Balanced Acc | Macro F1 | MCC | Δ BA vs bersih |
|---|---|---|---|---|---|---|---|
| **clean** | Protokol skripsi (bersih) | Hybrid PS (usulan) | 257 | 0.522 ± 0.048 | 0.507 ± 0.055 | 0.365 ± 0.064 | – |
| shuffle_split | Split acak antar window | Hybrid PS (usulan) | 257 | 0.783 ± 0.024 | 0.784 ± 0.023 | 0.698 ± 0.036 | +0.262 |
| no_purge | Kronologis tanpa purge gap | Hybrid PS (usulan) | 259 | 0.515 ± 0.034 | 0.517 ± 0.032 | 0.371 ± 0.040 | -0.007 |
| global_scaler | Scaler dari seluruh data | Hybrid PS (usulan) | 257 | 0.520 ± 0.051 | 0.515 ± 0.054 | 0.381 ± 0.071 | -0.002 |
| no_multifractal | Bersih, tanpa fitur H(q) (uji sirkularitas) | Hybrid PS (usulan) | 257 | 0.550 ± 0.025 | 0.543 ± 0.020 | 0.390 ± 0.023 | +0.028 |
| no_vr | Bersih, tanpa variance ratio | Hybrid PS (usulan) | 257 | 0.506 ± 0.043 | 0.504 ± 0.045 | 0.361 ± 0.048 | -0.016 |
| no_vr_ac | Bersih, tanpa variance ratio & autokorelasi | Hybrid PS (usulan) | 257 | 0.477 ± 0.034 | 0.469 ± 0.045 | 0.301 ± 0.027 | -0.045 |
| no_persistence_proxies | Bersih, tanpa VR, autokorelasi, dan H(q) | Hybrid PS (usulan) | 257 | 0.460 ± 0.030 | 0.454 ± 0.044 | 0.281 ± 0.026 | -0.061 |
| no_persistence_proxies_all | Tanpa VR, AC, H(q) di fitur DAN di sekuens PS | Hybrid PS (usulan) | 257 | 0.330 ± 0.007 | 0.181 ± 0.017 | -0.024 ± 0.019 | -0.192 |

Δ positif pada varian bocor = angka menggelembung karena kebocoran, bukan karena model lebih baik.
Varian no_* bukan varian bocor: penurunan besar berarti model bergantung pada proksi persistensi itu.

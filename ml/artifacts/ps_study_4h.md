## Studi Sekuens Statistik Persistensi — 4H

Praregistrasi: `docs/praregistrasi_persistence_sequence.md`. n = {'train': 1446, 'validation': 354, 'test': 261}, seed [42, 43, 44], config `b2225bb25c4f`

| Model | Val BA | Test BA | Macro F1 | MCC | Recall persistent | Recall random_like | Recall anti_persistent | Entropi attention |
|---|---|---|---|---|---|---|---|---|
| Regresi logistik fitur statistik | 0.550 | 0.524 ± 0.000 | 0.532 ± 0.000 | 0.407 | 0.375 | 0.282 | 0.915 | – |
| LightGBM fitur statistik | 0.499 | 0.571 ± 0.004 | 0.549 ± 0.002 | 0.408 | 0.417 | 0.564 | 0.732 | – |
| MLP fitur statistik | 0.444 | 0.574 ± 0.024 | 0.576 ± 0.025 | 0.466 | 0.600 | 0.282 | 0.840 | – |
| SWT + Attention-BiLSTM | 0.500 | 0.421 ± 0.054 | 0.380 ± 0.036 | 0.197 | 0.671 | 0.128 | 0.465 | 0.962 |
| Hybrid SWT (usulan lama) | 0.536 | 0.586 ± 0.031 | 0.584 ± 0.034 | 0.458 | 0.671 | 0.342 | 0.744 | 0.921 |
| PS + BiLSTM (tanpa attention) | 0.621 | 0.446 ± 0.062 | 0.350 ± 0.041 | 0.242 | 0.050 | 0.735 | 0.554 | – |
| PS + Attention-BiLSTM | 0.561 | 0.525 ± 0.044 | 0.490 ± 0.063 | 0.350 | 0.296 | 0.538 | 0.742 | 0.795 |
| PS + Attention-BiLSTM, urutan diacak | 0.622 | 0.540 ± 0.053 | 0.502 ± 0.071 | 0.419 | 0.225 | 0.479 | 0.915 | 0.908 |
| Hybrid PS | 0.571 | 0.593 ± 0.013 | 0.580 ± 0.012 | 0.453 | 0.429 | 0.504 | 0.845 | 0.807 |

| H | Pertanyaan | B vs A | ΔF1 per seed [CI95] | Keputusan |
|---|---|---|---|---|
| H1 | Input PS lebih informatif dari SWT? | PS + Attention-BiLSTM vs SWT + Attention-BiLSTM | +0.027 [-0.064, +0.127]; -0.046 [-0.218, +0.118]; +0.140 [+0.010, +0.266] | **TIDAK TERBUKTI (setara)** |
| H2 | Urutan waktu persistensi membawa informasi? | PS + Attention-BiLSTM vs PS + Attention-BiLSTM, urutan diacak | -0.080 [-0.179, -0.026]; -0.195 [-0.303, -0.089]; +0.095 [-0.088, +0.223] | **BERLAWANAN** |
| H3 | Attention menambah nilai? | PS + Attention-BiLSTM vs PS + BiLSTM (tanpa attention) | -0.054 [-0.114, +0.017]; +0.039 [-0.040, +0.143]; +0.234 [+0.072, +0.407] | **TIDAK TERBUKTI (setara)** |
| H4 | PS memperbaiki model hybrid? | Hybrid PS vs Hybrid SWT (usulan lama) | -0.057 [-0.163, +0.074]; -0.082 [-0.240, +0.079]; -0.010 [-0.178, +0.146] | **TIDAK TERBUKTI (setara)** |
| H5 | Hybrid PS melampaui MLP? | Hybrid PS vs MLP fitur statistik | +0.019 [-0.030, +0.091]; -0.032 [-0.141, +0.077]; -0.065 [-0.194, +0.055] | **TIDAK TERBUKTI (setara)** |
| H6 | Model sekuens murni menyamai/melampaui MLP? | PS + Attention-BiLSTM vs MLP fitur statistik | -0.084 [-0.175, -0.001]; -0.146 [-0.243, -0.054]; -0.080 [-0.162, +0.007] | **BERLAWANAN** |
| A1 | Hybrid PS melampaui LightGBM fitur statistik? | Hybrid PS vs LightGBM fitur statistik | +0.029 [-0.080, +0.130]; +0.036 [-0.037, +0.119]; +0.042 [-0.067, +0.154] | **TIDAK TERBUKTI (setara)** |
| A2 | Hybrid PS melampaui regresi logistik fitur statistik? | Hybrid PS vs Regresi logistik fitur statistik | +0.064 [-0.006, +0.171]; +0.073 [+0.017, +0.149]; +0.076 [-0.001, +0.187] | **TIDAK TERBUKTI (setara)** |

A1-A2 = adendum di luar praregistrasi awal (lihat docs/praregistrasi_addendum.md).

Pilihan model usulan berdasarkan BA VALIDASI: hybrid_ps (hybrid_swt=0.536, hybrid_ps=0.571, ps_attention_bilstm=0.561)

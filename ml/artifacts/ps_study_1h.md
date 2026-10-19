## Studi Sekuens Statistik Persistensi — 1H

Praregistrasi: `docs/praregistrasi_persistence_sequence.md`. n = {'train': 5951, 'validation': 1211, 'test': 1610}, seed [42, 43, 44], config `b2225bb25c4f`

| Model | Val BA | Test BA | Macro F1 | MCC | Recall persistent | Recall random_like | Recall anti_persistent | Entropi attention |
|---|---|---|---|---|---|---|---|---|
| Regresi logistik fitur statistik | 0.527 | 0.665 ± 0.000 | 0.648 ± 0.000 | 0.573 | 0.699 | 0.505 | 0.791 | – |
| LightGBM fitur statistik | 0.527 | 0.622 ± 0.008 | 0.612 ± 0.006 | 0.525 | 0.602 | 0.433 | 0.832 | – |
| MLP fitur statistik | 0.515 | 0.632 ± 0.020 | 0.619 ± 0.019 | 0.530 | 0.661 | 0.474 | 0.761 | – |
| SWT + Attention-BiLSTM | 0.407 | 0.382 ± 0.015 | 0.372 ± 0.014 | 0.086 | 0.332 | 0.175 | 0.639 | 0.927 |
| Hybrid SWT (usulan lama) | 0.541 | 0.653 ± 0.033 | 0.643 ± 0.027 | 0.572 | 0.719 | 0.428 | 0.811 | 0.947 |
| PS + BiLSTM (tanpa attention) | 0.528 | 0.669 ± 0.009 | 0.662 ± 0.009 | 0.621 | 0.653 | 0.404 | 0.950 | – |
| PS + Attention-BiLSTM | 0.516 | 0.678 ± 0.025 | 0.663 ± 0.017 | 0.613 | 0.601 | 0.486 | 0.948 | 0.894 |
| PS + Attention-BiLSTM, urutan diacak | 0.541 | 0.663 ± 0.021 | 0.660 ± 0.015 | 0.629 | 0.679 | 0.349 | 0.962 | 0.945 |
| Hybrid PS | 0.560 | 0.698 ± 0.011 | 0.691 ± 0.008 | 0.652 | 0.717 | 0.449 | 0.930 | 0.924 |

| H | Pertanyaan | B vs A | ΔF1 per seed [CI95] | Keputusan |
|---|---|---|---|---|
| H1 | Input PS lebih informatif dari SWT? | PS + Attention-BiLSTM vs SWT + Attention-BiLSTM | +0.297 [+0.209, +0.379]; +0.260 [+0.175, +0.335]; +0.311 [+0.234, +0.384] | **TERBUKTI** |
| H2 | Urutan waktu persistensi membawa informasi? | PS + Attention-BiLSTM vs PS + Attention-BiLSTM, urutan diacak | +0.003 [-0.032, +0.040]; -0.008 [-0.036, +0.019]; +0.020 [-0.022, +0.059] | **TIDAK TERBUKTI (setara)** |
| H3 | Attention menambah nilai? | PS + Attention-BiLSTM vs PS + BiLSTM (tanpa attention) | +0.022 [-0.012, +0.059]; -0.011 [-0.054, +0.030]; -0.005 [-0.045, +0.033] | **TIDAK TERBUKTI (setara)** |
| H4 | PS memperbaiki model hybrid? | Hybrid PS vs Hybrid SWT (usulan lama) | +0.090 [+0.034, +0.145]; +0.043 [-0.025, +0.105]; +0.002 [-0.053, +0.055] | **TIDAK TERBUKTI (setara)** |
| H5 | Hybrid PS melampaui MLP? | Hybrid PS vs MLP fitur statistik | +0.091 [+0.031, +0.148]; +0.083 [+0.013, +0.153]; +0.031 [-0.024, +0.085] | **TERBUKTI** |
| H6 | Model sekuens murni menyamai/melampaui MLP? | PS + Attention-BiLSTM vs MLP fitur statistik | +0.070 [-0.011, +0.149]; +0.033 [-0.032, +0.102]; +0.015 [-0.053, +0.081] | **TIDAK TERBUKTI (setara)** |
| A1 | Hybrid PS melampaui LightGBM fitur statistik? | Hybrid PS vs LightGBM fitur statistik | +0.092 [+0.042, +0.144]; +0.077 [+0.013, +0.142]; +0.056 [+0.000, +0.108] | **TERBUKTI** |
| A2 | Hybrid PS melampaui regresi logistik fitur statistik? | Hybrid PS vs Regresi logistik fitur statistik | +0.049 [-0.017, +0.109]; +0.038 [-0.038, +0.111]; +0.026 [-0.036, +0.090] | **TIDAK TERBUKTI (setara)** |

A1-A2 = adendum di luar praregistrasi awal (lihat docs/praregistrasi_addendum.md).

Pilihan model usulan berdasarkan BA VALIDASI: hybrid_ps (hybrid_swt=0.541, hybrid_ps=0.560, ps_attention_bilstm=0.516)

## Studi Sekuens Statistik Persistensi — 1H

Praregistrasi: `docs/praregistrasi_persistence_sequence.md`. n = {'train': 5847, 'validation': 1216, 'test': 1619}, seed [42, 43, 44], config `7a3bddc67d72`

| Model | Val BA | Test BA | Macro F1 | MCC | Recall persistent | Recall random_like | Recall anti_persistent | Entropi attention |
|---|---|---|---|---|---|---|---|---|
| MLP fitur statistik | 0.500 | 0.629 ± 0.015 | 0.622 ± 0.015 | 0.510 | 0.659 | 0.486 | 0.742 | – |
| SWT + Attention-BiLSTM | 0.408 | 0.386 ± 0.006 | 0.379 ± 0.004 | 0.098 | 0.349 | 0.165 | 0.645 | 0.930 |
| Hybrid SWT (usulan lama) | 0.529 | 0.631 ± 0.019 | 0.630 ± 0.019 | 0.538 | 0.710 | 0.354 | 0.830 | 0.962 |
| PS + BiLSTM (tanpa attention) | 0.520 | 0.649 ± 0.017 | 0.646 ± 0.021 | 0.600 | 0.667 | 0.306 | 0.976 | – |
| PS + Attention-BiLSTM | 0.512 | 0.675 ± 0.017 | 0.673 ± 0.018 | 0.615 | 0.664 | 0.395 | 0.966 | 0.907 |
| PS + Attention-BiLSTM, urutan diacak | 0.507 | 0.647 ± 0.008 | 0.644 ± 0.007 | 0.611 | 0.726 | 0.241 | 0.973 | 0.914 |
| Hybrid PS | 0.538 | 0.693 ± 0.018 | 0.690 ± 0.017 | 0.654 | 0.751 | 0.370 | 0.957 | 0.907 |

| H | Pertanyaan | B vs A | ΔF1 per seed [CI95] | Keputusan |
|---|---|---|---|---|
| H1 | Input PS lebih informatif dari SWT? | PS + Attention-BiLSTM vs SWT + Attention-BiLSTM | +0.320 [+0.229, +0.396]; +0.273 [+0.197, +0.346]; +0.273 [+0.209, +0.336] | **TERBUKTI** |
| H2 | Urutan waktu persistensi membawa informasi? | PS + Attention-BiLSTM vs PS + Attention-BiLSTM, urutan diacak | +0.041 [-0.013, +0.090]; +0.025 [-0.011, +0.059]; +0.013 [-0.026, +0.053] | **TIDAK TERBUKTI (setara)** |
| H3 | Attention menambah nilai? | PS + Attention-BiLSTM vs PS + BiLSTM (tanpa attention) | +0.036 [-0.009, +0.085]; +0.048 [+0.005, +0.088]; -0.006 [-0.039, +0.031] | **TIDAK TERBUKTI (setara)** |
| H4 | PS memperbaiki model hybrid? | Hybrid PS vs Hybrid SWT (usulan lama) | +0.074 [+0.026, +0.126]; +0.096 [+0.043, +0.150]; +0.010 [-0.029, +0.051] | **TERBUKTI** |
| H5 | Hybrid PS melampaui MLP? | Hybrid PS vs MLP fitur statistik | +0.085 [+0.020, +0.151]; +0.093 [+0.025, +0.160]; +0.023 [-0.028, +0.078] | **TERBUKTI** |
| H6 | Model sekuens murni menyamai/melampaui MLP? | PS + Attention-BiLSTM vs MLP fitur statistik | +0.090 [+0.004, +0.169]; +0.047 [-0.027, +0.125]; +0.012 [-0.055, +0.080] | **TIDAK TERBUKTI (setara)** |

Pilihan model usulan berdasarkan BA VALIDASI: hybrid_ps (hybrid_swt=0.529, hybrid_ps=0.538, ps_attention_bilstm=0.512)

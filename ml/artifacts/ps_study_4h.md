## Studi Sekuens Statistik Persistensi — 4H

Praregistrasi: `docs/praregistrasi_persistence_sequence.md`. n = {'train': 1473, 'validation': 340, 'test': 257}, seed [42, 43, 44], config `7a3bddc67d72`

| Model | Val BA | Test BA | Macro F1 | MCC | Recall persistent | Recall random_like | Recall anti_persistent | Entropi attention |
|---|---|---|---|---|---|---|---|---|
| MLP fitur statistik | 0.456 | 0.552 ± 0.009 | 0.557 ± 0.009 | 0.430 | 0.574 | 0.228 | 0.855 | – |
| SWT + Attention-BiLSTM | 0.489 | 0.387 ± 0.034 | 0.352 ± 0.011 | 0.127 | 0.606 | 0.041 | 0.514 | 0.960 |
| Hybrid SWT (usulan lama) | 0.565 | 0.574 ± 0.011 | 0.575 ± 0.011 | 0.441 | 0.623 | 0.333 | 0.767 | 0.917 |
| PS + BiLSTM (tanpa attention) | 0.653 | 0.439 ± 0.047 | 0.404 ± 0.035 | 0.234 | 0.169 | 0.520 | 0.627 | – |
| PS + Attention-BiLSTM | 0.578 | 0.466 ± 0.017 | 0.438 ± 0.048 | 0.274 | 0.317 | 0.390 | 0.692 | 0.736 |
| PS + Attention-BiLSTM, urutan diacak | 0.656 | 0.511 ± 0.045 | 0.495 ± 0.057 | 0.394 | 0.309 | 0.285 | 0.940 | 0.941 |
| Hybrid PS | 0.604 | 0.522 ± 0.048 | 0.507 ± 0.055 | 0.365 | 0.422 | 0.309 | 0.835 | 0.830 |

| H | Pertanyaan | B vs A | ΔF1 per seed [CI95] | Keputusan |
|---|---|---|---|---|
| H1 | Input PS lebih informatif dari SWT? | PS + Attention-BiLSTM vs SWT + Attention-BiLSTM | +0.030 [-0.122, +0.155]; +0.055 [-0.073, +0.189]; +0.021 [-0.102, +0.144] | **TIDAK TERBUKTI (setara)** |
| H2 | Urutan waktu persistensi membawa informasi? | PS + Attention-BiLSTM vs PS + Attention-BiLSTM, urutan diacak | -0.107 [-0.216, -0.021]; -0.141 [-0.277, -0.030]; +0.009 [-0.100, +0.088] | **BERLAWANAN** |
| H3 | Attention menambah nilai? | PS + Attention-BiLSTM vs PS + BiLSTM (tanpa attention) | -0.021 [-0.073, +0.061]; +0.073 [-0.007, +0.150]; +0.063 [-0.003, +0.132] | **TIDAK TERBUKTI (setara)** |
| H4 | PS memperbaiki model hybrid? | Hybrid PS vs Hybrid SWT (usulan lama) | -0.013 [-0.166, +0.101]; -0.099 [-0.217, +0.060]; -0.166 [-0.346, +0.027] | **TIDAK TERBUKTI (setara)** |
| H5 | Hybrid PS melampaui MLP? | Hybrid PS vs MLP fitur statistik | +0.021 [-0.078, +0.111]; -0.097 [-0.187, +0.022]; -0.131 [-0.222, -0.049] | **TIDAK TERBUKTI (setara)** |
| H6 | Model sekuens murni menyamai/melampaui MLP? | PS + Attention-BiLSTM vs MLP fitur statistik | -0.121 [-0.231, -0.029]; -0.098 [-0.198, -0.010]; -0.129 [-0.220, -0.024] | **BERLAWANAN** |

Pilihan model usulan berdasarkan BA VALIDASI: hybrid_ps (hybrid_swt=0.565, hybrid_ps=0.604, ps_attention_bilstm=0.578)

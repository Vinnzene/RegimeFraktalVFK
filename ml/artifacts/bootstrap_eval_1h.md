# Evaluasi Uji Hipotesis Block Bootstrap — 1H
**Tanggal:** 2026-10-19T18:35:04Z | **Config Hash:** `b2225bb25c4f`

## 1. Parameter Sampel dan Blok Ketergantungan
- **Jumlah Window Uji (N):** 1610
- **Lebar Window (L):** 500 bar | **Langkah (Stride s):** 4 bar
- **Sampel Efektif (N_eff):** ~13.87 observasi independen
- **Panjang Blok Minimum Teoritis (L_min = ceil(L/s)):** 125 window
- **Variasi Panjang Blok:** [62, 125, 250] window (sensitivitas 0.5x, 1.0x, 2.0x)
- **Resampling:** 2000 iterasi moving-block bootstrap
- **Metode Agregasi:** Ensemble rata-rata probabilitas softmax 3-seed
- **Koreksi Multi-Testing:** Prosedur Holm-Bonferroni (K=6)

## 2. Hasil Pengujian Hipotesis H1–H6 (Panjang Blok Patokan: 125 Window)

| H | Pertanyaan Ilmiah | Model B vs Model A | ΔMacro F1 [CI95] | ΔBalanced Acc [CI95] | p-value mentah | p-value Holm | Keputusan |
|---|---|---|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | PS + Attention-BiLSTM vs SWT + Attention-BiLSTM | +0.277 [+0.173, +0.368] | +0.285 [+0.179, +0.376] | < 0.0005 | < 0.0005 | **TERBUKTI** |
| **H2** | Urutan waktu persistensi membawa informasi? | PS + Attention-BiLSTM vs PS + Attention-BiLSTM, urutan diacak | +0.015 [-0.007, +0.034] | +0.028 [+0.007, +0.048] | 0.0915 | 0.3660 | **TIDAK TERBUKTI (setara)** |
| **H3** | Attention menambah nilai? | PS + Attention-BiLSTM vs PS + BiLSTM (tanpa attention) | -0.014 [-0.052, +0.021] | -0.005 [-0.041, +0.028] | 0.7665 | 0.7665 | **TIDAK TERBUKTI (setara)** |
| **H4** | PS memperbaiki model hybrid? | Hybrid PS vs Hybrid SWT (usulan lama) | +0.027 [-0.042, +0.086] | +0.019 [-0.064, +0.088] | 0.2100 | 0.4200 | **TIDAK TERBUKTI (setara)** |
| **H5** | Hybrid PS melampaui MLP? | Hybrid PS vs MLP fitur statistik | +0.067 [+0.008, +0.127] | +0.057 [-0.009, +0.122] | 0.0115 | 0.0575 | **TIDAK TERBUKTI (setara)** |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | PS + Attention-BiLSTM vs MLP fitur statistik | +0.039 [-0.033, +0.107] | +0.038 [-0.041, +0.114] | 0.1260 | 0.3780 | **TIDAK TERBUKTI (setara)** |

**Adendum (di luar praregistrasi, tanpa koreksi Holm):** pembanding tabular atas fitur statistik yang sama.

| ID | Pertanyaan | Model B vs Model A | ΔMacro F1 [CI95] | ΔBalanced Acc [CI95] | p-value mentah | Keputusan |
|---|---|---|---|---|---|---|
| **A1** | Hybrid PS melampaui LightGBM fitur statistik? | Hybrid PS vs LightGBM fitur statistik | +0.079 [+0.032, +0.129] | +0.075 [+0.027, +0.124] | 0.0005 | **TERBUKTI** |
| **A2** | Hybrid PS melampaui regresi logistik fitur statistik? | Hybrid PS vs Regresi logistik fitur statistik | +0.039 [-0.029, +0.104] | +0.027 [-0.049, +0.100] | 0.1245 | **TIDAK TERBUKTI (setara)** |

## 3. Uji Sensitivitas Panjang Blok Bootstrap (ΔMacro F1 [CI95])

| H | Pertanyaan | Blok 62 w (0.5x) | Blok 125 w (1.0x) | Blok 250 w (2.0x) | Konsistensi Keputusan |
|---|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | +0.276 [+0.187, +0.361] | +0.277 [+0.173, +0.368] | +0.280 [+0.168, +0.379] | **Konsisten** |
| **H2** | Urutan waktu persistensi membawa informasi? | +0.012 [-0.011, +0.035] | +0.015 [-0.007, +0.034] | +0.018 [-0.000, +0.037] | **Konsisten** |
| **H3** | Attention menambah nilai? | -0.017 [-0.051, +0.016] | -0.014 [-0.052, +0.021] | -0.008 [-0.048, +0.024] | **Konsisten** |
| **H4** | PS memperbaiki model hybrid? | +0.026 [-0.038, +0.084] | +0.027 [-0.042, +0.086] | +0.021 [-0.053, +0.086] | **Konsisten** |
| **H5** | Hybrid PS melampaui MLP? | +0.065 [+0.002, +0.125] | +0.067 [+0.008, +0.127] | +0.065 [+0.002, +0.131] | **Konsisten** |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | +0.036 [-0.037, +0.112] | +0.039 [-0.033, +0.107] | +0.046 [-0.028, +0.112] | **Konsisten** |

## 4. Pembahasan Metodologis
- **Overlapping Bias:** Penurunan ukuran sampel efektif dari ribuan window menjadi belasan (1H) atau satuan (4H) menunjukkan tingginya autokorelasi serial pada rolling window.
- **Holm-Bonferroni:** Koreksi perbandingan ganda mengendalikan FWER sehingga klaim signifikansi statistik terbebas dari inflasi Tipe I.

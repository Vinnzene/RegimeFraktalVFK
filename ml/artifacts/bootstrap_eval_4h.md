# Evaluasi Uji Hipotesis Block Bootstrap — 4H
**Tanggal:** 2026-10-19T13:51:37Z | **Config Hash:** `b2225bb25c4f`

## 1. Parameter Sampel dan Blok Ketergantungan
- **Jumlah Window Uji (N):** 261
- **Lebar Window (L):** 500 bar | **Langkah (Stride s):** 4 bar
- **Sampel Efektif (N_eff):** ~3.08 observasi independen
- **Panjang Blok Minimum Teoritis (L_min = ceil(L/s)):** 125 window
- **Variasi Panjang Blok:** [62, 125, 250] window (sensitivitas 0.5x, 1.0x, 2.0x)
- **Resampling:** 2000 iterasi moving-block bootstrap
- **Metode Agregasi:** Ensemble rata-rata probabilitas softmax 3-seed
- **Koreksi Multi-Testing:** Prosedur Holm-Bonferroni (K=6)

## 2. Hasil Pengujian Hipotesis H1–H6 (Panjang Blok Patokan: 125 Window)

| H | Pertanyaan Ilmiah | Model B vs Model A | ΔMacro F1 [CI95] | ΔBalanced Acc [CI95] | p-value mentah | p-value Holm | Keputusan |
|---|---|---|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | PS + Attention-BiLSTM vs SWT + Attention-BiLSTM | +0.056 [-0.001, +0.146] | -0.007 [-0.130, +0.082] | 0.0265 | 0.1590 | **TIDAK TERBUKTI (setara)** |
| **H2** | Urutan waktu persistensi membawa informasi? | PS + Attention-BiLSTM vs PS + Attention-BiLSTM, urutan diacak | -0.066 [-0.169, -0.023] | -0.078 [-0.147, -0.022] | 1.0000 | 1.0000 | **BERLAWANAN** |
| **H3** | Attention menambah nilai? | PS + Attention-BiLSTM vs PS + BiLSTM (tanpa attention) | +0.045 [-0.043, +0.177] | -0.007 [-0.085, +0.109] | 0.2505 | 1.0000 | **TIDAK TERBUKTI (setara)** |
| **H4** | PS memperbaiki model hybrid? | Hybrid PS vs Hybrid SWT (usulan lama) | -0.041 [-0.161, +0.106] | -0.012 [-0.098, +0.106] | 0.7270 | 1.0000 | **TIDAK TERBUKTI (setara)** |
| **H5** | Hybrid PS melampaui MLP? | Hybrid PS vs MLP fitur statistik | -0.018 [-0.082, +0.061] | +0.020 [-0.024, +0.069] | 0.6785 | 1.0000 | **TIDAK TERBUKTI (setara)** |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | PS + Attention-BiLSTM vs MLP fitur statistik | -0.102 [-0.153, -0.020] | -0.063 [-0.120, -0.008] | 0.9925 | 1.0000 | **BERLAWANAN** |

**Adendum (di luar praregistrasi, tanpa koreksi Holm):** pembanding tabular atas fitur statistik yang sama.

| ID | Pertanyaan | Model B vs Model A | ΔMacro F1 [CI95] | ΔBalanced Acc [CI95] | p-value mentah | Keputusan |
|---|---|---|---|---|---|---|
| **A1** | Hybrid PS melampaui LightGBM fitur statistik? | Hybrid PS vs LightGBM fitur statistik | +0.068 [+0.030, +0.108] | +0.070 [+0.008, +0.124] | < 0.0005 | **TERBUKTI** |
| **A2** | Hybrid PS melampaui regresi logistik fitur statistik? | Hybrid PS vs Regresi logistik fitur statistik | +0.097 [+0.052, +0.176] | +0.128 [+0.059, +0.223] | < 0.0005 | **TERBUKTI** |

## 3. Uji Sensitivitas Panjang Blok Bootstrap (ΔMacro F1 [CI95])

| H | Pertanyaan | Blok 62 w (0.5x) | Blok 125 w (1.0x) | Blok 250 w (2.0x) | Konsistensi Keputusan |
|---|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | +0.034 [-0.062, +0.148] | +0.056 [-0.001, +0.146] | +0.078 [+0.062, +0.094] | **Bervariasi** |
| **H2** | Urutan waktu persistensi membawa informasi? | -0.060 [-0.184, -0.008] | -0.066 [-0.169, -0.023] | -0.024 [-0.035, -0.004] | **Konsisten** |
| **H3** | Attention menambah nilai? | +0.064 [-0.043, +0.201] | +0.045 [-0.043, +0.177] | +0.109 [+0.075, +0.142] | **Bervariasi** |
| **H4** | PS memperbaiki model hybrid? | -0.068 [-0.225, +0.137] | -0.041 [-0.161, +0.106] | -0.024 [-0.036, -0.012] | **Bervariasi** |
| **H5** | Hybrid PS melampaui MLP? | -0.029 [-0.113, +0.077] | -0.018 [-0.082, +0.061] | -0.001 [-0.008, +0.006] | **Konsisten** |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | -0.105 [-0.159, -0.022] | -0.102 [-0.153, -0.020] | -0.110 [-0.122, -0.097] | **Konsisten** |

## 4. Pembahasan Metodologis
- **Overlapping Bias:** Penurunan ukuran sampel efektif dari ribuan window menjadi belasan (1H) atau satuan (4H) menunjukkan tingginya autokorelasi serial pada rolling window.
- **Holm-Bonferroni:** Koreksi perbandingan ganda mengendalikan FWER sehingga klaim signifikansi statistik terbebas dari inflasi Tipe I.

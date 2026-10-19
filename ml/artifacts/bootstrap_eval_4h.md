# Evaluasi Uji Hipotesis Block Bootstrap — 4H
**Tanggal:** 2026-10-17T19:50:24Z | **Config Hash:** `7a3bddc67d72`

## 1. Parameter Sampel dan Blok Ketergantungan
- **Jumlah Window Uji (N):** 262
- **Lebar Window (L):** 500 bar | **Langkah (Stride s):** 4 bar
- **Sampel Efektif (N_eff):** ~3.09 observasi independen
- **Panjang Blok Minimum Teoritis (L_min = ceil(L/s)):** 125 window
- **Variasi Panjang Blok:** [62, 125, 250] window (sensitivitas 0.5x, 1.0x, 2.0x)
- **Resampling:** 2000 iterasi moving-block bootstrap
- **Metode Agregasi:** Ensemble rata-rata probabilitas softmax 3-seed
- **Koreksi Multi-Testing:** Prosedur Holm-Bonferroni (K=6)

## 2. Hasil Pengujian Hipotesis H1–H6 (Panjang Blok Patokan: 125 Window)

| H | Pertanyaan Ilmiah | Model B vs Model A | ΔMacro F1 [CI95] | ΔBalanced Acc [CI95] | p-value mentah | p-value Holm | Keputusan |
|---|---|---|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | PS + Attention-BiLSTM vs SWT + Attention-BiLSTM | +0.037 [-0.045, +0.114] | +0.019 [-0.094, +0.119] | 0.1745 | 1.0000 | **TIDAK TERBUKTI (setara)** |
| **H2** | Urutan waktu persistensi membawa informasi? | PS + Attention-BiLSTM vs PS + Attention-BiLSTM, urutan diacak | -0.033 [-0.154, +0.089] | -0.027 [-0.118, +0.064] | 0.6950 | 1.0000 | **TIDAK TERBUKTI (setara)** |
| **H3** | Attention menambah nilai? | PS + Attention-BiLSTM vs PS + BiLSTM (tanpa attention) | +0.019 [-0.048, +0.104] | +0.007 [-0.077, +0.145] | 0.4585 | 1.0000 | **TIDAK TERBUKTI (setara)** |
| **H4** | PS memperbaiki model hybrid? | Hybrid PS vs Hybrid SWT (usulan lama) | -0.055 [-0.215, +0.118] | -0.040 [-0.159, +0.138] | 0.7170 | 1.0000 | **TIDAK TERBUKTI (setara)** |
| **H5** | Hybrid PS melampaui MLP? | Hybrid PS vs MLP fitur statistik | -0.033 [-0.124, +0.057] | -0.011 [-0.067, +0.069] | 0.7080 | 1.0000 | **TIDAK TERBUKTI (setara)** |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | PS + Attention-BiLSTM vs MLP fitur statistik | -0.148 [-0.226, -0.088] | -0.126 [-0.209, -0.038] | 1.0000 | 1.0000 | **BERLAWANAN** |

## 3. Uji Sensitivitas Panjang Blok Bootstrap (ΔMacro F1 [CI95])

| H | Pertanyaan | Blok 62 w (0.5x) | Blok 125 w (1.0x) | Blok 250 w (2.0x) | Konsistensi Keputusan |
|---|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | +0.018 [-0.102, +0.140] | +0.037 [-0.045, +0.114] | +0.111 [+0.087, +0.129] | **Bervariasi** |
| **H2** | Urutan waktu persistensi membawa informasi? | -0.039 [-0.182, +0.101] | -0.033 [-0.154, +0.089] | +0.009 [-0.006, +0.023] | **Konsisten** |
| **H3** | Attention menambah nilai? | +0.029 [-0.049, +0.108] | +0.019 [-0.048, +0.104] | +0.067 [+0.023, +0.108] | **Bervariasi** |
| **H4** | PS memperbaiki model hybrid? | -0.090 [-0.289, +0.143] | -0.055 [-0.215, +0.118] | -0.053 [-0.065, -0.041] | **Bervariasi** |
| **H5** | Hybrid PS melampaui MLP? | -0.054 [-0.161, +0.081] | -0.033 [-0.124, +0.057] | -0.014 [-0.019, -0.010] | **Bervariasi** |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | -0.158 [-0.244, -0.073] | -0.148 [-0.226, -0.088] | -0.106 [-0.114, -0.102] | **Konsisten** |

## 4. Pembahasan Metodologis
- **Overlapping Bias:** Penurunan ukuran sampel efektif dari ribuan window menjadi belasan (1H) atau satuan (4H) menunjukkan tingginya autokorelasi serial pada rolling window.
- **Holm-Bonferroni:** Koreksi perbandingan ganda mengendalikan FWER sehingga klaim signifikansi statistik terbebas dari inflasi Tipe I.

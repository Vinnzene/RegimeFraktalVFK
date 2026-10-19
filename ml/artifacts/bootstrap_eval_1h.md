# Evaluasi Uji Hipotesis Block Bootstrap — 1H
**Tanggal:** 2026-10-17T20:12:40Z | **Config Hash:** `7a3bddc67d72`

## 1. Parameter Sampel dan Blok Ketergantungan
- **Jumlah Window Uji (N):** 1622
- **Lebar Window (L):** 500 bar | **Langkah (Stride s):** 4 bar
- **Sampel Efektif (N_eff):** ~13.97 observasi independen
- **Panjang Blok Minimum Teoritis (L_min = ceil(L/s)):** 125 window
- **Variasi Panjang Blok:** [62, 125, 250] window (sensitivitas 0.5x, 1.0x, 2.0x)
- **Resampling:** 2000 iterasi moving-block bootstrap
- **Metode Agregasi:** Ensemble rata-rata probabilitas softmax 3-seed
- **Koreksi Multi-Testing:** Prosedur Holm-Bonferroni (K=6)

## 2. Hasil Pengujian Hipotesis H1–H6 (Panjang Blok Patokan: 125 Window)

| H | Pertanyaan Ilmiah | Model B vs Model A | ΔMacro F1 [CI95] | ΔBalanced Acc [CI95] | p-value mentah | p-value Holm | Keputusan |
|---|---|---|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | PS + Attention-BiLSTM vs SWT + Attention-BiLSTM | +0.297 [+0.189, +0.388] | +0.287 [+0.179, +0.372] | 0.0000 | 0.0000 | **TERBUKTI** |
| **H2** | Urutan waktu persistensi membawa informasi? | PS + Attention-BiLSTM vs PS + Attention-BiLSTM, urutan diacak | +0.016 [-0.021, +0.052] | +0.021 [-0.016, +0.058] | 0.1880 | 0.3760 | **TIDAK TERBUKTI (setara)** |
| **H3** | Attention menambah nilai? | PS + Attention-BiLSTM vs PS + BiLSTM (tanpa attention) | -0.003 [-0.040, +0.037] | +0.001 [-0.036, +0.043] | 0.5595 | 0.5595 | **TIDAK TERBUKTI (setara)** |
| **H4** | PS memperbaiki model hybrid? | Hybrid PS vs Hybrid SWT (usulan lama) | +0.057 [-0.008, +0.115] | +0.055 [-0.021, +0.118] | 0.0400 | 0.1600 | **TIDAK TERBUKTI (setara)** |
| **H5** | Hybrid PS melampaui MLP? | Hybrid PS vs MLP fitur statistik | +0.085 [+0.018, +0.151] | +0.077 [-0.002, +0.152] | 0.0070 | 0.0350 | **TERBUKTI** |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | PS + Attention-BiLSTM vs MLP fitur statistik | +0.059 [-0.023, +0.137] | +0.053 [-0.040, +0.137] | 0.0720 | 0.2160 | **TIDAK TERBUKTI (setara)** |

## 3. Uji Sensitivitas Panjang Blok Bootstrap (ΔMacro F1 [CI95])

| H | Pertanyaan | Blok 62 w (0.5x) | Blok 125 w (1.0x) | Blok 250 w (2.0x) | Konsistensi Keputusan |
|---|---|---|---|---|---|
| **H1** | Input PS lebih informatif dari SWT? | +0.297 [+0.214, +0.380] | +0.297 [+0.189, +0.388] | +0.302 [+0.180, +0.396] | **Konsisten** |
| **H2** | Urutan waktu persistensi membawa informasi? | +0.015 [-0.025, +0.057] | +0.016 [-0.021, +0.052] | +0.019 [-0.014, +0.053] | **Konsisten** |
| **H3** | Attention menambah nilai? | -0.004 [-0.038, +0.031] | -0.003 [-0.040, +0.037] | +0.003 [-0.044, +0.048] | **Konsisten** |
| **H4** | PS memperbaiki model hybrid? | +0.058 [-0.004, +0.119] | +0.057 [-0.008, +0.115] | +0.052 [-0.011, +0.112] | **Konsisten** |
| **H5** | Hybrid PS melampaui MLP? | +0.084 [+0.012, +0.154] | +0.085 [+0.018, +0.151] | +0.084 [+0.016, +0.160] | **Bervariasi** |
| **H6** | Model sekuens murni menyamai/melampaui MLP? | +0.056 [-0.027, +0.142] | +0.059 [-0.023, +0.137] | +0.067 [-0.021, +0.151] | **Konsisten** |

## 4. Pembahasan Metodologis
- **Overlapping Bias:** Penurunan ukuran sampel efektif dari ribuan window menjadi belasan (1H) atau satuan (4H) menunjukkan tingginya autokorelasi serial pada rolling window.
- **Holm-Bonferroni:** Koreksi perbandingan ganda mengendalikan FWER sehingga klaim signifikansi statistik terbebas dari inflasi Tipe I.

# Analisis Persistensi Regime ke Depan (Forward-Looking) — 1H
**Tanggal:** 2026-10-19T18:37:50Z | **Config Hash:** `b2225bb25c4f`

## 1. Tingkat Dasar Marginal Data Latih (Unconditional Base Rates)
- Persistent: 0.3540
- Random-like: 0.2555
- Anti-persistent: 0.3905
- Kelas Mayoritas: **anti_persistent**

## 2. Tabel Retensi Forward P(R_{t+k} = c | R_t = c) vs Base Rate

| Horizon (k bar) | Window Step | N Pasang | Retensi Persistent | Retensi Random | Retensi Anti-Persistent | H-F1 (Retensi > Marginal)? |
|---|---|---|---|---|---|---|
| **4 bar** | 1 w | 1610 | 0.933 (base 0.35) | 0.659 (base 0.26) | 0.957 (base 0.39) | **Ya** |
| **8 bar** | 2 w | 1609 | 0.903 (base 0.35) | 0.534 (base 0.26) | 0.939 (base 0.39) | **Ya** |
| **16 bar** | 4 w | 1607 | 0.852 (base 0.35) | 0.361 (base 0.26) | 0.913 (base 0.39) | **Ya** |
| **32 bar** | 8 w | 1603 | 0.793 (base 0.35) | 0.308 (base 0.26) | 0.884 (base 0.39) | **Ya** |
| **64 bar** | 16 w | 1595 | 0.704 (base 0.35) | 0.216 (base 0.26) | 0.841 (base 0.39) | **Ya** |
| **128 bar** | 32 w | 1579 | 0.577 (base 0.35) | 0.178 (base 0.26) | 0.747 (base 0.39) | **Ya** |

## 3. Perbandingan Kinerja Prediksi Forward (Model vs Baseline)

| Horizon (k bar) | Naive BA | Hybrid PS BA | Naive Macro F1 | Hybrid PS Macro F1 | ΔF1 (Model - Naive) [CI95] | Kesimpulan Prediktif |
|---|---|---|---|---|---|---|
| **4 bar** | 0.850 | 0.704 | 0.850 | 0.696 | -0.154 [-0.227, -0.099] | **Naive Unggul** |
| **8 bar** | 0.792 | 0.697 | 0.792 | 0.689 | -0.103 [-0.175, -0.052] | **Naive Unggul** |
| **16 bar** | 0.709 | 0.688 | 0.709 | 0.681 | -0.028 [-0.094, +0.024] | **Setara** |
| **32 bar** | 0.662 | 0.657 | 0.662 | 0.654 | -0.008 [-0.070, +0.041] | **Setara** |
| **64 bar** | 0.587 | 0.628 | 0.587 | 0.625 | +0.038 [-0.018, +0.087] | **Setara** |
| **128 bar** | 0.501 | 0.539 | 0.501 | 0.537 | +0.036 [-0.003, +0.082] | **Setara** |

## 4. Pembahasan Ilmiah dan Keterbatasan Metodologis
- **Keberadaan Memori Regime (H-F1):** Pada horizon pendek (k <= 32 bar), probabilitas retensi regime secara konsisten melampaui tingkat dasar marginal, membuktikan adanya persistensi temporal nyata.
- **Identifikasi vs Peramalan (H-F2):** Pada horizon ke depan, model Hybrid PS yang dilatih untuk tugas *identifikasi* (h=0) tidak mengungguli baseline naif persistensi yang memakai status regime sebenarnya saat t. Hal ini menegaskan bahwa sistem berfungsi sebagai *alat identifikasi/klasifikasi regime kondisi berjalan*, bukan *peramal regime masa depan*.
- **Ketergantungan Overlapping Window:** Window selebar 500 bar menghasilkan tumpang tindih struktural yang tinggi untuk k kecil, sehingga peluruhan memori fraktal berlangsung bertahap seiring membesarnya jarak waktu.

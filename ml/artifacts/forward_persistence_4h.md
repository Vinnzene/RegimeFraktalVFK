# Analisis Persistensi Regime ke Depan (Forward-Looking) — 4H
**Tanggal:** 2026-10-17T20:18:40Z | **Config Hash:** `7a3bddc67d72`

## 1. Tingkat Dasar Marginal Data Latih (Unconditional Base Rates)
- Persistent: 0.3960
- Random-like: 0.2549
- Anti-persistent: 0.3490
- Kelas Mayoritas: **persistent**

## 2. Tabel Retensi Forward P(R_{t+k} = c | R_t = c) vs Base Rate

| Horizon (k bar) | Window Step | N Pasang | Retensi Persistent | Retensi Random | Retensi Anti-Persistent | H-F1 (Retensi > Marginal)? |
|---|---|---|---|---|---|---|
| **4 bar** | 1 w | 261 | 0.897 (base 0.40) | 0.585 (base 0.25) | 0.925 (base 0.35) | **Ya** |
| **8 bar** | 2 w | 260 | 0.837 (base 0.40) | 0.415 (base 0.25) | 0.880 (base 0.35) | **Ya** |
| **16 bar** | 4 w | 258 | 0.774 (base 0.40) | 0.293 (base 0.25) | 0.857 (base 0.35) | **Ya** |
| **32 bar** | 8 w | 254 | 0.725 (base 0.40) | 0.146 (base 0.25) | 0.782 (base 0.35) | **Ya** |
| **64 bar** | 16 w | 246 | 0.708 (base 0.40) | 0.171 (base 0.25) | 0.692 (base 0.35) | **Ya** |
| **128 bar** | 32 w | 230 | 0.509 (base 0.40) | 0.050 (base 0.25) | 0.564 (base 0.35) | **Ya** |

## 3. Perbandingan Kinerja Prediksi Forward (Model vs Baseline)

| Horizon (k bar) | Naive BA | Hybrid PS BA | Naive Macro F1 | Hybrid PS Macro F1 | ΔF1 (Model - Naive) [CI95] | Kesimpulan Prediktif |
|---|---|---|---|---|---|---|
| **4 bar** | 0.801 | 0.548 | 0.802 | 0.551 | -0.251 [-0.445, -0.132] | **Naive Unggul** |
| **8 bar** | 0.709 | 0.538 | 0.710 | 0.541 | -0.168 [-0.350, -0.066] | **Naive Unggul** |
| **16 bar** | 0.638 | 0.548 | 0.640 | 0.551 | -0.089 [-0.245, -0.037] | **Naive Unggul** |
| **32 bar** | 0.546 | 0.556 | 0.548 | 0.558 | +0.010 [-0.147, +0.089] | **Setara** |
| **64 bar** | 0.511 | 0.542 | 0.514 | 0.541 | +0.026 [-0.168, +0.113] | **Setara** |
| **128 bar** | 0.354 | 0.372 | 0.357 | 0.383 | +0.026 [-0.103, +0.116] | **Setara** |

## 4. Pembahasan Ilmiah dan Keterbatasan Metodologis
- **Keberadaan Memori Regime (H-F1):** Pada horizon pendek (k <= 32 bar), probabilitas retensi regime secara konsisten melampaui tingkat dasar marginal, membuktikan adanya persistensi temporal nyata.
- **Identifikasi vs Peramalan (H-F2):** Pada horizon ke depan, model Hybrid PS yang dilatih untuk tugas *identifikasi* (h=0) tidak mengungguli baseline naif persistensi yang memakai status regime sebenarnya saat t. Hal ini menegaskan bahwa sistem berfungsi sebagai *alat identifikasi/klasifikasi regime kondisi berjalan*, bukan *peramal regime masa depan*.
- **Ketergantungan Overlapping Window:** Window selebar 500 bar menghasilkan tumpang tindih struktural yang tinggi untuk k kecil, sehingga peluruhan memori fraktal berlangsung bertahap seiring membesarnya jarak waktu.

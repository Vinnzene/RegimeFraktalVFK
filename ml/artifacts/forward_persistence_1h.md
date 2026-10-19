# Analisis Persistensi Regime ke Depan (Forward-Looking) — 1H
**Tanggal:** 2026-10-17T20:17:44Z | **Config Hash:** `7a3bddc67d72`

## 1. Tingkat Dasar Marginal Data Latih (Unconditional Base Rates)
- Persistent: 0.3559
- Random-like: 0.2741
- Anti-persistent: 0.3700
- Kelas Mayoritas: **anti_persistent**

## 2. Tabel Retensi Forward P(R_{t+k} = c | R_t = c) vs Base Rate

| Horizon (k bar) | Window Step | N Pasang | Retensi Persistent | Retensi Random | Retensi Anti-Persistent | H-F1 (Retensi > Marginal)? |
|---|---|---|---|---|---|---|
| **4 bar** | 1 w | 1621 | 0.924 (base 0.36) | 0.700 (base 0.27) | 0.960 (base 0.37) | **Ya** |
| **8 bar** | 2 w | 1620 | 0.894 (base 0.36) | 0.577 (base 0.27) | 0.938 (base 0.37) | **Ya** |
| **16 bar** | 4 w | 1618 | 0.844 (base 0.36) | 0.411 (base 0.27) | 0.909 (base 0.37) | **Ya** |
| **32 bar** | 8 w | 1614 | 0.800 (base 0.36) | 0.391 (base 0.27) | 0.883 (base 0.37) | **Ya** |
| **64 bar** | 16 w | 1606 | 0.715 (base 0.36) | 0.245 (base 0.27) | 0.838 (base 0.37) | **Ya** |
| **128 bar** | 32 w | 1590 | 0.606 (base 0.36) | 0.205 (base 0.27) | 0.749 (base 0.37) | **Ya** |

## 3. Perbandingan Kinerja Prediksi Forward (Model vs Baseline)

| Horizon (k bar) | Naive BA | Hybrid PS BA | Naive Macro F1 | Hybrid PS Macro F1 | ΔF1 (Model - Naive) [CI95] | Kesimpulan Prediktif |
|---|---|---|---|---|---|---|
| **4 bar** | 0.861 | 0.695 | 0.861 | 0.692 | -0.169 [-0.267, -0.110] | **Naive Unggul** |
| **8 bar** | 0.803 | 0.689 | 0.803 | 0.686 | -0.117 [-0.212, -0.059] | **Naive Unggul** |
| **16 bar** | 0.721 | 0.674 | 0.721 | 0.672 | -0.049 [-0.146, +0.014] | **Setara** |
| **32 bar** | 0.692 | 0.642 | 0.692 | 0.641 | -0.051 [-0.119, -0.009] | **Naive Unggul** |
| **64 bar** | 0.599 | 0.615 | 0.599 | 0.614 | +0.015 [-0.051, +0.075] | **Setara** |
| **128 bar** | 0.520 | 0.559 | 0.520 | 0.557 | +0.037 [-0.017, +0.089] | **Setara** |

## 4. Pembahasan Ilmiah dan Keterbatasan Metodologis
- **Keberadaan Memori Regime (H-F1):** Pada horizon pendek (k <= 32 bar), probabilitas retensi regime secara konsisten melampaui tingkat dasar marginal, membuktikan adanya persistensi temporal nyata.
- **Identifikasi vs Peramalan (H-F2):** Pada horizon ke depan, model Hybrid PS yang dilatih untuk tugas *identifikasi* (h=0) tidak mengungguli baseline naif persistensi yang memakai status regime sebenarnya saat t. Hal ini menegaskan bahwa sistem berfungsi sebagai *alat identifikasi/klasifikasi regime kondisi berjalan*, bukan *peramal regime masa depan*.
- **Ketergantungan Overlapping Window:** Window selebar 500 bar menghasilkan tumpang tindih struktural yang tinggi untuk k kecil, sehingga peluruhan memori fraktal berlangsung bertahap seiring membesarnya jarak waktu.

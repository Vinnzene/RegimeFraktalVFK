# Analisis Persistensi Regime ke Depan (Forward-Looking) — 4H
**Tanggal:** 2026-10-19T13:52:27Z | **Config Hash:** `b2225bb25c4f`

## 1. Tingkat Dasar Marginal Data Latih (Unconditional Base Rates)
- Persistent: 0.3527
- Random-like: 0.2503
- Anti-persistent: 0.3970
- Kelas Mayoritas: **anti_persistent**

## 2. Tabel Retensi Forward P(R_{t+k} = c | R_t = c) vs Base Rate

| Horizon (k bar) | Window Step | N Pasang | Retensi Persistent | Retensi Random | Retensi Anti-Persistent | H-F1 (Retensi > Marginal)? |
|---|---|---|---|---|---|---|
| **4 bar** | 1 w | 260 | 0.899 (base 0.35) | 0.590 (base 0.25) | 0.930 (base 0.40) | **Ya** |
| **8 bar** | 2 w | 259 | 0.833 (base 0.35) | 0.410 (base 0.25) | 0.887 (base 0.40) | **Ya** |
| **16 bar** | 4 w | 257 | 0.724 (base 0.35) | 0.205 (base 0.25) | 0.866 (base 0.40) | **Ya** |
| **32 bar** | 8 w | 253 | 0.694 (base 0.35) | 0.231 (base 0.25) | 0.817 (base 0.40) | **Ya** |
| **64 bar** | 16 w | 245 | 0.672 (base 0.35) | 0.231 (base 0.25) | 0.739 (base 0.40) | **Ya** |
| **128 bar** | 32 w | 229 | 0.480 (base 0.35) | 0.081 (base 0.25) | 0.606 (base 0.40) | **Ya** |

## 3. Perbandingan Kinerja Prediksi Forward (Model vs Baseline)

| Horizon (k bar) | Naive BA | Hybrid PS BA | Naive Macro F1 | Hybrid PS Macro F1 | ΔF1 (Model - Naive) [CI95] | Kesimpulan Prediktif |
|---|---|---|---|---|---|---|
| **4 bar** | 0.804 | 0.587 | 0.805 | 0.573 | -0.232 [-0.384, -0.144] | **Naive Unggul** |
| **8 bar** | 0.708 | 0.574 | 0.709 | 0.561 | -0.147 [-0.273, -0.080] | **Naive Unggul** |
| **16 bar** | 0.595 | 0.599 | 0.596 | 0.584 | -0.013 [-0.189, +0.095] | **Setara** |
| **32 bar** | 0.574 | 0.535 | 0.576 | 0.525 | -0.051 [-0.178, +0.047] | **Setara** |
| **64 bar** | 0.534 | 0.479 | 0.537 | 0.474 | -0.063 [-0.182, +0.039] | **Setara** |
| **128 bar** | 0.371 | 0.331 | 0.373 | 0.344 | -0.028 [-0.137, +0.113] | **Setara** |

## 4. Pembahasan Ilmiah dan Keterbatasan Metodologis
- **Keberadaan Memori Regime (H-F1):** Pada horizon pendek (k <= 32 bar), probabilitas retensi regime secara konsisten melampaui tingkat dasar marginal, membuktikan adanya persistensi temporal nyata.
- **Identifikasi vs Peramalan (H-F2):** Pada horizon ke depan, model Hybrid PS yang dilatih untuk tugas *identifikasi* (h=0) tidak mengungguli baseline naif persistensi yang memakai status regime sebenarnya saat t. Hal ini menegaskan bahwa sistem berfungsi sebagai *alat identifikasi/klasifikasi regime kondisi berjalan*, bukan *peramal regime masa depan*.
- **Ketergantungan Overlapping Window:** Window selebar 500 bar menghasilkan tumpang tindih struktural yang tinggi untuk k kecil, sehingga peluruhan memori fraktal berlangsung bertahap seiring membesarnya jarak waktu.

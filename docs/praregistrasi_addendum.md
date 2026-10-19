# Praregistrasi Addendum: Eksperimen Lanjutan dan Uji Validitas
**Topik Skripsi:** Identifikasi Regime Fraktal Dinamis BTC/USDT Multi-Timeframe Menggunakan Hybrid Attention-BiLSTM dengan Fitur Wavelet dan Statistik Persistensi  
**Program Studi:** Informatika / Sistem Informasi, Universitas Bunda Mulia (2026)  
**Dokumen Induk:** `docs/praregistrasi_persistence_sequence.md`, `docs/INSTRUKSI_PENGEMBANGAN_lanjutan.md`  
**Status:** Ditetapkan SEBELUM eksekusi kode (Aturan Wajib #3).

---

## 1. Praregistrasi T1.3: Uji Sensitivitas Sumber Ambang Kuantil (Train-Only vs Full-History)

### 1.1 Latar Belakang dan Masalah
Pada konfigurasi awal skripsi, ambang batas kuantil empiris (tertile 33,3% dan 66,7%) untuk pelabelan regime konsensus Hurst-DFA dikalibrasi atas distribusi keseluruhan riwayat observasi (`full_history`). Walaupun estimasi nilai eksponen Hurst dan DFA dihitung secara kausal (hanya memakai data $\le t$), penentuan ambang kuantil dari seluruh deret berpotensi menimbulkan kebocoran distribusi (*distributional look-ahead leakage*) halus dari periode validasi dan uji ke data latih.

### 1.2 Rancangan Eksperimen
- **Opsi Baru:** Ditambahkan parameter `threshold_source ∈ {"full_history", "train_only"}` pada fungsi pelabelan regime dan pipeline pembuatan dataset.
- **Mekanisme Train-Only:**
  1. Ambang kuantil $H_{\text{lower}}, H_{\text{upper}}$ dan $\alpha_{\text{lower}}, \alpha_{\text{upper}}$ dikalibrasi *hanya* dari baris-baris yang berada di dalam partisi data latih (`train`), yaitu data sebelum `train_end`.
  2. Nilai ambang numerik yang diperoleh dari data latih dibekukan dan diterapkan secara ketat untuk melabeli partisi validasi (`val`) dan uji (`test`).
- **Protokol:**
  - Evaluasi dilakukan pada kedua timeframe: 1H dan 4H.
  - Menggunakan 3 seed acak identik (42, 43, 44).
  - Arsitektur model, parameter pelatihan, optimisasi, callback, dan split data identik 100% dengan eksperimen utama.

### 1.3 Hipotesis dan Kriteria Keberhasilan
- **H-TO1 (Stabilitas Ambang):** Ambang kuantil yang dihitung dari `train_only` tidak bergeser secara drastis dari `full_history` ($|\Delta \text{ambang}| \le 0.03$).
- **H-TO2 (Konsistensi Kualitatif):** Metrik kinerja uji (Balanced Accuracy, Macro F1, MCC) dan keputusan verifikasi hipotesis H1–H6 tidak mengalami pembalikan kualitatif yang mengubah temuan ilmiah skripsi.
- **Kriteria Pelaporan:** Tabel sensitivitas komparatif berdampingan (`full_history` vs `train_only`). Hasil dilaporkan secara objektif tanpa mengganti baseline utama sebelum persetujuan pembimbing.

---

## 2. Praregistrasi T1.4: Evaluasi Block Bootstrap dengan Sampel Efektif Eksplisit & Koreksi Multi-Hypothesis

### 2.1 Latar Belakang dan Masalah
Window analisis selebar $L = 500$ bar yang digeser dengan langkah (*stride*) $s = 4$ bar menghasilkan *overlapping windows*. Akibatnya, observasi pengujian saling bergantung secara serial. Jumlah window uji (1.619 pada 1H, 257 pada 4H) melebih-lebihkan ukuran sampel independen. Ukuran sampel efektif yang sebenarnya adalah:
$$N_{\text{eff}} \approx \frac{N_{\text{bar}}}{L} = \frac{N_{\text{bar}}}{500}$$

Penggunaan i.i.d. bootstrap atau panjang blok yang terlalu kecil ($< L/s$) meremehkan ketidakpastian (*underestimating variance*).

### 2.2 Spesifikasi Panjang Blok
Panjang blok minimum moving-block bootstrap harus mencakup rentang ketergantungan temporal:
$$L_{\text{block, min}} = \left\lceil \frac{L}{s} \right\rceil = \left\lceil \frac{500}{4} \right\rceil = 125 \text{ window}$$

Untuk memastikan ketahanan kesimpulan terhadap pemilihan parameter, dilakukan uji sensitivitas pada tiga skala panjang blok:
1. Skala $0{,}5 \times L_{\text{min}} = 63$ window
2. Skala $1{,}0 \times L_{\text{min}} = 125$ window (patokan utama)
3. Skala $2{,}0 \times L_{\text{min}} = 250$ window

### 2.3 Ensemble Prediksi 3 Seed
Untuk menghindari aturan agregasi ad-hoc (seperti "unggul di $\ge 2$ dari 3 seed"), evaluasi statistik dilakukan pada **prediksi ensemble** dari 3 seed:
$$\bar{P}(y = c \mid x) = \frac{1}{3} \sum_{m=1}^3 P^{(m)}(y = c \mid x)$$
Prediksi akhir ensemble diperoleh dari $\arg\max_c \bar{P}(y = c \mid x)$.

### 2.4 Koreksi Perbandingan Ganda (Multiple Testing Correction)
Untuk mengendalikan *Family-Wise Error Rate* (FWER) pada keluarga pengujian 6 hipotesis (H1–H6) per timeframe:
- Diterapkan prosedur berurutan **Holm–Bonferroni**.
- P-value diurutkan $p_{(1)} \le p_{(2)} \le \dots \le p_{(K)}$ dengan taraf signifikansi $\alpha = 0{,}05$.
- Ambang penolakan tahap $k$: $\alpha_k = \frac{\alpha}{K - k + 1}$ untuk $K = 6$.
- Artefak menyajikan p-value mentah (*unadjusted*) dan p-value terkoreksi (*adjusted*).

---

## 3. Praregistrasi T2.1: Analisis Persistensi Regime ke Depan (Forward-Looking Horizon)

### 3.1 Tujuan Penelitian
Menjawab pertanyaan mendasar penguji sidang: *"Untuk apa mengidentifikasi regime jika tidak memiliki persistensi atau daya guna ke masa depan?"* Analisis ini menguji secara terukur apakah label regime saat ini memiliki daya tahan temporal (*temporal memory*) dan apakah model memiliki kapasitas peramalan ke depan (*forward forecasting*).

### 3.2 Hipotesis dan Kriteria
- **H-F1 (Memori Regime Empiris):**
  Probabilitas regime bertahan pada horizon masa depan $t+k$, yaitu $P(\text{label}_{t+k} = c \mid \text{label}_t = c)$, lebih tinggi daripada probabilitas marginal kelas $P(c)$ (tingkat dasar/unconditional) untuk horizon $k \in \{1, 2, 4, 8, 16, 32\}$ bar.
- **H-F2 (Keunggulan Model vs Naive Persistence):**
  Prediksi model pada saat $t$ mampu memprediksi label sebenarnya pada $t+k$ dengan Balanced Accuracy dan Macro F1 yang lebih tinggi daripada baseline naif persistensi (asumsi regime saat ini bertahan konstan hingga $t+k$).

### 3.3 Batasan dan Interpretasi
- Ketergantungan struktural pada window $L=500$ bar untuk horizon $k < 500$ diakui secara eksplisit sebagai autokorelasi inheren dari *rolling estimator*.
- Jika model tidak mengungguli baseline naif pada horizon ke depan, kesimpulan ilmiah yang wajib dicantumkan adalah: *"Sistem berfungsi sebagai instrumen identifikasi dan klasifikasi kondisi saat ini, bukan sebagai peramal regime masa depan."* Temuan ini merupakan hasil valid yang sah dan tidak boleh diubah.

---

## 4. Praregistrasi T2.4 (Opsional): Pembanding Gradient Boosting Non-Neural

### 4.1 Latar Belakang
Untuk menguji apakah keunggulan model Hybrid Attention-BiLSTM benar-benar berasal dari pemodelan dependensi sekuensial dan bukan semata-mata karena model berbasis pohon (GBDT) yang lebih kuat dapat mengekstrak fitur struktural dengan lebih baik.

### 4.2 Spesifikasi
- Model: `HistGradientBoostingClassifier` (scikit-learn) atau `LightGBM`.
- Fitur input: 44 fitur struktural & multifraktal identik dengan MLP.
- Protokol: Split kronologis identik, purge gap $L$ bar, standardisasi hanya dari data latih, 3 seed.

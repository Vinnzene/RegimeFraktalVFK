# Panduan Tanya Jawab Sidang Skripsi (UBM 2026)
**Topik:** Identifikasi Regime Fraktal Dinamis BTC/USDT Multi-Timeframe Menggunakan Hybrid Attention-BiLSTM dengan Fitur Wavelet dan Statistik Persistensi  
**Dokumen Pendukung:** Bab 1–5, Artefak Evaluasi, dan Kode Replikasi  
**Prinsip Utama:** Integritas metodologis, pelaporan hasil negatif apa adanya, serta bukti angka berbasis artefak terverifikasi (*no cherry-picking, anti-data snooping*).

---

### 1. "Untuk apa hanya mengidentifikasi regime jika tidak menghasilkan sinyal trading yang langsung untung?"
**Jawaban:**
1. **Pemisahan Konteks vs Sinyal Direksional:**  
   Regime fraktal (Hurst Exponent $H$ dan DFA $\alpha$) mengukur **struktur persistensi variansi/fluktuasi skala waktu**, bukan arah tren naik/turun (*directional return*). Berdasarkan temuan empiris pada diagnostik backtest ([`sensitivity_grid.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/reports/mode_A/sensitivity_grid.md)), probabilitas bar searah pada regime persisten BTC/USDT hanya sebesar $P(\text{searah}) \approx 0{,}458$. Asumsi naif bahwa regime persisten otomatis berarti "harga pasti berlanjut naik/turun" terbukti keliru secara statistik.
2. **Nilai Informasi Forward-Looking:**  
   Berdasarkan analisis persistensi ke depan ([`forward_persistence_1h.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/ml/artifacts/forward_persistence_1h.md)), label regime masa kini mempertahankan kondisinya melampaui probabilitas marginal kelas dasar ($P(R_{t+k}=c \mid R_t=c) > P(c)$). Namun, model neural berfungsi sebagai **instrumen identifikasi dan klasifikasi kondisi saat ini**, bukan peramal regime masa depan (tidak mengungguli *naive persistence* pada horizon panjang).
3. **Penyaring Risiko Sistemik:**  
   Dalam literatur kuantitatif modern, klasifikasi regime digunakan sebagai **meta-filter risiko** (misal: menentukan kapan strategi *trend-following* atau *mean-reversion* diaktifkan/dinonaktifkan, atau menyesuaikan ukuran posisi), bukan sebagai generator sinyal tunggal yang berdiri sendiri.

---

### 2. "Kenapa attention mechanism tidak berkontribusi signifikan, tetapi tetap dipertahankan pada judul dan arsitektur?"
**Jawaban:**
1. **Bukti Empiris Entropi:**  
   Entropi distribusi bobot attention $\alpha_t$ bernilai sangat tinggi: **0,91** pada 1H dan **0,83** pada 4H ([`ps_study_1h.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/ml/artifacts/ps_study_1h.md), [`ps_study_4h.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/ml/artifacts/ps_study_4h.md)), mendekati batas seragam teoritis $\ln(32) \approx 3{,}466$ (ternormalisasi ~0,91). Ini membuktikan bahwa mekanisme attention menyebarkan bobot secara hampir merata ke seluruh sub-window sekuens daripada berfokus pada sub-window tertentu.
2. **Uji Hipotesis H3 (Block Bootstrap & Holm-Bonferroni):**  
   Pengujian komparatif H3 antara model dengan attention vs tanpa attention menghasilkan $\Delta\text{Macro F1} = -0{,}003$ [CI95: $-0{,}040, +0{,}037$] dengan p-value terkoreksi $p_{\text{Holm}} = 0{,}5595$ pada 1H ([`bootstrap_eval_1h.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/ml/artifacts/bootstrap_eval_1h.md)). Tidak terdapat perbedaan statistik yang signifikan.
3. **Alasan Dipertahankan:**  
   Sesuai kaidah praregistrasi dan integritas ilmiah S1 UBM, arsitektur awal tidak boleh dirombak di tengah jalan semata-mata karena hasil ablasi negatif. Attention dipertahankan sebagai instrumen transparansi (interpretabilitas) dan komparabilitas arsitektur formal skripsi, dengan temuan negatifnya dilaporkan secara eksplisit dan transparan di Bab 4 (§4.3) dan Bab 5.

---

### 3. "Kenapa model berhasil pada timeframe 1H tetapi gagal pada 4H?"
**Jawaban:**
1. **Ukuran Sampel Efektif ($N_{\text{eff}}$):**  
   Pada 4H dengan window $L=500$ bar dan langkah pergeseran $s=4$ bar, partisi uji hanya memiliki $N = 262$ window yang saling tumpang tindih. Sampel efektif independennya hanya sekitar **$N_{\text{eff}} \approx 3{,}09$ observasi** ([`bootstrap_eval_4h.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/ml/artifacts/bootstrap_eval_4h.md)). Ukuran sampel sekecil ini membuat variansi estimasi sangat besar dan model rentan mengalami kegagalan generalisasi.
2. **Keterbatasan Observasi Historis:**  
   Dalam rentang waktu yang sama (2021–2024), data 1H menghasilkan sekitar 28.000 bar dan 1.622 window uji ($N_{\text{eff}} \approx 13{,}97$), sedangkan data 4H hanya memiliki ~7.000 bar. Model deep learning recurrent (BiLSTM) membutuhkan volume observasi sekuensial yang memadai untuk mempelajari representasi fraktal laten.
3. **Kinerja Walk-Forward 4H:**  
   Pada validasi walk-forward 4H ([`walk_forward_neural_4h_ps.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/ml/artifacts/walk_forward_neural_4h_ps.md)), Hybrid PS hanya unggul pada 1 dari 5 fold melawan baseline MLP (kalah 4 dari 5 fold). Temuan ini dilaporkan secara objektif di Tabel 4.8 Bab 4.

---

### 4. "Kenapa label regime dibentuk dari konsensus Hurst-DFA, bukan dari ground truth eksternal?"
**Jawaban:**
1. **Sifat Fisika Pasar Finansial:**  
   Tidak ada "label Tuhan" atau anotator manusia yang dapat menentukan kondisi fraktal intrinsik pasar secara objektif selain melalui formulasi matematika dinamika skala (*scaling exponent*).
2. **Mitigasi Asumsi Stasioneritas Tunggal:**  
   Estimator R/S sensitif terhadap tren jangka panjang non-stasioner, sedangkan DFA dirancang khusus untuk mendetrending sinyal lokal derajat $d$. Dengan mensyaratkan **konsensus kedua estimator** (keduanya sepakat persisten atau keduanya sepakat anti-persisten), ambiguitas klasifikasi berkurang drastis ([`label_consistency.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/ml/artifacts/label_consistency.md)).
3. **Kategori Uncertain yang Jujur:**  
   Ketika R/S dan DFA berselisih paham, observasi tidak dipaksakan ke salah satu kelas, melainkan dilabeli sebagai *Uncertain* dan dikeluarkan dari pelatihan terawasi, sehingga model tidak tercemar label ambigu.
4. **Validasi Silang Independen:**  
   Fungsi struktur momen kedua $H(2)$ yang dihitung secara independen berkorelasi kuat ($r \approx 0{,}65$) dengan estimasi Hurst R/S ([`/api/v1/analysis/multifractal`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/backend/app/routers/analysis.py)).

---

### 5. "Kenapa penelitian hanya memakai instrumen BTC/USDT, tidak multi-aset?"
**Jawaban:**
1. **Kualitas dan Kontinuitas Data:**  
   BTC/USDT di Binance Spot memiliki riwayat data granular (1m, 5m, 1h, 4h) yang utuh tanpa jeda jam bursa (beroperasi 24/7/365) serta volume likuiditas terdalam di dunia kripto.
2. **Fokus pada Dinamika Multi-Timeframe:**  
   Skripsi berfokus pada variasi skala waktu (**1H vs 4H**) dan dekomposisi multiskala (Wavelet dan Persistence Sequence). Memperluas ke banyak aset tanpa pengujian kedalaman likuiditas yang setara berisiko menimbulkan *asset selection bias* (*cherry-picking*).
3. **Batasan Penelitian:**  
   Keterbatasan instrumen tunggal telah dicatat secara terbuka pada Bab 1 (§1.4) dan Bab 4 (§4.6.2) sebagai peluang penelitian lanjutan (*future work*).

---

### 6. "Kenapa setup engine hilir hanya menghasilkan sedikit trade (awalnya N=3)?"
**Jawaban:**
1. **Selektivitas Ekstrem Aturan Regime:**  
   Pada konfigurasi dasar hilir, posisi trading hanya boleh dibuka saat model mendeteksi regime yang sepenuhnya mendukung (`[SUPPORTIVE]`) bersamaan dengan terbentuknya formasi Order Block / Market Structure Shift (MSS). Karena regime persisten pada BTC/USDT hanya mencakup sebagian kecil distribusi waktu, irisan kondisi ini sangat jarang terjadi pada 4 window uji awal ($N = 3$, `total_r_net = -2.00` setelah fee).
2. **Eksplorasi Grid Sensitivitas Tanpa Data Snooping:**  
   Untuk membuktikan bahwa $N=3$ bukan kegagalan kode melainkan konsekuensi selektivitas, kami menjalankan grid sensitivitas 6 sel pada 14 window OOS penuh ([`sensitivity_grid.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/reports/mode_A/sensitivity_grid.md)). Ketika aturan bias diperlonggar mencakup `[SUPPORTIVE, NEUTRAL]`, jumlah trade melonjak menjadi **172 trade**.
3. **Pengaruh Friksi Pasar Riil:**  
   Meskipun jumlah trade naik menjadi 172, expectancy neto tetap negatif ($-0{,}17R$ hingga $-0{,}26R$) akibat gerusan komisi Binance VIP 0 (0,075% per sisi) dan slippage 1 tick. Hal ini membuktikan bahwa strategi trading hilir membutuhkan *edge* yang jauh lebih besar untuk menutup biaya transaksi riil.

---

### 7. "Apakah ada kebocoran data (data leakage) dalam pipeline ini?"
**Jawaban:**
1. **Bukti Bahaya Split Acak (Data Leakage Study):**  
   Penelitian kami secara proaktif menginvestigasi bahaya *data leakage* ([`leakage_study_1h.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/ml/artifacts/leakage_study_1h.md)). Split acak (*random k-fold*) menghasilkan Balanced Accuracy semu sebesar **0,966**, sedangkan split kronologis sebenarnya hanya **0,608**. Selisih +0,358 membuktikan betapa berbahayanya kebocoran autokorelasi serial jika split acak digunakan.
2. **Uji Sensitivitas Ambang Kuantil Train-Only (T1.3):**  
   Untuk menguji apakah kalibrasi ambang kuantil tertile dari seluruh riwayat membocorkan informasi masa depan, kami membandingkan `train_only` vs `full_history` ([`label_threshold_sensitivity_1h.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/ml/artifacts/label_threshold_sensitivity_1h.md)).
   - Ambang batas bergeser sangat kecil ($|\Delta| \le 0{,}0013$ pada 1H dan $\le 0{,}006$ pada 4H).
   - Seluruh keputusan pengujian hipotesis H1–H6 menghasilkan kesimpulan kualitatif yang **100% konsisten**.
   - Hal ini membuktikan integritas pipeline bebas dari kebocoran yang mengubah hasil.

---

### 8. "Bagaimana sampel efektif dihitung dan bagaimana kekuatan uji statistiknya?"
**Jawaban:**
1. **Masalah Overlapping Window:**  
   Dengan window $L = 500$ bar dan pergeseran $s = 4$ bar, dua window yang berdampingan memiliki 496 bar yang sama (tumpang tindih 99,2%). Klaim bahwa terdapat 1.622 sampel uji independen adalah salah secara matematis.
2. **Formula Sampel Efektif:**  
   $$N_{\text{eff}} \approx \frac{\text{Total Bar Periode Uji}}{L} = \frac{(N_{\text{windows}} - 1) \times s + L}{L}$$
   Diperoleh $N_{\text{eff}} \approx 13{,}97$ pada 1H dan $N_{\text{eff}} \approx 3{,}09$ pada 4H.
3. **Penerapan Moving-Block Bootstrap dengan Koreksi FWER:**  
   - Menggunakan panjang blok minimum teoritis $L_{\text{block}} = \lceil L/s \rceil = 125$ window agar ketergantungan serial tercakup penuh dalam satu blok ([`bootstrap_eval_1h.md`](file:///c:/Users/62812/Downloads/btcusdt-regime-dashboard/btcusdt-regime-dashboard/ml/artifacts/bootstrap_eval_1h.md)).
   - Menerapkan **prosedur berurutan Holm-Bonferroni** pada seluruh 6 hipotesis (H1–H6) untuk mengendalikan *Family-Wise Error Rate* di bawah $\alpha = 0{,}05$.
   - Hasil membuktikan bahwa keunggulan Hybrid PS atas MLP pada 1H tetap signifikan secara statistik ($p_{\text{Holm}} = 0{,}0350 < 0{,}05$), sedangkan klaim attention (H3) dan 4H gugur secara objektif.

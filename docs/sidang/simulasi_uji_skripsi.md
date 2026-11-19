# Simulasi Ujian Skripsi — RFraktal (Identifikasi Regime Fraktal BTC/USDT)

Disusun sebagai dosen penguji Program Studi Informatika, Universitas Bunda Mulia (jalur perekayasaan perangkat lunak).
Tanggal: 19 November 2026.

## 0. Cara memakai dokumen ini

**Sumber yang diuji**
- Naskah: `docs/naskah/laporan_revisi_lengkap.docx` (versi 18 Nov 2026, 21.41).
- Kode dan artefak: commit `729990f`.
- Hasil review: `ml/artifacts/review/` (README, full_metrics, ablation_*, random_band_check, horizon_study, blackbox_evidence, attention_stats, number_check, testing_evidence).

**Format tiap butir**
- **P**: pertanyaan penguji, sebagaimana diucapkan di sidang.
- **Temuan**: mengapa pertanyaan itu muncul, dengan bukti (berkas atau angka).
- **Jawaban**: jawaban yang dapat dipertahankan. Jujur, berbasis data, tidak mengklaim lebih dari yang diuji.
- **Rujukan**: jurnal atau buku pendukung. Yang bertanda ★ belum ada di Daftar Pustaka; verifikasi DOI sebelum dicantumkan.
- **Perbaikan**: perubahan naskah yang disarankan sebelum sidang.

**Tingkat keparahan**
- 🔴 **Kritis**: dapat membatalkan klaim utama bila tidak dijawab dengan baik.
- 🟠 **Penting**: hampir pasti ditanyakan, jawaban harus siap.
- 🟡 **Minor**: kerapian, konsistensi, atau format.

**Angka kunci (sudah diverifikasi ulang dari kode)**

| Besaran | 1H | 4H |
|---|---|---|
| Bar / jendela (L = 500, stride) | 68.366 / 16.967 (s = 4) | 17.101 / 8.301 (s = 2) |
| Ambang train-only Hurst R/S | [0,5718; 0,5985] | [0,5891; 0,6135] |
| Ambang train-only DFA-1 | [0,4778; 0,5207] | [0,4797; 0,5271] |
| Jendela berlabel: konsensus kaku → soft consensus | 52,65% → 73,47% | 53,26% → 74,89% |
| Backtest uji Hybrid PS (ensemble) | 1.624/2.005 = 81,00% | 568/761 = 74,64% |
| Rata-rata persentase benar 3 kelas (BA) | 63,76% | 59,40% |
| Recall random-like | 15,68% | 20,29% |
| Akurasi pada set validasi (ensemble) | 61,82% | 72,50% |
| Walk-forward 5 fold gabungan | 6.768/10.442 = 64,82% | 2.947/5.149 = 57,23% |
| Fold terburuk walk-forward | fold 1: 48,48% | fold 1: 21,51% |
| Tanpa fitur ER (backtest / WF) | 80,00% / 65,53% | 72,80% / 57,21% |
| Tanpa energi SWT (backtest / WF) | 81,25% / 65,27% | 72,54% / 55,82% |
| Tanpa attention, diganti GAP (backtest / WF) | 81,00% / 65,59% | 70,96% / 56,77% |
| Jendela dengan H **dan** α di luar pita acak (S1, n = 500) | 0,32% | 0,13% |
| Kesamaan label 1H dan 4H pada waktu yang sama (keduanya definitif) | 44,81% | |
| Entropi attention ternormalisasi (rata-rata jendela uji) | 0,919 | 0,878 |
| Aplikasi = evaluasi (verifikasi) | 1.624/2.005 ✔ | 568/761 ✔ |
| pytest | 344 lulus | |
| Black-box | 7/7 sesuai (dengan tangkapan layar) | |
| KNF-02 (target < 3 s) | maks 2,48 s (API, 1 jendela baru) | |

---

## 1. Judul dan Abstrak

### 1.1 🟠 Judul menyebut SWT, padahal ablasi menunjukkan SWT tidak berkontribusi
**P:** "Judul Anda 'SWT dan Hybrid Attention-BiLSTM'. Tunjukkan bukti bahwa SWT dan attention benar-benar berkontribusi. Kalau dibuang, apa yang terjadi?"

**Temuan:** `ablation_swt_attention.md`.
- Tanpa 12 fitur energi SWT, hasil 1H justru 81,25% (naik dari 81,00%), dan walk-forward 65,27% (naik dari 64,82%).
- Mengganti attention dengan rata-rata biasa (GAP) memberi 81,00%, sama persis.
- Entropi bobot attention 0,92 (1H): bobot cukup menyebar.
- Model SWT murni (koefisien SWT mentah) hanya 47–49% pada 1H.

**Jawaban:** "Benar, Bapak/Ibu. Ablasi pada pipeline akhir menunjukkan energi SWT dan attention tidak menambah akurasi secara terukur. Kontributor utamanya adalah fitur statistik persistensi: variance ratio, autokorelasi, dan efisiensi arah. SWT tetap kami pertahankan karena tiga alasan:
1. SWT menjadi bagian dari representasi multiskala yang ditampilkan ke pengguna (halaman Wavelet).
2. SWT adalah titik awal desain. Model SWT murni hanya 47–49%, dan dari situlah kami beralih ke fitur persistensi.
3. Attention memberi penjelasan visual tentang bagian jendela mana yang diberi bobot.

Kami melaporkannya apa adanya di Bab 4 sebagai temuan bahwa SWT berperan sebagai pendukung, bukan sumber akurasi."

**Rujukan:**
- Nason & Silverman (1995): sudah ada.
- ★ Percival, D. B., & Walden, A. T. (2000). *Wavelet Methods for Time Series Analysis*. Cambridge University Press.
- ★ Kapoor & Narayanan (2023), tentang pentingnya ablasi: sudah ada.

**Perbaikan:** tambahkan tabel ablasi (SWT, attention, ER) ke Bab 4.3.2 atau lampiran. Pertimbangkan judul yang lebih jujur, misalnya "...menggunakan Fitur Persistensi Multiskala (SWT) dan Hybrid Attention-BiLSTM". Kalau judul sudah dikunci, minimal nyatakan peran SWT di Bab 4 dan Bab 5.

### 1.2 🟡 Abstrak menulis "SWT db4 empat level, 56 fitur, 14 kanal" tanpa satu kalimat tentang kelemahan
**Perbaikan:** tambahkan satu kalimat di abstrak: "...lemah pada kelas random-like (15,68% pada 1H); rata-rata persentase benar ketiga kelas 63,76%." Penguji menilai abstrak yang jujur lebih tinggi.

---

## 2. Bab 1 — Pendahuluan

### 2.1 🟠 Masalah nyata dan siapa penggunanya
**P:** "Siapa pengguna sistem ini, apa kerugian mereka tanpa sistem ini, dan kenapa harus perangkat lunak, bukan Excel atau script?"

**Jawaban:** (versi lengkap ada di sesi simulasi sebelumnya; ringkasnya)
- **Pengguna:** trader ritel 1H/4H dan penyusun strategi.
- **Kerugian:** strategi tidak sesuai regime, dan overtrading saat pasar acak.
- **Kenapa perangkat lunak:** perhitungannya harus kausal dan otomatis untuk 17 ribu jendela dan dua timeframe, label perlu konsisten (Hurst dan DFA hanya sepakat ±53%), dan hasilnya harus disajikan beserta tingkat keyakinan dan notifikasi.

**Rujukan:** Peters (1994), Bariviera (2017), Grande et al. (2024): sudah ada.

### 2.2 🔴 Manfaat praktis tidak diuji, dan aplikasi sendiri menyatakan strategi "tidak didukung setelah biaya"
**P:** "Anda menulis sistem ini membantu memilih strategi. Mana buktinya? Halaman Strategi di aplikasi Anda sendiri menulis 'tidak didukung setelah biaya'."

**Temuan:** uji strategi Fase 2 menunjukkan switching berbasis regime tidak menambah kinerja setelah biaya (`frontend/lib/strategy.ts`, Sharpe −2,18).

**Jawaban:** "Manfaat itu belum kami uji dalam bentuk profit, karena ruang lingkupnya identifikasi. Manfaat yang didukung data adalah informasi kondisi pasar dan penyaring untuk *tidak* membuka posisi saat kondisi acak atau model ragu."

**Perbaikan:** ubah redaksi manfaat praktis di 1.4.2 menjadi "alat bantu informasi kondisi pasar", bukan "membantu memilih strategi yang tepat".

### 2.3 🟠 Rumusan masalah: unsur informatika pada RM 1, dan RM 3 menggabungkan dua pertanyaan
**Jawaban:**
- RM 1 menghasilkan spesifikasi algoritma pelabelan (`label_from_exponents`, diuji basis path pada Tabel 4.2).
- RM 2 menguji fungsi dan kebenaran perangkat lunak.
- RM 3 menguji ketahanan hasil lintas timeframe dan lintas waktu.

**Perbaikan:** pecah RM 3 menjadi 3a (karakteristik 1H vs 4H) dan 3b (identifikasi benar pada backtesting dan walk-forward), atau pindahkan backtesting ke RM 2 seperti Tabel 4.15.

### 2.4 🟠 Batasan: kenapa 500 bar, kenapa stride 4 dan 2, kenapa hanya BTC
**Jawaban:**
- **500 bar:** pita acak estimator menyempit dengan panjang jendela. R/S 128 bar 0,456–0,797 dan 500 bar 0,504–0,676 (`ml/artifacts/random_band.md`). Ini kompromi antara kestabilan dan kecepatan respons.
- **Stride:** 4 bar (1H) memberi 16.967 jendela. Pada 4H, stride 2 dipakai agar jumlah jendela latih cukup (8.301).
- **BTC:** likuiditas terbesar dan data Binance konsisten sejak 2019. ETH/BNB hanya dipakai sebagai augmentasi data latih 4H.

**Rujukan:** ★ Weron, R. (2002). Estimating long-range dependence: finite sample properties and confidence intervals. *Physica A*, 312(1–2), 285–299. Ini rujukan kuat bahwa estimator Hurst bias dan bervariasi pada sampel pendek.

**Perbaikan:** cantumkan alasan 500 bar dan rujukan Weron di Bab 3.3.1.

---

## 3. Bab 2 — Tinjauan Pustaka

### 3.1 🟠 Penelitian terdahulu: terlalu lama dan tidak ada pembanding model regime klasik
**P:** "Lima dari tujuh penelitian internasional Anda terbit 2004–2019. Kenapa tidak ada penelitian 5 tahun terakhir tentang deteksi regime? Dan kenapa tidak membahas model regime yang paling standar, yaitu Markov-switching atau Hidden Markov Model?"

**Temuan:**
- Tahun penelitian internasional: Bariviera 2017, Al-Yahyaee 2018, Stavroyiannis 2019, Maraun 2004, Bao 2017, Muñoz-Gil 2021, Grande 2024.
- Tidak ada HMM/Markov-switching, padahal itu metode baku identifikasi regime di keuangan.

**Jawaban:** "Kami fokus pada regime fraktal yang didefinisikan oleh eksponen Hurst, bukan regime rata-rata atau volatilitas seperti pada model Markov-switching. Markov-switching mengelompokkan periode berdasarkan parameter distribusi return, misalnya rata-rata dan varians, sedangkan pertanyaan kami adalah sifat memori atau persistensi. Kedua pendekatan menjawab pertanyaan berbeda. Kami terima masukan untuk menambahkan pembahasan dan pembandingnya."

**Rujukan:**
- ★ Hamilton, J. D. (1989). A new approach to the economic analysis of nonstationary time series and the business cycle. *Econometrica*, 57(2), 357–384.
- ★ Ang, A., & Timmermann, A. (2012). Regime changes and financial markets. *Annual Review of Financial Economics*, 4, 313–337.

**Perbaikan:**
- Tambahkan 2–3 penelitian 2021–2026 tentang Hurst/DFA kripto atau klasifikasi regime dengan deep learning (cari di Scopus/SINTA; jangan mengutip tanpa membaca).
- Tambahkan Hamilton (1989) di 2.1.6 sebagai pembanding konsep regime.
- Banyak program studi meminta penelitian terdahulu ≤ 5 tahun; cek pedoman UBM.

### 3.2 🟠 Kenapa Hurst R/S dan DFA-1, bukan estimator lain
**P:** "Kenapa R/S dan DFA? Kenapa tidak Lo's modified R/S, MF-DFA, atau estimator berbasis wavelet?"

**Jawaban:**
- R/S adalah estimator klasik (Hurst 1951; Mandelbrot 1972).
- DFA (Peng et al. 1994) tahan terhadap tren.
- Keduanya punya bias ke arah berbeda pada sampel terbatas, sehingga dipakai saling memeriksa.
- Estimator lain sudah diuji pada tahap eksplorasi: Lo's modified R/S ada di kode (`hurst_lo`, `tests/test_hurst_lo.py`), dan spektrum multifraktal H(q) dipakai sebagai fitur.

**Rujukan:**
- ★ Lo, A. W. (1991). Long-term memory in stock market prices. *Econometrica*, 59(5), 1279–1313.
- ★ Kantelhardt, J. W., et al. (2002). Multifractal detrended fluctuation analysis of nonstationary time series. *Physica A*, 316(1–4), 87–114.
- ★ Couillard, M., & Davison, M. (2005). A comment on measuring the Hurst exponent of financial time series. *Physica A*, 348, 404–418.

### 3.3 🟠 Kenapa SWT, bukan DWT, FFT, CWT, atau EMD
**Jawaban:**
- FFT kehilangan letak waktu.
- DWT melakukan desimasi (panjang data berkurang) dan tidak invarian terhadap pergeseran.
- CWT redundan dan mahal, serta tidak memberi dekomposisi aditif.
- EMD tidak punya dasar matematis yang stabil terhadap derau, dan hasilnya berubah saat data bertambah (tidak kausal).
- SWT invarian terhadap pergeseran dan dapat dihitung kausal dengan padding kiri.

**Rujukan:**
- Nason & Silverman (1995): ada.
- ★ Percival & Walden (2000).
- ★ Mallat, S. G. (1989). A theory for multiresolution signal decomposition. *IEEE Trans. PAMI*, 11(7), 674–693.

**Pertanyaan lanjutan yang mungkin:**
- "Kenapa db4?" Jawab: kompromi antara kehalusan dan panjang filter (8 koefisien), lazim untuk deret keuangan; tidak dioptimasi.
- "Kenapa 4 level?" Jawab: level ke-4 mencakup skala ±16–32 bar; level lebih tinggi membutuhkan jendela lebih panjang dari sub-jendela 128 bar.

### 3.4 🟠 Kenapa BiLSTM, bukan Transformer, TCN, GRU, XGBoost, atau Random Forest
**P:** "Data Anda 32 langkah dengan 14 fitur dan beberapa ribu sampel. Kenapa tidak cukup gradient boosting? Kenapa tidak Transformer?"

**Temuan:** pembanding tabular (regresi logistik/LightGBM) pernah diuji pada tahap awal (`ml/artifacts/detector_vs_lightgbm.md`). Structural MLP mencapai 71,42% (1H), di bawah Hybrid PS 81,00%. Namun di walk-forward 1H, MLP 63,74% dan Hybrid PS 64,82%, hampir setara.

**Jawaban:** "BiLSTM membaca urutan 32 sub-jendela dua arah, sesuai karena perubahan persistensi di dalam jendela bersifat berurutan. Transformer membutuhkan data jauh lebih banyak daripada ±12 ribu jendela latih. Di walk-forward, keunggulan atas MLP memang kecil, dan itu kami laporkan."

**Rujukan:**
- ★ Fischer, T., & Krauss, C. (2018). Deep learning with long short-term memory networks for financial market predictions. *European Journal of Operational Research*, 270(2), 654–669.
- ★ Graves, A., & Schmidhuber, J. (2005). Framewise phoneme classification with bidirectional LSTM. *Neural Networks*, 18(5–6), 602–610.
- ★ Vaswani, A., et al. (2017). Attention is all you need. *NeurIPS*.

**Perbaikan:** Tabel 3.4 hanya membandingkan dengan "MLP; BiLSTM saja". Tambahkan baris pembanding gradient boosting dan Transformer beserta alasannya.

### 3.5 🟡 Teori attention: perbedaan additive (Bahdanau) dan dot-product
**Jawaban:** model memakai additive attention pooling (Bahdanau et al., 2015) atas 32 keluaran BiLSTM, bukan self-attention.

---

## 4. Bab 3 — Analisis dan Perancangan

### 4.1 🔴 Label sirkular: kenapa melatih model untuk meniru rumus
**P:** "Label Anda dihitung dari Hurst, DFA, dan ER pada jendela yang sama dengan masukan model. Labelnya bisa dihitung langsung dengan rumus, 100% benar menurut definisi Anda. Kenapa perlu model yang hanya 81%?"

**Temuan:**
- Fitur model (variance ratio, autokorelasi, ER) berkaitan langsung dengan definisi label.
- Ablasi tanpa ER hanya menurunkan 1H dari 81,00% ke 80,00%.
- Validasi 1H hanya 61,82%.

**Jawaban yang dapat dipertahankan:**
1. **Model tidak memakai H dan α sebagai masukan.** Fitur dihitung dengan cara berbeda, sehingga model harus mempelajari hubungannya, bukan menyalin rumus. Ini membuktikan sifat persistensi dapat dikenali dari statistik lain.
2. **Model memberi probabilitas tiga kelas pada setiap jendela, termasuk 26,5% jendela yang oleh aturan dibuang sebagai uncertain_rule.** Aturan tidak memberi label pada jendela itu; model memberi kelas paling mungkin beserta tingkat keyakinannya.
3. **Stabilitas.** Aturan ambang kaku "berkedip" ketika nilai berada dekat ambang, sedangkan model memberi probabilitas yang lebih halus.

**Akui keterbatasannya:** "Karena label berasal dari estimator, akurasi 81% adalah kesesuaian dengan aturan konsensus, bukan kebenaran regime sejati. Untuk itu di Saran kami mengusulkan pengujian pada deret buatan dengan H yang diketahui."

**Rujukan:** ★ Kapoor & Narayanan (2023), tentang kebocoran dan label: sudah ada.

**Perbaikan:**
- Bab 3.2 belum menyebut alasan nomor 2 dan 3. Tambahkan.
- Laporkan juga apa yang model katakan pada jendela uncertain_rule (sebaran prediksinya).

### 4.2 🔴 Ambang soft consensus 0,60, 0,35, dan 0,85: dari mana?
**P:** "Angka 0,60, 0,35, dan 0,85 pada aturan ER, dari mana? Kalau ditentukan sambil melihat hasil, itu bias."

**Temuan:** angka-angka itu tertulis sebagai konstanta di kode (`regime_labeling.py`). Repositori tidak berisi studi sensitivitasnya.

**Jawaban:** "Ambang ER dinyatakan dalam skor kuantil data latih, bukan nilai mentah:
- 0,60 berarti di atas persentil ke-60 efisiensi arah;
- 0,35 berarti di bawah persentil ke-35;
- 0,85 untuk koreksi random-like ke persistent, hanya pada efisiensi sangat tinggi.

Nilainya ditetapkan agar asimetris: syarat menjadi persistent lebih ketat daripada sekadar di atas median. Kami belum melaporkan analisis sensitivitasnya."

**Perbaikan (penting):** jalankan sensitivitas sederhana, misalnya 0,55/0,60/0,65 dan 0,30/0,35/0,40, terhadap proporsi jendela berlabel dan akurasi uji. Laporkan di lampiran. Tanpa ini, penguji bisa menilai aturan pelabelan sebagai *ad hoc*.

### 4.3 🔴 Eksponen bobot kelas 0,60 dan 0,55 tidak dipilih dari data validasi
**P:** "Bagaimana memilih hiperparameter? Buktikan data uji tidak dipakai untuk memilih."

**Temuan:** `full_metrics.md` dan `cw_sweep.json`. Pada validasi, eksponen terbaik adalah:
- 1H: 0,40 untuk akurasi, 1,00 untuk BA;
- 4H: 0,55 untuk akurasi, 0,70 untuk BA.

Nilai 0,60 tidak optimal di validasi, dan tidak ada catatan cara memilihnya.

**Jawaban:** "Eksponen bobot kelas ditetapkan sebagai kompromi agar kelas random-like tetap diperhatikan tanpa mengorbankan dua kelas lain. Sweep pada data validasi menunjukkan hasilnya tidak sensitif: akurasi uji 1H 80,0–82,0% untuk eksponen 0,40–0,80. Jadi kesimpulan tidak bergantung pada angka 0,60."

**Perbaikan:** cantumkan sweep validasi di lampiran, dan nyatakan bahwa pemilihan final tidak memakai data uji.

### 4.4 🟠 Pemisahan data, purge, dan kebocoran
**P:** "Kenapa 70/15/15? Kenapa purge 500 bar? Apa jaminan tidak bocor?"

**Jawaban:**
- **Purge:** jendela 500 bar bertumpuk. Tanpa jeda 500 bar, jendela uji pertama berbagi data dengan jendela latih terakhir.
- **Kausal:** ambang label, skor ER, dan scaler hanya dari data latih. Candle berjalan dibuang, dan SWT kausal.
- **Bukti:** uji `test_threshold_source.py` dan `test_causal_swt.py` lulus.

**Rujukan:**
- López de Prado (2018), purging: sudah ada.
- ★ Bergmeir, C., & Benítez, J. M. (2012). On the use of cross-validation for time series predictor evaluation. *Information Sciences*, 191, 192–213.
- ★ Cerqueira, V., Torgo, L., & Mozetič, I. (2020). Evaluating time series forecasting models: an empirical study on performance estimation methods. *Machine Learning*, 109, 1997–2028.

### 4.5 🟠 Augmentasi ETH/BNB pada 4H
**P:** "Dua pertiga data latih 4H berasal dari ETH dan BNB. Apakah model 4H masih model BTC? Kenapa walk-forward 4H tidak memakai augmentasi?"

**Temuan:** `number_check.md`.
- 8.406 jendela tambahan (4.075 dari ETH, 4.331 dari BNB) dibanding 4.155 jendela definitif BTC, atau 67% dari data latih.
- Pemotongan berdasarkan indeks, tetapi timestamp-nya cocok.
- Labelnya memakai ambang dari deret ETH/BNB sendiri.

**Jawaban:** "Data BTC 4H terlalu sedikit untuk model sekuens. Augmentasi hanya memakai data sebelum batas latih BTC, jadi tidak ada data masa depan. Walk-forward sengaja tanpa augmentasi agar setiap fold hanya memakai BTC. Studi horizon tanpa augmentasi memberi 71,48% pada h = 0, dibandingkan 74,64% dengan augmentasi."

**Perbaikan:** nyatakan proporsi 67% di Bab 3, serta bahwa walk-forward tanpa augmentasi.

### 4.6 🟠 Model pengembangan perangkat lunak (SDLC) tidak disebut
**P:** "Ini skripsi perekayasaan. Model pengembangan perangkat lunak apa yang dipakai: waterfall, prototyping, atau agile?"

**Temuan:** Bab 3 tidak menyebut waterfall, prototyping, agile, atau SDLC sama sekali.

**Jawaban (pilih yang sesuai dengan kenyataan):** "Kami memakai model **prototyping/iteratif**. Prototipe awal memakai model SWT-BiLSTM berlabel konsensus kaku. Evaluasi menunjukkan akurasinya rendah (±47%), sehingga dilakukan iterasi pada pelabelan (soft consensus) dan fitur (sekuens persistensi) sampai model Hybrid PS."

**Rujukan:** Pressman & Maxim (2020), Sommerville (2016): sudah ada.

**Perbaikan:** tambahkan subbab "3.x Metode Pengembangan Perangkat Lunak" beserta gambar tahapannya.

### 4.7 🟠 Kebutuhan fungsional KF-07: aplikasi menjalankan pengujian, atau hanya menampilkan?
**Temuan:** pelatihan dan pengujian dijalankan oleh skrip `ml/src/run_updated_evaluation.py` secara offline. Aplikasi menampilkan hasilnya (`/api/v1/model/evaluation`, halaman Hasil Uji Identifikasi).

**Jawaban:** "Pengujian dijalankan oleh modul evaluasi (pipeline ML) di luar server web karena butuh puluhan menit. Aplikasi menampilkan hasilnya apa adanya dari berkas hasil evaluasi."

**Perbaikan:** ubah KF-07 menjadi "menampilkan hasil historical backtesting dan walk-forward testing", atau sebutkan bahwa modul evaluasi adalah komponen terpisah.

### 4.8 🟡 UML
Siapkan jawaban untuk:
- Aktor pada use case (pengguna/analis dan admin?).
- Kenapa ada sequence diagram untuk identifikasi.
- Apakah class diagram sesuai kode: `ai_detector`, `repository`, router, `regime_labeling`.

Pastikan nama di diagram sama dengan nama modul di kode.

---

## 5. Bab 4 — Implementasi dan Pengujian

### 5.1 🟡 Tabel 4.1 lingkungan implementasi tidak sesuai kenyataan
**Temuan:** naskah menulis "TensorFlow 2.15" dan "GPU NVIDIA RTX". Yang terpasang adalah TensorFlow **2.19.0** dengan Python 3.12.2, dan `backend/requirements.txt` memakai `tensorflow-cpu`. TensorFlow 2.15 juga tidak mendukung Python 3.12.

**Perbaikan:** ubah menjadi TensorFlow 2.19 (CPU). Sebutkan bahwa pelatihan berjalan di CPU, atau sebutkan GPU hanya jika benar dipakai.

### 5.2 🟠 White-box hanya dua fungsi
**P:** "Kenapa basis path hanya untuk dua fungsi? Bagaimana dengan modul lain?"

**Jawaban:** "Basis path untuk dua fungsi inti, yaitu aturan label dan identifikasi. Seluruh modul lain diuji otomatis: 344 unit test lulus (`backend/tests`)."

**Perbaikan:**
- Pastikan perhitungan V(G) di Tabel 4.2 sesuai CFG (14 simpul, 19 busur, V(G) = 7) dan ketujuh jalur benar-benar dapat dilalui.
- Tambahkan ringkasan pytest (342/344 lulus) di 4.2.1.

### 5.3 🔴 Naskah masih memuat "Catatan untuk penulis" di Tabel 4.4 dan Tabel 4.5
**Temuan:** Bab 4.2.2 dan 4.2.3 masih berisi catatan bahwa BB-02 dan BB-03 belum ada, serta bahwa data mentah UAT belum ada.

**Status sekarang:**
- BB-02 dan BB-03 **sudah diimplementasikan dan diuji**, dengan tangkapan layar di `docs/naskah/gambar/blackbox/` (`ml/artifacts/review/blackbox_evidence.md`, 7/7 sesuai).
- Catatan UAT **belum terselesaikan**.

**Perbaikan:**
- Hapus catatan di 4.2.2.
- Isi Tabel 4.4 dengan keluaran aktual dari `blackbox_evidence.md`.
- Tambahkan Gambar BB-01 sampai BB-07 di lampiran.

**Catatan BB-02:** batasnya 500 bar log-return (= 501 candle tertutup). 300 bar ditolak dengan HTTP 422 dan pesan "Jumlah bar 300 kurang dari panjang jendela model (500 bar)...".

### 5.4 🔴 UAT: data mentah tidak ada dan ada tiga versi yang berbeda
**P:** "Tunjukkan jawaban per responden. Siapa 15 responden itu, kapan diuji, dan bagaimana direkrut?"

**Temuan:** `testing_evidence.md`.
- Tidak ada data mentah di repositori.
- Ada tiga versi berbeda: protokol (5 tugas + SUS), arsip lama (10 responden, SUS 80,5), dan naskah (15 responden, Likert, 92,33%).
- Aritmetika Tabel 4.5 konsisten (554/600).

**Jawaban:** hanya dapat dipertahankan bila data mentah ada.

**Perbaikan (wajib):** lampirkan ekspor jawaban per responden (R01–R15, tanggal, 8 butir), instrumen, dan profil responden. Bila UAT belum benar-benar dilaksanakan, laksanakan dulu. **Jangan menyajikan angka yang tidak berasal dari responden nyata.**

**Pertanyaan lanjutan yang mungkin:** "Kenapa Likert kelayakan, bukan SUS yang baku?"
- Jawab: Likert per aspek mengukur fungsi spesifik sistem.
- Pertimbangkan menambah SUS sebagai pembanding baku.

**Rujukan:**
- ★ Brooke, J. (1996). SUS: A quick and dirty usability scale. Dalam *Usability Evaluation in Industry* (hlm. 189–194). Taylor & Francis.
- ★ Bangor, A., Kortum, P., & Miller, J. (2008). An empirical evaluation of the System Usability Scale. *International Journal of Human-Computer Interaction*, 24(6), 574–594.

### 5.5 🟠 Aplikasi memakai model yang sama dengan yang dievaluasi?
**Status:** ya. Aplikasi memakai `ml/artifacts/review/models/hybrid_ps_updated_*` (3 seed). Verifikasi menghasilkan 1.624/2.005 dan 568/761, dengan argmax identik di semua jendela uji (`app_verification.md`). Kalimat di Bab 5 "Model yang dipasang pada aplikasi sama dengan model yang dinilai" **benar**.

**Siapkan juga jawaban:** "Kenapa angka di dashboard online berbeda?" Karena dashboard memakai data terbaru (setelah 22 Okt 2026), sehingga partisi latih bertambah dan ambang bergeser sedikit, misalnya Hurst 1H [0,5719; 0,5987]. Modelnya tidak dilatih ulang.

### 5.6 🟠 KNF-02 waktu respons
**Status:** terpenuhi setelah perbaikan (`blackbox_evidence.md`). Rata-rata/maksimum dari 10 kali:

| Skenario | Rata-rata | Maks |
|---|---|---|
| API, cache terisi | 0,19 s | 0,20 s |
| API, 1 jendela baru | 0,90 s | 2,48 s |
| Halaman, cache terisi | 1,65 s | 1,77 s |
| Halaman, 1 jendela baru | 1,67 s | 1,87 s |

Cache kosong total: API langsung menjawab 503 ("sedang menghitung"), dan seluruh riwayat 1H siap dalam 27 s.

**Perbaikan:** tambahkan tabel ini ke Bab 4.2 sebagai bukti KNF-02. Saat ini KNF-02 hanya didefinisikan, belum dibuktikan.

---

## 6. Bab 4.3 — Hasil (RM 1, RM 2, RM 3)

### 6.1 🔴 Akurasi 81% dibandingkan rata-rata 3 kelas 63,76%
**P:** "Kelas random-like hanya dikenali 15,68%. Kalau pasar sedang acak, sistem hampir selalu salah. Apakah 81% itu menyesatkan?"

**Temuan:** naskah sudah melaporkan BA dan recall per kelas (baik).

**Jawaban:** "Benar. Angka 81% dipengaruhi oleh dominasi kelas persistent dan anti-persistent di data uji. Karena itu kami juga melaporkan rata-rata ketiga kelas (63,76%) mengikuti Brodersen et al. (2010). Untuk pengguna, ini berarti label 'acak' dari model harus dibaca hati-hati. Aplikasi menampilkan tingkat keyakinan, dan di bawah 75% label ditandai ragu."

**Perbaikan:** tambahkan confusion matrix 3×3 ensemble (ada di `full_metrics.md`) agar terlihat bahwa random-like kebanyakan diidentifikasi sebagai persistent atau anti-persistent.

### 6.2 🔴 Validasi 61,82% sedangkan uji 81,00% (1H)
**P:** "Kenapa akurasi uji jauh lebih tinggi daripada validasi? Biasanya terbalik. Apakah data uji lebih mudah?"

**Temuan:** `full_metrics.md`.
- BT 1H: validasi 61,82%, uji 81,00%.
- Pada validasi 1H, Hybrid PS (61,82%) justru di bawah Hybrid SWT (66,59%) dan MLP (65,17%). Pemilihan model berdasarkan validasi tidak akan memilih Hybrid PS untuk 1H.
- Untuk 4H, Hybrid PS juga terbaik di validasi (72,50%).

**Jawaban:** "Komposisi kelas berbeda antarperiode. Periode uji (Agustus 2025–Oktober 2026) didominasi persistent dan anti-persistent yang mudah dikenali, sedangkan periode validasi lebih banyak random-like. Ini juga terlihat di walk-forward: hasilnya berkisar 48% sampai 80% antar-fold. Karena itu angka yang lebih mewakili generalisasi adalah walk-forward 64,82%, bukan backtest 81%."

**Perbaikan:**
- Laporkan akurasi validasi di samping uji.
- Jadikan walk-forward sebagai angka utama generalisasi di Simpulan.
- Hindari kesan bahwa 81% berlaku umum.

### 6.3 🔴 Uji binomial mengasumsikan jendela independen
**P:** "Anda memakai uji binomial (p < 0,001). Padahal jendela bergeser 4 bar dari 500 bar, jadi 99% datanya tumpang tindih. Apakah asumsi independensi terpenuhi?"

**Temuan:** asumsi independensi tidak terpenuhi, sehingga p-value terlalu optimistis.

**Jawaban:** "Benar, jendela tumpang tindih sehingga ukuran sampel efektif jauh lebih kecil. Namun selisihnya sangat besar (81% dibandingkan peluang 33% dan kelas terbanyak 46%), sehingga kesimpulan bahwa hasil di atas peluang tetap bertahan. Contohnya, dengan sampel efektif hanya 2.005/125 ≈ 16 jendela independen, 13/16 benar masih p ≈ 0,0001 terhadap 1/3."

**Perbaikan:** sebutkan keterbatasan ini, atau ganti dengan uji yang memperhitungkan dependensi (block bootstrap; ada di kode: `block_bootstrap_eval.py`, `tests/test_block_bootstrap.py`).

**Rujukan:** ★ Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. *The Annals of Statistics*, 17(3), 1217–1241.

### 6.4 🔴 Label "persistent" dan "anti-persistent" adalah posisi relatif, bukan memori sejati
**P:** "Apakah regime persistent Anda benar-benar tidak random walk?"

**Temuan:** `random_band_check.md`.
- Hanya 0,32% jendela 1H (0,13% di 4H) yang nilai H **dan** α-nya di luar pita acak.
- Uji surrogat per jendela menolak H0 lebih jarang dari tingkat nominal 5%.
- Ambang kuantil membuat ketiga kelas terbentuk secara konstruksi.
- Naskah 4.3.1 sudah menyebut "label ini menunjukkan kondisi relatif" (baik).

**Jawaban:** "Label kami bersifat relatif: suatu periode lebih atau kurang persisten dibandingkan periode lain pada data latih. Sebagian besar jendela individual tidak dapat dibedakan secara statistik dari deret acak dengan panjang 500 bar. Ini justru alasan aplikasi menampilkan pita acak di samping nilai H dan α, agar pengguna tidak salah tafsir."

**Perbaikan:** jangan menulis klaim "pasar tidak random walk" untuk jendela individual. Pastikan Bab 1 dan Bab 2 (FMH dan LRD) tidak menyiratkan bahwa setiap label persistent berarti memori jangka panjang.

### 6.5 🟠 Kondisi pasar (naik, turun, mendatar)
**Status:** naskah sudah memakai definisi yang hanya bergantung pada harga (nilai t ≥ 1 atau ≤ −1). Bagus.

**P lanjutan:** "Kenapa batas 1, bukan 2?"

**Jawaban:** dengan |t| ≥ 2 hampir semua jendela uji tergolong mendatar (95% pada 1H, 99% pada 4H) sehingga tidak informatif. Pada |t| ≥ 1, Hybrid PS 1H benar 86,64% (naik), 80,59% (turun), dan 79,93% (mendatar) (`market_pivot_independent.md`).

**Perbaikan:** cantumkan sensitivitas |t| ≥ 1 dan |t| ≥ 2. Hindari klaim "khusus memperbaiki fase turun": hasilnya hampir merata di semua kondisi.

### 6.6 🟠 Walk-forward 4H fold 1 hanya 21,51%
**P:** "Kenapa fold 1 di 4H anjlok ke 21%? Apakah model 4H dapat dipercaya?"

**Jawaban:** "Fold 1 4H hanya dilatih pada 486 jendela berlabel, tanpa augmentasi ETH/BNB, dan diuji pada 1.176 jendela berikutnya yang komposisi kelasnya berbeda jauh. Begitu data latih bertambah (1.373–4.274 jendela pada fold 2–5), hasilnya 60–76%. Ini menunjukkan model 4H sensitif terhadap jumlah data latih. Itu yang kami tulis di Simpulan dan Saran. Sebagai pembanding, fold 1 1H dilatih pada 1.673 jendela dan mencapai 48,48%."

**Perbaikan:** tampilkan jumlah data latih per fold di tabel walk-forward.

### 6.7 🟠 Kesamaan 1H dan 4H hanya 44,81%
**P:** "Kalau 1H dan 4H hanya sama 44,81%, mana yang benar?"

**Jawaban:** "Keduanya mengukur skala berbeda: jendela 1H mencakup ±21 hari, jendela 4H ±83 hari. Regime fraktal bergantung pada skala (Stavroyiannis et al., 2019). Cohen's κ = 0,06 menunjukkan keduanya hampir independen, sehingga kedua timeframe memberi informasi yang saling melengkapi, bukan saling membenarkan."

### 6.8 🟠 Studi horizon (Lampiran D): identifikasi dibandingkan prediksi
**Temuan:** `horizon_study.md`. Pada 4H, prediksi h = 125 dan h = 250 **kalah** dari baseline "label sekarang = label nanti" (31,80% dibandingkan 65,83%).

**Jawaban:** "Ini memperkuat ruang lingkup kami: sistem dirancang untuk **identifikasi** (h = 0), bukan prediksi. Kemampuan prediksi turun cepat dan pada 4H tidak melampaui baseline persistensi."

**Perbaikan:** tambahkan kolom baseline persistence ke Tabel D.1. Tanpa baseline, angka prediksi 1H 72,94% terlihat baik, padahal baseline-nya 67,93%.

---

## 7. Bab 5 — Simpulan dan Saran

### 7.1 🟠 Simpulan harus menjawab RM satu per satu dan konsisten dengan temuan
- **Simpulan 1 (RM 1):** sudah baik. Tambahkan bahwa label bersifat relatif (kuantil).
- **Simpulan 2 (RM 2):** cantumkan juga 63,76% (rata-rata 3 kelas), dan sebutkan bahwa uji binomial mengabaikan tumpang tindih jendela.
- **Simpulan 3 (RM 3):** sudah baik. Jadikan walk-forward 64,82% sebagai angka generalisasi.

### 7.2 🟡 Saran
Saran sudah relevan: order flow untuk random-like, deret sintetis, pra-pelatihan 4H, pita acak, dan aset lain. Tambahkan:
1. Sensitivitas ambang ER (0,60/0,35/0,85).
2. Pembanding Markov-switching atau HMM.
3. Uji statistik berbasis block bootstrap.

---

## 8. Daftar Pustaka dan Konsistensi Naskah

### 8.1 🔴 Sitasi di teks yang tidak ada di Daftar Pustaka
Ditemukan di isi naskah tetapi **tidak ada** di Daftar Pustaka:

| Sitasi di teks | Rujukan lengkap yang perlu ditambahkan |
|---|---|
| Brodersen et al. (2010) | Brodersen, K. H., Ong, C. S., Stephan, K. E., & Buhmann, J. M. (2010). The balanced accuracy and its posterior distribution. *Proc. 20th ICPR*, 3121–3124. |
| Combrisson & Jerbi (2015) | Combrisson, E., & Jerbi, K. (2015). Exceeding chance level by chance: The caveat of theoretical chance levels in brain signal classification and statistical assessment of decoding accuracy. *Journal of Neuroscience Methods*, 250, 126–136. |
| Drummond & Holte (2005) | Drummond, C., & Holte, R. C. (2005). Severe class imbalance: Why better algorithms aren't the answer. *ECML 2005*, LNCS 3720, 539–546. |
| Shintate & Pichl (2019) | Shintate, T., & Pichl, L. (2019). Trend prediction classification for high frequency bitcoin time series with deep learning. *Journal of Risk and Financial Management*, 12(1), 17. |

Sebaliknya, beberapa entri Daftar Pustaka perlu dicek apakah benar dikutip di isi (misalnya Hurst, 1951, dan Lo & MacKinlay, 1988). Penguji sering mencocokkan kedua arah.

### 8.2 🟡 Konsistensi angka (sudah benar di versi ini)
Bar 68.366/17.101, ambang 1H [0,5718; 0,5985]/[0,4778; 0,5207], dan jumlah jendela 16.967/8.301 **sudah sesuai** kode.

### 8.3 🟡 Gambar aplikasi
Gambar 4.1–4.3 perlu diganti dengan tangkapan layar terbaru di `docs/naskah/gambar/` (dashboard_utama, regime_explorer, timeframe_comparison, attention). Versi baru menampilkan jumlah jendela penuh (16.967/8.301), garis ER, dan tabel label per jendela.

---

## 9. Pertanyaan cepat ("kenapa pakai ini, bukan itu?")

| # | Pertanyaan | Jawaban singkat | Rujukan |
|---|---|---|---|
| 1 | Log-return, bukan harga? | Harga punya akar unit; Hurst pada harga ≈ 1 | Teori 2.1.2; ★ Lo (1991) |
| 2 | Ambang kuantil, bukan tetap 0,5? | R/S bias ke atas (min ±0,46 pada BTC); ambang 0,45/0,55 membuat anti-persistent kosong | Couillard & Davison (2005) ★ |
| 3 | Kuantil dari data latih saja? | Mencegah kebocoran distribusi masa depan | López de Prado (2018) |
| 4 | 3 seed + ensemble? | Hasil per seed bervariasi (1H 79,65–81,00%); ensemble mengurangi varians | — |
| 5 | Label smoothing 0,02, L2, early stopping? | Regularisasi terhadap label berderau di sekitar ambang | — |
| 6 | Bobot kelas? | Random-like hanya ±11%; tanpa bobot, model mengabaikannya | ★ Sokolova & Lapalme (2009), *Information Processing & Management*, 45(4), 427–437 |
| 7 | Metrik selain akurasi? | BA dan MCC tahan terhadap ketidakseimbangan kelas | Brodersen (2010) ★; ★ Chicco & Jurman (2020), *BMC Genomics*, 21, 6 |
| 8 | FastAPI, bukan Flask/Django? | Asinkron, validasi Pydantic, dokumentasi OpenAPI otomatis; cocok untuk API model | — |
| 9 | Next.js, bukan Streamlit? | Dashboard multi-halaman dengan login, notifikasi, dan grafik interaktif; Streamlit terbatas untuk produk multi-pengguna | — |
| 10 | Parquet, bukan basis data? | Data deret waktu kolumnar, baca cepat, satu penulis; cukup untuk skala ini | — |
| 11 | Stride 4, bukan 1? | Stride 1 memberi 4× jendela yang 99,8% sama; biaya naik tanpa informasi baru | — |
| 12 | Kenapa tidak memprediksi? | Studi horizon: prediksi 4H kalah dari baseline persistensi | Lampiran D |
| 13 | τ = 0,75 untuk "ragu"? | Pada validasi, keyakinan ≥ 0,75 benar 85,7% (1H) dan 94,8% (4H) dengan cakupan 25%/49%; label tetap argmax | — |
| 14 | Kenapa tidak deret sintetis sebagai label? | Masuk Saran; detektor latih-sintetis pernah dibuat tetapi tidak dipakai karena label naskah adalah konsensus BTC | — |
| 15 | Kenapa Binance? | Volume terbesar, API publik, data 2019–2026 lengkap | — |

---

## 10. Ringkasan untuk agent berikutnya

### 10.1 Prioritas perbaikan naskah (urut)
1. 🔴 **UAT**: lampirkan data mentah per responden, atau laksanakan UAT bila belum. Selaraskan satu versi (Likert 8 butir, 15 responden).
2. 🔴 **Hapus "Catatan untuk penulis"** di 4.2.2 dan 4.2.3. Isi Tabel 4.4 dengan keluaran aktual dari `ml/artifacts/review/blackbox_evidence.md` dan lampirkan `docs/naskah/gambar/blackbox/*.png`.
3. 🔴 **Tambahkan 4 rujukan yang hilang** di Daftar Pustaka (Brodersen, Combrisson & Jerbi, Drummond & Holte, Shintate & Pichl).
4. 🔴 **Akui keterbatasan statistik**: uji binomial mengabaikan tumpang tindih jendela. Nyatakan walk-forward (64,82%/57,23%) sebagai angka generalisasi utama, dan laporkan akurasi validasi.
5. 🔴 **Sensitivitas ambang ER** (0,60/0,35/0,85) dan **sweep eksponen bobot kelas pada validasi** di lampiran.
6. 🟠 Tambahkan subbab **metode pengembangan perangkat lunak** (prototyping/iteratif) di Bab 3.
7. 🟠 Tambahkan **tabel ablasi** (tanpa ER, tanpa SWT, tanpa attention) dan sikap jujur tentang peran SWT dan attention.
8. 🟠 Tambahkan pembahasan **Markov-switching/HMM** dan 2–3 penelitian terdahulu 2021–2026.
9. 🟠 Perbaiki redaksi **manfaat praktis** (alat bantu informasi, bukan pemilih strategi yang terbukti).
10. 🟠 Tambahkan tabel **KNF-02** (waktu respons) ke Bab 4.2.
11. 🟠 Ubah **KF-07** ("menampilkan hasil pengujian").
12. 🟡 Tabel 4.1: TensorFlow 2.19 (CPU), bukan 2.15/GPU.
13. 🟡 Tambahkan baseline persistence ke Tabel D.1 (studi horizon).
14. 🟡 Ganti Gambar 4.1–4.3 dengan tangkapan layar baru, dan tambahkan Gambar halaman Fokus Model (attention).

### 10.2 Penilaian simulasi (bila sidang hari ini)

| Aspek | Nilai | Catatan |
|---|---|---|
| Perumusan masalah dan kontribusi | B+ | Masalah jelas; manfaat praktis perlu diredaksi ulang |
| Tinjauan pustaka | B− | Kurang penelitian terbaru dan pembanding model regime; 4 rujukan hilang |
| Metodologi (rekayasa data dan model) | B+ | Protokol tanpa kebocoran kuat; ambang ER dan bobot kelas belum dijustifikasi |
| Implementasi perangkat lunak | A− | Model aplikasi identik dengan evaluasi; 344 tes lulus; black-box 7/7 dengan bukti; KNF-02 terpenuhi |
| Pengujian dan hasil | B | Pelaporan BA dan per kelas baik; validasi < uji dan uji binomial perlu diakui; UAT belum terverifikasi |
| Kejujuran dan konsistensi | B+ | Banyak keterbatasan sudah diakui; tinggal UAT dan catatan penulis |
| **Perkiraan keseluruhan** | **B+ (lulus dengan revisi)**, dengan syarat butir 1–3 di 10.1 diselesaikan | Tanpa data mentah UAT, risiko terbesar ada di 4.2.3 |

### 10.3 Berkas bukti yang perlu dibuka agent berikutnya
- `ml/artifacts/review/README.md`: indeks dan ringkasan temuan.
- `ml/artifacts/review/full_metrics.md`: confusion matrix, BA, MCC, validasi, sweep bobot kelas.
- `ml/artifacts/review/ablation_no_er.md`, `ablation_swt_attention.md`: ablasi.
- `ml/artifacts/review/random_band_check.md`: pita acak dan surrogat.
- `ml/artifacts/review/market_pivot_independent.md`: kondisi pasar |t| ≥ 1 dan ≥ 2.
- `ml/artifacts/review/horizon_study.md`: identifikasi dibandingkan prediksi, dengan baseline.
- `ml/artifacts/review/blackbox_evidence.md`: BB-01..07 dan KNF-02.
- `ml/artifacts/review/attention_stats.md`: sebaran bobot attention.
- `ml/artifacts/review/number_check.md`, `testing_evidence.md`, `app_verification.md`.
- `docs/naskah/gambar/` dan `docs/naskah/gambar/blackbox/`: tangkapan layar.

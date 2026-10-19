# Rencana Pengembangan Skripsi (8 minggu)

> **Posisi terakhir (2026-10-20).** Ruang lingkup dikunci (lihat "Ruang
> lingkup final"). Fase 0 sedang dijalankan ulang (1H walk-forward dst.).
> Fase 1: praregistrasi dikunci, generator + kalibrasi + skrip benchmark
> selesai, cache data selesai; pelatihan benchmark menunggu Fase 0. Data 19 aset
> untuk uji generalisasi sudah diunduh; praregistrasi generalisasi dikunci.
> Di luar skripsi inti: dashboard (login Firebase, Regime → Strategi,
> notifikasi Telegram menunggu kredensial) dan halaman presentasi.

Ditulis 2026-10-19, ruang lingkup direvisi 2026-10-20. Fokus tetap
**identifikasi** regime (nowcasting):

1. Kebenaran regime tidak lagi didefinisikan sebagai keluaran Hurst-DFA.
   Regime dianggap laten; R/S, DFA, dan model sama-sama alat identifikasi yang
   diadu pada data sintetis dengan H diketahui.
2. **Detektor dilatih pada data sintetis, bukan pada BTC**, sehingga tidak
   bergantung pada satu aset, lalu diterapkan tanpa latih ulang ke 20 aset
   kripto, emas, dan saham Indonesia (permintaan dosen: sistem tidak hanya
   untuk BTC).
3. Kegunaan dibuktikan lewat masalah nyata: **pemilihan strategi**
   (momentum vs mean-reversion vs tidak trading) di semua aset.

## Usulan judul

> Sistem Identifikasi Regime Persistensi Lintas Aset untuk Pemilihan Strategi
> Trading: Model Pembelajaran Mesin Berbasis Data Sintetis pada Kripto, Emas,
> dan Saham Indonesia

## Masalah nyata

Strategi momentum menguntungkan saat pasar persisten dan merugi saat pasar
berbalik; mean-reversion sebaliknya. Trader dan bot umumnya memakai satu
strategi di semua kondisi dan di semua aset. Skripsi menjawab: apakah regime
yang teridentifikasi saat ini, oleh sistem yang tidak dilatih pada aset
tersebut, dapat dipakai memilih strategi yang tepat setelah biaya transaksi?

## Rumusan masalah

| # | Rumusan | Bukti | Praregistrasi |
|---|---|---|---|
| RM1 | Seberapa akurat R/S dan DFA mengidentifikasi regime pada sampel terbatas dengan ekor tebal dan volatility clustering? | Benchmark sintetis | `praregistrasi_fase1_sintetis.md` |
| RM2 | Apakah model yang dilatih pada data sintetis berkarakter kripto lebih akurat daripada R/S dan DFA? | Benchmark sintetis | sama |
| RM3 | Apakah regime yang dideteksi berbeda perilaku masa depannya secara nyata, di BTC dan aset lain? | Uji validitas ke depan lintas 20 aset | `praregistrasi_generalisasi_aset.md` |
| RM4 | Apakah pemilihan strategi berdasarkan regime memberi kinerja bersih lebih baik daripada strategi tunggal, lintas aset? | Backtest walk-forward + uji SPA | Fase 2 (belum ditulis) |
| RM5 | Seberapa besar protokol evaluasi bocor menggelembungkan hasil? | Studi kebocoran BTC (Bab 4 lama) | `praregistrasi_addendum.md` |

## Ruang lingkup final (dikunci 2026-10-20)

| Masuk skripsi | Dikeluarkan |
|---|---|
| Fase 1: benchmark sintetis | Pelatihan gabungan lintas aset (bocor waktu, aset kripto bergerak bersama) |
| Detektor sintetis diterapkan ke 20 aset | Absorption / order flow → saran penelitian lanjutan |
| Model lama latih-BTC sebagai pembanding | Setup engine → lampiran |
| Fase 2: pemilihan strategi di semua aset | Deteksi pergantian regime → hanya bila waktu tersisa |
| Studi kebocoran BTC (Bab 4 lama) | 4H untuk saham; 1H saham/emas berjangka (data gratis hanya ±2 tahun) |
| Dashboard + Telegram sebagai alat demo | Fitur dashboard baru |

## Jadwal sisa

| Minggu | Pekerjaan |
|---|---|
| 1 | Selesaikan Fase 0 dan benchmark Fase 1 → detektor terpilih |
| 2 | Uji generalisasi 20 aset (D-sintetis vs D-BTC vs D-konsensus) |
| 3–4 | Praregistrasi lalu jalankan Fase 2 (pemilihan strategi lintas aset) |
| 5–6 | Tulis Bab 3–5 |
| 7–8 | Cadangan dan persiapan sidang |

## Posisi terhadap literatur

Penelusuran 2026-10-19. Sebagian besar baru dibaca dari abstrak; periksa full
text sebelum dikutip.

### Landasan (bukan sumber novelty)

| Rujukan | Temuan | Dipakai untuk |
|---|---|---|
| Bariviera (2017), *Economics Letters* | DFA sliding window: return BTC makin efisien, volatilitas tetap bermemori panjang | Dasar rolling window |
| Takaishi & Adachi (2019), *Asia-Pacific Financial Markets* | H < 0,5 sebelum 2013, mendekati 0,5 sesudahnya, tetapi berulang kali turun di bawah 0,5 | Regime BTC berubah-ubah |
| Kyriazis (2019), *JRFM* 12(2):67 (survei) | Kesimpulan efisiensi kripto saling bertentangan antar studi | Mendukung ketidaksepakatan R/S–DFA 47% (Bab 4 §4.1) |
| Barunik & Kristoufek (2010), *Physica A* | Pada ekor tebal R/S menuju 0,5, DFA menaksir terlalu rendah | Menjelaskan ambang DFA (0,47–0,52) jauh di bawah R/S (0,57–0,60) |

### Paling dekat dengan project ini

| Rujukan | Isi | Selisih dengan project ini |
|---|---|---|
| Di Persio & Dufera (2024), *Mathematics* 12(22):3483 | Neural network dilatih dengan target R/S dan DFA, 446 saham S&P 500 | **Sama dengan desain lama** (model meniru label R/S-DFA). Wajib dikutip; alasan utama label tidak lagi berasal dari estimator |
| Raubitzek dkk. (2023), *Entropy* 25(12):1671 | LightGBM/MLP/CatBoost dilatih pada fBm dan fractional Lévy motion, mengalahkan R/S dan DFA; diterapkan ke indeks saham AS | Tanpa volatility clustering dan lonjakan, bukan kripto, regresi H (bukan klasifikasi regime dengan abstain), tanpa strategi trading |
| Mukherjee dkk. (2023), *IJCSE*; arXiv 2401.01789 (LSTM pada fBm) | Estimasi H dengan neural network; fokus kecepatan dan akurasi | Proses sintetis sederhana, tanpa aplikasi pasar |
| Chang, Lizardi & Shah (2022), arXiv 2205.11122 (preprint) | Hurst > 0,5 → momentum, < 0,5 → mean-reversion; return lebih tinggi, risiko lebih tinggi | Bukan BTC; abstrak tidak menyebut biaya, out-of-sample, atau uji data snooping |
| *Mathematics* 12(18):2911 (2024) | Pairs trading kripto: spread dengan Hurst anti-persisten lebih cepat kembali ke rata-rata | Pairs trading, bukan pemilihan strategi satu aset; mendukung hipotesis RM4 |
| Martínez-Farías dkk. (2025), *Computational Economics* 66(5) | Kripto per menit: makin jauh H dari 0,5, makin kecil galat ramalan LSTM | Data 2 × 3 minggu; tugas forecasting |

### Celah yang diisi skripsi ini

1. Benchmark identifikasi regime pada data sintetis **berkarakter kripto**:
   volatility clustering (GARCH), ekor tebal, lonjakan, dan H yang berganti di
   dalam window (skenario S3–S5), dalam bentuk **klasifikasi tiga regime dengan
   kelas abstain**, bukan regresi H. Raubitzek dkk. (2023) hanya menguji fBm
   dan fLm.
2. Pemilihan strategi berbasis regime pada **BTC** dengan walk-forward, biaya
   transaksi nyata, uji Hansen SPA, dan praregistrasi. Studi terdekat (Chang
   dkk., 2022) adalah preprint pada saham tanpa uji tersebut di abstraknya.
3. Bukti kuantitatif bahwa protokol evaluasi membalik kesimpulan (studi
   kebocoran, RM5).

Klaim yang **tidak** boleh dipakai sebagai novelty: "Hurst BTC berubah-ubah",
"neural network meniru R/S/DFA", dan "ML lebih akurat dari R/S/DFA pada fBm".

## Fase 0 — Perbaikan wajib (minggu 1)

- [x] Satuan biaya Tabel 4.10 (USDT tertulis sebagai R) — `run_setup_sensitivity_grid.py`, `bab4_hasil.md`.
- [x] `threshold_source: train_only` menjadi konfigurasi utama; `full_history` jadi sensitivitas (kode + adendum §5; run ulang berjalan).
- [ ] Walk-forward dijadikan angka utama; hapus narasi "periode mudah" §4.4.1 atau buktikan dengan statistik per periode.
- [ ] Seragamkan N uji (1.619/1.622, 257/262) dan laporkan p < 1/B, bukan 0,0000.
- [ ] Bab 4 §4.1: bahas bias R/S. Pada deret acak murni n = 500 taksiran R/S rata-rata 0,59 (`threshold_criteria.md`), hampir sama dengan ambang bawah kuantil R/S di BTC (0,572), sehingga label "persistent" versi R/S sebagian besar dapat berupa bias estimator.
- [ ] Baseline tambahan: regresi logistik, LightGBM (50 fitur), Statistical Jump Model, HMM.
- [ ] Repo git sendiri di folder project (saat ini repo git berada di folder home) dan commit praregistrasi sebelum eksperimen baru, agar waktunya dapat diverifikasi.

## Fase 1 — Benchmark sintetis (minggu 1) → RM1, RM2

Generator `ml/src/synthetic_regimes.py`, H diketahui pasti (detail final dan kalibrasi di praregistrasi + adendum 1):

| Skenario | Proses |
|---|---|
| S1 bersih | fGn |
| S2 ekor tebal | fGn dengan inovasi Student-t (ν = 3–5) |
| S3 volatility clustering | fGn × volatilitas GARCH(1,1) dikalibrasi ke BTC |
| S4 lengkap | S2 + S3 + lompatan (jumps) |
| S5 regime berganti | H berubah di dalam window (titik ganti acak) |

- Label kebenaran dari H pembangkit dengan **ambang absolut** 0,47 / 0,53 (titik impas ekonomi strategi setelah biaya), sensitivitas 0,45 / 0,55. Rancangan lengkap dan terkunci: `docs/praregistrasi_fase1_sintetis.md`.
- Pembanding: R/S, R/S termodifikasi Lo (1991), DFA-1, uji VR Lo-MacKinlay, MLP, LightGBM, Hybrid PS.
- Pembanding kunci untuk celah literatur: model yang **dilatih hanya pada fBm/fLm** (setara Raubitzek dkk., 2023) lalu diuji pada S3–S5. Bila model yang dilatih pada data berkarakter kripto tidak lebih baik dari ini, celah 1 tidak terbukti.
- Metrik: BA dan Macro F1 terhadap regime sebenarnya, bias dan RMSE estimasi H, sebagai fungsi panjang window (128 / 256 / 500).
- Set uji sintetis dibangkitkan dengan seed terpisah dan tidak pernah dipakai untuk tuning.

## Generalisasi lintas aset (minggu 2) → RM3

Rancangan terkunci: `docs/praregistrasi_generalisasi_aset.md`. Detektor
terpilih Fase 1 (dilatih sintetis) diterapkan tanpa latih ulang ke 20 aset
(kripto 1H, PAXG 1H, emas berjangka dan saham IDX 1D), dibandingkan dengan
model latih-BTC dan konsensus R/S–DFA. Ukuran: pemisahan perilaku masa depan
(VR maju) antara regime persistent dan anti-persistent.

## Fase 2 — Pemilihan strategi lintas aset (minggu 3–4) → RM4

Dijalankan pada seluruh aset di praregistrasi generalisasi §2, dengan aturan,
parameter, dan biaya yang ditetapkan sebelum Fase 2 dimulai. Semua sinyal hanya
memakai data ≤ t; posisi dibuka pada bar berikutnya.

| Strategi | Aturan |
|---|---|
| Momentum | arah = tanda return k bar terakhir |
| Mean-reversion | arah = kebalikan z-score harga terhadap rata-rata bergerak |
| Buy & hold | pembanding pasif |
| **Switching (usulan)** | persistent → momentum, anti-persistent → mean-reversion, random-like → tidak masuk |
| Switching dengan regime R/S, DFA, Jump Model, HMM | pembanding identifikasi |

- Biaya: taker 0,075% per sisi + slippage realistis (mis. 1–2 bps), bukan 1 tick.
- Walk-forward expanding, parameter strategi dipilih hanya di data latih tiap fold.
- Metrik: return bersih, Sharpe, Sortino, max drawdown, turnover.
- Uji: beda Sharpe (Ledoit-Wolf 2008), Hansen SPA terhadap seluruh pembanding, regresi return strategi pada dummy regime dengan HAC.
- Hipotesis, aturan, dan parameter ditulis di praregistrasi **sebelum** dijalankan.

Risiko yang diketahui: temuan "Hurst-Direction Disconnect" (§4.7.1)
menunjukkan persistensi tidak otomatis berarti momentum arah. Hasil negatif
tetap sah bila dipraregistrasi; regime dari estimator yang lebih akurat (Fase
1) juga bisa memberi gambaran berbeda.

## Fase 3 — Penulisan dan dashboard (minggu 5–6)

- Bab 3–5 ditulis ulang mengikuti RM1–RM5; setup engine dipindah ke lampiran.
- Dashboard: halaman "Regime saat ini → strategi yang direkomendasikan" beserta
  bukti historis per regime (kinerja tiap strategi, interval kepercayaan).

## Fase 4 — Cadangan dan persiapan sidang (minggu 7–8)

- Perbarui `tanya_jawab_sidang.md` dengan pertanyaan sirkularitas, N_eff, dan
  biaya transaksi.
- Jika waktu tersisa: deteksi pergantian regime (praregistrasi Fase 1 §8).

## Yang dipertahankan

Pipeline data, fitur PS dan statistik, arsitektur model, purge, scaler dari
data latih, walk-forward, studi kebocoran, block bootstrap + Holm.

## Rencana cadangan bila hasil model tidak bagus

Ditulis 2026-10-19, SEBELUM hasil 1H dengan `train_only` keluar. Hasil 4H
sudah ada: Hybrid PS setara MLP (H5), kalah dari MLP di 4/5 fold walk-forward.

### Aturan yang tidak boleh dilanggar

- Tidak mengubah model, seed, ambang, atau fitur lalu menjalankan ulang sampai
  angka uji membaik (p-hacking). Riwayat git dan praregistrasi akan
  memperlihatkannya.
- Tidak kembali ke `full_history` karena angkanya lebih bagus; alasan
  perpindahan sudah tercatat di `praregistrasi_addendum.md` §5.
- Semua hasil dilaporkan, termasuk yang negatif.
- Perbaikan model hanya boleh bila (a) ditulis di praregistrasi baru sebelum
  dijalankan, dan (b) seleksinya memakai validasi atau walk-forward, bukan data
  uji. Hasilnya dilaporkan sebagai eksperimen lanjutan, terpisah dari hasil
  utama.

### Skenario hasil 1H

| Hasil | Arti | Tindakan |
|---|---|---|
| A. Hybrid PS > MLP, setara LightGBM | Keunggulan dari fitur PS, bukan arsitektur | Klaim turun menjadi "kompetitif dengan model terkuat"; kontribusi model = fitur PS |
| B. Hybrid PS setara MLP dan LightGBM | Arsitektur kompleks tidak menambah nilai | Model untuk Fase 2 dan bot = model paling sederhana yang setara (MLP/LightGBM), alasan ditulis terbuka |
| C. Hybrid PS lebih buruk | Overfit pada data efektif yang kecil | Seperti B, ditambah pembahasan: N_eff kecil, sinyal ada di statistik ringkasan (H2, H3, H6) |

Pada ketiga skenario, judul tidak menyebut arsitektur tertentu ("Model
Pembelajaran Mesin" bila B/C).

### Pusat kontribusi digeser

Perbandingan Hybrid PS vs pembanding bukan lagi kontribusi utama. Kontribusi
skripsi bertumpu pada:

1. Benchmark sintetis (Fase 1): akurasi R/S, DFA, dan model ML pada kondisi
   berkarakter kripto. Hasil apa pun bernilai: ML unggul memberi alasan
   memakainya; estimator klasik unggul berarti "estimator klasik cukup untuk
   kondisi X".
2. Pemilihan strategi (Fase 2): positif atau negatif sama-sama dilaporkan.
3. Studi kebocoran (RM5): tidak bergantung pada model mana yang menang.

### Arah perbaikan model (urut dampak)

1. Label yang benar: latih dan uji pada data sintetis dengan regime diketahui
   (Fase 1), alih-alih meniru label R/S-DFA yang hanya sepakat 53%.
2. Model paling sederhana yang setara.
3. Kelas abstain terkalibrasi: model boleh menjawab "tidak yakin" dan bot diam.
4. Arsitektur baru hanya bila ada alasan kuat.

Tetap identifikasi (nowcasting). Peramalan harga tidak diambil (di luar
pembatasan masalah Bab 1, novelty rendah, waktu tidak cukup). Peramalan regime
tidak diambil karena baseline naif sudah mengalahkan model pada horizon pendek
(Bab 4 Tabel 4.9e).

### Perluasan cadangan: deteksi pergantian regime

Diaktifkan bila skenario B/C terjadi, atau bila waktu Fase 1 memungkinkan.
Tetap tugas identifikasi, dengan dimensi waktu.

- Pertanyaan: saat regime berganti, seberapa cepat tiap metode mengenalinya
  dan seberapa sering salah alarm?
- Alasan: R/S dan DFA atas window 500 bar lambat secara alami. Di sini model
  sekuens punya alasan dipakai, sedangkan pada tugas identifikasi statis urutan
  waktu terbukti tidak membantu (H2).
- Data: skenario S5 (H berganti di titik yang diketahui) ditambah urutan
  regime panjang dengan beberapa titik ganti.
- Metrik: keterlambatan deteksi (bar sejak titik ganti sampai metode
  menyatakan regime baru), tingkat salah alarm per 1.000 bar, dan proporsi
  pergantian yang tidak terdeteksi.
- Pembanding: R/S dan DFA rolling dengan aturan konfirmasi yang sama, Jump
  Model, HMM, MLP/LightGBM, model sekuens.
- Kegunaan: menjadi dasar notifikasi Telegram "regime berganti" dan menjawab
  kebutuhan pengguna grid bot yang perlu tahu secepat mungkin saat pasar mulai
  trending.
- Hipotesis dan aturan konfirmasi ditulis di praregistrasi Fase 1 sebelum
  dijalankan.

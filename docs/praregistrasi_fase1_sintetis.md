# Praregistrasi Fase 1: Benchmark identifikasi regime pada data sintetis

Status: **dikunci 2026-10-20** (commit "Praregistrasi Fase 1 (dikunci)").
Isi tidak boleh diubah; perubahan ditulis sebagai adendum bertanggal di bagian
bawah.

Rumusan masalah yang dijawab: RM1 dan RM2 (`docs/rencana_pengembangan.md`).

## 1. Tujuan

Mengukur seberapa tepat metode klasik (R/S, DFA, R/S termodifikasi Lo, variance
ratio) dan model pembelajaran mesin mengenali regime persistensi pada deret
yang **regime aslinya diketahui**, dalam kondisi yang menyerupai return BTC 1H:
ekor tebal, volatility clustering, dan lonjakan harga.

Ini menggantikan kunci jawaban Hurst-DFA pada data BTC, yang hanya sepakat pada
53% window dan tidak dapat dipakai menilai estimator itu sendiri.

## 2. Kebenaran dasar

- Setiap deret dibangkitkan dari fractional Gaussian noise (fGn, Davies-Harte,
  `hurst_dfa.fbm_increments`) dengan eksponen **H** yang diketahui.
- Label dari H pembangkit dengan **ambang absolut**:

  | Konfigurasi | Anti-persistent | Random-like | Persistent |
  |---|---|---|---|
  | **Utama** | H < 0,47 | 0,47 ≤ H ≤ 0,53 | H > 0,53 |
  | Sensitivitas | H < 0,45 | 0,45 ≤ H ≤ 0,55 | H > 0,55 |

- Dasar ambang utama (`ml/src/threshold_criteria.py`,
  `ml/artifacts/threshold_criteria.md`), dihitung sebelum dokumen ini dikunci
  dan tanpa melihat kinerja model mana pun: pada data sintetis, strategi
  mean-reversion baru untung setelah biaya bila H < 0,475 dan momentum bila
  H > 0,531 (strategi dan biaya = `regime_strategy_demo.py`). Di antara keduanya
  tidak ada strategi yang menguntungkan; itulah definisi praktis "random-like".
  Titik impas dibulatkan simetris menjadi ±0,03 di sekitar 0,5. Ambang
  sensitivitas = konvensi literatur/praktisi.
- Keterbatasan yang diakui: titik impas bergantung pada strategi, lookback, dan
  biaya simulasi. Bila strategi Fase 2 berbeda, ambang tetap dan perbedaan itu
  dibahas.
- Pengambilan sampel **seimbang per kelas**: kelas dipilih dengan peluang sama,
  lalu H ditarik seragam di dalam rentang kelas (anti-persistent [0,30; 0,47),
  random-like [0,47; 0,53], persistent (0,53; 0,70]). Tanpa ini kelas
  random-like hanya ±15% sampel. Untuk konfigurasi sensitivitas, set uji yang
  sama dilabel ulang dengan ambang 0,45/0,55 (proporsi kelas tidak seimbang;
  metrik BA tetap sah).
- Pada S5, label adalah regime **segmen terakhir** window (lihat §3).
- Catatan dari kriteria statistik (dasar ekspektasi, bukan ambang): pada deret
  acak murni n = 500, taksiran R/S rata-rata 0,59 (rentang 95%: 0,50–0,68) dan
  DFA 0,50 (0,39–0,62). Galat estimator jauh lebih lebar dari pita ±0,03,
  sehingga kelas random-like diperkirakan paling sulit dikenali oleh metode
  apa pun.

## 3. Skenario

Semua skenario diskalakan ke simpangan baku 0,0066 per bar (BTC 1H).

| Kode | Proses | Alasan |
|---|---|---|
| S1 | fGn Gaussian | Pembanding bersih, setara literatur |
| S2 | fGn ditransformasi monoton ke marginal Student-t (ν = 3) lewat copula Gaussian | Ekor tebal. Transformasi monoton ganjil berperingkat Hermite 1 sehingga eksponen memori jangka panjang tetap H |
| S3 | r_t = σ_t · z_t, z = fGn (S1), log σ_t = AR(1) independen dari z | Volatility clustering tanpa mengubah struktur tanda z, sehingga H kebenaran tetap H milik z |
| S4 | S2 + S3 + lonjakan Poisson | Paling mirip BTC. Lonjakan: peluang 0,002 per bar, ukuran N(0, (10·σ_t)²) |
| S5 | Seperti S4, tetapi H berganti satu kali di titik acak dalam 40–90% panjang window, dari kelas satu ke kelas lain | Regime berganti di dalam window |

Kalibrasi S3/S4 dilakukan **sebelum** eksperimen dengan skrip terpisah, hanya
memakai statistik deskriptif return BTC 1H 2019–2026 (bukan label, bukan hasil
strategi):

| Statistik BTC 1H | Nilai |
|---|---|
| Kurtosis return | 50,1 |
| Autokorelasi \|r\| lag 1 / 5 / 24 / 100 | 0,286 / 0,199 / 0,174 / 0,115 |

Parameter AR(1) log σ_t (φ, simpangan baku inovasi) dipilih dengan grid agar
autokorelasi \|r\| sintetis berada dalam ±0,05 dari angka BTC pada keempat lag.
Nilai terpilih dicatat di adendum sebelum §5 dijalankan.

## 4. Data

- Panjang window n ∈ {128, 256, 500}. Utama: n = 500 (sama dengan BTC).
- Tiap skenario × n: 12.000 deret latih, 3.000 validasi, 3.000 uji.
- Deret independen satu sama lain, sehingga tidak ada tumpang tindih dan tidak
  perlu purge. Satu sampel = satu deret.
- Seed terpisah untuk latih, validasi, dan uji (dasar 1000, 2000, 3000 + indeks).
  Set uji dibangkitkan sekali dan **hanya dipakai satu kali**, setelah seluruh
  model dan ambang dikunci.

## 5. Metode yang dibandingkan

**Estimator klasik**, masing-masing dalam dua varian:
- *naif*: ambang absolut 0,45 / 0,55 pada nilai estimasinya;
- *terkalibrasi*: dua ambang dipilih pada set **validasi** untuk memaksimalkan
  balanced accuracy, lalu dibekukan.

| Estimator | Sumber |
|---|---|
| R/S | `hurst_dfa.hurst_rs` |
| DFA-1 | `hurst_dfa.dfa_alpha` |
| R/S termodifikasi Lo (1991), lag Andrews | diimplementasikan baru, dengan unit test |
| Variance ratio: H_VR = ½·(1 + log₂ VR(2)) dan kemiringan log VR(q) terhadap log q | `structural_features.variance_ratio` |
| Konsensus R/S–DFA (definisi label BTC saat ini) | `regime_labeling.label_from_exponents` |

**Model pembelajaran mesin** (input = 50 fitur statistik dan/atau sekuens PS,
fungsi yang sama dengan pipeline BTC; Hurst dan DFA tidak menjadi input):
regresi logistik, LightGBM, MLP, Hybrid PS. Hyperparameter sama dengan Bab 4,
tidak disetel ulang.

Dua rezim pelatihan:
- **M-fBm**: dilatih hanya pada S1. Setara pendekatan Raubitzek dkk. (2023).
- **M-kripto**: dilatih pada campuran seimbang S1–S4.

Model terbaik tiap rezim dipilih dengan BA **validasi** (campuran S1–S4, n = 500).

## 6. Metrik

- Utama: balanced accuracy (BA) terhadap kelas sebenarnya.
- Pendukung: Macro F1, recall per kelas, matriks konfusi.
- Deskriptif untuk estimator klasik: bias dan RMSE estimasi H terhadap H
  sebenarnya.
- Interval kepercayaan 95%: bootstrap berpasangan atas deret uji (B = 2.000).
  Deret independen, jadi bootstrap biasa sah.

## 7. Hipotesis dan kriteria keputusan

Semua pada n = 500 dan ambang utama kecuali disebut lain. "Terbukti" = batas
bawah CI95 selisih BA > 0. Koreksi Holm atas H1–H3 (K = 3). H4 eksploratif.
H1–H3 diulang dengan ambang sensitivitas (0,45/0,55) dan dilaporkan
berdampingan; kesimpulan utama tetap dari ambang utama.

| ID | Pernyataan | Pembanding |
|---|---|---|
| H1 | Akurasi estimator klasik turun pada kondisi berkarakter kripto | BA estimator klasik terkalibrasi terbaik: S1 − S4 > 0 |
| H2 | Model M-kripto lebih akurat daripada estimator klasik pada S4 | BA M-kripto − BA estimator klasik terkalibrasi terbaik, pada S4 > 0 |
| H3 | Pelatihan berkarakter kripto memberi nilai tambah dibanding pelatihan fBm saja | BA M-kripto − BA M-fBm, pada S4 > 0 |
| H4 (eksploratif) | Keunggulan model lebih besar pada window pendek | Selisih H2 pada n = 128 dibanding n = 500 |

"Estimator klasik terkalibrasi terbaik" dipilih dengan BA validasi, bukan uji.

### Tafsir hasil (ditetapkan sekarang)

| Hasil | Kesimpulan yang ditulis |
|---|---|
| H2 dan H3 terbukti | Celah 1 terisi: model yang dilatih pada data berkarakter kripto lebih akurat dari estimator klasik dan dari pendekatan fBm-saja |
| H2 terbukti, H3 tidak | Model ML lebih akurat dari estimator klasik, tetapi pelatihan berkarakter kripto tidak menambah nilai; kontribusi novelty berkurang |
| H2 tidak terbukti | Estimator klasik terkalibrasi sudah memadai pada kondisi ini; dashboard dan Fase 2 memakai estimator klasik terkalibrasi |
| H1 tidak terbukti | Kondisi kripto tidak menurunkan akurasi estimator klasik; dilaporkan apa adanya |

Semua hasil dilaporkan, termasuk yang negatif.

## 8. Perluasan cadangan: deteksi pergantian regime

Dijalankan bila skenario B/C terjadi pada hasil 1H Fase 0, atau bila waktu
memungkinkan (`rencana_pengembangan.md`, rencana cadangan).

- Data: deret panjang (20.000 bar) dengan 8–12 titik ganti regime pada posisi
  acak, proses S4.
- Setiap metode dijalankan bergulir (window 500, langkah 4 bar, sama dengan BTC)
  dengan aturan konfirmasi yang sama dengan notifikasi Telegram: K = 3 window
  berturut-turut berlabel sama.
- Metrik: keterlambatan deteksi (bar sejak titik ganti sampai regime baru
  terkonfirmasi), salah alarm per 1.000 bar, dan proporsi pergantian yang tidak
  terdeteksi.
- H5: model terpilih mendeteksi pergantian lebih cepat (median keterlambatan
  lebih kecil) daripada konsensus R/S–DFA, tanpa salah alarm lebih banyak.

## 9. Yang tidak dilakukan

- Tidak ada penyetelan hyperparameter pada set uji.
- Data BTC tidak dipakai di Fase 1 selain statistik kalibrasi di §3.
- Skenario, ambang kelas, dan hipotesis tidak diubah setelah hasil terlihat.

## 10. Keluaran

- `ml/src/synthetic_benchmark.py` (generator S1–S5 + evaluasi), dengan unit test
  untuk generator (H sebenarnya terpulihkan pada S1 oleh estimator dengan
  n besar) dan untuk R/S termodifikasi Lo.
- `ml/artifacts/synthetic_benchmark.{json,md}` dan gambar BA per skenario × n.

## Adendum

### Adendum 1 (2026-10-20): hasil kalibrasi, sebelum §5 dijalankan

Belum ada estimator maupun model yang dijalankan pada data sintetis saat
adendum ini ditulis.

**Volatilitas stokastik S3/S4** (`ml/src/calibrate_synthetic.py`,
`ml/artifacts/synthetic_calibration.json`): φ = 0,995, η = 0,20. Autokorelasi
\|r\| S4 = 0,247 / 0,245 / 0,214 / 0,110 pada lag 1 / 5 / 24 / 100 (BTC: 0,286 /
0,199 / 0,174 / 0,115); simpangan maksimum 0,046, lolos toleransi ±0,05.

**Ketidaksesuaian ekor yang ditemukan.** Kurtosis per window 500 bar: BTC median
7,8 (persentil 10–90: 3,5–27,4); S4 median 23,1 (8,1–110,7). Penyebab: Student-t
ν = 3 dan lonjakan 10σ dari §3. Kurtosis bukan kriteria kalibrasi di §3, dan
desain yang sudah dikunci tidak diubah. Konsekuensinya:

- **S4 tetap persis seperti §3** dan dibaca sebagai **uji tekanan** yang lebih
  berat dari BTC. H1–H3 tetap diuji pada S4.
- **S4k ditambahkan sebagai skenario eksploratif**: Student-t ν = 4, lonjakan
  peluang 0,002 dengan ukuran N(0, (3·σ_t)²), φ = 0,99, η = 0,18 (dipilih dengan
  grid bersama). Kurtosis per window median 8,7; autokorelasi \|r\| simpangan
  maksimum 0,041. H2 dan H3 diulang pada S4k dan dilaporkan sebagai temuan
  eksploratif tanpa koreksi Holm; tidak menggantikan kesimpulan dari S4.
- Model M-kripto tetap dilatih pada campuran S1–S4 sesuai §5; S4k tidak masuk
  data latih.

### Adendum 2 (2026-10-20): detail implementasi, sebelum benchmark penuh

Hal-hal yang tidak diatur §1–§10, ditetapkan sebelum benchmark penuh
dijalankan (`ml/src/synthetic_benchmark.py`):

1. **Hybrid PS hanya pada n = 500.** Definisi sekuens PS Bab 3 (sub-window 128,
   32 langkah) mensyaratkan (n − 128) habis dibagi 31; hanya n = 500 yang
   memenuhi. Pada n = 256 dan 128 model ML terdiri dari regresi logistik,
   LightGBM, dan MLP. H1–H3 diuji pada n = 500 sehingga tidak terdampak; H4
   (eksploratif) membandingkan model terpilih apa pun pada tiap n.
2. **Satu seed (42)** untuk model neural dan LightGBM. Data latih sintetis
   12.000–48.000 deret independen, jauh lebih besar dari data BTC; variasi antar
   seed diperkirakan kecil. Hyperparameter, batch, epoch, early stopping, dan
   bobot kelas sama dengan Bab 4.
3. **Kalibrasi ambang estimator klasik**: dua ambang dicari pada grid persentil
   1–99 nilai estimasi di set validasi campuran S1–S4 (n yang sama), memaksimalkan
   BA. Estimator terkalibrasi "terbaik" dipilih dengan BA validasi yang sama.
4. **Konsensus R/S–DFA**: bila kedua estimator tidak sepakat, prediksi = "tidak
   pasti" dan dihitung salah untuk semua kelas (sama dengan perlakuan
   `uncertain_rule` di BTC bila dipaksa menjawab). Versi terkalibrasi memakai
   ambang terkalibrasi masing-masing estimator.
5. **Estimator variance ratio**: H_VR2 = ½(1 + log₂ VR(2)); H_slope = ½(1 + kemiringan
   log VR(q) terhadap log q) untuk q = 2…48 (horizon yang sama dengan fitur).
6. **Rezim M-fBm** memakai validasi S1 untuk early stopping; seleksi model kedua
   rezim tetap dengan BA validasi campuran S1–S4 sesuai §5.
7. **H1** membandingkan dua set uji berbeda (S1 vs S4), sehingga bootstrap
   dilakukan terpisah pada tiap set; H2 dan H3 berpasangan pada set uji S4.
8. **Konfigurasi sensitivitas** (0,45/0,55): deret yang sama dilabel ulang, dan
   seluruh kalibrasi serta pelatihan diulang dengan label tersebut.
9. **Uji alur (smoke test)** dengan 300/150/150 deret dijalankan sekali untuk
   memastikan kode tidak error. Keluarannya dibuang dan tidak dilaporkan; seed
   dan ukuran data benchmark penuh tidak diubah setelahnya.

### Adendum 3 (2026-10-20): detektor yang dipasang di sistem selalu model AI

Ditulis saat benchmark penuh sedang berjalan, **sebelum** hasil uji (H1–H4)
tersedia. Yang sudah terlihat di log hanyalah BA **validasi** tahap seleksi
model (dipakai §5 untuk memilih model M-fBm/M-kripto), bukan hasil uji.

Alasan: syarat institusi (program studi informatika) mewajibkan sistem yang
dihasilkan memakai metode AI. Baris "H2 tidak terbukti" pada tabel tafsir §7
semula menyatakan dashboard dan Fase 2 memakai estimator klasik terkalibrasi;
itu berarti sistem bisa berakhir tanpa komponen AI.

Perubahan:

1. Detektor yang dipasang di sistem (dashboard, notifikasi, uji generalisasi,
   Fase 2) adalah **model M-kripto terpilih §5**, apa pun hasil H2.
2. Estimator klasik terkalibrasi terbaik **tetap** menjadi pembanding wajib di
   Fase 1, uji generalisasi, dan Fase 2. Bila H2 tidak terbukti, kesimpulan yang
   ditulis tetap "model AI tidak lebih akurat daripada estimator klasik
   terkalibrasi pada kondisi ini"; pemakaian model AI di sistem dibenarkan oleh
   syarat institusi dan oleh keluaran probabilitasnya (dasar kelas abstain),
   bukan oleh keunggulan akurasi.
3. Hipotesis H1–H4, kriteria, dan data tidak berubah.

### Adendum 4 (2026-10-22): ablasi fitur energi SWT pada detektor resmi

Ditulis sebelum ablasi dijalankan. Belum ada model tanpa fitur SWT yang
pernah dilatih atau dievaluasi.

Alasan: judul skripsi yang disetujui memuat "SWT". Pada detektor resmi, SWT
masuk sebagai 12 fitur rasio energi antar-skala (`swt_energy_w*_d*`) di dalam
50 fitur struktural; sekuens PS tidak memuat SWT. Kontribusi 12 fitur itu
belum pernah diukur.

1. **Varian**: A0 = detektor resmi (50 fitur); A1 = 12 kolom `swt_energy_*`
   dibuang (38 fitur). Arsitektur, data latih/validasi (campuran S1–S4,
   n = 500), ambang utama, dan konfigurasi latih sama dengan
   `train_detector.py`. Setiap varian dilatih dengan seed 42, 43, 44.
2. **Uji**: set uji S1, S2, S3, S4, S4k. BA dilaporkan per seed (rata-rata ±
   simpangan baku).
3. **Hipotesis S-SWT** (pada S4, set uji utama Fase 1): ΔBA = BA(A0) − BA(A1)
   dengan probabilitas rata-rata 3 seed per varian. CI95 dengan bootstrap
   berpasangan per deret (deret uji saling independen), B = 2.000.
   - batas bawah > 0: fitur SWT menyumbang akurasi;
   - CI memuat 0: kontribusi fitur SWT tidak terdeteksi;
   - batas atas < 0: fitur SWT menurunkan akurasi.
4. Hasil apa pun dilaporkan. Detektor resmi **tidak diganti** berdasarkan
   hasil ini (pemilihan model sudah selesai di §5; set uji tidak dipakai
   untuk memilih).
5. Keluaran: `ml/src/swt_ablation.py`, `ml/artifacts/swt_ablation.{json,md}`.

### Adendum 5 (2026-10-22): menjalankan §8 (deteksi pergantian regime) dan kurva abstain

Ditulis sebelum kedua analisis dijalankan. Belum ada deret panjang berganti
regime yang pernah dibangkitkan, dan probabilitas detektor belum pernah
dianalisis terhadap ambang keyakinan.

**A. Deteksi pergantian regime (melaksanakan §8, rincian implementasi)**

1. Data: 40 deret panjang × 20.000 bar (seed `SeedSequence([8000, i])`).
   Jumlah titik ganti 8–12 (seragam), posisi acak dengan panjang segmen minimum
   1.000 bar. Kelas segmen pertama acak; kelas setiap segmen berikutnya dipilih
   acak dari dua kelas lain (selalu berganti). H segmen = `sample_h(kelas)`
   (ambang utama 0,47/0,53). Proses S4: fGn per segmen disambung, lalu ekor
   tebal, volatilitas stokastik, dan lonjakan diterapkan sekali pada seluruh
   deret (sama dengan cara S5).
2. Metode bergulir (jendela 500, langkah 4 bar):
   - **D-sintetis**: detektor resmi, normalisasi per jendela sama dengan sistem;
   - **Konsensus R/S–DFA** naif (ambang 0,47/0,53) — pembanding H5;
   - Konsensus R/S–DFA terkalibrasi dan VR(2) terkalibrasi (ambang Fase 1) — sekunder;
   - **D-sintetis + abstain** (bagian B) — sekunder.
3. Konfirmasi: K = 3 jendela berturut-turut berlabel sama (kelas utama); label
   lain memutus rentetan. Keadaan awal = regime terkonfirmasi pertama.
4. Metrik per titik ganti c (kelas baru k): **keterlambatan** = bar akhir
   jendela pada konfirmasi pertama ke kelas k setelah c, dikurangi c, selama
   sebelum titik ganti berikutnya; bila tidak ada, **terlewat**. **Salah alarm**
   = konfirmasi pergantian ke kelas yang berbeda dari kelas segmen yang memuat
   bar akhir jendela; dilaporkan per 1.000 bar.
5. **H5**: median keterlambatan D-sintetis < konsensus R/S–DFA naif **dan**
   salah alarm tidak lebih banyak. Bootstrap per deret (B = 2.000): terbukti bila
   batas atas CI95 selisih median keterlambatan (D-sintetis − konsensus) < 0 dan
   batas bawah CI95 selisih salah alarm per 1.000 bar ≤ 0. Keterlambatan hanya
   dihitung pada pergantian yang terdeteksi; proporsi terlewat dilaporkan
   berdampingan dan dibandingkan dengan CI95 bootstrap yang sama.

**B. Abstain berdasarkan keyakinan (deskriptif)**

1. Keyakinan = probabilitas kelas tertinggi detektor. Kurva untuk τ = 0,40,
   0,45, …, 0,95: cakupan (proporsi jendela dengan keyakinan ≥ τ) dan BA pada
   jendela tercakup.
2. **Pemilihan τ (validasi campuran S1–S4)**: τ terkecil dengan BA tercakup
   ≥ 0,90. Bila tidak ada, τ dengan BA tercakup tertinggi dengan cakupan ≥ 20%.
3. Pada τ terpilih dilaporkan BA tercakup dan cakupan di uji S4 dan S4k, serta
   proporsi jendela BTC 1H/4H yang akan berlabel "tidak pasti" (dari cache
   sistem). Tidak ada hipotesis; dashboard tidak diubah otomatis oleh hasil ini.

Keluaran: `ml/src/regime_change_study.py`, `ml/artifacts/regime_change_study.{json,md}`.

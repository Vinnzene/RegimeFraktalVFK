# Praregistrasi: Uji generalisasi lintas aset

Status: **dikunci 2026-10-20** (commit "Praregistrasi generalisasi aset
(dikunci)"). Perubahan hanya lewat adendum bertanggal di bagian bawah.

## 1. Pertanyaan

Apakah sistem deteksi regime berlaku lintas aset, bukan hanya pada BTC/USDT?

Detektor utama **tidak dilatih pada aset nyata mana pun**: ia dilatih dan
dipilih pada data sintetis (Fase 1). Karena itu detektor yang sama dapat
diterapkan ke semua aset tanpa latih ulang. Model lama yang dilatih pada BTC
dipakai sebagai pembanding untuk menjawab: apakah pendekatan lama hanya cocok
untuk BTC?

## 2. Aset (ditetapkan sekarang, tidak ditambah/dikurangi setelah hasil terlihat)

| Kelompok | Aset | Timeframe | Sumber |
|---|---|---|---|
| Kripto | BTC, ETH, BNB, SOL, XRP, ADA, DOGE (pasangan USDT) | 1H, sejak 2019/listing | Binance |
| Emas | PAXGUSDT (token emas fisik, 24/7) | 1H, sejak 2020 | Binance |
| Emas | GC=F (emas berjangka COMEX) | 1D, sejak 2000 | Yahoo |
| Saham IDX | IHSG (^JKSE), BBCA, BBRI, BMRI, BBNI, TLKM, ASII, ANTM, UNVR, ICBP, ADRO | 1D, sejak 2000-an | Yahoo |

- Saham IDX dan GC=F memakai 1D karena data 1H gratis hanya ±730 hari
  (±10 window tak tumpang tindih). Data 1H keduanya tidak dianalisis.
- XAUUSD spot (Dukascopy) tidak dipakai karena host-nya diblokir jaringan.
- Inventaris: `ml/artifacts/asset_inventory.json` (`ml/src/fetch_assets.py`).
  Sebelum dokumen ini dikunci, data aset hanya dilihat sebatas jumlah bar dan
  rentang tanggal.

## 3. Detektor yang dibandingkan

| Kode | Detektor | Dilatih pada |
|---|---|---|
| **D-sintetis (utama)** | Detektor terpilih Fase 1: model M-kripto bila H2 Fase 1 terbukti; bila tidak, estimator klasik terkalibrasi terbaik (sesuai tafsir praregistrasi Fase 1 §7) | Data sintetis |
| D-BTC | Model usulan BTC hasil Fase 0 (sesuai skenario A/B/C `rencana_pengembangan.md`), protokol `train_only` | BTC 1H |
| D-konsensus | Konsensus R/S–DFA dengan ambang BTC `train_only` (definisi label Bab 4) | Tidak dilatih |

Semua detektor memakai window 500 bar dan langkah 4 bar, bobot dan scaler
dibekukan. Tidak ada data aset §2 yang dipakai untuk fit, kalibrasi, atau
pemilihan apa pun. Untuk BTC, D-BTC hanya dievaluasi pada periode setelah batas
latihnya.

## 4. Uji validitas ke depan (utama)

Pada aset nyata tidak ada kunci jawaban, sehingga deteksi dinilai dari
perilaku harga **sesudah** window yang dideteksi (data yang tidak dilihat
detektor):

- Untuk setiap titik deteksi t, hitung **VR maju**: variance ratio VR(4) atas
  return bar t+1 … t+M, dengan M = 200 bar (1H ≈ 8 hari; 1D ≈ 9 bulan; untuk 1D
  dipakai M = 60, ≈ 3 bulan).
- Statistik pemisah: **Δ = rata-rata log VR maju (persistent) − rata-rata log VR
  maju (anti-persistent)**. Detektor yang benar menghasilkan Δ > 0.
- CI95 Δ dengan moving-block bootstrap, panjang blok = (500 + M) / 4 titik
  deteksi agar menutup tumpang tindih window dan horizon maju (B = 2.000).

**Hipotesis**

| ID | Pernyataan | Kriteria |
|---|---|---|
| G1 | D-sintetis memisahkan perilaku masa depan pada aset per aset | Batas bawah CI95 Δ > 0 |
| G1-kelompok | D-sintetis tergeneralisasi pada suatu kelompok | G1 terpenuhi pada ≥ 2/3 aset kelompok (kripto; emas; saham IDX) |
| G2 | D-sintetis memisahkan lebih baik daripada D-BTC | Selisih Δ (D-sintetis − D-BTC) per aset, CI95 bootstrap berpasangan; dirangkum sebagai jumlah aset dengan batas bawah > 0 |
| G3 | D-sintetis memisahkan lebih baik daripada D-konsensus | Seperti G2 |

G1-kelompok adalah klaim utama untuk pernyataan "sistem tidak hanya berlaku
untuk BTC". G2 dan G3 dilaporkan apa adanya tanpa koreksi berganda; jumlah
aset yang mendukung dan yang berlawanan dilaporkan berdampingan.

## 5. Uji kegunaan (diteruskan ke Fase 2)

Uji pemilihan strategi Fase 2 dijalankan pada seluruh aset §2 dengan aturan,
parameter, dan biaya yang ditetapkan sebelum Fase 2 dimulai (praregistrasi
Fase 2). Daftar aset §2 mengikat Fase 2.

## 6. Yang tidak dilakukan

- Tidak ada pelatihan ulang, kalibrasi ambang, atau pemilihan model memakai
  data aset §2.
- Tidak ada pelatihan gabungan lintas aset (berisiko bocor waktu karena aset
  kripto bergerak bersama; dikeluarkan dari ruang lingkup).
- Tidak ada penghapusan aset karena hasilnya buruk; semua aset §2 dilaporkan.

## 7. Keluaran

- `ml/src/generalization_study.py`
- `ml/artifacts/generalization.{json,md}` dan gambar Δ per aset per detektor.

## Adendum

(belum ada)

### Adendum 1 (2026-10-20): definisi D-sintetis

Mengikuti adendum 3 praregistrasi Fase 1 (ditulis sebelum hasil uji Fase 1
tersedia): **D-sintetis = model M-kripto terpilih Fase 1, apa pun hasil H2**.
Estimator klasik terkalibrasi terbaik Fase 1 ditambahkan sebagai detektor
pembanding keempat, **D-klasik**, dengan perlakuan yang sama dengan D-BTC dan
D-konsensus (§3–§4). Uji G2/G3 ditambah G4: D-sintetis vs D-klasik, dilaporkan
dengan cara yang sama. Sesuai skenario B Fase 0 (`rencana_pengembangan.md`),
D-BTC = regresi logistik latih-BTC.

### Adendum 2 (2026-10-20): detail implementasi, sebelum uji dijalankan

Belum ada detektor yang diterapkan pada data aset §2 saat adendum ini ditulis.

1. **Normalisasi per window**: return 500 bar tiap window diskalakan ke
   simpangan baku 0,0066 sebelum fitur dihitung, sama seperti data latih
   sintetis (setiap deret sintetis dinormalisasi ke angka itu). Fitur statistik
   (autokorelasi, VR, energi SWT relatif, kurtosis, H(q), dll.) dan estimator
   R/S, DFA, VR(2) tidak berubah oleh penskalaan; yang terpengaruh hanya kanal
   log-volatilitas sekuens PS. Perlakuan yang sama dipakai untuk semua detektor.
2. **Titik deteksi**: setiap 4 bar, mulai saat 500 return tersedia, sampai
   M bar sebelum akhir data (M = 200 untuk 1H, 60 untuk 1D) agar horizon maju
   lengkap. VR maju = VR(4) atas return bar t+1 … t+M (tanpa normalisasi).
3. **D-BTC pada BTC** hanya dievaluasi pada titik deteksi setelah batas
   latih+validasi BTC (`detector_meta.json: btc_train_end_time`); pada aset lain
   semua titik dipakai. Detektor lain dievaluasi pada semua titik semua aset.
4. **D-konsensus**: bila R/S dan DFA tidak sepakat, titik itu tidak termasuk
   kelas persistent maupun anti-persistent (tidak ikut Δ).
5. **Bootstrap**: moving-block atas urutan titik deteksi, panjang blok
   ⌈(500 + M) / 4⌉ titik, B = 2.000, sampel ulang yang sama dipakai untuk semua
   detektor (selisih berpasangan). Sampel ulang yang tidak memuat salah satu
   kelas dibuang untuk Δ detektor tersebut; proporsi yang terbuang dilaporkan.
6. Model yang dipakai adalah berkas hasil `ml/src/train_detector.py`
   (hyperparameter dan seed sama dengan benchmark Fase 1); BA uji S4 hasil latih
   ulang dicatat di `detector_meta.json` sebagai pemeriksaan kesetaraan.

# Praregistrasi: identifikasi regime multi-skala (multi-timeframe sebagai masukan)

Status: **dikunci 2026-10-22** (commit "Praregistrasi multi-skala (dikunci)").
Perubahan hanya lewat adendum bertanggal di bagian bawah.

## 1. Pertanyaan

Detektor resmi melihat satu skala waktu (500 bar pada timeframe yang
diidentifikasi). Pada proses fraktal *self-similar*, H sama di semua skala
agregasi, sehingga melihat skala yang lebih kasar (misalnya 4H dan 1D saat
mengidentifikasi 1H) memberi pengukuran tambahan atas H yang sama.

1. Apakah masukan **multi-skala** meningkatkan ketepatan identifikasi?
2. Apakah peningkatan itu berasal dari multi-skala itu sendiri, atau hanya dari
   cakupan sejarah yang lebih panjang?
3. Berapa harga yang dibayar dalam kecepatan mendeteksi pergantian regime?

**Yang sudah diketahui:** hasil Fase 1 (jendela 500: BA S4 0,813; jendela 256:
0,732), ablasi SWT, Fase 0b, dan uji pergantian regime (adendum 5 Fase 1:
keterlambatan median 296 bar). Belum ada model multi-skala yang dilatih atau
dievaluasi.

## 2. Skala yang dipakai dan alasannya

Skala dasar ×1 = timeframe yang diidentifikasi (setara 1H; parameter sintetis
dikalibrasi ke BTC 1H). Skala tambahan hanya yang **lebih kasar** dan tersedia
di data nyata: **×4 (setara 4H)** dan **×24 (setara 1D)**.

Tidak dipakai: 5m (derau mikrostruktur, parameter sintetis tidak dikalibrasi
untuk resolusi itu), 3D dan mingguan (data BTC tidak cukup untuk satu jendela
500 bar).

Return skala ×k = jumlah k return dasar berurutan, diselaraskan sehingga
agregat terakhir berakhir pada bar t.

## 3. Model

Semua model memakai arsitektur Hybrid PS (Attention-BiLSTM) dengan konfigurasi
latih yang sama dengan detektor resmi (Adam 1e-3, batch 64, maks. 80 epoch,
early stopping `val_loss` patience 12, ReduceLROnPlateau, bobot kelas), seed 42,
43, 44. Setiap jendela dinormalisasi ke σ = 0,0066 sebelum fitur dihitung.

| Kode | Masukan | Cakupan sejarah (bar dasar) |
|---|---|---|
| **M1** | Skala ×1, jendela 500 (sama dengan detektor resmi, dilatih ulang pada data baru) | 500 |
| **M2** | Skala ×1 + ×4, masing-masing jendela 500 | 2.000 |
| **M3** | Skala ×1 + ×4 + ×24, masing-masing jendela 500 | 12.000 |
| **M4** | Skala ×1, jendela panjang 2.000 (sub-jendela PS 512) — pembanding cakupan setara M2 | 2.000 |

Multi-skala: 50 fitur struktural per skala digabung (100 atau 150 fitur);
sekuens PS per skala digabung pada sumbu kanal (32 × 22 atau 32 × 33).
Standarisasi dihitung dari data latih masing-masing model.

## 4. Data

- Deret sintetis sepanjang 12.000 bar per sampel, dengan satu H konstan per
  deret (`make_series`, skenario S1–S4, ambang utama 0,47/0,53, kelas seimbang).
  Seed `SeedSequence([9100 + split, skenario, idx])`; semua model memakai
  deret yang sama.
- Latih 6.000 deret per skenario (S1–S4, total 24.000), validasi 1.500 per
  skenario, uji 3.000 untuk S4 (utama) serta S1 dan S4k (deskriptif).

## 5. Hipotesis (uji S4)

ΔBA dengan probabilitas rata-rata 3 seed, bootstrap berpasangan per deret
(deret saling independen), B = 2.000, p satu sisi. Koreksi Holm atas 3 uji.
Terbukti bila p Holm < 0,05 dan batas bawah CI95 > 0.

| ID | Pernyataan | Pembanding |
|---|---|---|
| MS-H1 | Menambah skala 4H meningkatkan ketepatan | M2 − M1 > 0 |
| MS-H2 | Menambah skala 4H dan 1D meningkatkan ketepatan | M3 − M1 > 0 |
| MS-H3 | Multi-skala lebih baik daripada satu skala dengan cakupan sejarah sama | M2 − M4 > 0 |

## 6. Kecepatan (deskriptif, kriteria ditetapkan sekarang)

- 20 deret S4 × 30.000 bar, 12–18 titik ganti (seragam), segmen minimum 1.000
  bar, kelas segmen selalu berganti, seed `SeedSequence([8100, i])`.
- Deteksi bergulir langkah 4 bar dimulai dari bar 12.000 (agar M3 punya
  sejarah lengkap); hanya titik ganti setelah bar 12.000 yang dihitung.
- Konfirmasi K = 3; metrik sama dengan adendum 5 Fase 1: median keterlambatan,
  salah alarm per 1.000 bar, dan proporsi terlewat, untuk M1–M4 (probabilitas
  rata-rata 3 seed).

## 7. Tafsir dan keputusan untuk sistem (ditetapkan sekarang)

Model multi-skala (M2 atau M3) **direkomendasikan** untuk sistem hanya bila
ketiga syarat ini terpenuhi:

1. hipotesisnya terbukti (MS-H1 untuk M2, MS-H2 untuk M3);
2. median keterlambatan naik paling banyak **25%** dibanding M1;
3. salah alarm per 1.000 bar tidak lebih tinggi daripada M1.

Bila lebih dari satu memenuhi, dipilih yang BA S4-nya lebih tinggi. Bila tidak
ada, detektor resmi tetap satu skala dan hasilnya dilaporkan sebagai temuan
("ketepatan vs kecepatan"). Penggantian detektor di sistem tetap memerlukan
langkah terpisah dan tidak dilakukan otomatis oleh skrip.

| Hasil | Kesimpulan yang ditulis |
|---|---|
| MS-H1/H2 terbukti dan MS-H3 terbukti | Informasi multi-skala menambah ketepatan, bukan sekadar sejarah lebih panjang |
| MS-H1/H2 terbukti, MS-H3 tidak | Peningkatan terutama berasal dari cakupan sejarah yang lebih panjang |
| MS-H1 dan MS-H2 tidak terbukti | Menambah timeframe lebih kasar tidak meningkatkan ketepatan pada data sintetis |

## 8. Yang tidak dilakukan

- Tidak ada penyetelan skala, jendela, arsitektur, atau epoch setelah hasil terlihat.
- Tidak ada pelatihan atau evaluasi pada data BTC dalam praregistrasi ini.
- Tidak ada pelatihan gabungan label Hurst-DFA lintas timeframe (risiko
  kebocoran waktu dan derau label; lihat Fase 0b).

## 9. Keluaran

- `ml/src/multiscale_study.py`
- `ml/artifacts/multiscale_study.{json,md}`

## Adendum

(belum ada)

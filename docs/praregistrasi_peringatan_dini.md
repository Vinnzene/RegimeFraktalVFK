# Praregistrasi: peringatan dini dua kecepatan

Status: **dikunci 2026-10-22** (commit "Praregistrasi peringatan dini (dikunci)").
Perubahan hanya lewat adendum bertanggal di bagian bawah.

## 1. Pertanyaan

Studi deteksi cepat (`ml/artifacts/fast_detection_study.md`) menunjukkan model
A (jendela 500, dilatih juga pada pergantian regime) mengenali pergantian 2,5×
lebih cepat dari detektor resmi D0, tetapi kurang tepat pada kondisi stabil
dan lebih sering salah alarm, sehingga tidak dipakai sebagai detektor utama.

Rancangan dua kecepatan: **D0 tetap menentukan label** di sistem; A hanya
memberi **peringatan dini** "kemungkinan regime sedang berganti ke X".
Pertanyaan: seberapa awal peringatan itu datang dan seberapa sering benar?

**Yang sudah diketahui:** hasil studi deteksi cepat (metrik agregat A dan D0).
Belum pernah dihitung kapan peringatan A terjadi relatif terhadap konfirmasi
D0, maupun ketepatan peringatan.

## 2. Data dan model

- 40 deret panjang yang sama dengan adendum 5 Fase 1 dan studi deteksi cepat
  (20.000 bar, 8–12 titik ganti, proses S4), titik deteksi tiap 4 bar.
- D0: detektor resmi. A: dilatih ulang persis seperti studi deteksi cepat
  (data latih dari cache yang sama, seed 42, 43, 44, probabilitas rata-rata).
  Model A disimpan ke `ml/artifacts/detector/early_warning_s{seed}.keras`
  beserta statistik standarisasinya agar dapat dipakai sistem bila lolos §5.

## 3. Definisi

- **Keadaan D0**: regime terkonfirmasi D0 (K = 3, seperti notifikasi).
- **Peringatan**: A mengonfirmasi (K = 3) kelas k yang **berbeda dari keadaan
  D0 saat itu**. Peringatan baru untuk kelas k tidak diulang selama keadaan D0
  belum berubah dan A tetap di k.
- **Peringatan benar**: kelas k sama dengan kelas segmen sebenarnya yang
  memuat bar akhir jendela saat peringatan.
- **Waktu tunggu yang dihemat (lead)**: untuk setiap titik ganti c ke kelas k
  yang dikonfirmasi D0 sebelum titik ganti berikutnya: bar konfirmasi D0 ke k
  dikurangi bar peringatan pertama ke k setelah c (bila ada peringatan
  sebelum konfirmasi D0; bila tidak, lead = 0).

## 4. Metrik

1. Median lead (bar) atas semua pergantian yang dikonfirmasi D0.
2. Proporsi pergantian yang didahului peringatan benar.
3. **Ketepatan peringatan** = peringatan benar / semua peringatan.
4. Peringatan salah per 1.000 bar.

## 5. Hipotesis dan keputusan (ditetapkan sekarang)

- **DINI-H1**: median lead > 0. Bootstrap per deret (B = 2.000): terbukti bila
  batas bawah CI95 > 0.
- Peringatan dini **dipasang di sistem** (dashboard dan Telegram, diberi label
  "peringatan dini, belum terkonfirmasi") hanya bila DINI-H1 terbukti **dan**
  ketepatan peringatan ≥ 70% **dan** peringatan salah ≤ 1,0 per 1.000 bar
  (±1 per 6 minggu di 1H). Bila tidak, rancangan ini dilaporkan sebagai temuan
  dan tidak dipasang.

## 6. Yang tidak dilakukan

- Tidak ada penyetelan K, ambang, atau model setelah hasil terlihat.
- Tidak ada evaluasi pada data BTC dalam praregistrasi ini.

## 7. Keluaran

- `ml/src/early_warning_study.py`
- `ml/artifacts/early_warning_study.{json,md}`

## Adendum

(belum ada)

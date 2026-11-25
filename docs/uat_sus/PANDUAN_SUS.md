# Panduan Pengumpulan Data Kuesioner SUS — RFraktal

Evaluasi pengguna memakai **System Usability Scale (SUS; Brooke, 1996)** saja, diisi langsung
di aplikasi pada halaman **Kuesioner SUS** (`https://rfraktal.my.id/uat`). Panduan UAT berbasis
tugas yang lama (`PANDUAN_UAT_SUS.md`, Google Form, lembar observasi) sudah **usang**.

Semua angka di naskah harus berasal dari jawaban responden asli yang tersimpan di aplikasi.
Peneliti tidak membuat, mengisi, atau mengubah jawaban.

---

## 1. Instrumen

- 10 pernyataan SUS (teks persis: `docs/naskah/cek_silang/sus.md`), skala 1 (sangat tidak
  setuju) sampai 5 (sangat setuju).
- Skor per responden: SUS = 2,5 × [Σ(butir ganjil − 1) + Σ(5 − butir genap)], 0–100.
- Profil singkat: peran, lama pengalaman trading/analisis kripto (bulan), usia (opsional).
- Sebelum kuesioner, responden mencoba aplikasi secara bebas. Ada tiga halaman yang wajib
  dibuka: Ringkasan, Hasil Uji Identifikasi, dan Fokus Model.

## 2. Kriteria responden

Responden **memenuhi syarat** bila:

1. Pernah melakukan trading **atau** analisis aset kripto (spot, futures, atau sekadar membaca
   grafik untuk keputusan sendiri). Lama pengalaman dicatat dalam bulan.
2. **Bukan pengembang**: tidak bekerja sebagai pengembang perangkat lunak dan tidak terlibat
   membuat RFraktal.
3. Mengisi sendiri dengan akun sendiri (satu orang satu akun, satu kali).

Responden **tidak memenuhi syarat**: peneliti sendiri, dosen pembimbing/penguji, pengembang
perangkat lunak, dan orang yang belum pernah trading maupun menganalisis kripto.

**Target minimal 10 responden** yang menyelesaikan kuesioner. Teruslah mengajak sampai jumlah
"Jumlah responden" di halaman Rekap SUS minimal 10. Akun yang baru memulai tetapi belum
mengirim tidak dihitung.

## 3. Persiapan peneliti (sekali, sebelum menyebar ajakan)

1. Kuesioner terbuka untuk semua akun yang sudah login; tidak ada kode undangan. Pastikan email
   admin tercantum di VPS pada `frontend/.env.local`:
   ```
   ADMIN_EMAILS=vinzenne123@gmail.com
   ```
2. Bila baris itu baru diubah, terapkan (dari folder project di VPS):
   ```
   docker compose -f infra/docker-compose.vps.yml up -d --force-recreate frontend
   ```
3. Buka `https://rfraktal.my.id/uat` dengan akun admin hanya untuk memastikan formulir Persetujuan tampil.
   **Jangan menekan "Mulai"**: setiap akun yang menekan Mulai memakai satu kode (R01, …) dan
   tercatat sebagai "belum selesai" di Rekap SUS. Uji coba alur lengkap dilakukan di laptop
   dengan mode demo (jawabannya hanya di memori, kode D…).
4. Buka `https://rfraktal.my.id/admin/uat` (menu akun → **Rekap SUS**) dan pastikan
   "Belum ada responden yang mengirim jawaban."

## 4. Cara responden mendapat akses dan login

1. Responden membuka tautan **`https://rfraktal.my.id/uat`**.
2. Bila belum login, aplikasi membuka halaman **Masuk**. Responden memilih **Lanjut dengan
   Google**, atau **Buat akun** dengan email dan password.
3. Setelah login, responden otomatis kembali ke halaman Kuesioner SUS.
4. Halaman ini juga dapat dibuka dari menu akun (pojok kanan atas) → **Isi Kuesioner SUS**.

## 5. Langkah pengisian (yang dilihat responden)

| Langkah | Yang dilakukan responden |
|---|---|
| 1. Persetujuan & profil | Membaca keterangan, mencentang persetujuan, memilih peran, mengisi pengalaman (bulan) dan usia (opsional), lalu menekan **Mulai**. Kode responden (R01, R02, …) diberikan otomatis. |
| 2. Mencoba aplikasi | Membuka **Ringkasan**, **Hasil Uji Identifikasi**, dan **Fokus Model** lewat tombol "Buka di tab baru ↗", melihat isinya, lalu kembali. Boleh mencoba halaman lain lewat menu. Tombol **"Saya sudah mencoba, lanjut ke kuesioner"** aktif setelah ketiga halaman dibuka. |
| 3. Kuesioner SUS | Menjawab 10 pernyataan (1–5) sesuai kesan pertama, mengisi saran (opsional), lalu menekan **Kirim jawaban** dan mengonfirmasi. |
| 4. Selesai | Muncul "Terima kasih!" beserta kode responden. Jawaban tidak dapat diubah dan akun yang sama tidak dapat mengisi lagi. |

Perkiraan waktu 10–15 menit. Tangkapan layar tiap langkah ada di
`docs/naskah/cek_silang/sus.md`.

**Aturan bagi peneliti selama pengisian:**

- Jangan mengarahkan jawaban atau menjelaskan maksud pernyataan SUS. Responden menjawab sesuai
  kesan sendiri.
- Bantuan hanya untuk masalah teknis, misalnya tidak bisa login atau tautan tidak terbuka.
- Jangan mengisi atas nama orang lain, dan jangan meminta satu orang mengisi dengan beberapa akun.
- Catat di luar aplikasi bila ada kejadian khusus (misalnya responden berhenti di tengah jalan),
  tanpa mencatat nama.

## 6. Setelah data terkumpul

1. Buka **Rekap SUS** (`/admin/uat`). Halaman ini menampilkan jumlah responden, rata-rata,
   simpangan baku, minimum, maksimum, median, skala kata sifat Bangor dkk. (2009), jumlah skor
   ≥ 68, rata-rata tiap butir, dan jawaban per responden tanpa nama atau email.
2. Tekan **Ekspor CSV (tanpa nama/email)**, lalu simpan berkasnya di
   `docs/naskah/cek_silang/` (mis. `sus_rfraktal_2026-12-05.csv`). Jangan mengubah isinya.
3. Jalankan dari akar repo:
   ```
   python scripts/rekap_sus.py docs/naskah/cek_silang/sus_rfraktal_2026-12-05.csv
   ```
   Skrip menghitung ulang semua skor, berhenti bila ada skor yang berbeda dari ekspor atau bila
   CSV kosong, lalu menulis `docs/naskah/cek_silang/sus_hasil.md` (tabel per responden dan
   ringkasan) untuk Bab 4.
4. Cocokkan angka `sus_hasil.md` dengan halaman Rekap SUS. Keduanya harus sama.

## 7. Pesan ajakan (WhatsApp)

> Halo, aku lagi menyelesaikan skripsi tentang **RFraktal**, aplikasi yang mengenali kondisi
> pasar BTC/USDT (tren berlanjut, acak, atau cenderung berbalik).
>
> Boleh minta bantuan isi kuesioner singkat (±10–15 menit)? Syaratnya pernah trading atau
> analisis kripto, dan bukan programmer/pengembang aplikasi.
>
> 1. Buka https://rfraktal.my.id/uat
> 2. Masuk pakai akun Google (atau buat akun dengan email)
> 3. Coba tiga halaman yang diminta, lalu isi 10 pernyataan
>
> Nama dan email tidak disimpan bersama jawaban. Terima kasih banyak! 🙏

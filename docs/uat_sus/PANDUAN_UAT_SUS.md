# Panduan UAT dan SUS — Sistem Identifikasi Regime BTC/USDT

Dokumen ini adalah protokol pengujian pengguna yang **ditetapkan sebelum
pengujian dimulai**. Target dan cara analisis di §6 tidak diubah setelah data
terkumpul. Semua angka di Bab 4.11.3 wajib berasal dari jawaban responden
nyata yang disimpan mentah (§7).

Isi folder ini:

| Berkas | Fungsi |
|---|---|
| `PANDUAN_UAT_SUS.md` | Protokol ini |
| `create_google_form.gs` | Skrip Google Apps Script: membuat Google Form kuesioner secara otomatis |
| `lembar_observasi.csv` | Lembar yang diisi **pengamat** (kamu) per responden per tugas |
| `../../scripts/olah_uat_sus.py` | Mengolah ekspor CSV Google Form + lembar observasi menjadi tabel Bab 4.11.3 |

---

## 1. Tujuan

1. **UAT (User Acceptance Testing):** apakah calon pengguna dapat menyelesaikan
   tugas utama sistem tanpa bantuan dan memahami informasinya dengan benar.
2. **SUS (System Usability Scale):** seberapa mudah sistem digunakan menurut
   pengguna (skor 0–100).

## 2. Responden

- **Jumlah:** minimal 10 orang (disarankan 12–15 untuk cadangan bila ada yang batal).
- **Kriteria:** pernah trading kripto atau saham minimal 3 bulan, atau mahasiswa
  yang aktif mengikuti pasar kripto. Bukan anggota tim pengembang.
- **Persetujuan:** setiap responden membaca dan menyetujui pernyataan di awal
  formulir (tidak ada data pribadi selain kode responden, pengalaman, dan jenis
  trader; jawaban hanya untuk skripsi).
- **Kode responden:** R01, R02, … — dipakai sama di Google Form dan lembar
  observasi. Jangan menulis nama asli di data.

## 3. Persiapan sistem (sebelum sesi pertama)

- [ ] Backend dan frontend berjalan; cache detektor AI 1H dan 4H sudah terbentuk
      (halaman Ringkasan menampilkan kondisi tanpa pesan "sedang menghitung").
- [ ] Token bot Telegram sudah diisi dan **Kirim pesan uji** sudah dicoba sendiri.
- [ ] Akun uji disiapkan bila responden tidak ingin memakai akun Google pribadi
      (Email/Password di Firebase), misalnya `uji01@…` sampai `uji15@…`.
- [ ] Cara akses ditentukan:
  - **Tatap muka (disarankan):** responden memakai laptopmu, kamu mengamati di samping.
  - **Daring:** Zoom/Google Meet dengan *remote control* ke laptopmu, atau
    aplikasi dipublikasikan sementara (misalnya tunnel). Bila memakai domain
    lain, tambahkan domain itu di Firebase Authentication → Authorized domains.
- [ ] Semua sesi memakai versi aplikasi yang sama (catat hash commit di lembar observasi).

## 4. Alur satu sesi (±25 menit)

1. Pembukaan (2 menit): jelaskan tujuan, bahwa yang diuji adalah **sistemnya,
   bukan respondennya**, dan minta responden mengisi bagian A Google Form
   (persetujuan + profil).
2. Tugas UAT (±15 menit): bacakan skenario §5 satu per satu. Jangan membantu
   kecuali responden meminta atau macet > 2 menit. Isi lembar observasi.
3. Kuesioner (±5 menit): responden mengisi bagian B (jawaban tugas) dan C (SUS)
   di Google Form **setelah** semua tugas selesai, tanpa didampingi.
4. Penutup (2 menit): tanyakan satu hal yang paling membingungkan dan satu yang
   paling berguna; catat di kolom komentar lembar observasi.

## 5. Skenario tugas UAT

Setiap tugas dinilai pengamat dengan tiga status:
**Berhasil** (tanpa bantuan) · **Berhasil dengan bantuan** · **Gagal**.
Pengamat juga mencatat waktu (detik) dan apakah jawaban responden benar.

| Kode | Skenario yang dibacakan | Kriteria berhasil | Jawaban yang diperiksa |
|---|---|---|---|
| **TSK01** | "Masuk ke sistem, lalu sebutkan kondisi pasar BTC/USDT saat ini pada skala 1 jam beserta tingkat keyakinan modelnya." | Login berhasil; menyebut kondisi dan persentase keyakinan 1H dari halaman Ringkasan | Kondisi + keyakinan sesuai layar |
| **TSK02** | "Bandingkan dengan skala 4 jam. Apakah kondisinya sama? Apakah ada tanda keyakinan rendah?" | Menemukan strip 1H/4H atau tombol 4H; menjawab sama/berbeda dan ada/tidak tanda keyakinan rendah | Sesuai layar |
| **TSK03** | "Berdasarkan sistem, strategi apa yang disarankan untuk kondisi saat ini, dan apakah saran itu didukung hasil uji?" | Membuka kartu "Apa artinya untuk Anda?" atau halaman Regime → Strategi; menyebut strategi dan status bukti (mis. "Didukung uji Fase 2") | Strategi + status bukti sesuai layar |
| **TSK04** | "Pada grafik riwayat harga, tunjukkan kapan terakhir kali pasar berada dalam kondisi 'Cenderung Berbalik'." | Membaca warna pita regime / legenda pada grafik dan menunjuk periode yang benar (boleh memakai zoom atau rentang 1M/3M) | Periode yang ditunjuk sesuai |
| **TSK05** | "Aktifkan notifikasi Telegram agar Anda diberi tahu saat kondisi pasar berganti, lalu kirim pesan uji." | Membuka Strategi → Notifikasi Telegram, menekan **Hubungkan Telegram**, menekan Start di bot, lalu **Kirim pesan uji** dan pesan diterima | Pesan uji diterima di Telegram |

**Cara mengisi `lembar_observasi.csv`** (satu baris per responden per tugas):

| Kolom | Isi |
|---|---|
| `status` | `berhasil` (tanpa bantuan) · `bantuan` (berhasil setelah dibantu) · `gagal` |
| `waktu_detik` | Waktu dari skenario selesai dibacakan sampai responden menyatakan selesai |
| `jawaban_benar` | `ya` / `tidak` — dibandingkan dengan tampilan sistem saat itu |
| `bantuan_diberikan` | Bentuk bantuan bila ada (mis. "menunjukkan menu Strategi") |
| `komentar` | Kebingungan, komentar spontan, kendala teknis |
| `commit_aplikasi` | Hash commit aplikasi saat sesi (`git log --oneline -1`) |

Setelah setiap tugas, responden juga menilai kemudahannya dengan **Single
Ease Question** (SEQ, 1 = sangat sulit … 7 = sangat mudah; Sauro & Dumas, 2009)
di bagian B formulir.

Catatan TSK05: bila responden tidak punya Telegram, gunakan akun Telegram
pengamat dan catat "memakai akun pengamat" di komentar; statusnya tetap dinilai.

## 6. Rencana analisis dan target (ditetapkan sekarang)

**SUS** (Brooke, 1996): skor tiap responden =
[Σ(butir ganjil − 1) + Σ(5 − butir genap)] × 2,5, rentang 0–100.
Dilaporkan: rata-rata, simpangan baku, median, minimum–maksimum, dan
interpretasi Bangor dkk. (2009) — *adjective rating* dan *acceptability range*.

**UAT:** per tugas dilaporkan jumlah Berhasil / Berhasil dengan bantuan /
Gagal, tingkat keberhasilan tanpa bantuan, median waktu, dan proporsi jawaban
benar, serta median SEQ. Interval kepercayaan 95% tingkat keberhasilan memakai
metode Wilson (sampel kecil).

**Target keberhasilan (dikunci):**

| Ukuran | Target |
|---|---|
| Rata-rata skor SUS | ≥ 68 (rata-rata industri; Sauro, 2011) |
| Keberhasilan tanpa bantuan per tugas | ≥ 80% |
| Jawaban benar per tugas | ≥ 80% |

Semua hasil dilaporkan apa adanya, termasuk tugas yang tidak mencapai target,
beserta temuan masalah usability dan perbaikan yang dilakukan. Bila sistem
diperbaiki setelah pengujian, catat perbaikannya; jangan mengganti data lama
dengan data baru tanpa menyebutkannya.

## 7. Penyimpanan data mentah

- Ekspor Google Form: **Responses → Download responses (.csv)**, simpan sebagai
  `docs/uat_sus/data/respon_google_form.csv`.
- Lembar observasi terisi: `docs/uat_sus/data/lembar_observasi_terisi.csv`.
- Jangan mengedit jawaban responden. Kesalahan input dicatat di kolom komentar.
- Lalu jalankan:

  ```
  python scripts/olah_uat_sus.py \
      --form docs/uat_sus/data/respon_google_form.csv \
      --observasi docs/uat_sus/data/lembar_observasi_terisi.csv
  ```

  Keluaran: `docs/uat_sus/data/hasil_uat_sus.md` (tabel siap pakai untuk Bab 4.11.3).

## 8. Kuesioner SUS versi Bahasa Indonesia

Skala 1 = Sangat tidak setuju … 5 = Sangat setuju. Terjemahan mengikuti adaptasi
SUS Bahasa Indonesia (Sharfina & Santoso, 2016; cocokkan redaksinya dengan
sumber asli sebelum dikutip).

| No | Pernyataan |
|---|---|
| SUS1 | Saya berpikir akan menggunakan sistem ini lagi. |
| SUS2 | Saya merasa sistem ini rumit untuk digunakan. |
| SUS3 | Saya merasa sistem ini mudah digunakan. |
| SUS4 | Saya membutuhkan bantuan dari orang lain atau teknisi dalam menggunakan sistem ini. |
| SUS5 | Saya merasa fitur-fitur sistem ini berjalan dengan semestinya. |
| SUS6 | Saya merasa ada banyak hal yang tidak konsisten pada sistem ini. |
| SUS7 | Saya merasa orang lain akan memahami cara menggunakan sistem ini dengan cepat. |
| SUS8 | Saya merasa sistem ini membingungkan. |
| SUS9 | Saya merasa tidak ada hambatan dalam menggunakan sistem ini. |
| SUS10 | Saya perlu membiasakan diri terlebih dahulu sebelum menggunakan sistem ini. |

## 9. Teks untuk Bab 3.12 (silakan disesuaikan)

> Pengujian penerimaan pengguna dilakukan terhadap minimal 10 responden yang
> memiliki pengalaman trading. Setiap responden menjalankan lima skenario tugas
> (melihat kondisi pasar 1H, membandingkan dengan 4H, membaca saran strategi
> beserta buktinya, membaca riwayat regime pada grafik, dan mengaktifkan
> notifikasi Telegram) sambil diamati. Status penyelesaian, waktu, dan
> kebenaran jawaban dicatat pada lembar observasi. Setelah itu responden
> mengisi kuesioner System Usability Scale versi Bahasa Indonesia. Target
> ditetapkan sebelum pengujian: skor SUS rata-rata ≥ 68 serta keberhasilan
> tanpa bantuan dan ketepatan jawaban ≥ 80% per tugas.

## 10. Rujukan

- Brooke, J. (1996). SUS: A "quick and dirty" usability scale. Dalam *Usability Evaluation in Industry*. Taylor & Francis.
- Bangor, A., Kortum, P., & Miller, J. (2009). Determining what individual SUS scores mean: Adding an adjective rating scale. *Journal of Usability Studies*, 4(3), 114–123.
- Sauro, J. (2011). *A Practical Guide to the System Usability Scale*. Measuring Usability LLC.
- Sauro, J., & Dumas, J. S. (2009). Comparison of three one-question, post-task usability questionnaires. *Proceedings of CHI 2009*, 1599–1608.
- Sharfina, Z., & Santoso, H. B. (2016). An Indonesian adaptation of the System Usability Scale (SUS). *ICACSIS 2016*.

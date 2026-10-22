# To-do list menuju sidang

Status per 22 Oktober 2026. Centang `[x]` setiap kali selesai.
Kolom **Siapa**: *Kamu* = harus dikerjakan sendiri; *Claude* = bisa dikerjakan/dibantu Claude.

## A. WAJIB (penghalang sidang)

| # | Tugas | Siapa | Estimasi | Selesai |
|---|---|---|---|---|
| A1 | Kirim draf revisi Bab I–IV (`docs/skripsi_bab1_bab4_revisi.md`) ke dosen pembimbing. Jelaskan perubahan klaim: H5 tidak terbukti, SWT tidak berkontribusi, F1 tidak berlaku, generalisasi tidak terpenuhi | Kamu | 1 hari | [ ] |
| A2 | Siapkan formulir UAT (5 skenario tugas) + kuesioner SUS (10 butir) di Google Form — paket di `docs/uat_sus/`; tinggal jalankan `create_google_form.gs` | Claude | 1 jam | [x] |
| A3 | Rekrut minimal 10 responden (trader kripto aktif); jalankan UAT + SUS; simpan semua jawaban mentah | Kamu | 1–2 minggu | [ ] |
| A4 | Olah hasil UAT/SUS (skor SUS, tingkat keberhasilan tugas) dan isi Bab 4.11.3 | Claude | 1 jam | [ ] |
| A5 | Isi token bot Telegram (`backend/.env` dan `frontend/.env.local`; jangan ditempel di chat), lalu uji: tautkan akun, terima notifikasi, `/status`, `/stop` | Kamu + Claude | 1 jam | [x] |
| A6 | Uji black-box: tabel kasus uji per fitur (login, ringkasan pasar, ganti 1H/4H, grafik, strategi, Telegram, order flow) beserta hasil nyata | Claude buat daftar, Kamu eksekusi | 2–3 jam | [ ] |
| A7 | Ambil tangkapan layar semua halaman utama untuk Bab 4.11.1 | Claude | 30 menit | [ ] |
| A8 | Tulis Bab V (Kesimpulan dan Saran) | Claude draf, Kamu revisi | 2 jam | [ ] |
| A9 | Verifikasi setiap rujukan Bab II ke sumber asli; susun daftar pustaka (APA/IEEE sesuai pedoman kampus) | Kamu (Claude bantu cari) | 1–2 hari | [ ] |
| A10 | Revisi naskah sesuai masukan dosen, lalu minta persetujuan maju sidang | Kamu | tergantung dosen | [ ] |

## B. SEBAIKNYA (memperkuat sidang)

| # | Tugas | Siapa | Estimasi | Selesai |
|---|---|---|---|---|
| B1 | Pasang abstain τ = 0,75: tanda "keyakinan rendah" di dashboard; notifikasi Telegram memakai versi abstain (salah alarm turun 3×) | Claude | 1–2 jam | [x] |
| B2 | Bersihkan halaman lama yang masih memakai model/label usang (model comparison, attention, backtest lama), atau beri label "arsip Fase 0" | Claude | 2 jam | [x] |
| B3 | Mode demo offline untuk sidang (data dan cache lokal, tanpa internet) dan uji di laptop yang dipakai sidang | Claude + Kamu | 1–2 jam | [ ] |
| B4 | Masukkan rujukan baru ke Bab II (Entropy 2023, López de Prado 2018, Bailey dkk. 2017, Song dkk. 2023, Müller dkk. 2019, Ismail Fawaz dkk. 2018) | Claude | 1 jam | [ ] |
| B5 | Tambahkan subbab analisis overfitting/underfitting (tabel latih/validasi/uji detektor dan Fase 0) ke Bab IV | Claude | 30 menit | [ ] |
| B6 | Putuskan nasib berkas yang belum di-commit: `rancangan_skripsi_bab1_bab4.md` (draf lama), `sweet_spot_study.*`, `run_sweet_spot_study.py`, perubahan `model_architecture.py` dan `train.py`. Jangan dipakai sebagai klaim | Kamu putuskan, Claude rapikan | 30 menit | [ ] |
| B7 | Gambar/diagram final untuk naskah (alur penelitian, arsitektur model, arsitektur sistem, grafik hasil Fase 1/2) | Claude | 2–3 jam | [ ] |

## C. PERSIAPAN PRESENTASI

| # | Tugas | Siapa | Estimasi | Selesai |
|---|---|---|---|---|
| C1 | Slide sidang (±15 slide): masalah → metode → hasil Fase 0/1/2 → sistem → kesimpulan | Claude draf, Kamu revisi | 1 hari | [ ] |
| C2 | Skenario demo langsung (urutan klik, ±5 menit) + rencana cadangan jika internet/backend gagal | Claude | 1 jam | [ ] |
| C3 | Daftar pertanyaan penguji + jawaban (BiLSTM-Attention, SWT, data sintetis, strategi rugi, generalisasi, overfitting) | Claude | 1 jam | [ ] |
| C4 | Latihan presentasi minimal 2 kali, termasuk sesi tanya jawab | Kamu | 2 hari | [ ] |
| C5 | Hafalkan angka kunci: 52,6%; 0,813 vs 0,654; 0,268; H5 p 0,0575; 296 vs 604 bar; τ 0,75 → BA 0,905 | Kamu | – | [ ] |

## Urutan yang disarankan

1. **Minggu ini:** A1 (kirim ke dosen), A2 (formulir), A5 (Telegram), B1 (abstain), B2 (bersihkan halaman). Sistem harus final **sebelum** UAT supaya responden menguji versi akhir.
2. **Minggu 1–2:** A3 (UAT/SUS berjalan). Sambil menunggu: A6, A7, A8, A9, B4, B5, B7.
3. **Setelah UAT:** A4, lalu A10 (revisi dan persetujuan dosen).
4. **Menjelang sidang:** C1–C5, B3.

## Hal yang tidak boleh dilakukan

- Memakai angka UAT/SUS/Jira dari draf lama atau dari template.
- Mengubah hasil eksperimen yang sudah dipraregistrasi, atau memilih konfigurasi sambil melihat data uji.
- Mengklaim SWT, attention, atau pemilihan strategi "terbukti meningkatkan" sesuatu.

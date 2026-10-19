# INSTRUKSI PENGEMBANGAN UNTUK AI AGENT
**Proyek:** `regimefraktalVFK` / BTCUSDT Regime Dashboard
**Topik skripsi:** Identifikasi Regime Fraktal Dinamis BTC/USDT Multi-Timeframe Menggunakan Hybrid Attention-BiLSTM dengan Fitur Wavelet dan Statistik Persistensi
**Konteks:** Skripsi S1, Universitas Bunda Mulia, 2026. Tujuan dokumen ini adalah menutup celah validitas dan kelengkapan sebelum sidang.

> Baca seluruh dokumen ini sebelum menulis kode. Jangan mengasumsikan struktur kode; **periksa dulu repositori** (`backend/`, `ml/`, `frontend/`, `docs/`, `setup_engine.yaml`) lalu sesuaikan langkah di bawah dengan kondisi nyata. Jika ada perbedaan antara dokumen ini dan kode, laporkan perbedaannya kepada pengguna sebelum melanjutkan.

---

## 0. ATURAN WAJIB (tidak boleh dilanggar)

1. **Dilarang mengubah metode atau parameter karena hasil kurang bagus.** Ini skripsi bertema anti-*data snooping*. Perubahan hanya boleh jika (a) memperbaiki cacat validitas, atau (b) ditetapkan sebelum melihat hasil dan dicatat.
2. **Konfigurasi utama dibekukan.** Jika perlu variasi parameter, jalankan sebagai **analisis sensitivitas** dan laporkan **semua** varian, termasuk yang gagal. Jangan hanya menampilkan varian terbaik.
3. **Catat sebelum menjalankan.** Untuk setiap eksperimen baru, tulis hipotesis dan kriteria keberhasilan di `docs/praregistrasi_addendum.md` (buat file ini) **sebelum** menjalankan kode. Beri timestamp (git commit).
4. **Hasil negatif dilaporkan apa adanya.** Jangan menyembunyikan, memperhalus, atau menghapus hasil yang buruk.
5. **Jangan membuat klaim tanpa angka.** Khususnya: jangan mengklaim sistem menghasilkan profit atau sinyal trading yang berguna kecuali ada bukti statistik.
6. **Jangan memakai data uji untuk keputusan apa pun.** Seleksi model, pemilihan ambang, dan tuning hanya boleh memakai data latih/validasi.
7. **Reproducibility.** Setiap skrip baru menerima `--seed`, menyimpan config hash, dan menulis artefak ke `ml/artifacts/` atau `reports/` dengan nama deskriptif.
8. **Semua perubahan kode disertai tes** di `backend/tests/` atau `ml/tests/`. Jalankan `pytest` penuh sebelum dan sesudah; jangan merusak 96+ tes yang ada.
9. **Bahasa:** dokumentasi dan naskah dalam Bahasa Indonesia; kode, nama variabel, dan komentar teknis dalam Bahasa Inggris kecuali konvensi proyek menyatakan lain.
10. **Jangan menghapus artefak lama.** Hasil baru disimpan berdampingan agar perbandingan sebelum/sesudah tetap ada.

---

## 1. PRIORITAS 1: Cacat validitas dan konsistensi (kerjakan lebih dulu)

### T1.1 Koreksi Tabel 4.8 dan narasi walk-forward di `docs/bab4_hasil.md`
- Hitung ulang kolom "Menang vs MLP" langsung dari `ml/artifacts/walk_forward_neural_*.json` (jangan menyalin dari teks).
- Dugaan saat ini: Hybrid PS 4H menang **1/5** fold (bukan 2/5), dan kalah **4/5**. Verifikasi dari data.
- Perbarui kalimat di §4.4 dan tabel rangkuman §4.7 bila terpengaruh.
- **Selesai jika:** semua angka di tabel dan narasi cocok dengan JSON sumber; tambahkan skrip `ml/src/verify_bab4_numbers.py` yang mencocokkan angka kunci Bab 4 dengan artefak dan gagal bila ada selisih.

### T1.2 Samakan angka entropi attention
- Cari semua kemunculan entropi attention di `docs/kerangka_skripsi.md`, `docs/STATUS.md`, `docs/bab4_hasil.md`, README.
- Satu sumber kebenaran: `ml/artifacts/ps_study_*.md` dan metadata model. Cantumkan **model mana** yang diukur (Hybrid PS vs Hybrid SWT).
- **Selesai jika:** tidak ada angka entropi yang berbeda antar dokumen tanpa keterangan model.

### T1.3 Ambang kuantil label dihitung hanya dari data latih
**Masalah:** ambang kuantil regime saat ini dihitung dari distribusi seluruh riwayat, sehingga label data latih terpengaruh distribusi periode uji (kebocoran halus).
- Tambahkan opsi (mis. `label.threshold_source: train_only | full_history`) di modul labeling (`backend/app/services/hurst_dfa.py` dan pipeline ML terkait). Default lama tetap tersedia agar hasil lama bisa direproduksi.
- Untuk `train_only`: hitung ambang dari split latih saja (atau dari data latih tiap fold pada walk-forward), lalu terapkan ke validasi/uji.
- Jalankan ulang pipeline utama (1H dan 4H) dengan `train_only`, 3 seed, protokol yang sama.
- Laporkan sebagai **uji sensitivitas**: tabel berdampingan (ambang full-history vs train-only) untuk BA, macro F1, MCC, dan keputusan H1–H6.
- **Jangan** otomatis mengganti hasil utama. Jika hasil `train_only` berbeda secara kualitatif, laporkan ke pengguna; keputusan konfigurasi utama ada pada pengguna dan pembimbing.
- **Selesai jika:** artefak `label_threshold_sensitivity_{tf}.md/json` + tes yang memastikan ambang tidak memakai data setelah batas latih.

### T1.4 Block bootstrap dengan sampel efektif yang eksplisit
**Masalah:** window 500 bar saling tumpang tindih; sampel uji efektif jauh lebih kecil daripada jumlah window (1H test 1.619 window, 4H test 257 window).
- **Verifikasi dulu** stride antar window dari kode (dugaan ±4 bar pada 1H). Hitung sampel efektif ≈ (jumlah bar periode uji) / 500.
- Periksa implementasi block bootstrap yang ada: berapa panjang blok? Panjang blok harus ≥ ceil(500 / stride) window agar blok mencakup rentang ketergantungan.
- Jalankan ulang ΔF1 dan ΔBA CI95 dengan panjang blok eksplisit; laporkan sebagai parameter. Lakukan sensitivitas pada beberapa panjang blok (mis. 0,5×, 1×, 2× dari nilai minimum).
- Gantikan kriteria "≥ 2 dari 3 seed" dengan **ensemble prediksi 3 seed** (rata-rata probabilitas), lalu satu uji bootstrap per perbandingan.
- Terapkan koreksi perbandingan ganda (Holm–Bonferroni) pada keluarga hipotesis H1–H6 per timeframe, atau tulis eksplisit bahwa tidak ada koreksi. Sediakan kedua versi.
- Tambahkan output: sampel efektif, panjang blok, jumlah resampling, CI95 dan p-value (mentah dan terkoreksi).
- **Selesai jika:** skrip `ml/src/block_bootstrap_eval.py` + artefak `bootstrap_eval_{tf}.md/json` + tes sintetis (data tanpa perbedaan nyata tidak boleh menghasilkan signifikansi berlebihan).

> **Catatan:** Jangan memakai Wilcoxon signed-rank dengan n=5 fold untuk menguji p<0,05. Nilai p dua-sisi minimumnya 0,0625 sehingga uji itu secara matematis tidak dapat mencapai 0,05. Fold expanding-window juga tidak independen.

### T1.5 Nonaktifkan OFI/CVD; jadikan Mode A standar
- Data `bookTicker`/`bookDepth` Binance spot mengembalikan HTTP 404 sehingga kolom `ofi_*` dan `cvd_*` bernilai 0.0.
- Di `setup_engine.yaml` dan kode, jadikan **Mode A (price structure + regime)** default resmi. Mode B dinonaktifkan, tidak boleh menulis nilai 0.0 seolah-olah filter berjalan.
- Hapus kolom OFI/CVD dari `trade_log.csv` untuk Mode A, atau isi `NaN` dan beri dokumentasi.
- Perbarui `docs/` dan README: tulis di batasan penelitian bahwa data mikrostruktur tidak tersedia.
- **Selesai jika:** tidak ada kolom berisi 0.0 palsu pada output Mode A, dan tes memastikan Mode B menolak berjalan tanpa data valid.

### T1.6 Fee dan slippage di outcome resolver
- Edit `backend/app/services/setup_engine/outcome_resolver.py`.
- Parameter di `setup_engine.yaml`: `execution.taker_fee_pct` (default 0.075% per sisi, total entry+exit), `execution.slippage_ticks` (default 1 tick), tick size BTCUSDT dari konfigurasi.
- Rumus:
  `R_real = ((P_exit - P_entry) * direction - biaya_total) / risk_distance`
- Simpan **R sebelum dan sesudah biaya** di `trade_log.csv` (`r_gross`, `r_net`).
- Tes: trade TP/SL sintetis dengan biaya nol harus sama dengan perilaku lama; biaya positif selalu menurunkan R.
- **Selesai jika:** semua ringkasan (`walk_forward_summary.csv`, `cumulative_R.html`) menampilkan hasil bruto dan neto.

### T1.7 Atasi N=3 pada setup engine tanpa data snooping
- **Langkah 1 (utama):** perluas horizon walk-forward ke seluruh periode out-of-sample yang valid (bukan hanya 4 window uji), dengan konfigurasi **tidak berubah**.
- **Langkah 2 (sensitivitas):** jalankan grid kecil yang ditetapkan sebelumnya, misalnya `max_setup_wait_bars ∈ {6, 12, 18}` dan `bias_allowed_contexts ∈ {[SUPPORTIVE], [SUPPORTIVE, NEUTRAL]}`. Laporkan **seluruh sel grid**, jumlah trade (N), expectancy neto, win rate dengan CI, dan flag `n_small_sample`.
- Konfigurasi utama tetap yang sudah ada. Grid hanya untuk sensitivitas, bukan untuk memilih yang terbaik.
- Jika N < 30 di semua konfigurasi, laporkan apa adanya dan **jangan** menyimpulkan win rate atau profit factor.
- **Selesai jika:** `reports/mode_A/sensitivity_grid.csv/md` + tabel siap pakai untuk Bab 4 subbab hilir.

---

## 2. PRIORITAS 2: Menjawab "untuk apa identifikasi regime?"

### T2.1 Analisis persistensi regime ke depan (forward-looking)
**Tujuan:** memberi bukti terukur bahwa identifikasi regime saat ini punya nilai informasi ke depan, atau membuktikan bahwa tidak.

**Praregistrasi dulu** (tulis di `docs/praregistrasi_addendum.md` sebelum menjalankan):
- H-F1: Probabilitas label regime pada waktu *t* bertahan pada *t+k* lebih tinggi daripada tingkat dasar (probabilitas marginal kelas), untuk k = 1, 2, 4, 8, 16, 32 bar.
- H-F2: Prediksi model pada *t* memprediksi label *t+k* lebih baik daripada baseline naif "label terakhir bertahan" (*persistence baseline*).
- Kriteria: selisih BA/F1 dengan CI95 block bootstrap (lihat T1.4) di data uji; kronologis, tanpa kebocoran.

**Implementasi:**
- Hitung kurva P(label_{t+k} = label_t | label_t) per kelas, dari data **latih** untuk estimasi, **uji** untuk evaluasi.
- Baseline: (a) persistence naif memakai label sebenarnya di *t*; (b) kelas mayoritas; (c) model Hybrid PS dengan prediksinya di *t* dipakai untuk memprediksi label *t+k*.
- Pastikan label *t+k* tidak tumpang tindih tak wajar dengan window *t* saat menarik kesimpulan; dokumentasikan tumpang tindih (window 500 bar sangat tumpang tindih untuk k kecil, ini harus disebut sebagai keterbatasan).
- Output: `forward_persistence_{tf}.md/json`, `fig_forward_persistence_{tf}.png`.
- **Interpretasi yang diizinkan:** jika model tidak mengalahkan baseline naif, tulis "model mengidentifikasi, belum meramalkan". Itu hasil sah, jangan diubah.

### T2.2 Tampilkan konteks yang adil antara angka test dan walk-forward
- Tambahkan di Bab 4 tabel/kalimat yang menyandingkan BA test 1H (0,693) dengan rata-rata walk-forward (0,578 ± 0,069), dan catat bahwa periode uji mirip fold 5 (0,686) yang relatif mudah.
- Tidak mengubah angka; hanya menambah konteks.

### T2.3 Subbab hilir di Bab 4
- Tambahkan subbab "Studi Kelayakan Hilir" yang memuat: temuan negatif backtest langsung dari Hurst (P searah ≈ 0,458, dari `/api/v1/backtest/diagnostics`) dan hasil setup engine setelah T1.5–T1.7 (neto setelah biaya, N, sensitivitas).
- Bingkai sebagai studi kelayakan, bukan kontribusi utama.
- Jangan menyatakan strategi menguntungkan kecuali ada uji statistik yang mendukung.

### T2.4 (Opsional, tetapi menambah kekuatan) Pembanding non-neural yang lebih kuat
- Latih gradient boosting (mis. LightGBM atau sklearn `HistGradientBoostingClassifier`) pada fitur statistik yang sama dengan MLP, protokol identik (kronologis, purge, scaler dari latih saja, 3 seed).
- Praregistrasi dulu. Laporkan hasil apa pun, termasuk jika Hybrid PS tidak lebih baik.

---

## 3. PRIORITAS 3: Kesiapan sidang dan demo

### T3.1 Halaman multifraktal di dashboard
- Endpoint `GET /api/v1/analysis/multifractal` sudah ada. Buat halaman `frontend/app/multifractal/page.tsx` (atau tab di `/regime-explorer`).
- Tampilkan kurva H(q) untuk q = 1, 2, 4 dan lebar spektrum ΔH, dengan penjelasan singkat dan rumus (KaTeX) selaras `docs/PRD.md`.
- Ikuti gaya komponen dan chart yang sudah ada (Tailwind + Lightweight Charts / chart yang dipakai halaman lain). Tambahkan ke navigasi.
- Tangani state loading dan error; berfungsi dengan `use_mock: false`.

### T3.2 Mode demo offline dan one-command launch
- Pastikan seluruh dashboard berjalan dengan `runtime.use_mock: false` hanya dari data Parquet lokal di `data/processed/`, **tanpa koneksi internet**.
- Buat `scripts/launch_demo.ps1` (Windows) dan, jika diperlukan, `docker-compose.yml`, yang menjalankan backend dan frontend sekaligus, menunggu health check, lalu membuka browser.
- Tambahkan `scripts/check_offline_ready.py`: memeriksa file data dan artefak yang dibutuhkan setiap halaman, mencetak daftar yang hilang.
- Dokumentasikan di README.

### T3.3 Reproducibility
- Pin versi dependensi (`requirements.txt` / lockfile untuk backend dan ml, `package-lock.json` untuk frontend).
- README: langkah dari nol, perintah menjalankan tes, regenerasi gambar, dan pelatihan ulang.
- Pastikan setiap artefak mencatat config hash dan seed.

### T3.4 Dokumen tanya-jawab sidang
Buat `docs/tanya_jawab_sidang.md`, jawaban jujur dan berbasis angka dari artefak (cantumkan rujukan file untuk setiap angka):
1. Untuk apa hanya mengidentifikasi regime? (batas klaim; regime sebagai konteks, bukan sinyal; temuan konsistensi label, bahaya split acak, fitur pembeda; hasil T2.1)
2. Kenapa attention tidak berkontribusi, tetapi tetap dipakai?
3. Kenapa 4H gagal?
4. Kenapa label berasal dari Hurst-DFA, bukan sumber independen?
5. Kenapa hanya BTC/USDT?
6. Kenapa setup engine hanya sedikit trade?
7. Apakah ada kebocoran data? (leakage study, T1.3)
8. Bagaimana sampel efektif dan kekuatan uji statistik? (T1.4)

---

## 4. PERUBAHAN NASKAH (`docs/`)

Setelah T1–T2 selesai dan angka final, perbarui:
- `docs/bab4_hasil.md`: koreksi Tabel 4.8; tambahkan sensitivitas ambang (T1.3), bootstrap baru (T1.4), analisis forward (T2.1), konteks 0,693 vs 0,578 (T2.2), subbab hilir (T2.3). Ubah catatan draf (mis. "Hal ini harus dinyatakan terbuka") menjadi kalimat pernyataan. Hapus rujukan internal yang salah letak (mis. "menegaskan temuan §4.2.2" di dalam §4.2.2).
- `docs/bab3_metodologi.md`: dokumentasikan perubahan metodologi (ambang train-only, ensemble + bootstrap, fee/slippage, Mode A).
- Keterbatasan §4.6.2: tambahkan sampel efektif kecil dan periode uji 1H yang termasuk mudah; perbarui poin ambang kuantil sesuai hasil T1.3.
- `docs/STATUS.md`, `README.md`: sinkronkan.
- Draf Bab 1 (5 masalah khusus) dan Bab 5 (5 kesimpulan) **hanya setelah** Bab 4 final; jangan menulis kesimpulan mendahului hasil.

---

## 5. URUTAN KERJA

1. T1.1, T1.2 (cepat; angka dan konsistensi)
2. T1.5, T1.6, T1.7 (setup engine) + T2.3
3. T1.3 (ambang train-only), lalu T1.4 (bootstrap), karena keduanya dapat mengubah angka Bab 4
4. T2.1, T2.2
5. Perbarui naskah (§4)
6. T3.1–T3.4
7. T2.4 (jika waktu longgar)

## 6. DEFINISI SELESAI (untuk setiap tugas)

- [ ] Kode + tes lulus (`pytest` penuh hijau)
- [ ] Hipotesis dan kriteria tercatat di praregistrasi **sebelum** eksekusi (untuk eksperimen baru)
- [ ] Artefak tersimpan dengan config hash + seed
- [ ] Semua varian dilaporkan, termasuk yang negatif
- [ ] Dokumen terkait diperbarui, tidak ada angka yang bertentangan antar dokumen
- [ ] Ringkasan perubahan dan temuan dilaporkan ke pengguna, termasuk hasil yang mengubah kesimpulan sebelumnya

## 7. HAL YANG HARUS DITANYAKAN KE PENGGUNA (jangan diputuskan sendiri)

- Hasil T1.3 mengubah kesimpulan kualitatif: konfigurasi utama mana yang dipakai di naskah (perlu persetujuan pembimbing).
- Keputusan λ Statistical Jump Model (kuantil statis sebagai ground truth utama, λ = 0,5 sebagai uji ketahanan) menunggu persetujuan pembimbing.
- Menambah aset kedua (ETH/USDT) atau model pembanding baru.
- Perubahan judul skripsi.

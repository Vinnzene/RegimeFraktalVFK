# regimefraktalVFK

Dashboard riset untuk identifikasi **regime fraktal dinamis BTC/USDT** multi-timeframe
(1H & 4H) menggunakan Hurst Exponent + DFA, Stationary Wavelet Transform, dan
Attention-BiLSTM.

Alat visualisasi hasil penelitian — bukan aplikasi trading, bukan rekomendasi investasi.

## Menjalankan

```bash
# Backend (http://localhost:8000)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (http://localhost:3000)
cd frontend
npm install
npm run dev
```

### Peluncur Satu Perintah (Mode Demo Offline untuk Sidang)

Untuk menjalankan seluruh sistem (backend FastAPI + frontend Next.js) dalam mode demo **100% offline** tanpa ketergantungan internet:

```powershell
# 1. Periksa kesiapan file data dan model lokal
python scripts/check_offline_ready.py

# 2. Jalankan backend dan frontend otomatis, lalu buka browser
powershell -ExecutionPolicy Bypass -File scripts/launch_demo.ps1
```

Atau lewat Docker (frontend + backend, tanpa database):

```bash
docker compose -f infra/docker-compose.yml up --build
```

### Verifikasi Angka dan Replikasi Ilmiah

Untuk memverifikasi integritas angka di naskah skripsi Bab 4 dan mereplikasi uji statistik:

```powershell
# 1. Verifikasi kecocokan angka Bab 4 dengan artefak JSON
python ml/src/verify_bab4_numbers.py

# 2. Jalankan seluruh unit test backend (302 test)
pytest backend/tests -q

# 3. Uji hipotesis Block Bootstrap (Holm-Bonferroni, L=125, N_eff)
python ml/src/block_bootstrap_eval.py --timeframe all

# 4. Analisis daya tahan informasi ke depan (Forward Persistence)
python ml/src/forward_persistence_analysis.py --timeframe all

# 5. Uji sensitivitas ambang kuantil (Train-Only vs Full-History)
python ml/src/run_threshold_sensitivity.py --timeframe all
```

### Login

Semua halaman dashboard wajib login (Firebase Authentication, akun Google apa
pun boleh masuk). Salin `frontend/.env.example` menjadi `frontend/.env.local`
dan `backend/.env.example` menjadi `backend/.env`, lalu:

1. **Buat project Firebase** di <https://console.firebase.google.com>.
2. **Aktifkan metode login**: *Build → Authentication → Sign-in method*, lalu
   aktifkan **Google** dan **Email/Password** (dipakai form email, "Buat akun",
   dan "Lupa password?" di halaman login).
3. **Aktifkan Firestore**: *Build → Firestore Database → Create database*
   (mode production). Pasang aturan dari `firestore.rules` (menolak semua akses
   langsung dari browser; semua akses lewat server).
4. **Config web**: *Project settings → General → Your apps → Add app → Web*.
   Salin `apiKey`, `authDomain`, `projectId`, `appId` ke
   `NEXT_PUBLIC_FIREBASE_*` di `frontend/.env.local`.
5. **Kunci service account**: *Project settings → Service accounts → Generate
   new private key*. Simpan sebagai `secrets/firebase-service-account.json` di
   root project (folder `secrets/` diabaikan git). Frontend dan backend sama-sama
   membacanya lewat `FIREBASE_SERVICE_ACCOUNT`.
6. **Domain**: `localhost` sudah diizinkan bawaan. Bila dipasang online, tambahkan
   domainnya di *Authentication → Settings → Authorized domains*.
7. **Mode demo** (`DEMO_LOGIN=true` + `SESSION_SECRET`): tombol "Masuk mode demo"
   untuk sidang tanpa internet. Hanya berlaku bila dashboard dibuka lewat
   localhost; dari alamat lain permintaan ditolak.

Jalankan ulang `npm run dev` setelah mengubah `.env.local`.

### Notifikasi Telegram

Pengguna menautkan Telegram dari menu **Strategi → Notifikasi Telegram**:
dashboard membuat kode sekali pakai (15 menit) dan membuka
`t.me/<bot>?start=<kode>`; saat pengguna menekan Start, backend menyimpan chat
ID-nya di Firestore. Pengguna tidak perlu mencari chat ID sendiri.

1. Buat bot lewat **@BotFather** (`/newbot`), salin token dan username-nya.
2. Isi `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_BOT_USERNAME` di `backend/.env`, serta
   `TELEGRAM_BOT_TOKEN` dan `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` di
   `frontend/.env.local`.
3. Jalankan ulang backend. Bot memakai long polling, jadi tidak perlu alamat
   publik; jangan jalankan dua backend dengan token yang sama.

Notifikasi dikirim saat regime berganti dan sudah stabil
`NOTIFY_CONFIRM_WINDOWS` window berturut-turut (bawaan 3). Saat backend pertama
kali menyala, regime terkini hanya dicatat tanpa siaran. Setiap notifikasi
ditulis ke `data/signals/regime_notifications.jsonl` sebagai catatan uji maju.
Perintah bot: `/status`, `/stop`.

## Konfigurasi

Seluruh parameter berada di `config.yaml` di root — tidak ada parameter tersembunyi
di dalam kode. SHA-256 dari konfigurasi ditampilkan di footer setiap panel, sehingga
setiap angka di dashboard dapat ditelusuri ke konfigurasi yang menghasilkannya.

| Kelompok | Parameter |
|---|---|
| `source` | `provider`, `base_urls`, `years`, `drop_open_bar`, `auto_refresh`, `refresh_minutes` |
| `analysis` | `L` (rolling window), `J` (level SWT), ambang Hurst & DFA, `input: log_return` |
| `model` | `h` (horizon), `stride`, `purge_gap`, `tau`, `seed` |
| `split` | `ratios` — time-based, tanpa shuffle |
| `runtime` | `use_mock`, `storage` |

## Aturan metodologis yang ditegakkan di kode

1. **Hurst & DFA dihitung pada log-return, bukan harga level.** Harga bersifat
   non-stasioner (unit root); pada harga level estimasi H mendekati 1 untuk hampir
   semua window. Ditegakkan lewat validator di `app/core/config.py` dan diuji di
   `tests/test_hurst_dfa.py::test_log_return_membuang_unit_root`.

2. **SWT bersifat causal.** `pywt.swt` pada seluruh deret membuat koefisien di titik
   t menyerap sampel setelah t. Sistem menghitung ulang SWT per window dari data ≤ t.
   Dibuktikan di `tests/test_causal_swt.py`, lengkap dengan kontrol negatif yang
   menunjukkan pendekatan naif memang bocor.

3. **Target bersifat prediktif.** `X_t` dari data ≤ t, `Y_t = Regime(W_{t+h})` —
   bukan regime window yang sama, agar model tidak sekadar meniru rumus Hurst-DFA.

4. **Backtest hanya boleh memakai regime yang tersedia pada t.** Label ground truth
   ditolak sebagai sumber sinyal dengan HTTP 400. Diuji di
   `tests/test_api.py::test_backtest_menolak_ground_truth_sebagai_sumber_sinyal`.

5. **Dua jenis Uncertain dipisah.** `uncertain_rule` (Hurst & DFA tidak sepakat —
   soal DATA) dan `uncertain_lowconf` (`max(P) < τ` — soal MODEL) punya warna dan
   pola visual berbeda, serta dihitung terpisah di distribusi dan matriks transisi.

6. **Purge gap di batas split.** Sebesar `L + h` bar dibuang di batas train|val dan
   val|test agar window training tidak tumpang tindih dengan window test.

7. **Baseline Persistence wajib.** Panel Model Comparison menampilkan tebakan naif
   "regime t+h = regime t" sebagai ambang minimum. Metrik sekunder memakai balanced
   accuracy dan MCC karena kelas tidak seimbang.

   Metrik dilaporkan dalam **dua lapis** beserta cakupannya: `argmax` (daya
   diskriminasi tanpa ambang) dan `thresholded` (hanya window yang lolos τ).
   Tanpa pemisahan ini, model yang jarang yakin tercatat `BA = 0.0` seolah salah
   total, padahal artinya model memilih tidak menjawab. Diuji di
   `tests/test_regressions.py::test_coverage_nol_tidak_terbaca_sebagai_prediksi_salah`.

8. **Satuan bar vs window tidak boleh tertukar.** `L`, `h`, dan `purge_gap` di
   `config.yaml` bersatuan **bar**, sedangkan deret hasil analisis berindeks
   **window** (satu baris = `stride_bars` bar). Setiap konversi wajib lewat
   `splitting.bars_to_rows()` dengan `stride_bars` yang tersimpan sebagai kolom
   hasil — bukan diturunkan dari `effective_window`. Router dan pipeline training
   memakai helper yang sama agar horizon evaluasi tidak bisa berbeda dari horizon
   training. Diuji di `tests/test_regressions.py`.

9. **Purge dialokasikan sebelum rasio split.** `split_indices` memotong dua zona
   purge dari total lebih dulu, baru membagi sisanya menurut `split.ratios`.
   Urutan sebaliknya membuat purge memakan jatah validation dan test hingga
   keduanya bisa kosong tanpa error yang terlihat.

10. **Bar yang belum tutup tidak pernah masuk analisis.** `source.drop_open_bar`
    divalidasi harus `true`. Candle berjalan belum final, sehingga menyertakannya
    membuat label regime pada window terakhir berubah tiap penyegaran.

11. **Verifikasi TLS tidak pernah dimatikan.** Saat koneksi dicegat filter ISP,
    respons yang datang adalah halaman blokir, bukan data harga. Mematikan
    verifikasi tidak menyelamatkan data, hanya menyembunyikan kerusakannya.

12. **H(q) memakai estimator yang berbeda dari pembentuk label.** Generalized
    Hurst dihitung lewat fungsi struktur, bukan R/S maupun DFA yang membentuk
    label regime. Memakai estimator yang sama akan membuat model menghafal
    aturan ambang (label sirkular). Lebar spektrum diuji terhadap fBm
    monofraktal — yang harus mendekati nol — beserta kontrol positif berupa
    deret multifraktal. Lihat `tests/test_multifractal.py`.

13. **Hasil backtest wajib disertai diagnostik.** Equity curve saja tidak
    menjelaskan penyebab. `/api/v1/backtest/diagnostics` memisahkan kontribusi
    arah posisi, volatility drag, dan biaya; membandingkan terhadap posisi acak
    ber-exposure sama; serta menguji apakah asumsi arah pada aturan Bab 3
    berlaku. Tanpa ini, strategi ber-edge nol tetap terlihat "gagal" padahal
    kerugiannya murni efek compounding.

## Struktur

```
config.yaml            sumber tunggal seluruh parameter
backend/               FastAPI — analisis + inference (tidak pernah training)
  app/core/            loader config + config_hash
  app/db/repository.py abstraksi storage (ParquetRepository)
  app/services/        hurst_dfa, multifractal, swt, regime_labeling,
                       splitting, model_registry, backtest_engine,
                       data_ingestion, scheduler
  app/mock/            generator data sintetis (runtime.use_mock)
  tests/               125 test — estimator, multifraktal, kausalitas,
                       kontrak API, regresi, ingestion, inference, diagnostik
frontend/              Next.js 14 App Router + Tailwind + Lightweight Charts
ml/                    training offline (TensorFlow) — terpisah dari serving
  src/train.py         training model
  src/synthetic.py     dataset fBm dengan H diketahui (pretraining)
  src/train_multitask.py  pretraining fBm + fine-tune multi-task
  src/horizon_study.py sensitivitas horizon
  src/evaluate.py      evaluasi lawan baseline
data/processed/        artefak Parquet
infra/                 docker-compose + Dockerfile
```

## Halaman

| Route | Isi |
|---|---|
| `/` | Candlestick + overlay regime + batas train/purge/val/test |
| `/regime-explorer` | Hurst & DFA, distribusi, durasi, matriks transisi |
| `/model-comparison` | 3 model + Baseline Persistence, slider τ interaktif |
| `/swt` | Dekomposisi multiskala per level (causal) |
| `/attention` | Heatmap bobot α_t + candlestick window yang sama |
| `/timeframe-comparison` | 1H vs 4H berdampingan |
| `/backtest` | Equity curve vs Buy & Hold, Sharpe, drawdown, turnover, diagnostik |
| `/methodology` | Rumus (KaTeX) + diagram walk-forward |
| `/about` | Latar belakang, batasan, konfigurasi aktif |

Endpoint `GET /api/v1/analysis/multifractal` menyajikan H(q) untuk q = 1, 2, 4
beserta lebar spektrumnya; halaman yang menampilkannya belum dibuat.

## Training

```bash
cd ml
pip install -r requirements.txt
python src/train.py --timeframe 1h --model swt_attention_bilstm
python src/evaluate.py --timeframe 1h
```

Artefak tersimpan di `ml/artifacts/` beserta metadata `config_hash`. Backend membaca
artefak tersebut; backend tidak pernah mengimpor TensorFlow.

## Sumber data

`runtime.use_mock: false` — dashboard memakai data BTC/USDT asli dari Binance.

| Timeframe | Bar | Rentang |
|---|---|---|
| 1H | ~26.300 | 3 tahun terakhir |
| 4H | ~6.600 | 3 tahun terakhir |

Endpoint yang dipakai adalah `data-api.binance.vision`, mirror data pasar resmi
Binance. `api.binance.com` disimpan sebagai cadangan tetapi umumnya dicegat filter
ISP Indonesia (Telkomsel "Internet Baik", Indosat) yang menyodorkan sertifikat TLS
milik operator, sehingga verifikasi gagal. Mirror tersebut tidak ikut terblokir.

**Bar yang belum tutup selalu dibuang.** Candle berjalan masih berubah nilai
penutupnya; menyertakannya membuat Hurst dan label regime pada window terakhir
berubah setiap penyegaran. Karena itu jeda satu bar dari waktu sekarang adalah
perilaku yang benar, bukan tanda data tertinggal.

Verifikasi TLS tidak pernah dimatikan. Saat koneksi dicegat, yang dikirim balik
adalah halaman blokir — mematikan verifikasi hanya menyembunyikan bahwa datanya
sudah rusak. Bila sumber tidak dapat dihubungi, `/api/v1/data/connectivity`
melaporkan penyebabnya dan dashboard tetap melayani data terakhir yang tersimpan.

```bash
# Tarik ulang seluruh rentang
curl -X POST http://localhost:8000/api/v1/data/refresh -d '{"full":true}' -H "Content-Type: application/json"

# Periksa kesegaran data + status scheduler
curl http://localhost:8000/api/v1/data/status
```

Penyegaran berkala berjalan otomatis tiap `source.refresh_minutes` menit. Untuk
demo yang benar-benar statis, setel `source.auto_refresh: false`.

Untuk kembali ke data sintetis, setel `runtime.use_mock: true`.

## Status model

Empat artefak tersedia di `ml/artifacts/` (2 model × 2 timeframe), hasil
`ml/src/train.py`. Backend memuatnya langsung untuk inference dan bobot attention.

Hasil pada 1H, `tau = 0.40`, h = 500 bar:

| Model | Cakupan | BA (argmax) | BA (setelah τ) |
|---|---|---|---|
| SWT + Attention-BiLSTM | 36.3% | **0.409** | 0.490 |
| SWT + BiLSTM | 6.3% | 0.374 | 0.407 |
| Hurst-DFA rule-based | 94.6% | 0.326 | 0.325 |
| Baseline Persistence | 53.2% | 0.144 | 0.271 |

Tebakan seragam tiga kelas menghasilkan BA ≈ 0.333. Model usulan mengungguli
seluruh pembanding, dan komponen attention memberi kontribusi terukur
(0.409 vs 0.374). Cakupan di bawah 100% berarti model menahan diri saat tidak
yakin — bukan menjawab salah.

Latih ulang:

```bash
python ml/src/train.py --timeframe 1h --model both --epochs 60
python ml/src/train.py --timeframe 4h --model both --epochs 60
```

### Pretraining fBm + multi-task

```bash
python ml/src/train_multitask.py --timeframe 1h
python ml/src/train_multitask.py --timeframe 1h --no-pretrain    # ablasi
python ml/src/train_multitask.py --timeframe 1h --lambda-reg 0   # ablasi
```

Model dilatih dulu pada fractional Brownian motion dengan H **diketahui
persis**, lalu di-fine-tune ke BTC. Arsitekturnya punya dua head yang berbagi
encoder: klasifikasi regime dan regresi nilai H kontinu, dengan loss
`CE + lambda·MSE`.

Alasan head regresi: label regime adalah hasil diskretisasi H lewat ambang, dan
diskretisasi membuang informasi — H = 0.56 dan H = 0.85 mendapat label sama
padahal jaraknya jauh. Head kedua memaksa representasi internal tetap membawa
besaran kontinu itu.

Dua flag ablasi di atas mengukur kontribusi masing-masing komponen. Hasil
ablasi penuh belum diproduksi; skripnya sudah terverifikasi berjalan
end-to-end.

### Sensitivitas horizon

```bash
python ml/src/horizon_study.py --timeframe 1h --horizons 125 250 500 1000
```

Melatih ulang model pada beberapa nilai `h` dan membandingkan tiap horizon
terhadap Baseline Persistence **pada horizon yang sama**:

| h (bar) | ~hari | BA model | BA baseline | Selisih |
|---|---|---|---|---|
| 125 | 5.2 | 0.393 | 0.638 | −0.246 |
| 250 | 10.4 | 0.370 | 0.493 | −0.123 |
| **500** | **20.8** | **0.346** | **0.271** | **+0.075** |
| 1000 | 41.7 | 0.323 | 0.348 | −0.025 |

Balanced accuracy mentah tidak sebanding antar horizon: pada horizon pendek
regime jarang berubah sehingga tebakan naif otomatis tinggi. Yang sebanding
adalah selisih terhadap baseline. Model hanya unggul pada h = 500 bar — di bawah
itu persistensi terlalu mudah ditebak, di atasnya sinyal habis.

Hasil dibaca lewat `GET /api/v1/model/horizon-study?tf=1h` dan ditampilkan di
panel Sensitivitas Horizon.

Ketersediaan artefak model terpisah dari `runtime.use_mock`: flag tersebut hanya
mengatur sumber data harga. Data pasar asli dapat dipakai jauh sebelum model dilatih.
Bila artefak belum ada, sistem memakai stand-in deterministik dan menyatakannya
lewat `prediction_source: placeholder`.

## Verifikasi

```bash
cd backend && python -m pytest tests -q     # 125 passed
cd frontend && npm run build                # 12 route
```

Jangan menjalankan `npm run build` saat `npm run dev` sedang hidup: keduanya
memakai folder `.next` yang sama dan dev server akan kehilangan chunk-nya.
Bila terjadi, hentikan dev server, hapus `.next`, lalu jalankan ulang.

Test dijalankan pada data mock di direktori sementara (`tests/conftest.py`), tidak
menyentuh jaringan maupun `data/processed/`. Dengan begitu hasilnya deterministik
dan tetap lolos di jaringan yang memblokir exchange.

# Peta Navigasi Codebase & Fungsi Seluruh File (Pegangan Sidang Skripsi)

**Proyek:** `RegimeFraktalVFK` — *Identifikasi Regime Pasar Kripto Berbasis Analisis Fraktal (Hurst-DFA), Causal SWT, dan BiLSTM-Attention*  
**Tujuan Dokumen:** Menjadi buku pegangan cepat (*cheat sheet*) saat Sidang Skripsi agar Anda mengetahui fungsi setiap folder, file, dan baris kode penting ketika diminta mendemokan atau membedah program oleh Dosen Penguji.

---

## DAFTAR ISI
1. [Struktur Pohon Direktori Utama](#1-struktur-pohon-direktori-utama)
2. [Penjelasan Detail Folder Tingkat Atas (Top-Level)](#2-penjelasan-detail-folder-tingkat-atas-top-level)
   - [2.1 `.github/` & `.vscode/`](#21-github--vscode)
   - [2.2 `backend/` (Mesin Utama FastAPI & Algoritma Kuantitatif)](#22-backend-mesin-utama-fastapi--algoritma-kuantitatif)
   - [2.3 `data/` (Penyimpanan Dataset Parquet)](#23-data-penyimpanan-dataset-parquet)
   - [2.4 `docs/` (Dokumentasi Naskah & Pengujian)](#24-docs-dokumentasi-naskah--pengujian)
   - [2.5 `frontend/` (Antarmuka Web Next.js 14 & TradingView)](#25-frontend-antarmuka-web-nextjs-14--tradingview)
   - [2.6 `infra/` (Docker & Deployment VPS)](#26-infra-docker--deployment-vps)
3. [Penjelasan Detail Folder Eksperimen & Operasional (`ml/`, `reports/`, `scripts/`, `secrets/`)](#3-penjelasan-detail-folder-eksperimen--operasional-ml-reports-scripts-secrets)
   - [3.1 `ml/` (Laboratorium Eksperimen & Pelatihan Model)](#31-ml-laboratorium-eksperimen--pelatihan-model)
   - [3.2 `reports/` (Hasil Evaluasi Strategi Mode A & Mode B)](#32-reports-hasil-evaluasi-strategi-mode-a--mode-b)
   - [3.3 `scripts/` (Skrip Utilitas & Persiapan Demo Sidang)](#33-scripts-skrip-utilitas--persiapan-demo-sidang)
   - [3.4 `secrets/` (Kredensial Autentikasi)](#34-secrets-kredensial-autentikasi)
4. [Penjelasan File Konfigurasi & Dokumen di Root Proyek](#4-penjelasan-file-konfigurasi--dokumen-di-root-proyek)
5. [Tabel Peta Cepat: "Jika Dosen Penguji Bertanya X, Buka File Y"](#5-tabel-peta-cepat-jika-dosen-penguji-bertanya-x-buka-file-y)

---

## 1. Struktur Pohon Direktori Utama

```text
btcusdt-regime-dashboard/
├── .github/workflows/ci.yml        # Pipeline CI otomatis (pytest + Next.js build)
├── .vscode/                        # Konfigurasi editor VS Code
├── backend/                        # Server REST API (Python FastAPI) & Mesin Fraktal
│   ├── app/
│   │   ├── core/                   # Konfigurasi sistem, konstanta, security
│   │   ├── db/                     # Repository pembacaan & caching Parquet
│   │   ├── routers/                # Endpoint HTTP API (/ohlcv, /model, /analysis, /backtest)
│   │   ├── schemas/                # Kontrak data Pydantic (validasi response JSON)
│   │   ├── services/               # INTI ALGORITMA (Hurst-DFA, SWT, Pelabelan, Jump Model, AI)
│   │   └── main.py                 # Entry point aplikasi FastAPI
│   ├── tests/                      # 251 Unit Test White-Box (pytest)
│   └── requirements.txt            # Daftar dependensi Python backend
├── data/                           # Penyimpanan lokal dataset OHLCV & cache fitur (.parquet)
├── docs/                           # Dokumen referensi Bab 1-4, QA Jira, UAT/SUS, Q&A Sidang
├── frontend/                       # Aplikasi Web Dashboard (Next.js 14, TypeScript, Tailwind)
│   ├── app/                        # Halaman rute web (/, /walk-forward-evaluation, /swt, dll.)
│   ├── components/                 # Komponen grafik TradingView (CandlestickChart, TopNav, dll.)
│   └── lib/                        # Klien HTTP API, autentikasi Firebase, state store
├── infra/                          # Dockerfile, docker-compose, dan Caddyfile untuk VPS
├── ml/                             # Pipeline Pelatihan & Eksperimen Ilmiah Machine Learning
│   ├── artifacts/                  # Bobot model (.pt), JSON evaluasi, & seri Walk-Forward
│   ├── notebooks/                  # Notebook Jupyter eksplorasi awal
│   ├── src/                        # Skrip pelatihan BiLSTM-Attention & studi ilmiah Bab 4
│   └── requirements.txt            # Dependensi pelatihan ML
├── reports/                        # Laporan CSV/HTML hasil simulasi strategi (mode_A & mode_B)
├── scripts/                        # Skrip operasional (launch_demo.ps1, olah_uat_sus.py, dll.)
├── secrets/                        # Kunci akun layanan Firebase (diabaikan oleh git)
├── config.yaml                     # Parameter ilmiah utama yang dikunci dengan hash SHA-256
├── setup_engine.yaml               # Konfigurasi parameter evaluasi strategi regime-conditioned
├── firestore.rules                 # Aturan keamanan akses database Cloud Firestore
├── pyrefly.toml & pyrightconfig.json # Konfigurasi static type checker Python
├── README.md                       # Dokumentasi utama repositori
├── THESIS_CODEBASE_AUDIT.md        # Ringkasan audit arsitektur & bebas kebocoran data
├── THESIS_MULTI_ASSET_WALK_FORWARD.md # Laporan hasil Walk-Forward 2019-2026 pada 12 aset
└── THESIS_UPDATED_RESULTS.md       # Ringkasan angka-angka final untuk Bab 4
```

---

## 2. Penjelasan Detail Folder Tingkat Atas (*Top-Level*)

### 2.1 `.github/` & `.vscode/`
* **`.github/workflows/ci.yml`:** Pipeline *Continuous Integration (CI)* di GitHub Actions. Setiap ada `git push`, GitHub otomatis menjalankan dua pekerjaan (*jobs*):
  1. `backend`: Menguji seluruh 251 unit test `pytest` (estimator Hurst-DFA, kausalitas SWT, kontrak API).
  2. `frontend`: Menguji pemeriksaan tipe TypeScript (`tsc --noEmit`) dan `next build`.
* **`.vscode/`:** Pengaturan lokal editor VS Code agar mengarah ke virtual environment Python yang tepat.

---

### 2.2 `backend/` (Mesin Utama FastAPI & Algoritma Kuantitatif)

#### A. `backend/app/main.py` & `backend/app/core/`
* **`backend/app/main.py`:** Titik masuk (*entry point*) server FastAPI. Mengatur *middleware* CORS, mengaktifkan *background scheduler* penarikan data, dan mendaftarkan seluruh *router* API.
* **`backend/app/core/config.py`:** Membaca file `config.yaml`, memvalidasi parameter, dan menghitung **SHA-256 Hash** konfigurasi untuk menjamin reproduktifitas eksperimen.
* **`backend/app/core/security.py`:** Memverifikasi token autentikasi Firebase pengguna serta menyediakan mode *bypass* aman khusus `localhost` saat demonstrasi sidang offline.

#### B. `backend/app/db/repository.py`
* **`repository.py`:** Lapisan akses data (*Data Access Layer*). Bertugas membaca file OHLCV `.parquet`, menjalankan pembaruan fitur secara inkremental (hanya menghitung bar baru agar cepat), serta menyimpan hasil di memori (*in-memory cache*) dan disk (`data/processed/`).

#### C. `backend/app/services/` (Jantung Algoritma Skripsi Anda)
| Nama File | Fungsi Utama & Peran Ilmiah di Skripsi |
| :--- | :--- |
| **`hurst_dfa.py`** | Menghitung eksponen **Rolling Hurst R/S ($H$)** dengan koreksi Anis-Lloyd, **Detrended Fluctuation Analysis ($\alpha$)** orde-1, dan **Multiscale Efficiency Ratio (ER)** pada jendela geser $L=500$. |
| **`swt.py`** | Menghitung dekomposisi **Causal Stationary Wavelet Transform (SWT)** menggunakan wavelet *Daubechies-4 (`db4`)* hingga 4 level. Fungsi `causal_swt_at()` memotong deret tepat di indeks $t$ sehingga **mustahil bocor ke masa depan ($t+1$)**. |
| **`regime_labeling.py`** | Berisi fungsi **`label_from_exponents()`** (aturan konsensus *Trend-Aware Soft Consensus* untuk menetapkan label *Persistent*, *Random-Like*, *Anti-Persistent*, atau `uncertain_rule`) dan fungsi **`apply_tau()`** (mengubah prediksi model dengan probabilitas $\max(P) < \tau$ menjadi `uncertain_lowconf`). |
| **`jump_model.py`** | Mengimplementasikan **Statistical Jump Model (SJM)** berbasis pemrograman dinamis (*Viterbi-like dynamic programming*) dengan penalti pergantian $\lambda = 0{,}5$ untuk menekan *whipsaw* (noise pergantian regime palsu). |
| **`multifractal.py`** | Menghitung spektrum **Multifractal DFA (MF-DFA)** pada momen $q \in \{1, 2, 4\}$ serta lebar spektrum $\Delta H = H(1) - H(4)$ untuk mengukur derajat multifraktalitas pasar. |
| **`ai_detector.py` & `inference.py`** | Memuat bobot model terlatih (*BiLSTM-Attention* & *LightGBM*) dan menjalankan inferensi identifikasi regime ($h=0$ / *Nowcasting*) secara real-time maupun historis. |
| **`walk_forward.py`** | Layanan evaluasi lintas lipatan waktu (*walk-forward folds*) pada backend. |
| **`backtest_engine.py` & `setup_engine/`** | Mesin pengujian strategi perdagangan terkondisi regime (*regime-conditioned strategy evaluation*) lengkap dengan potongan biaya transaksi *taker fee* 0,075% dan *slippage*. |
| **`order_flow.py` & `orderflow_features.py`** | Menghitung ketidakseimbangan arus order (*Taker Buy Ratio*, *Cumulative Volume Delta / CVD*) sebagai fitur mikrostruktur pendamping. |
| **`telegram_bot.py` & `regime_notifier.py`** | Mengelola bot Telegram dan mengirim notifikasi otomatis ke ponsel pengguna ketika terjadi transisi regime yang telah terkonfirmasi stabil selama $N$ bar berturut-turut. |
| **`data_ingestion.py` & `scheduler.py`** | Menarik data candlestick terbaru dari mirror publik Binance Vision secara berkala dengan aturan `drop_open_bar: true` (bar yang belum tutup tidak ikut dihitung). |

#### D. `backend/app/routers/` (Endpoint HTTP REST API)
* **`ohlcv.py`:** Melayani endpoint `/api/v1/ohlcv` (data harga candlestick) dan `/api/v1/regime` (data label regime, nilai $H$, $\alpha$, dan matriks transisi).
* **`model.py`:** Melayani endpoint `/api/v1/model/compare` (perbandingan metrik BiLSTM-Attention vs LightGBM vs Baseline), `/api/v1/model/walk-forward-multi-asset` (ringkasan akurasi 12 aset), dan `/api/v1/model/walk-forward-timeline` (data candlestick + pita regime 2019–2026).
* **`analysis.py`:** Melayani endpoint `/api/v1/analysis/multifractal`, `/api/v1/analysis/swt`, dan `/api/v1/analysis/order-flow`.
* **`backtest.py`:** Melayani endpoint simulasi strategi berbasis regime (`/api/v1/backtest`).
* **`meta.py` & `internal.py`:** Melayani status kesehatan server (`/health`), informasi hash konfigurasi SHA-256, dan tautan akun Telegram.

#### E. `backend/tests/` (Pengujian *White-Box* `pytest`)
Berisi **251 pengujian otomatis**, di antaranya:
* **`test_causal_swt.py`:** Bukti matematis bahwa koefisien SWT pada waktu $t$ tidak berubah sedikit pun ($\text{atol} = 10^{-12}$) walaupun data masa depan $t+1 \dots T$ ditambahkan.
* **`test_hurst_dfa.py` & `test_synthetic_regimes.py`:** Menguji akurasi estimator Hurst dan DFA pada deret sintetis *fractional Brownian motion (fBm)*.
* **`test_ai_detector_abstain.py`:** Menguji mekanisme abstensi दो-lapis (`uncertain_rule` vs `uncertain_lowconf`).
* **`test_regressions.py`:** Menguji konsistensi perhitungan penuh vs perhitungan inkremental.

---

### 2.3 `data/` (Penyimpanan Dataset Parquet)
* **`data/raw/`:** Menyimpan file Parquet OHLCV mentah untuk **12 aset lintas kelas** (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `ADAUSDT`, `DOGEUSDT`, `TAOUSDT`, `PAXGUSDT`, `GCF` Emas Berjangka, `SIF` Perak Berjangka, dan `ANTMJK` Saham Aneka Tambang IDX) pada berbagai timeframe (`1h`, `4h`, `1d`).
* **`data/processed/`:** Menyimpan cache hasil perhitungan fitur fraktal dan label regime agar pemuatan dashboard berlangsung instan ($<80\text{ ms}$).

---

### 2.4 `docs/` (Dokumentasi Naskah & Pengujian)
* **`PANDUAN_PENGUJIAN_QA_JIRA_DAN_UAT.md`:** Dokumentasi pengujian *Black-Box* menggunakan **Jira** (`RFVFK-TC01` s/d `TC17` dan `RFVFK-BUG01` s/d `BUG04`) serta hasil pengujian **UAT & SUS** (Skor **80,5 / Grade A-**).
* **`PENGUJIAN_WHITEBOX_DAN_BLACKBOX.md`:** Dokumentasi detail *Basis Path Testing*, *Cyclomatic Complexity* $V(G)$, dan *Equivalence Partitioning*.
* **`tanya_jawab_sidang.md`:** Bank jawaban untuk menghadapi pertanyaan kritis dosen penguji.
* **`bab3_metodologi.md` & `bab4_hasil.md`:** Draf narasi metodologi dan hasil eksperimen.

---

### 2.5 `frontend/` (Antarmuka Web Next.js 14 & TradingView)
* **`frontend/app/page.tsx`:** Halaman utama dashboard. Menampilkan grafik candlestick BTC/USDT dengan pita warna regime (*Hijau = Persistent*, *Merah = Anti-Persistent*, *Abu-abu = Uncertain*), indikator eksponen $H$ & $\alpha$ terkini, serta matriks probabilitas transisi.
* **`frontend/app/walk-forward-evaluation/page.tsx`:** Halaman **Walk-Forward Regime Identification (2019 $\rightarrow$ 2026)**. Menampilkan grafik interaktif *TradingView Lightweight Charts* sepanjang 7 tahun untuk 12 aset, metrik akurasi per lipatan tahunan (*yearly folds*), dan distribusi proporsi regime.
* **`frontend/app/model-comparison/page.tsx`:** Halaman perbandingan performa *BiLSTM-Attention*, *LightGBM*, *Random Forest*, dan *Markov Baseline* beserta slider interaktif ambang abstensi $\tau$.
* **`frontend/app/multifractal/page.tsx` & `frontend/app/swt/page.tsx`:** Halaman visualisasi kurva spektrum multifraktal $H(q)$ dan sub-band dekomposisi gelombang *Causal SWT* ($A_4, D_4, D_3, D_2, D_1$).
* **`frontend/components/CandlestickChart.tsx`:** Komponen grafik utama yang membungkus *TradingView Lightweight Charts* dengan *overlay* pita warna regime dan penanda batas *Train / Val / Test*.

---

### 2.6 `infra/` (Docker & Deployment VPS)
* **`Dockerfile.backend` & `Dockerfile.frontend`:** Instruksi pembuatan image kontainer untuk server FastAPI dan aplikasi web Next.js.
* **`docker-compose.yml` & `docker-compose.vps.yml`:** Orkestrasi seluruh layanan (backend, frontend, dan proxy Caddy) dalam satu perintah `docker compose up -d`.
* **`Caddyfile`:** Konfigurasi web server Caddy untuk mengatur domain dan sertifikat HTTPS/SSL otomatis.
* **`.env.example`:** Template variabel lingkungan (*environment variables*) untuk konfigurasi port, URL API, dan token bot Telegram.

---

## 3. Penjelasan Detail Folder Eksperimen & Operasional (`ml/`, `reports/`, `scripts/`, `secrets/`)

### 3.1 `ml/` (Laboratorium Eksperimen & Pelatihan Model)

#### A. `ml/artifacts/`
Folder tempat menyimpan seluruh output eksperimen yang sudah diverifikasi:
* **`multi_asset_walk_forward_2019_2026.json`:** Hasil numerik evaluasi Walk-Forward 2019–2026 pada 12 aset (rata-rata BA **88,24%**).
* **`walk_forward_series/wf_series_*.parquet`:** 23 file deret waktu hasil prediksi *out-of-sample* Walk-Forward (2019–2026) yang disajikan langsung ke grafik TradingView di halaman `/walk-forward-evaluation`.
* **`sweet_spot_study.json` & `horizon_study.json`:** Artefak hasil eksperimen optimasi regularisasi dan studi peluruhan horizon prediksi.

#### B. `ml/src/` (Skrip Eksperimen Ilmiah Bab 4)
| Nama File di `ml/src/` | Fungsi Eksperimen |
| :--- | :--- |
| **`model_architecture.py`** | Mendefinisikan arsitektur jaringan **BiLSTM 2-Lapis + Bahdanau Temporal Attention** beserta fungsi kerugian **Focal Loss** ($\gamma=2{,}0$). |
| **`train.py` & `evaluate.py`** | Melatih model pada split *Train* (dengan aturan `threshold_source: train_only`) dan mengevaluasi metrik dua-lapis pada split *Validation* & *Test*. |
| **`run_multi_asset_walk_forward.py`** | Menjalankan protokol **Expanding-Window Walk-Forward (2019 $\rightarrow$ 2026)** dari tahun ke tahun pada 12 aset lintas kelas tanpa kebocoran masa depan. |
| **`run_sweet_spot_study.py`** | Mencari kombinasi hiperparameter terbaik (*Sweet Spot*) antara kapasitas jaringan, *dropout*, dan penalti lompatan $\lambda$. |
| **`horizon_study.py`** | Menguji horizon $h=0$ (*Nowcasting*) vs $h \in \{1, 2, 4, 8, 24\}$ (*Forecasting*) untuk membuktikan bahwa struktur fraktal bekerja sebagai pengidentifikasi status pasar saat ini ($h=0$). |
| **`leakage_study.py`** | Membuktikan secara kuantitatif seberapa besar bias yang terjadi jika kalibrasi kuantil atau SWT dilakukan secara non-kausal (`full_history`) dibandingkan protokol kausal (`train_only`). |
| **`calibrate_synthetic.py`** | Eksperimen Fase 1 pada deret sintetis *fractional Brownian motion (fBm)* dengan $H$ diketahui untuk memvalidasi akurasi estimator dasar. |
| **`tune_jump_penalty.py`** | Eksperimen penalaan penalti $\lambda$ pada *Statistical Jump Model* untuk menyeimbangkan reduksi *whipsaw* vs kesepakatan label dasar. |

---

### 3.2 `reports/` (Hasil Evaluasi Strategi `mode_A` & `mode_B`)
Berisi laporan CSV dan visualisasi HTML dari pengujian aplikasi praktis (*Decision Support System*):
* **`reports/mode_A/`:** Hasil evaluasi aturan penyaringan ketat (*Mode A*) beserta tabel sensitivitas parameter (`sensitivity_grid.csv`, `regime_conditioned_results.csv`, `trade_log.csv`).
* **`reports/mode_B/`:** Hasil evaluasi aturan eksekusi terkondisi regime (*Mode B*), mendokumentasikan perbandingan kurva ekuitas kumulatif ($R_{\text{net}}$) dan penurunan *Maximum Drawdown (MDD)* ketika eksposur ditahan pada zona `uncertain`.

---

### 3.3 `scripts/` (Skrip Utilitas & Persiapan Demo Sidang)
* **`build_regime_parquet.py`:** Memproses ulang seluruh file OHLCV mentah di `data/raw/` menjadi file fitur lengkap di `data/processed/`.
* **`check_offline_ready.py`:** Memvalidasi kesiapan seluruh file data dan artefak lokal sebelum sidang agar aplikasi dapat didemokan **100% tanpa internet**.
* **`launch_demo.ps1`:** Skrip PowerShell praktis untuk menyalakan server Backend FastAPI dan Frontend Next.js secara bersamaan saat sidang.
* **`olah_uat_sus.py`:** Menghitung skor rata-rata **System Usability Scale (SUS)** dan rekapitulasi keberhasilan tugas **UAT** dari data kuesioner responden.
* **`pack_for_deploy.ps1`:** Mengarsipkan proyek menjadi paket siap unggah ke VPS.
* **`rerun_train_only.sh`:** Menjalankan ulang seluruh pipeline pelatihan dan evaluasi dengan penguncian ambang `train_only`.

---

### 3.4 `secrets/` (Kredensial Autentikasi)
* **`firebase-service-account.json`:** Kunci privat Firebase Admin SDK untuk memvalidasi token login Google/Email dan menyimpan tautan Telegram pengguna di Firestore. File ini tidak pernah di-upload ke GitHub (dilindungi oleh `.gitignore`).

---

## 4. Penjelasan File Konfigurasi & Dokumen di Root Proyek

* **`config.yaml`:** Pusat kendali seluruh parameter ilmiah proyek (window $L=500$, wavelet `db4` level 4, kuantil kalibrasi `train_only`, $\lambda = 0{,}5$, $\tau = 0{,}40$). Setiap perubahan pada file ini otomatis mengubah sidik jari **SHA-256** di bagian bawah (*footer*) dashboard.
* **`setup_engine.yaml`:** Konfigurasi parameter simulasi *setup engine* (biaya komisi *taker* 0,075%, *slippage* 1 tick, dan aturan manajemen risiko).
* **`firestore.rules`:** Aturan hak akses database Cloud Firestore.
* **`pyrefly.toml` & `pyrightconfig.json`:** Konfigurasi pemeriksa tipe statis Python (*static type checking*).
* **`THESIS_CODEBASE_AUDIT.md`:** Bukti tertulis audit menyeluruh terhadap kode sumber bahwa tidak ada *dead code* maupun *data leakage*.
* **`THESIS_MULTI_ASSET_WALK_FORWARD.md`:** Ringkasan eksekutif hasil pengujian Walk-Forward 12 aset (2019–2026) untuk bahan presentasi sidang.
* **`THESIS_UPDATED_RESULTS.md`:** Kumpulan tabel metrik final yang sinkron antara kode program dan naskah Bab 4.

---

## 5. Tabel Peta Cepat: "Jika Dosen Penguji Bertanya X, Buka File Y"

Gunakan tabel ini saat Dosen Penguji meminta Anda menunjukkan bukti langsung di VS Code:

| No | Pertanyaan / Permintaan Dosen Penguji | File yang Harus Anda Buka di VS Code |
| :---: | :--- | :--- |
| 1 | *"Tunjukkan di mana kamu menulis rumus **Hurst Exponent (R/S)** dan **DFA**!"* | `backend/app/services/hurst_dfa.py` (Fungsi `hurst_rs` & `dfa_alpha`) |
| 2 | *"Bagaimana kamu menjamin **Wavelet SWT** tidak melihat data masa depan (look-ahead bias)?"* | `backend/app/services/swt.py` (Fungsi `causal_swt_at`) & bukti ujinya di `backend/tests/test_causal_swt.py` |
| 3 | *"Tunjukkan logika kode yang memisahkan **Persistent, Anti-Persistent, Random-Like, dan Uncertain**!"* | `backend/app/services/regime_labeling.py` (Fungsi `label_from_exponents` di baris 130 & `apply_tau` di baris 238) |
| 4 | *"Bagaimana cara kerja **Statistical Jump Model (SJM)** meredam whipsaw di kodinganmu?"* | `backend/app/services/jump_model.py` |
| 5 | *"Tunjukkan arsitektur **BiLSTM + Temporal Attention** dan **Focal Loss** yang kamu pakai!"* | `ml/src/model_architecture.py` |
| 6 | *"Mana kode eksperimen **Walk-Forward 2019–2026 pada 12 aset**?"* | Skrip: `ml/src/run_multi_asset_walk_forward.py` <br>API: `backend/app/routers/model.py` <br>UI Grafik: `frontend/app/walk-forward-evaluation/page.tsx` |
| 7 | *"Kenapa sistem ini disebut **Regime Identification ($h=0$)**, bukan Forecasting harga ($h>0$)?"* | Buka `ml/src/horizon_study.py` — tunjukkan bahwa eksperimen membuktikan struktur fraktal mengukur keadaan pasar saat ini ($h=0$, BA ~90%), sedangkan $h \ge 1$ meluruh ke ~33%. |
| 8 | *"Bagaimana kamu melakukan **White-Box Testing** dan **Black-Box Testing (Jira)**?"* | White-Box: folder `backend/tests/` (`pytest`) & `docs/PENGUJIAN_WHITEBOX_DAN_BLACKBOX.md` <br>Black-Box Jira & UAT: `docs/PANDUAN_PENGUJIAN_QA_JIRA_DAN_UAT.md` |
| 9 | *"Di mana semua parameter penelitian dikunci supaya tidak dimanipulasi?"* | `config.yaml` & perhitungan SHA-256 di `backend/app/core/config.py` |

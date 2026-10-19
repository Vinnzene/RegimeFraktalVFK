# Product Requirements Document (PRD)
## Web Dashboard: Identifikasi Regime Fraktal Dinamis BTC/USDT Multi-Timeframe (SWT + Attention-BiLSTM berbasis Hurst-DFA)

| | |
|---|---|
| **Dokumen** | PRD v1.0 |
| **Disusun oleh** | Claude (sebagai Project Manager) |
| **Berdasarkan** | Skripsi — Vinnzene Fernando Karim (32230115), Universitas Bunda Mulia, 2026 |
| **Tanggal** | 9 September 2026 |
| **Status** | Draft untuk direview |

---

## 1. Latar Belakang

Skripsi ini mengangkat pendekatan identifikasi **regime karakteristik** (persistent, random-like, anti-persistent) pada time series BTC/USDT, bukan prediksi harga langsung. Metode yang dipakai:

- **Hurst Exponent + Detrended Fluctuation Analysis (DFA)** — dihitung secara *rolling window* untuk mengkarakterisasi kecenderungan persistensi.
- **Stationary Wavelet Transform (SWT)** — merepresentasikan data pada beberapa skala (multiscale).
- **Attention-BiLSTM** — mempelajari pola temporal dari representasi SWT untuk mengidentifikasi regime.
- **Timeframe pembanding**: 1 jam (1H) dan 4 jam (4H).
- **Backtesting** — sebagai analisis tambahan penerapan informasi regime pada data historis (bukan jaminan profit).

Website ini dibuat sebagai **alat bantu visualisasi dan eksplorasi hasil penelitian** — mengubah keluaran analisis (regime label, metrik Hurst-DFA, dekomposisi SWT, prediksi Attention-BiLSTM, hasil backtest) menjadi dashboard interaktif yang bisa dipakai untuk sidang, demo, maupun eksplorasi lanjutan.

> **Catatan PM**: Skripsi yang diunggah baru berisi Bab 1 (Pendahuluan) secara utuh — Bab 2 (Tinjauan Pustaka) dan Bab 3 (Analisis & Perancangan) belum tersedia isinya, hanya kerangka sistematika penulisan. PRD ini disusun berdasarkan pembatasan masalah, rumusan masalah, dan tujuan pada Bab 1. Begitu Bab 3 (perancangan sistem, spesifikasi model, skema data) tersedia, PRD ini **wajib direvisi** — terutama bagian arsitektur model dan skema data — agar konsisten dengan rancangan resmi di skripsi.

---

## 2. Tujuan Produk

1. Menyediakan dashboard yang menampilkan **regime aktif** BTC/USDT (persistent / random-like / anti-persistent) untuk timeframe 1H dan 4H.
2. Memvisualisasikan **proses analisis**: harga → SWT decomposition → Hurst-DFA rolling window → klasifikasi regime via Attention-BiLSTM.
3. Menyajikan **perbandingan 1H vs 4H** agar terlihat apakah karakteristik regime berubah sesuai skala waktu.
4. Menyediakan modul **backtesting** yang menunjukkan bagaimana informasi regime dapat diterapkan pada data historis.
5. Menjadi alat pendukung sidang skripsi & portofolio, dengan kemungkinan dikembangkan lebih lanjut sebagai riset lanjutan.

## 3. Target Pengguna

- **Utama**: penulis skripsi sendiri (untuk demo sidang dan analisis eksploratif).
- **Sekunder**: dosen penguji/pembimbing yang ingin mengeksplorasi hasil.
- **Tersier**: pembaca/peneliti lain yang tertarik pada pendekatan regime fraktal (non-prediksi harga) di aset kripto.

## 4. Ruang Lingkup

### In-scope
- Ingest data historis OHLCV BTC/USDT (1H & 4H).
- Pipeline analisis: SWT → Hurst-DFA rolling window → label regime → Attention-BiLSTM.
- Visualisasi candlestick + overlay regime (color-coded band).
- Visualisasi dekomposisi SWT multiskala.
- Visualisasi metrik Hurst Exponent & DFA sepanjang waktu.
- Perbandingan side-by-side 1H vs 4H.
- Modul backtesting sederhana berbasis sinyal regime (equity curve, drawdown, win-rate) — **eksploratif, bukan rekomendasi trading**.
- Halaman metodologi (menjelaskan Hurst-DFA, SWT, Attention-BiLSTM secara ringkas untuk audiens sidang).

### Out-of-scope (sesuai Pembatasan Masalah Bab 1)
- Prediksi harga langsung sebagai output utama.
- Faktor eksternal: berita, sentimen sosial media, makroekonomi, fundamental.
- Live trading / eksekusi order otomatis ke exchange.
- Evaluasi model dengan accuracy/precision/recall/F1 sebagai indikator utama (skripsi eksplisit tidak memakai ini sebagai metrik keberhasilan utama — dashboard cukup menampilkannya sebagai info sekunder jika relevan, bukan headline metric).
- Data selain BTC/USDT.
- Multi-user login/roles kompleks (v1 cukup single-user atau tanpa auth, sesuai kebutuhan demo).

## 5. Rumusan Masalah → Fitur Produk

| Rumusan Masalah (Bab 1) | Fitur Website |
|---|---|
| Karakteristik regime fraktal berdasarkan Hurst-DFA | Panel "Regime Explorer": grafik Hurst & DFA rolling window + label regime saat ini |
| SWT + Attention-BiLSTM untuk identifikasi regime | Panel "Model Pipeline": visualisasi SWT decomposition dan output klasifikasi regime dari model |
| Perbedaan regime 1H vs 4H + backtesting | Panel "Timeframe Comparison" dan Panel "Backtest Result" |

## 6. Functional Requirements

### 6.1 Data Layer
- FR-1: Sistem dapat menarik data OHLCV BTC/USDT historis (1H, 4H) dari exchange API.
- FR-2: Sistem menyimpan data historis di database time series agar tidak fetch berulang.
- FR-3: Sistem dapat melakukan refresh data terbaru (scheduled job, mis. tiap jam).

### 6.2 Analysis Pipeline
- FR-4: Sistem menghitung Hurst Exponent & DFA dengan rolling window (parameter window dapat dikonfigurasi).
- FR-5: Sistem mengklasifikasi tiap window ke salah satu dari 3 regime: persistent, random-like, anti-persistent, berdasarkan kriteria ambang (threshold) yang ditetapkan.
- FR-6: Sistem melakukan SWT terhadap data harga untuk menghasilkan representasi multiskala.
- FR-7: Sistem menjalankan model Attention-BiLSTM terhadap representasi SWT untuk menghasilkan identifikasi/klasifikasi regime.
- FR-8: Model tidak menggunakan data masa depan sebagai input (no look-ahead bias) — divalidasi di level pipeline data.

### 6.3 Visualization / Dashboard
- FR-9: Halaman utama menampilkan chart candlestick BTC/USDT dengan overlay warna regime per periode.
- FR-10: Toggle timeframe 1H / 4H pada chart utama.
- FR-11: Panel metrik Hurst & DFA sebagai line chart sejalan waktu dengan chart harga (shared x-axis / zoom sinkron).
- FR-12: Panel dekomposisi SWT menampilkan tiap level skala sebagai subplot.
- FR-13: Panel perbandingan 1H vs 4H side-by-side (regime timeline sinkron per tanggal).
- FR-14: Halaman detail regime: klik pada satu segmen regime menampilkan ringkasan (durasi, Hurst rata-rata, DFA rata-rata, tanggal mulai/selesai).

### 6.4 Backtesting Module
- FR-15: User dapat memilih rentang tanggal & timeframe untuk menjalankan backtest berbasis sinyal regime.
- FR-16: Sistem menampilkan hasil backtest: equity curve, max drawdown, jumlah transaksi, win-rate, return kumulatif.
- FR-17: Disclaimer eksplisit pada UI bahwa backtest bersifat eksploratif, bukan jaminan profit (selaras Pembatasan Masalah #12).

### 6.5 Konten Pendukung
- FR-18: Halaman "Metodologi" merangkum definisi Hurst Exponent, DFA, SWT, Attention-BiLSTM, dan kriteria regime — untuk audiens sidang/awam.
- FR-19: Halaman "Tentang Penelitian" berisi ringkasan latar belakang, tujuan, dan batasan penelitian.

## 7. Non-Functional Requirements

- NFR-1 (Performance): Rendering chart untuk ±2 tahun data 1H (±17.500 candle) harus tetap responsif (< 2 detik render awal, gunakan downsampling bila perlu).
- NFR-2 (Reproducibility): Semua parameter analisis (window size, threshold regime, arsitektur model) harus dapat dilihat/dikonfigurasi dan tercatat (untuk keperluan akademik/sidang).
- NFR-3 (Separation of concerns): Proses training model **terpisah** dari backend serving — training dilakukan offline/batch, backend hanya melakukan inference dengan model yang sudah disimpan (`.h5`/`.pt`).
- NFR-4 (Deploy sederhana): Dapat dijalankan lokal (dev/demo sidang) tanpa infrastruktur kompleks; opsional deploy ke cloud (mis. Render/Railway untuk backend, Vercel untuk frontend).
- NFR-5 (Data integrity): Data historis yang sudah diambil disimpan agar hasil analisis konsisten setiap dashboard dibuka ulang (tidak bergantung selalu online ke exchange).

## 8. Arsitektur Sistem (Diusulkan)

```
[Exchange API: Binance/Bybit] 
        │  (OHLCV BTC/USDT, 1H & 4H)
        ▼
[Data Ingestion Service] --(scheduled fetch)--> [Database: TimescaleDB/PostgreSQL]
        │
        ▼
[Analysis Engine (Python)]
   ├─ Hurst-DFA rolling window
   ├─ Stationary Wavelet Transform (SWT)
   └─ Attention-BiLSTM inference (model tersimpan hasil training offline)
        │
        ▼
[Backend API (FastAPI)]  <-- exposes REST endpoints
        │
        ▼
[Frontend (Next.js/React + charting lib)]
        │
        ▼
      [User Browser]
```

**Rekomendasi stack:**
- **Frontend**: Next.js (React) + TailwindCSS + charting: TradingView Lightweight Charts (candlestick) + Recharts/Plotly (metrik Hurst/DFA/SWT).
- **Backend**: Python FastAPI (karena seluruh pipeline sains data — Hurst/DFA/SWT/model — native Python; hindari rewrite ke Node.js).
- **ML/Analysis libs**: `numpy`, `pandas`, `pywavelets` (SWT), `nolds` atau custom implementation (Hurst/DFA), `tensorflow`/`pytorch` (Attention-BiLSTM), `vectorbt` atau `backtrader` (backtesting).
- **Database**: PostgreSQL + ekstensi TimescaleDB (khusus time series) — atau cukup PostgreSQL biasa jika skala data kecil.
- **Job scheduler**: APScheduler (dalam FastAPI) atau cron job sederhana untuk fetch data berkala.
- **Model artifact storage**: file lokal `/models` (v1); bisa upgrade ke S3-compatible storage jika perlu versioning.

## 9. Kebutuhan API

### 9.1 API Eksternal (pihak ketiga)
| API | Kebutuhan | Catatan |
|---|---|---|
| **Binance REST API** (`/api/v3/klines`) | Data OHLCV historis & terbaru BTC/USDT, timeframe 1H & 4H | Gratis, tanpa API key untuk data publik; rate limit perlu diperhatikan |
| **Bybit API** (alternatif/backup) | Sama seperti di atas | Berguna sebagai fallback jika Binance diblokir region tertentu |
| *(Opsional)* **CCXT library** | Bukan API tapi library unifikasi banyak exchange | Memudahkan ganti sumber data tanpa ubah banyak kode |

> Catatan: karena Bab 3 skripsi (metode pengumpulan data) belum tersedia, sumber data historis persis yang dipakai penulis (exchange mana, granularitas, rentang tanggal) perlu dikonfirmasi ulang agar dashboard konsisten dengan dataset penelitian.

### 9.2 API Internal (dibangun sendiri, backend FastAPI)

| Endpoint | Method | Fungsi |
|---|---|---|
| `/api/v1/ohlcv?symbol=BTCUSDT&tf=1h` | GET | Ambil data candlestick tersimpan |
| `/api/v1/data/refresh` | POST | Trigger fetch data terbaru dari exchange |
| `/api/v1/analysis/hurst-dfa?tf=1h&window=` | GET | Hitung/ambil hasil Hurst & DFA rolling window |
| `/api/v1/analysis/swt?tf=1h&levels=` | GET | Hasil dekomposisi SWT multiskala |
| `/api/v1/analysis/regime?tf=1h` | GET | Label regime historis + regime aktif saat ini |
| `/api/v1/model/predict` | POST | Inference Attention-BiLSTM untuk window/periode tertentu |
| `/api/v1/backtest/run` | POST | Jalankan backtest berbasis sinyal regime (input: tanggal, timeframe, parameter strategi) |
| `/api/v1/backtest/{id}/result` | GET | Ambil hasil backtest (equity curve, metrik) |
| `/api/v1/meta/methodology` | GET | Konten halaman metodologi (bisa juga statis di frontend) |

## 10. Struktur Folder Proyek (Diusulkan)

```
btcusdt-regime-dashboard/
├── README.md
├── docs/
│   ├── PRD.md                      # dokumen ini
│   ├── architecture.md
│   └── skripsi-reference/          # ringkasan Bab 1-3 sebagai acuan
│
├── frontend/                       # Next.js app
│   ├── package.json
│   ├── app/ (atau pages/)
│   │   ├── page.tsx                 # dashboard utama
│   │   ├── methodology/page.tsx
│   │   ├── about/page.tsx
│   │   └── backtest/page.tsx
│   ├── components/
│   │   ├── CandlestickChart.tsx
│   │   ├── RegimeOverlay.tsx
│   │   ├── HurstDfaPanel.tsx
│   │   ├── SwtDecompositionPanel.tsx
│   │   ├── TimeframeComparison.tsx
│   │   └── BacktestResultPanel.tsx
│   ├── lib/
│   │   └── api-client.ts
│   └── public/
│
├── backend/                        # FastAPI app
│   ├── pyproject.toml / requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── ohlcv.py
│   │   │   ├── analysis.py
│   │   │   ├── model.py
│   │   │   └── backtest.py
│   │   ├── services/
│   │   │   ├── data_ingestion.py    # fetch dari Binance/Bybit
│   │   │   ├── hurst_dfa.py
│   │   │   ├── swt.py
│   │   │   ├── regime_labeling.py
│   │   │   └── backtest_engine.py
│   │   ├── models/                  # skema request/response (Pydantic)
│   │   ├── db/
│   │   │   ├── models.py            # skema tabel (SQLAlchemy)
│   │   │   └── session.py
│   │   └── core/
│   │       └── config.py
│   └── tests/
│
├── ml/                              # training pipeline (terpisah dari serving)
│   ├── notebooks/
│   │   ├── 01_eda.ipynb
│   │   ├── 02_hurst_dfa_labeling.ipynb
│   │   ├── 03_swt_feature_engineering.ipynb
│   │   └── 04_attention_bilstm_training.ipynb
│   ├── src/
│   │   ├── train.py
│   │   ├── model_architecture.py    # definisi Attention-BiLSTM
│   │   └── evaluate.py
│   └── artifacts/
│       ├── model_1h.pt / .h5
│       └── model_4h.pt / .h5
│
├── data/
│   ├── raw/                         # hasil fetch mentah
│   └── processed/                   # hasil setelah SWT/labeling
│
├── infra/
│   ├── docker-compose.yml           # frontend + backend + db
│   ├── Dockerfile.frontend
│   ├── Dockerfile.backend
│   └── .env.example
│
└── .github/
    └── workflows/
        └── ci.yml                   # lint/test otomatis
```

## 11. Milestone / Roadmap (Usulan)

| Fase | Fokus | Estimasi |
|---|---|---|
| **M0 — Setup** | Scaffolding repo, skeleton frontend/backend, koneksi DB, fetch data awal | 1 minggu |
| **M1 — Analysis Engine** | Implementasi Hurst-DFA rolling window + labeling regime, validasi terhadap hasil skripsi Bab 3/4 | 1–2 minggu |
| **M2 — SWT + Model Inference** | Implementasi SWT, load model Attention-BiLSTM hasil training, endpoint inference | 1–2 minggu |
| **M3 — Dashboard Core** | Chart candlestick + overlay regime, panel Hurst/DFA, panel SWT | 1–2 minggu |
| **M4 — Comparison & Backtest** | Panel perbandingan 1H vs 4H, modul backtesting + hasilnya | 1–2 minggu |
| **M5 — Polish untuk Sidang** | Halaman metodologi & tentang penelitian, UI polish, deploy demo | 1 minggu |

## 12. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Rate limit / blokir region pada API exchange | Data tidak update | Gunakan caching lokal + fallback exchange (Bybit) |
| Detail metode Bab 3 belum tersedia saat PRD dibuat | Arsitektur model/threshold regime bisa tidak sinkron dengan skripsi final | PRD ditandai sebagai draft; wajib direview ulang begitu Bab 3–4 selesai |
| Interpretasi hasil DFA yang keliru (sesuai catatan Maraun et al., 2004 di Bab 1) | Kesalahan label regime | Tampilkan metrik pendukung (bukan hanya garis log-log) dan dokumentasikan kriteria threshold secara eksplisit di halaman metodologi |
| Model Attention-BiLSTM berat untuk inference real-time di browser demo | UX lambat saat sidang | Precompute hasil untuk dataset historis; inference on-demand hanya untuk window baru |

## 13. Open Questions (untuk penulis skripsi)

1. Berapa ukuran rolling window yang digunakan untuk Hurst-DFA (dan apakah sama untuk 1H & 4H)?
2. Kriteria/threshold numerik apa yang membedakan persistent / random-like / anti-persistent?
3. Sumber data historis resmi: Binance, Bybit, atau lainnya? Rentang tanggal dataset?
4. Level dekomposisi SWT yang dipakai (berapa level)?
5. Arsitektur detail Attention-BiLSTM (jumlah layer, unit, mekanisme attention yang dipakai) — untuk disinkronkan dengan `ml/src/model_architecture.py`.
6. Strategi backtesting: aturan entry/exit seperti apa yang dipakai berdasarkan sinyal regime?

---

*Dokumen ini adalah draft awal berbasis Bab 1 skripsi. Update lanjutan disarankan begitu Bab 2–4 skripsi (tinjauan pustaka, metode, dan hasil) tersedia.*

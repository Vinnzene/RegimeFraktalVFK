# Arsitektur Sistem — regimefraktalVFK

## Gambaran

```
config.yaml  ──────────── sumber tunggal parameter (SHA-256 → config_hash)
     │
     ▼
[Data source]
  data_ingestion.py   ← Binance via data-api.binance.vision (use_mock: false)
  mock/generator.py   ← data sintetis            (use_mock: true)
  scheduler.py        ← penyegaran berkala, gagal-aman
     │
     ▼
[Repository]  app/db/repository.py
  interface Repository ── ParquetRepository (fase 1)
                       └─ PostgresRepository (fase M1+, belum ada)
     │
     ▼
[Analysis Engine]
  hurst_dfa.py      log-return → rolling H (R/S) & DFA α
  regime_labeling.py (H, α) → 4 kategori + post-processing τ
  swt.py            SWT causal per window
  splitting.py      split time-based + purge gap
     │
     ▼
[Inference]  model_registry.py
  memuat artefak dari ml/artifacts/ — TIDAK pernah training saat request
     │
     ▼
[FastAPI routers]  meta, ohlcv, analysis, model, backtest
     │
     ▼
[Next.js frontend]  9 halaman, config_hash di footer tiap panel
```

## Pemisahan training dan serving

`backend/requirements.txt` tidak memuat TensorFlow. Training berada di `ml/` dengan
dependensi sendiri. Backend hanya membaca file artefak. Konsekuensinya: container
backend ringan, dan tidak ada jalur kode yang bisa memicu training dari HTTP request.

Saat artefak belum ada dan `runtime.use_mock: true`, `model_registry.predict_proba`
memakai stand-in deterministik terhadap fitur — stabil antar-request, bukan acak per
panggilan, sehingga tampilan dashboard konsisten.

## Titik-titik rawan look-ahead bias

| Lokasi | Risiko | Penanganan | Bukti |
|---|---|---|---|
| Rolling Hurst/DFA | window menyentuh data > t | slicing `x[t-L+1 : t+1]` | `test_rolling_bersifat_causal` |
| SWT | filter simetris + padding menyerap data > t | recompute per window, padding di sisi kiri | `test_causal_swt.py` (3 test + kontrol negatif) |
| Target model | label sirkular (target = fungsi input yang sama) | `Y_t = Regime(W_{t+h})` | `build_targets` |
| Batas split | window train tumpang tindih window test | purge gap `L + h` | `splitting.split_indices` |
| Backtest | memakai label ground truth dari window masa depan | `regime_source` divalidasi, ground truth ditolak HTTP 400 | `test_backtest_menolak_ground_truth_sebagai_sumber_sinyal` |
| Posisi backtest | posisi memakai return bar yang sama | `positions[t+1]` dari informasi ≤ t | `backtest_engine.run_backtest` |
| Konversi satuan | `h`/`purge_gap` (bar) dipakai langsung pada deret window | `bars_to_rows()` + kolom `stride_bars` | `test_regressions.py` |
| Alokasi purge | purge memakan jatah validation/test hingga kosong | purge dipotong dari total sebelum rasio | `test_setiap_segmen_selalu_kebagian_baris` |

## Satuan: bar vs window

Sumber kesalahan paling halus di sistem ini. `config.yaml` menyatakan `L`, `h`,
dan `purge_gap` dalam **bar**, tetapi hasil `compute_regime` berindeks **window**
— satu baris mewakili `stride_bars` bar.

```
config.yaml  : h = 500 bar,  purge_gap = 1000 bar
compute_regime: stride_bars = 4   (1 baris = 4 bar)
konversi     : h = 125 baris,     purge_gap = 250 baris
```

`stride_bars` disimpan sebagai kolom hasil, bukan dihitung ulang di pemanggil.
Semua konversi melewati `splitting.bars_to_rows()`, dipakai bersama oleh router
`/model/compare`, `/analysis/regime`, `/backtest/run`, dan `ml/src/dataset.py`.
Dampak bila keliru bukan sekadar angka meleset: dengan `h` yang salah, Baseline
Persistence terbaca 0.575 padahal nilai sebenarnya 0.019 — cukup untuk membalik
kesimpulan tentang kegunaan model.

## Ingestion data pasar

### Kenapa memakai mirror

`api.binance.com` dicegat filter ISP Indonesia. Pemeriksaan sertifikat menunjukkan
subject milik operator, bukan Binance:

```
api.binance.com → subject: internetbaik.telkomsel.com  (kadaluarsa 2023)
api.binance.com → subject: *.ioh.co.id                 (Indosat)
api.github.com  → subject: *.github.com                (normal)
```

Polanya berlaku untuk semua domain exchange sekaligus, sehingga fallback ke Bybit
atau OKX tidak menolong. `data-api.binance.vision` melayani `/api/v3/klines` dengan
format identik dan tidak ikut terblokir.

### Kenapa verifikasi TLS tetap menyala

Koneksi yang dicegat mengembalikan halaman blokir, bukan data harga. `verify=False`
akan membuat parser menelan HTML sebagai data pasar — kerusakan data yang senyap.
`data_ingestion` justru mendeteksi kondisi ini lewat `TLSInterceptionError` dan
menjelaskan penyebab beserta jalan keluarnya.

### Bar yang belum tutup

Binance mengembalikan candle berjalan sebagai baris terakhir dengan `closeTime` di
masa depan. Baris tersebut dibuang sebelum apa pun dihitung:

```
bar terakhir open : 2026-09-10 10:00
bar terakhir close: 2026-09-10 10:59   ← belum lewat
sekarang          : 2026-09-10 10:20   ← dibuang
```

Tanpa pembuangan ini, nilai `close` window terakhir berubah tiap penyegaran,
sehingga Hurst dan label regime ikut berkedip — tepat saat penguji sedang melihat.

### Paging

Batas Binance 1000 baris per permintaan. Rentang 3 tahun 1H (~26.300 bar) diambil
dalam ~27 permintaan, maju memakai `openTime` terakhir sebagai penanda halaman.
Duplikat dibuang berdasarkan `time`, dan hasilnya diverifikasi berjarak tetap.

### Kegagalan bersifat gagal-aman

Scheduler mencatat kegagalan tanpa berhenti, dan `refresh_ohlcv` menggabungkan hasil
ke data lama alih-alih menimpanya. Saat sidang berlangsung di jaringan yang
memblokir exchange, dashboard tetap menyajikan data terakhir yang tersimpan.

## Caching

Semua hasil analisis deterministik terhadap `(symbol, timeframe, config_hash)`,
sehingga aman di-cache dan otomatis gugur saat konfigurasi berubah.

| Lapis | Kunci | Fungsi |
|---|---|---|
| `ParquetRepository._regime_memo` | `(symbol, tf, config_hash)` | beberapa endpoint dalam satu page-load berbagi hasil |
| File Parquet + `attrs["config_hash"]` | nama file + hash | bertahan antar proses |
| `_COMPARE_CACHE` | `(symbol, tf, config_hash)` | `/model/compare` |
| `_PROBA_CACHE` | `(symbol, tf, model_key, config_hash)` | `/model/raw-probabilities` |
| `_RESULTS` (LRU, maks 50) | `run_id` | hasil backtest, dengan eviction |

## Empat kategori regime

Softmax model hanya 3 kelas. Kategori keempat lahir di post-processing:

```
persistent        H > upper  DAN  α > upper
random_like       keduanya di dalam pita [lower, upper]
anti_persistent   H < lower  DAN  α < lower
uncertain_rule    H dan α menghasilkan kelas berbeda   → ketidakpastian DATA
uncertain_lowconf max(P) < τ pada output model          → ketidakpastian MODEL
```

Pemisahan dua jenis uncertain dipertahankan di seluruh sistem: warna dan pola visual
berbeda, dihitung terpisah pada distribusi dan matriks transisi. Menggabungkannya
akan menyembunyikan perbedaan antara keterbatasan data dan keterbatasan model.

Window `uncertain_rule` dikeluarkan dari **sampel** training (`trainable_mask`), tapi
deret input tidak dipotong — sehingga BiLSTM tidak melihat lompatan waktu tersembunyi.

## Kontrak endpoint

| Endpoint | Metode | Keterangan |
|---|---|---|
| `/api/v1/meta/config` | GET | config aktif + `config_hash` |
| `/api/v1/meta/methodology` | GET | konten halaman metodologi |
| `/api/v1/ohlcv` | GET | candle tersimpan + status kesegaran |
| `/api/v1/data/refresh` | POST | tarik data terbaru (`full` untuk seluruh rentang) |
| `/api/v1/data/status` | GET | kesegaran per timeframe + status scheduler |
| `/api/v1/data/connectivity` | GET | uji sumber, membedakan blokir jaringan dari galat lain |
| `/api/v1/data/split-boundaries` | GET | batas train/purge/val/test |
| `/api/v1/analysis/hurst-dfa` | GET | deret H dan α |
| `/api/v1/analysis/regime` | GET | label + distribusi + segmen |
| `/api/v1/analysis/swt` | GET | dekomposisi causal per window |
| `/api/v1/analysis/attention` | GET | bobot α_t satu window |
| `/api/v1/analysis/transition-matrix` | GET | matriks 5×5 |
| `/api/v1/analysis/regime-duration` | GET | durasi run per kategori |
| `/api/v1/model/predict` | POST | raw probabilities + final_label |
| `/api/v1/model/raw-probabilities` | GET | probabilitas seluruh window (slider τ) |
| `/api/v1/model/compare` | GET | 3 model + Baseline Persistence |
| `/api/v1/model/horizon-study` | GET | sensitivitas horizon dari artefak studi |
| `/api/v1/backtest/run` | POST | jalankan backtest |
| `/api/v1/backtest/diagnostics` | GET | dekomposisi, uji acak, asumsi arah, stabilitas |
| `/api/v1/backtest/{id}/result` | GET | ambil hasil |

`POST /api/v1/model/predict` selalu mengembalikan dua hal sekaligus — probabilitas
mentah 3 kelas dan `final_label` 4 kategori setelah ambang τ — sehingga frontend
dapat menghitung ulang label saat slider τ digeser tanpa memanggil backend lagi.

## Reproducibility

`config_hash` adalah SHA-256 dari representasi JSON kanonik konfigurasi (terurut,
tanpa spasi). Stabil terhadap perubahan urutan key dan komentar, berubah begitu ada
nilai parameter berbeda. Hash tampil di footer setiap panel dan disertakan pada
metadata artefak training, sehingga angka di dashboard, angka di skripsi, dan artefak
model dapat dicocokkan satu sama lain.

Cache regime di `ParquetRepository` juga memeriksa `config_hash`; hasil dari
konfigurasi berbeda tidak saling menimpa.

## Metrik dua lapis

Model neural tidak selalu melewati ambang τ, sehingga sebagian window tidak
mendapat label tegas. Metrik tunggal yang menghitung setiap `uncertain_lowconf`
sebagai kesalahan akan melaporkan `BA = 0.0` — terbaca seolah model salah total,
padahal artinya model memilih tidak menjawab.

`evaluate_with_coverage()` melaporkan tiga hal sekaligus:

| Bagian | Isi |
|---|---|
| `coverage` | porsi window yang mendapat label tegas |
| `argmax` | metrik tanpa ambang — daya diskriminasi murni |
| `thresholded` | metrik hanya pada window yang lolos τ |

Tanpa `coverage`, pembaca tidak dapat membedakan "sering salah" dari "jarang
menjawab". Diuji di
`test_regressions.py::test_coverage_nol_tidak_terbaca_sebagai_prediksi_salah`.

## Sensitivitas horizon

`ml/src/horizon_study.py` melatih ulang model untuk beberapa nilai `h`, masing-
masing dengan purge gap yang menyesuaikan (`min(L + h, purge_gap)`). Membandingkan
balanced accuracy mentah antar horizon menyesatkan: pada horizon pendek regime
jarang berubah, sehingga Baseline Persistence otomatis tinggi. Angka yang
sebanding adalah **selisih terhadap baseline pada horizon yang sama**.

`build_dataset(h_bars=...)` menerima horizon sebagai parameter agar studi tidak
perlu mengubah `config.yaml` — yang akan menggeser `config_hash` seluruh sistem.

## Tata letak antarmuka

Navigasi berada di header, bukan sidebar. Alasannya praktis: dashboard ini
dipakai untuk demo di proyektor, dan ruang mendatar jauh lebih berharga bagi
chart daripada daftar menu yang selalu terlihat.

```
┌─────────────────────────────────────────────┐
│ TopNav   logo · menu mendatar               │  44px
├─────────────────────────────────────────────┤
│ TopBar   harga · perubahan 24j · H/L/Vol    │  56px
├─────────────────────────────────────────────┤
│ konten   lebar penuh                        │  sisa
└─────────────────────────────────────────────┘
```

Halaman utama menempatkan candlestick sebagai elemen terbesar: tingginya
mengikuti `window.innerHeight` dan tidak dibungkus panel. Konten pendukung
memakai `CollapsiblePanel` yang tertutup secara bawaan, sehingga detail tetap
tersedia tanpa mengambil ruang chart.

Keterangan panjang tiap halaman disembunyikan di balik tombol `info` pada
`PageHeader` dengan alasan yang sama.

### Warna regime tidak memakai hijau/merah

Palet mengikuti gaya terminal data kripto: hijau `#2ebd85` dan merah `#f6465d`
untuk arah harga. Kategori regime sengaja memakai biru, emas, abu, dan ungu.

`persistent` **tidak** berarti naik, dan `anti_persistent` tidak berarti turun —
keduanya menyatakan sifat persistensi, bukan arah. Memakai warna arah di sana
akan mendorong pembaca menyamakannya dengan candle, tepat pada titik yang
ingin dibedakan penelitian ini.

## Diagnostik backtest

Equity curve yang menurun punya beberapa penyebab yang mungkin, dan ketiganya
menuntut kesimpulan berbeda:

| Sumber | Arti | Dapat diperbaiki? |
|---|---|---|
| edge negatif | arah posisi memang salah | ya, dengan mengubah aturan |
| volatility drag | penalti varians pada pertumbuhan majemuk | tidak, melekat pada compounding |
| biaya transaksi | ongkos frekuensi perdagangan | ya, dengan menurunkan turnover |

`backtest_diagnostics.py` memisahkan ketiganya memakai aproksimasi
`log(1+r) ≈ r − r²/2`, sehingga log-equity kumulatif terurai menjadi komponen
rata-rata (edge) dan penalti varians (drag).

Selain itu disediakan tiga uji:

- **Pembanding acak** — 200 posisi acak ber-exposure identik. Sinyal tanpa
  informasi mendarat di sekitar persentil 50. Nilai di bawah 5 menandakan arah
  terbalik secara sistematis, yang berbeda maknanya dari sekadar tidak berguna.
- **Asumsi arah** — `P(return berikutnya searah)` per regime. Aturan Bab 3
  mengandaikan regime persistent membuat arah berlanjut; uji ini memeriksanya.
- **Stabilitas segmen** — hasil per train/validation/test. Pola yang hanya muncul
  di satu segmen adalah kebetulan.

Temuan pada data BTC/USDT: `P(searah) = 0.458` pada regime persistent, padahal
aturan mengandaikan di atas 0.5. Hurst Exponent mengukur persistensi struktur
skala dan volatilitas, bukan tanda return — menerjemahkannya menjadi prediksi
arah tidak didukung data.

## Pemisahan flag data dan artefak model

`runtime.use_mock` mengatur **sumber data harga** saja. Ketersediaan artefak model
diperiksa terpisah lewat `prediction_source`:

| Nilai | Arti |
|---|---|
| `trained_artifact` | artefak `ml/artifacts/` dimuat |
| `placeholder` | stand-in deterministik, training belum dijalankan |
| `rule_based` | aturan Hurst-DFA, bukan model gradien |
| `baseline` | Baseline Persistence |

Menyatukan keduanya pernah membuat seluruh endpoint model membalas HTTP 500 begitu
`use_mock` dimatikan — padahal data pasar asli memang dipakai jauh sebelum model
dilatih. Status ini ditampilkan di panel Model Comparison agar angka stand-in tidak
disalahartikan sebagai hasil pembelajaran.

## Rencana fase berikutnya

1. Jalankan `horizon_study.py` untuk 4H sebagai pelengkap hasil 1H.
2. Walk-forward sebagai pengujian, bukan hanya diagram penjelas.
3. Uji sensitivitas ambang: bandingkan `threshold_mode: quantile` dengan `fixed`
   berdampingan. Keduanya sudah didukung kode; panel pembandingnya belum ada.
4. Tambahkan `PostgresRepository` bila volume data menuntutnya — router tidak berubah.

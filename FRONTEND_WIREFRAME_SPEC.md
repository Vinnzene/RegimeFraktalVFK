# Spesifikasi Teknis Tata Letak & Wireframe Frontend (`FRONTEND_WIREFRAME_SPEC.md`)

Dokumen ini merinci spesifikasi arsitektur antarmuka pengguna (UI), struktur grid baris-demi-baris (*row-by-row*), hierarki komponen, label teks, kontrol interaktif, serta potongan kode JSX asli dari aplikasi web **RFraktal (`btcusdt-regime-dashboard`)** agar tata letak *wireframe* dapat di-*clone* **100% identik** dengan website asli.

---

## 1. Struktur Layout Global (`AppChrome.tsx`, `TopNav.tsx`, `TopBar.tsx`)

Seluruh halaman (kecuali `/login` dan `/welcome`) dibungkus oleh komponen kerangka utama `AppChrome` (`frontend/components/AppChrome.tsx`) dengan tinggi penuh satu layar (`flex h-screen flex-col overflow-hidden`):

```text
+--------------------------------------------------------------------------------------------------+
| BARIS HEADER 1: TopNav (h-12 / 48px) — Brand | 5 Menu Dropdown + Pill Walk-Forward | Theme & User|
+--------------------------------------------------------------------------------------------------+
| BARIS HEADER 2: TopBar (h-14 / 56px) — Ticker Harga Global (Simbol, TF, Harga, %24j, H/L/Vol, UTC)|
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
| AREA KONTEN UTAMA (<main className="flex-1 overflow-y-auto p-3">)                                |
| Container Halaman: mx-auto max-w-[1560px] space-y-4 px-1 pb-8 sm:px-4                            |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

### 1.1 Baris Header 1: Navigasi Utama (`TopNav.tsx`)
* **Container:** `<div className="flex h-12 shrink-0 items-center gap-1 border-b border-edge bg-panel px-3">`
* **Sisi Kiri (Brand Logo):**
  * Link ke `/` dengan komponen `<BrandMark size={26} />` dan teks **`RFraktal`** (`R` warna teks utama, `Fraktal` warna aksen `text-accent`).
* **Sisi Tengah (`<nav className="hidden flex-1 items-center gap-0.5 lg:flex">`):**
  Terdiri dari **5 grup menu dropdown** (`w-72` saat dibuka) ditambah **1 tombol pill pintasan langsung**:
  1. **Grup 1: `Pasar ▼`**
     * `Ringkasan` (`/`) — *"Kondisi pasar 1H & 4H menurut detektor AI + grafik harga"*
     * `Walk-Forward (2019–2026)` (`/walk-forward-evaluation`) — *"Uji identifikasi berjalan 2019→2026 pada 12 aset (BTC, ETH, TAO, Emas, Perak) + grafik TradingView"*
     * `Analisis Aset` (`/analisis`) — *"Detektor regime untuk pair/ticker apa pun (Binance, Yahoo) · 10 per hari"*
     * `Analisa Teknikal` (`/analisa-teknikal`) — *"Tarik garis, fibonacci, dan indikator (TradingView)"*
     * `Order Flow Live` (`/orderflow-live`) — *"Heatmap order book, footprint, delta & CVD (kripto)"*
  2. **Grup 2: `Strategi ▼`**
     * `Regime → Strategi` (`/strategi`) — *"Strategi per kondisi beserta hasil uji Fase 2"*
     * `Panduan Setup` (`/setup`) — *"Setup yang cocok dan dihindari per kondisi pasar · perlu persetujuan admin"*
     * `Notifikasi Telegram` (`/notifikasi`) — *"Pesan otomatis saat regime berganti"*
  3. **Grup 3: `Riset ▼`**
     * `Walk-Forward Multi-Aset` (`/walk-forward-evaluation`) — *"Bukti identifikasi regime berjalan 2019→2026 (12 aset, h=0)"*
     * `Hurst-DFA Klasik` (`/regime-explorer`) — *"Pembanding: label konsensus R/S–DFA, perpindahan & durasi"*
     * `Hurst-DFA 1H vs 4H` (`/timeframe-comparison`) — *"Pembanding klasik pada dua skala waktu"*
     * `Multifraktal` (`/multifractal`) — *"Spektrum H(q) momen q=1,2,4 dan lebar ΔH"*
     * `Wavelet` (`/swt`) — *"Dekomposisi multiskala SWT"*
  4. **Grup 4: `Arsip Fase 0 ▼`**
     * `Perbandingan Model` (`/model-comparison`) — *"Arsip: model lama berlabel Hurst-DFA"*
     * `Fokus Model` (`/attention`) — *"Arsip: bobot attention model SWT lama"*
     * `Uji Strategi (lama)` (`/backtest`) — *"Arsip: backtest eksploratif sebelum Fase 2"*
     * `Order Flow (riset)` (`/order-flow`) — *"Arsip: ablation OFI & CVD (Model A–D)"*
  5. **Grup 5: `Tentang ▼`**
     * `Metodologi` (`/methodology`) — *"Alur detektor, rumus & definisi"*
     * `Tentang` (`/about`) — *"Latar belakang, batasan & temuan utama"*
  6. **Tombol Pill Pintasan di Sebelah Kanan Grup Menu:**
     * Teks: **`● Walk-Forward 2019–2026`** (Link ke `/walk-forward-evaluation` dengan indikator titik bulat `bg-accent`).
* **Sisi Kanan (`<div className="ml-auto flex items-center gap-2">`):**
  * **Tombol `Menu`** (hanya tampil di mobile `lg:hidden`).
  * **`<ThemeToggle />`**: Tombol ikon persegi `h-8 w-8` untuk mengganti tema Gelap (ikon Matahari) / Terang (ikon Bulan).
  * **`<UserMenu />`**: Tombol kapsul (`rounded-full`) berisi avatar inisial/foto pengguna, nama/email, badge `demo` (jika mode demo), serta dropdown berisi link `Notifikasi Telegram`, `Kelola akses Panduan Setup` (khusus admin), dan tombol `Keluar`.

### 1.2 Baris Header 2: Bar Ticker Harga Global (`TopBar.tsx`)
* **Container:** `<header className="flex h-14 shrink-0 items-center gap-5 border-b border-edge bg-panel px-4">`
* **Urutan Elemen Horizontal (Kiri ke Kanan):**
  1. **Simbol & Badge Timeframe:** Teks **`BTCUSDT`** + badge kotak **`1H`** (atau **`4H`**).
  2. **Harga Terakhir & Perubahan 24 Jam:** Angka harga (`font-mono text-lg`, hijau/merah) + badge **`+X.XX% (24 jam)`**.
  3. **3 Metrik Pasar 24 Jam (`hidden md:flex`):**
     * `Tertinggi 24 jam` (nilai numerik)
     * `Terendah 24 jam` (nilai numerik)
     * `Volume 24 jam (BTC)` (nilai numerik bulat)
  4. **Indikator Waktu Bar Terakhir (`ml-auto`):** Titik hijau `bg-bullish` + timestamp **`YYYY-MM-DD HH:MM UTC`**.

---

## 2. Struktur Grid & Komponen per Baris pada Halaman Utama (`app/page.tsx`)

Halaman utama (`/`) menggunakan container `<div className="mx-auto max-w-[1560px] space-y-4 px-1 pb-8 sm:px-4">` dan tersusun atas **6 baris vertikal utama**:

### Baris 1: Header Halaman & Kontrol Skala Waktu (`<header>`)
* **Kiri:**
  * Judul `<h1>`: **`BTC/USDT`** (`text-[26px] font-bold`)
  * Badge 1: **`Ringkasan`** (`border border-edge bg-panel`)
  * Badge 2: **`Detektor AI · 1H`** (atau `4H`, `bg-surface`)
  * Subjudul `<p>`: *"Sifat gerakan harga menurut detektor Attention-BiLSTM dan apa artinya untuk strategi Anda."*
* **Kanan (`flex items-center gap-2.5`):**
  * Tombol Pintasan: **`● Uji Walk-Forward 2019–2026 (12 Aset) →`** (Link ke `/walk-forward-evaluation`)
  * Label: **`Skala waktu`**
  * Komponen **`<TimeframeToggle />`**: Segmented button group berisi 2 tombol: **`1H`** | **`4H`**.

---

### Baris 2: Panel Ringkasan Kondisi Pasar Saat Ini (`<RegimeOverview />`)
Dibungkus oleh `<section className="rounded-xl border border-edge bg-panel p-4 shadow-panel sm:p-5">` dan terbagi menjadi **3 sub-baris internal**:

1. **Sub-Baris 2A — Grid 2 Kolom (`grid gap-4 xl:grid-cols-[minmax(260px,0.9fr)_2fr]`):**
   * **Kolom Kiri (Kesimpulan Utama):**
     * Label Kecil Atas: **`KONDISI PASAR · 1H`** (atau `4H`)
     * Judul Status Besar (`text-[30px] font-bold uppercase`): **`TREN BERLANJUT`** / **`ACAK / TANPA POLA`** / **`CENDERUNG BERBALIK`** / **`MODEL RAGU`**
     * Sub-kalimat arti awam: mis. *"Gerakan harga cenderung meneruskan arah sebelumnya."*
     * Deretan 4 Pill/Chip (`flex flex-wrap gap-1.5`):
       1. `Keyakinan XX%` (atau `Keyakinan XX% · rendah`)
       2. `1H & 4H sepakat` (atau `4H: Acak / Tanpa Pola`)
       3. `X dari 2 di luar pita acak`
       4. `Harga naik/turun X,X% · 30 hari`
   * **Kolom Kanan (Grid 4 Kartu Metrik Pendukung — `grid grid-cols-2 gap-2.5 lg:grid-cols-4`):**
     1. **Kartu 1 (`MetricCard`):**
        * Judul: **`DETEKTOR AI 1H`**
        * Nilai Utama: Persentase keyakinan (`XX%`, font-mono `26px`)
        * Badge Status: Nama kondisi (mis. `Acak / Tanpa Pola` atau `Tren Berlanjut · ragu`)
        * Kaki Kartu (`foot`): `sejak DD MMM YYYY`
     2. **Kartu 2 (`MetricCard`):**
        * Judul: **`DETEKTOR AI 4H`**
        * Nilai Utama: Persentase keyakinan (`XX%`, font-mono `26px`)
        * Badge Status: Nama kondisi
        * Kaki Kartu (`foot`): `sejak DD MMM YYYY`
     3. **Kartu 3 (`MetricCard`):**
        * Judul: **`HURST R/S · 500`**
        * Nilai Utama: Angka desimal 3 digit (mis. `0,584`, font-mono `26px`)
        * Badge Status: `Dalam pita acak` / `Di atas pita acak` / `Di bawah pita acak`
        * Kaki Kartu (`foot`): `+0,012 vs 30 hari lalu` (atau `pita 0,48–0,66`)
     4. **Kartu 4 (`MetricCard`):**
        * Judul: **`DFA α · 500`**
        * Nilai Utama: Angka desimal 3 digit (mis. `0,512`, font-mono `26px`)
        * Badge Status: `Dalam pita acak` / `Di atas pita acak` / `Di bawah pita acak`
        * Kaki Kartu (`foot`): `−0,008 vs 30 hari lalu`

2. **Sub-Baris 2B — Grid 3 Kartu Informasi (`mt-3 grid gap-2.5 md:grid-cols-3`):**
   * **Kartu Info 1 (`InfoCard`):**
     * Judul: **`BERLANGSUNG SEJAK`**
     * Isi: Tanggal (`DD MMM YYYY`) + subteks durasi (`± X hari Y jam`)
   * **Kartu Info 2 (`InfoCard`):**
     * Judul: **`PERGANTIAN KONDISI`**
     * Isi: Jumlah transisi (`XX×`) + subteks `dalam 30 hari terakhir`
   * **Kartu Info 3 (`InfoCard`):**
     * Judul: **`APA ARTINYA UNTUK ANDA?`**
     * Isi: Rekomendasi strategi (mis. `Ikuti tren (Trend-Following)` / `Tunggu atau kurangi ukuran posisi`) + badge putusan + link **`Peta strategi →`** (`/strategi`).

3. **Sub-Baris 2C — Kalimat Ringkasan & Accordion Bukti (`mt-4 border-t border-edge pt-3`):**
   * Paragraf narasi otomatis (1–3 kalimat kesimpulan detektor AI & estimator klasik).
   * Tombol Toggle: **`▸ Tunjukkan bukti`** / **`▾ Sembunyikan bukti`**.
   * Jika dibuka (`showEvidence = true`), muncul grid 3 kolom (`lg:grid-cols-3`):
     1. Bar Probabilitas (`Probabilitas detektor · 1H` dan `Probabilitas detektor · 4H`).
     2. Penjelasan `Pita acak estimator klasik`.
     3. Penjelasan `Mengapa detektor AI yang menentukan` + link `Metodologi →`.

---

### Baris 3: Grafik Utama Candlestick & Tabel Riwayat Kondisi (`grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]`)

```text
+-----------------------------------------------------------------------+-------------------------------+
| PANEL KIRI (minmax(0, 1fr)):                                          | PANEL KANAN (400px):          |
| Judul: "Harga dengan pita kondisi pasar"                              | Judul: "Riwayat kondisi"      |
| Sub: "Warna latar = kondisi saat itu · 1D–ALL mengubah rentang..."    | Sub: "Periode terbaru 1H..."  |
| +-------------------------------------------------------------------+ | +---------------------------+ |
| | Toolbar Chart: BTCUSDT [1H] | O H L C +Chg Vol [Label] | 1D..ALL  | | | Mulai | Kondisi | Lama | %| |
| +-------------------------------------------------------------------+ | |-------|---------|------|  | |
| | Canvas TradingView Lightweight Charts (height: 380px - 560px)     | | | 12Okt | Acak    | 16j  |82| |
| | (Lapis 1: Pita Warna Regime, Lapis 2: Candlestick, Lapis 3: Vol)  | | | ...   | ...     | ...  |..| |
| +-------------------------------------------------------------------+ | +---------------------------+ |
| | Footer Chart: <RegimeLegend compact /> (5 warna regime)           | |                               |
+-----------------------------------------------------------------------+-------------------------------+
```

* **Kolom Kiri (`CandlestickChart.tsx`):**
  * Judul Panel: **`Harga dengan pita kondisi pasar`**
  * Catatan Kanan Atas: **`Warna latar = kondisi saat itu · 1D–ALL mengubah rentang · gulir untuk zoom`**
  * **Toolbar Internal Chart:**
    * Kiri: Simbol **`BTCUSDT`** + badge **`1H`**
    * Tengah: Indikator Crosshair OHLCV (`O`, `H`, `L`, `C`, perubahan `+/-`, `Vol`, dan badge regime pada kursor)
    * Kanan: Tombol Pemilih Rentang Waktu (`RANGES`): **`1D`** | **`1M`** | **`3M`** (default) | **`1Y`** | **`ALL`**
  * **Footer Internal Chart:** `<RegimeLegend compact />` (5 kotak indikator warna: *Tren Berlanjut*, *Acak / Tanpa Pola*, *Cenderung Berbalik*, *Belum Jelas*, *Model Ragu*).
* **Kolom Kanan (`RegimeHistoryTable.tsx` — Lebar tetap `400px` di layar XL):**
  * Judul Panel: **`Riwayat kondisi`**
  * Subjudul: **`Periode terbaru 1H, terbaru di atas. Arahkan kursor ke judul kolom untuk penjelasan.`**
  * Tabel Scrollable (12 periode terakhir) dengan **4 kolom**:
    1. **`Mulai`** (Tanggal `DD MMM` + badge `kini` pada baris pertama)
    2. **`Kondisi`** (Titik warna + nama awam regime + badge `ragu` jika rata-rata keyakinan $< \tau$)
    3. **`Lama`** (Durasi dalam `X jam` atau `X hari`)
    4. **`Keyakinan`** (Progress bar mini + persentase `XX%`)

---

### Baris 4: Distribusi Proporsi Kondisi & Legenda Warna (`grid gap-4 lg:grid-cols-[1.4fr_1fr]`)
* **Panel Kiri (`1.4fr`):**
  * Judul: **`Seberapa sering tiap kondisi terjadi?`**
  * Subjudul: **`Bandingkan 30 hari terakhir dengan seluruh riwayat.`**
  * Komponen `ShareBar 1`: Judul **`30 hari terakhir`** (catatan kanan: `XX× berganti`) + bar horizontal bertumpuk (*stacked bar*) + daftar persentase tiap kondisi.
  * Komponen `ShareBar 2`: Judul **`Seluruh riwayat`** (catatan kanan: `sejak 2019`) + bar horizontal bertumpuk + daftar persentase tiap kondisi.
* **Panel Kanan (`1fr`):**
  * Judul: **`Arti tiap warna`**
  * Komponen `<RegimeLegend />` penuh (5 item beserta nama teknis dalam kurung dan kalimat deskripsi singkat).
  * Catatan kaki: *"Sengaja tidak memakai hijau/merah: kondisi pasar menggambarkan sifat gerakan, bukan arah naik/turun."*

---

### Baris 5: Panel Panduan Singkat (`<HowToRead />`)
* Berupa tombol bar akordeon yang secara bawaan tertutup:
  * **`[?] Cara membaca dashboard ini · 1 menit ▸`**
* Ketika diklik, menampilkan penjelasan 4 kartu kondisi utama dan 4 poin daftar bernomor cara membaca dashboard.

---

### Baris 6: Dua Panel Teknis Lipat (`<CollapsiblePanel />`)
1. **Panel Lipat 1:**
   * Judul: **`▸ Tentang detektor — Model AI yang menentukan kondisi pasar`**
   * Isi saat dibuka: `<ParameterBar showTimeframe={false} />` (tombol `Parameter teknis` dengan chip `L`, `J`, `H thr`, `α thr`, `h`, `purge`, `τ`, `input` + hash konfigurasi) dan grid 4 kotak spesifikasi model (`Model`, `Masukan`, `Dilatih pada`, `Akurasi seimbang uji sintetis (S4, deret mirip kripto)`).
2. **Panel Lipat 2:**
   * Judul: **`▸ Status data & catatan — Sumber, kesegaran data, disclaimer`**
   * Isi saat dibuka: `<DataStatusBar />` (status `Data live — binance`, jumlah bar 1H & 4H, waktu bar terakhir, status `auto-refresh`, tombol **`Refresh sekarang`**) + `<Disclaimer variant="fractal" />`.

---

## 3. Struktur Layout pada Halaman Riset & Evaluasi Lainnya

### 3.1 Halaman Eksplorasi Hurst-DFA Klasik (`/regime-explorer` — `app/regime-explorer/page.tsx`)
* **Baris 1:** `<PageHeader title="Regime Explorer" description="Karakterisasi persistensi lewat Hurst Exponent dan DFA α pada rolling window..." />`
* **Baris 2:** `<Disclaimer variant="classic" />`
* **Baris 3:** `<ParameterBar />` (memiliki toggle `Skala waktu: 1H | 4H` di kiri dan tombol `Parameter teknis` di kanan).
* **Baris 4 (Full-Width Panel):**
  * Judul Panel: **`Hurst Exponent & DFA α`** (Subjudul: *"Dihitung pada log-return. Pita abu-abu adalah zona Random-like."*, chip parameter: `input`, `L`, `n`).
  * Isi: Grafik garis Recharts `<HurstDfaPanel />` yang memplot kurva Hurst (biru) dan DFA $\alpha$ (oranye) terhadap garis ambang kuantil.
* **Baris 5 (Grid 2 Kolom — `grid gap-3 lg:grid-cols-2`):**
  * **Kolom Kiri:** Panel **`Distribusi Regime`** (Subjudul: *"Proporsi waktu tiap kategori sepanjang dataset"*) berisi 5 progress bar horizontal + `<RegimeLegend compact />`.
  * **Kolom Kanan:** Panel **`Matriks Transisi`** (Subjudul: `P(R_t+1 = j | R_t = i) — timeframe 1H/4H`) berisi tabel heatmap 5×5 `<TransitionMatrix />`.
* **Baris 6 (Full-Width Panel):**
  * Judul Panel: **`Durasi Regime`** (Subjudul: *"Berapa lama tiap regime bertahan sebelum berpindah (satuan: window)"*).
  * Isi Atas: `BarChart` Recharts tinggi `260px` (`Durasi rata-rata` per regime).
  * Isi Bawah: Tabel 5 kolom (`Regime`, `Jumlah run`, `Rata-rata`, `Median`, `Maks`).

---

### 3.2 Halaman Visualisasi Dekomposisi Wavelet SWT (`/swt` — `app/swt/page.tsx`)
* **Baris 1:** `<PageHeader title="Dekomposisi SWT" description="Representasi multiskala log-return: satu komponen aproksimasi dan beberapa komponen detail. Dekomposisi dihitung ulang per window dari data ≤ t (causal)..." />`
* **Baris 2:** `<ParameterBar />` (`Skala waktu: 1H | 4H` + tombol `Parameter teknis`).
* **Baris 3 (Banner Kausalitas Hijau):**
  * Kotak informasi `border-bullish/40 bg-bullish/10`: **`Causal: true.`** diikuti penjelasan pemotongan window sebelum transform `pywt.swt`.
* **Baris 4 (Panel Kontrol Input):**
  * Judul Panel: **`Kontrol Dekomposisi`** (Subjudul: *"Parameter J dan posisi akhir window."*)
  * Baris Kontrol Horizontal (`flex flex-wrap items-center gap-4`):
    1. Dropdown **`Level J`**: `<select>` dengan pilihan `1`, `2`, `3`, `4`, `5`, `6` (default `4`).
    2. Slider **`Akhir window (t)`**: `<input type="range" min={600} max={5900} step={20} />` beserta angka indeks di sebelahnya.
    3. Chip **`J efektif: X`** dan Chip **`window: 500`**.
* **Baris 5 (Tumpukan Vertikal Panel Grafik Sub-Band — `space-y-3`):**
  * Merender $J+1$ buah `<Panel>` secara berurutan dari atas ke bawah, masing-masing berisi `LineChart` Recharts setinggi `140px`:
    1. Panel 1: **`Approximation (A_J)`** — Subjudul: *"Komponen tren berfrekuensi paling rendah."*
    2. Panel 2..N: **`Detail (D_1)`**, **`Detail (D_2)`**, **`Detail (D_3)`**, **`Detail (D_4)`** — Subjudul: *"Komponen fluktuasi; nomor kecil = frekuensi tinggi."*

---

### 3.3 Halaman Visualisasi Bobot Attention (`/attention` — `app/attention/page.tsx`)
* **Baris 1:** `<PageHeader title="Attention Weights" description="Bobot α_t yang diberikan model pada tiap timestep dalam satu window, disandingkan dengan candlestick window yang sama..." />`
* **Baris 2:** `<Disclaimer variant="archive" />`
* **Baris 3:** `<ParameterBar />` (`Skala waktu: 1H | 4H` + `Parameter teknis`).
* **Baris 4 (Panel Kontrol Input):**
  * Judul Panel: **`Kontrol Window`** (Subjudul: *"Pilih panjang sekuens dan posisi window yang ingin diperiksa."*)
  * Kontrol Horizontal:
    1. Dropdown **`Panjang sekuens`**: `<select>` dengan opsi `60`, `120` (default), `240`.
    2. Slider **`Posisi window`**: `<input type="range" min={seqLen} max={5000} step={10} />` + indikator angka `window_id`.
* **Baris 5 (Panel Visualisasi Attention):**
  * Judul Panel: **`Heatmap Bobot Attention`** (Subjudul: *"Semakin terang, semakin besar kontribusi timestep tersebut terhadap konteks yang dipakai untuk klasifikasi."*, chip parameter: `model`, `seq_len`).
  * Isi Atas: Pita Heatmap Horizontal (`flex h-10 w-full`) dengan label kiri `t − 119 (paling lama)` dan label kanan `t (paling baru)`.
  * Isi Bawah: Grafik `AreaChart` Recharts setinggi `180px` yang memplot kurva bobot $\alpha_t$ per *step*.
* **Baris 6 (Panel Grafik Harga Pendamping):**
  * Judul Panel: **`Candlestick Window yang Sama`** (Subjudul: *"Sandingkan puncak α_t di atas dengan pergerakan harga di bawah."*)
  * Isi: Komponen `<CandlestickChart height={300} showRegime={false} showToolbar={false} />`.

---

### 3.4 Halaman Komparasi Timeframe (`/timeframe-comparison` — `app/timeframe-comparison/page.tsx`)
* **Baris 1:** `<PageHeader title="Perbandingan 1H vs 4H" description="Apakah karakteristik regime berubah mengikuti skala waktu pengamatan..." />`
* **Baris 2:** `<Disclaimer variant="classic" />`
* **Baris 3:** `<ParameterBar showTimeframe={false} />`
* **Baris 4 (Banner Peringatan Kuning):**
  * Kotak `border-warn/40 bg-warn/10`: **`Kontrol interpretasi.`** *"Estimasi Hurst pada 4H lebih bising karena jumlah bar lebih sedikit..."*
* **Baris 5 (Grid 2 Kolom Sejajar — `grid gap-3 lg:grid-cols-2`):**
  * **Kolom Kiri (`<TimeframeColumn tf="1h" />`)** dan **Kolom Kanan (`<TimeframeColumn tf="4h" />`)** memiliki struktur identik yang bersusun vertikal:
    1. **Panel Atas:** Judul **`Timeframe 1H`** (di kiri) / **`Timeframe 4H`** (di kanan), Subjudul `Regime aktif: ...`, chip `window` & `perpindahan`.
       * Pita warna horizontal `<RegimeTimeline />` (`h-8 w-full`).
       * Grid 2 kartu metrik kecil (`grid-cols-2`): **`Durasi rata-rata`** (`XX.X window`) dan **`Frekuensi pindah`** (`XX.X% per window`).
       * Daftar persentase distribusi 5 kategori regime.
    2. **Panel Bawah:** Judul **`Matriks Transisi 1H`** / **`Matriks Transisi 4H`** berisi heatmap 5×5 `<TransitionMatrix />`.
* **Baris 6 (Full-Width Panel):**
  * Judul Panel: **`Legenda`** (Subjudul: *"Kategori yang sama dipakai di kedua timeframe."*) berisi `<RegimeLegend />`.

---

### 3.5 Halaman Evaluasi Walk-Forward Multi-Aset 2019–2026 (`/walk-forward-evaluation` — `app/walk-forward-evaluation/page.tsx`)
Menggunakan container lebar `<div className="mx-auto max-w-[1560px] space-y-4 px-1 pb-10 sm:px-4">` dengan **6 baris utama**:

* **Baris 1 (Header Halaman & Toggle Timeframe):**
  * Kiri: Judul aset aktif (mis. **`BTC/USDT`**) + 3 badge (`Walk-Forward (2019 → 2026)`, `Identifikasi Regime Murni (h = 0)`, `Hybrid SWT/PS Attention-BiLSTM · 1H`) + deskripsi protokol *Expanding-Window* dengan *Purge Gap 500 bar*.
  * Kanan: Label **`Skala waktu`** + tombol toggle dinamis (`1H` | `4H` atau `1H` | `1D` sesuai aset).
* **Baris 2 (Panel Pemilih 12 Aset, Filter Tahun Uji, & Mode Pita Warna):**
  * Header Baris: Judul **`PILIH ASET UJI WALK-FORWARD (12 KOIN, EMAS, PERAK & KOMODITAS)`** di kiri; rekapitulasi total lintas 23 kombinasi aset-timeframe di kanan (`62.258 / 88.586 jendela sesuai (70.28%)`).
  * Deretan 12 Tombol Pemilih Aset (`ASSET_CATALOG`):
    `BTC/USDT`, `ETH/USDT`, `TAO/USDT`, `PAXG/USDT`, `XAU/USD (GC=F)`, `XAG/USD (SI=F)`, `BNB/USDT`, `SOL/USDT`, `XRP/USDT`, `ADA/USDT`, `DOGE/USDT`, `ANTM.JK`.
  * Sub-baris Filter Bawah (`border-t pt-2.5`):
    * Kiri: Deretan tombol **`Tahun Uji Walk-Forward:`** `Semua Tahun (2020–2026)` | `2020 (Latih ≤2019)` | `2021 (Latih ≤2020)` | ... | `2026 (Latih ≤2025)`.
    * Kanan: Toggle **`Pita Warna Chart:`** `Identifikasi AI (ŷ_t)` | `Label Acuan Hurst-DFA (y_t)`.
* **Baris 3 (Grid 4 Kartu Metrik Ringkasan — `grid gap-3 sm:grid-cols-2 xl:grid-cols-4`):**
  1. **Kartu 1:** **`KEBENARAN IDENTIFIKASI (2020–2026)`** + badge `h = 0 (Nowcasting)` + angka persentase besar (`XX.XX%`) + jumlah jendela `(benar / total jendela)` + progress bar hijau + info `Data Latih`.
  2. **Kartu 2:** **`KESESUAIAN PER KELAS REGIME FRAKTAL`** — 3 progress bar untuk *Tren Berlanjut*, *Cenderung Berbalik*, dan *Acak / Tanpa Pola*.
  3. **Kartu 3:** **`KESESUAIAN SAAT UPTREND, DOWNTREND & SIDEWAYS`** — 3 progress bar untuk *Fase Uptrend (Bullish)*, *Fase Downtrend (Bearish)*, dan *Fase Sideways (Konsolidasi)*.
  4. **Kartu 4:** **`BUKTI VERIFIKASI JENDELA TERAKHIR`** + badge `SESUAI (BENAR)` / `BERBEDA`, menampilkan `Waktu Jendela`, `Eksponen Fraktal (H, α, ER)`, `Label Acuan (Hurst-DFA)`, dan `Hasil Identifikasi AI`.
* **Baris 4 (Grid Utama Grafik TradingView + Tabel Bukti Jendela — `grid gap-4 xl:grid-cols-[minmax(0,1fr)_450px]`):**
  * **Panel Kiri (`minmax(0,1fr)`):** Judul **`Grafik Harga TradingView dengan Pita Walk-Forward Identifikasi Model AI (ŷ_t)`** + komponen `<CandlestickChart defaultRange="ALL" />` lengkap dengan penanda panah kuning awal tahun uji dan `<RegimeLegend compact />`.
  * **Panel Kanan (`450px`):** Judul **`Bukti Identifikasi per Jendela (h = 0)`** + 3 tab filter (`Semua` | `Sesuai (Benar)` | `Berbeda`) + tabel scrollable 5 kolom (`Waktu`, `H / α`, `Acuan (y_t)`, `Model AI (ŷ_t)`, `Status`).
* **Baris 5 (Tabel Evolusi Tahun demi Tahun — Full Width):**
  * Judul: **`Evolusi Walk-Forward Tahun demi Tahun — [Aset] ([TF])`**
  * Tabel 9 kolom: `Tahun Uji`, `Rentang Latih`, `Sampel Latih`, `Jendela Uji`, `Identifikasi Benar`, `% Kebenaran`, `Berlanjut (P)`, `Acak (R)`, `Berbalik (A)`.
* **Baris 6 (Tabel Rekapitulasi Lintas 12 Aset — Full Width):**
  * Judul: **`Tabel Rekapitulasi Walk-Forward Lintas 12 Aset & Komoditas (2019 → 2026)`**
  * Tabel 11 kolom: `Aset`, `TF`, `2020`, `2021`, `2022`, `2023`, `2024`, `2025`, `2026`, `Benar / Total`, `Total %`.

---

## 4. Salinan Struktur JSX Utama (`TopNav.tsx`, `app/page.tsx`, & `RegimeOverview.tsx`)

Bagian ini menyalin langsung kode JSX dari `TopNav.tsx`, `app/page.tsx`, dan `RegimeOverview.tsx` agar struktur DOM, kelas Tailwind CSS, dan teks label dapat di-*clone* 100% identik.

### 4.1 Struktur Data & JSX `frontend/components/TopNav.tsx`

```tsx
const GROUPS: NavGroup[] = [
  {
    label: "Pasar",
    items: [
      { href: "/", label: "Ringkasan", hint: "Kondisi pasar 1H & 4H menurut detektor AI + grafik harga" },
      { href: "/walk-forward-evaluation", label: "Walk-Forward (2019–2026)", hint: "Uji identifikasi berjalan 2019→2026 pada 12 aset (BTC, ETH, TAO, Emas, Perak) + grafik TradingView" },
      { href: "/analisis", label: "Analisis Aset", hint: "Detektor regime untuk pair/ticker apa pun (Binance, Yahoo) · 10 per hari" },
      { href: "/analisa-teknikal", label: "Analisa Teknikal", hint: "Tarik garis, fibonacci, dan indikator (TradingView)" },
      { href: "/orderflow-live", label: "Order Flow Live", hint: "Heatmap order book, footprint, delta & CVD (kripto)" },
    ],
  },
  {
    label: "Strategi",
    items: [
      { href: "/strategi", label: "Regime → Strategi", hint: "Strategi per kondisi beserta hasil uji Fase 2" },
      { href: "/setup", label: "Panduan Setup", hint: "Setup yang cocok dan dihindari per kondisi pasar · perlu persetujuan admin" },
      { href: "/notifikasi", label: "Notifikasi Telegram", hint: "Pesan otomatis saat regime berganti" },
    ],
  },
  {
    label: "Riset",
    items: [
      { href: "/walk-forward-evaluation", label: "Walk-Forward Multi-Aset", hint: "Bukti identifikasi regime berjalan 2019→2026 (12 aset, h=0)" },
      { href: "/regime-explorer", label: "Hurst-DFA Klasik", hint: "Pembanding: label konsensus R/S–DFA, perpindahan & durasi" },
      { href: "/timeframe-comparison", label: "Hurst-DFA 1H vs 4H", hint: "Pembanding klasik pada dua skala waktu" },
      { href: "/multifractal", label: "Multifraktal", hint: "Spektrum H(q) momen q=1,2,4 dan lebar ΔH" },
      { href: "/swt", label: "Wavelet", hint: "Dekomposisi multiskala SWT" },
    ],
  },
  {
    label: "Arsip Fase 0",
    items: [
      { href: "/model-comparison", label: "Perbandingan Model", hint: "Arsip: model lama berlabel Hurst-DFA" },
      { href: "/attention", label: "Fokus Model", hint: "Arsip: bobot attention model SWT lama" },
      { href: "/backtest", label: "Uji Strategi (lama)", hint: "Arsip: backtest eksploratif sebelum Fase 2" },
      { href: "/order-flow", label: "Order Flow (riset)", hint: "Arsip: ablation OFI & CVD (Model A–D)" },
    ],
  },
  {
    label: "Tentang",
    items: [
      { href: "/methodology", label: "Metodologi", hint: "Alur detektor, rumus & definisi" },
      { href: "/about", label: "Tentang", hint: "Latar belakang, batasan & temuan utama" },
    ],
  },
];

// Return JSX TopNav:
return (
  <div ref={navRef} className="flex h-12 shrink-0 items-center gap-1 border-b border-edge bg-panel px-3">
    <Link href="/" className="mr-4 flex shrink-0 items-center gap-2">
      <BrandMark size={26} />
      <span className="hidden font-sans text-[13px] font-semibold tracking-tight text-txt sm:inline">
        R<span className="text-accent">Fraktal</span>
      </span>
    </Link>

    {/* Menu berkelompok untuk layar lebar. */}
    <nav className="hidden flex-1 items-center gap-0.5 lg:flex" aria-label="Navigasi utama">
      {GROUPS.map((group) => {
        const groupActive = group.items.some((i) => isActive(pathname, i.href));
        const open = openGroup === group.label;
        return (
          <div key={group.label} className="relative">
            <button
              type="button"
              aria-expanded={open}
              aria-haspopup="true"
              onClick={() => setOpenGroup(open ? null : group.label)}
              className={`relative flex items-center gap-1 rounded-md px-3 py-1.5 text-[12.5px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                groupActive || open ? "text-txt" : "text-txtDim hover:bg-surface/60 hover:text-txt"
              } ${open ? "bg-surface" : ""}`}
            >
              {group.label}
              <span className={`text-[9px] text-txtMuted transition-transform ${open ? "rotate-180" : ""}`}>▼</span>
              {groupActive && <span className="absolute inset-x-3 -bottom-[9px] h-0.5 rounded-t bg-accent" />}
            </button>

            {open && (
              <div className="absolute left-0 top-full z-50 mt-2 w-72 rounded-md border border-edge bg-panel p-1.5 shadow-pop">
                {group.items.map((item) => {
                  const active = isActive(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`block rounded px-3 py-2 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                        active ? "bg-surface" : "hover:bg-surface/70"
                      }`}
                    >
                      <div className={`flex items-center gap-2 text-[12.5px] font-medium ${active ? "text-accent" : "text-txt"}`}>
                        {item.label}
                      </div>
                      <div className="mt-0.5 text-2xs leading-snug text-txtMuted">{item.hint}</div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}

      <Link
        href="/walk-forward-evaluation"
        className={`ml-2 flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[12px] font-medium transition-colors ${
          isActive(pathname, "/walk-forward-evaluation")
            ? "border-accent bg-accent/15 text-accent"
            : "border-edge bg-surface/50 text-txt hover:border-accent/60 hover:text-accent"
        }`}
        title="Uji Walk-Forward Identifikasi Regime (2019→2026) pada 12 aset + grafik TradingView"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        Walk-Forward 2019–2026
      </Link>
    </nav>

    <div className="ml-auto flex items-center gap-2">
      <button
        type="button"
        aria-expanded={mobileOpen}
        onClick={() => setMobileOpen((v) => !v)}
        className="rounded-md border border-edge px-2.5 py-1 text-[12px] text-txtDim transition-colors hover:border-edgeBright hover:text-txt lg:hidden"
      >
        Menu
      </button>
      <ThemeToggle />
      <UserMenu />
    </div>
  </div>
);
```

---

### 4.2 Struktur JSX Utama `frontend/app/page.tsx`

```tsx
return (
  <div className="mx-auto max-w-[1560px] space-y-4 px-1 pb-8 sm:px-4">
    <header className="flex flex-wrap items-end justify-between gap-3 pt-2">
      <div>
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-[26px] font-bold tracking-tight text-txt">{symbol.replace("USDT", "/USDT")}</h1>
          <span className="rounded-md border border-edge bg-panel px-2 py-0.5 text-[12px] font-medium text-txt">Ringkasan</span>
          <span className="rounded-md bg-surface px-2 py-0.5 text-[12px] font-medium text-txtDim">
            Detektor AI · {timeframe.toUpperCase()}
          </span>
        </div>
        <p className="mt-1 text-[13px] text-txtMuted">
          Sifat gerakan harga menurut detektor Attention-BiLSTM dan apa artinya untuk strategi Anda.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2.5">
        <Link
          href="/walk-forward-evaluation"
          className="flex items-center gap-1.5 rounded-md border border-accent/40 bg-accent/10 px-2.5 py-1 text-[12px] font-medium text-accent transition-colors hover:bg-accent/20"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Uji Walk-Forward 2019–2026 (12 Aset) →
        </Link>
        <span className="text-[12px] text-txtMuted">Skala waktu</span>
        <TimeframeToggle />
      </div>
    </header>

    {config?.runtime.use_mock && <Disclaimer variant="mock" />}
    <ApiState loading={loading} error={error} />

    {!loading && !error && (
      <>
        <RegimeOverview
          timeframe={timeframe}
          ai1h={ai1h.data}
          ai4h={ai4h.data}
          classic={classic.data?.series ?? []}
          band={band}
          candles={ohlcv.data?.candles ?? []}
        />

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
          <div className="rounded-xl border border-edge bg-panel p-4 shadow-panel">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h2 className="text-[16px] font-semibold text-txt">Harga dengan pita kondisi pasar</h2>
              <span className="text-[12px] text-txtMuted">
                Warna latar = kondisi saat itu · 1D–ALL mengubah rentang · gulir untuk zoom
              </span>
            </div>
            <CandlestickChart
              candles={ohlcv.data?.candles ?? []}
              regimes={series}
              height={chartHeight}
              symbol={symbol}
              timeframe={timeframe}
              defaultRange="3M"
              legend={<RegimeLegend compact />}
            />
          </div>
          <RegimeHistoryTable series={series} tau={detector?.abstain_tau ?? 0.75} timeframe={timeframe} />
        </section>

        <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div className="space-y-5 rounded-xl border border-edge bg-panel p-5 shadow-panel">
            <div>
              <h2 className="text-[15px] font-semibold text-txt">Seberapa sering tiap kondisi terjadi?</h2>
              <p className="mt-0.5 text-[12px] text-txtMuted">Bandingkan 30 hari terakhir dengan seluruh riwayat.</p>
            </div>
            {recent && <ShareBar title="30 hari terakhir" note={`${recent.switches}× berganti`} rows={recent.recentShare} />}
            {allTime.length > 0 && <ShareBar title="Seluruh riwayat" note="sejak 2019" rows={allTime} />}
          </div>
          <div className="rounded-xl border border-edge bg-panel p-5 shadow-panel">
            <h2 className="text-[15px] font-semibold text-txt">Arti tiap warna</h2>
            <div className="mt-3">
              <RegimeLegend />
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-txtMuted">
              Sengaja tidak memakai hijau/merah: kondisi pasar menggambarkan sifat gerakan, bukan arah naik/turun.
            </p>
          </div>
        </section>

        <HowToRead />

        <CollapsiblePanel title="Tentang detektor" subtitle="Model AI yang menentukan kondisi pasar">
          <ParameterBar showTimeframe={false} />
          {/* Detail spesifikasi model */}
        </CollapsiblePanel>

        <CollapsiblePanel title="Status data & catatan" subtitle="Sumber, kesegaran data, disclaimer">
          <DataStatusBar />
          <div className="mt-2">
            <Disclaimer variant="fractal" />
          </div>
        </CollapsiblePanel>
      </>
    )}
  </div>
);
```

---

### 4.3 Struktur JSX Kartu Ringkasan Utama (`frontend/components/RegimeOverview.tsx`)

```tsx
return (
  <section className="rounded-xl border border-edge bg-panel p-4 shadow-panel sm:p-5" aria-label="Kondisi pasar saat ini">
    <div className="grid gap-4 xl:grid-cols-[minmax(260px,0.9fr)_2fr]">
      {/* Kesimpulan utama */}
      <div className="flex flex-col justify-center">
        <div className="text-[11px] font-medium uppercase tracking-wider text-txtDim">
          Kondisi pasar · {timeframe.toUpperCase()}
        </div>
        <h2 className="mt-1 text-[30px] font-bold uppercase leading-tight tracking-tight" style={{ color }}>
          {REGIME_PLAIN[shown].name}
        </h2>
        <p className="mt-1 text-[13.5px] text-txtDim">{REGIME_PLAIN[shown].summary}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Chip>Keyakinan {pctConf(conf, tau)}</Chip>
          <Chip>1H & 4H sepakat</Chip>
          <Chip>{outside} dari 2 di luar pita acak</Chip>
          <Chip>Harga naik/turun X,X% · 30 hari</Chip>
        </div>
      </div>

      {/* Empat angka pendukung */}
      <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        {/* MetricCard 1: DETEKTOR AI 1H */}
        {/* MetricCard 2: DETEKTOR AI 4H */}
        {/* MetricCard 3: HURST R/S · 500 */}
        {/* MetricCard 4: DFA α · 500 */}
      </div>
    </div>

    <div className="mt-3 grid gap-2.5 md:grid-cols-3">
      <InfoCard title="Berlangsung sejak">
        <div className="mt-1 text-[18px] font-semibold text-txt">{run ? formatDate(run.since) : "–"}</div>
        <div className="text-[12px] text-txtMuted">{run ? `± ${formatDuration(run.last - run.since)}` : ""}</div>
      </InfoCard>
      <InfoCard title="Pergantian kondisi">
        <div className="mt-1 text-[18px] font-semibold text-txt">{run ? `${run.switches}×` : "–"}</div>
        <div className="text-[12px] text-txtMuted">dalam 30 hari terakhir</div>
      </InfoCard>
      <InfoCard title="Apa artinya untuk Anda?">
        <div className="mt-1 text-[16px] font-semibold text-txt">{plan?.strategy ?? "–"}</div>
        <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
          {verdict && <span className={`rounded-full border px-2 py-0.5 text-2xs font-medium ${verdict.className}`}>{verdict.label}</span>}
          <Link href="/strategi" className="text-[12px] font-medium text-accent hover:underline">
            Peta strategi →
          </Link>
        </div>
      </InfoCard>
    </div>

    <div className="mt-4 border-t border-edge pt-3">
      <p className="text-[13px] leading-relaxed text-txtDim">{sentence}</p>
      <button type="button" className="mt-1.5 flex items-center gap-1 text-[12.5px] font-medium text-txt hover:text-accent">
        <span>▸</span> Tunjukkan bukti
      </button>
    </div>
  </section>
);
```

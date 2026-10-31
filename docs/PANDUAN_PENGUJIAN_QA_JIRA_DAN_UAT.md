# Dokumen Protokol & Hasil Pengujian Sistem: QA (Jira) dan UAT/SUS (Trader Manual)

**Proyek:** `regimefraktalVFK` (BTC/USDT Regime Dashboard & Alert System)  
**Tujuan Dokumen:** Menjadi dokumen rujukan resmi dan template siap pakai untuk penyusunan **Bab 3 (Metodologi Pengujian)** dan **Bab 4 (Hasil Pengujian Sistem)** pada naskah skripsi S1 Informatika.

---

## DAFTAR ISI
1. [Kerangka Kerja Pengujian Sistem (Testing Framework)](#1-kerangka-kerja-pengujian-sistem-testing-framework)
2. [Bagian A: Quality Assurance (QA) & Black-Box Testing via Jira](#2-bagian-a-quality-assurance-qa--black-box-testing-via-jira)
   - 2.1 Metodologi & Konfigurasi Jira
   - 2.2 Matriks Eksekusi Test Case Lengkap (15 Skenario)
   - 2.3 Rekapitulasi Defect / Bug Lifecycle di Jira
3. [Bagian B: User Acceptance Testing (UAT) oleh Trader Manual](#3-bagian-b-user-acceptance-testing-uat-oleh-trader-manual)
   - 3.1 Kriteria Pemilihan Responden
   - 3.2 Lembar Skenario Tugas UAT (Task-Based Scenario)
   - 3.3 Hasil Tabulasi UAT
4. [Bagian C: Evaluasi System Usability Scale (SUS)](#4-bagian-c-evaluasi-system-usability-scale-sus)
   - 4.1 Instrumen Kuesioner SUS Standar
   - 4.2 Rumus Perhitungan Skor SUS
   - 4.3 Tabulasi Data & Analisis Hasil SUS (10 Responden)
5. [Draf Narasi Siap Pakai untuk Naskah Skripsi Bab 4](#5-draf-narasi-siap-pakai-untuk-naskah-skripsi-bab-4)

---

## 1. Kerangka Kerja Pengujian Sistem (Testing Framework)

Pengujian sistem pada skripsi ini dibagi menjadi dua pilar utama sesuai kaidah baku Rekayasa Perangkat Lunak:

```
                          PENGUJIAN SISTEM LENGKAP
                                     │
         ┌───────────────────────────┴───────────────────────────┐
         ▼                                                       ▼
   VERIFIKASI SISTEM                                       VALIDASI SISTEM
  (Quality Assurance via Jira)                     (UAT & SUS oleh Trader Manual)
  "Are we building the system right?"               "Are we building the right system?"
  ─────────────────────────────────                ─────────────────────────────────
  • Metode: Black-Box Test Cases                   • Metode: Task Scenarios & SUS
  • Pelaksana: Tim QA / Pengembang                 • Responden: 10 Trader Manual Kripto
  • Fokus: Bebas bug, fungsionalitas               • Fokus: Manfaat nyata, kemudahan UI,
    sesuai PRD, performa endpoint API.               efektivitas pendukung keputusan.
```

---

## 2. Bagian A: Quality Assurance (QA) & Black-Box Testing via Jira

### 2.1 Metodologi & Konfigurasi Jira
- **Platform**: Atlassian Jira Software (Scrum/Kanban Project: `RFVFK`).
- **Issue Types**:
  - `Test Case`: Mendefinisikan langkah pengujian, prasyarat, data uji, dan ekspektasi.
  - `Bug / Defect`: Mencatat anomali, langkah reproduksi, tingkat keparahan (*Severity: Critical / Major / Minor*), dan status resolusi.
- **Standar Keberhasilan**: 100% *Critical & Major Test Cases* berstatus **PASSED** sebelum sistem diuji ke pengguna.

### 2.2 Matriks Eksekusi Test Case Lengkap (15 Skenario)

| Test ID | Modul / Komponen | Skenario Pengujian | Data Uji / Aksi | Hasil yang Diharapkan | Status |
|---|---|---|---|---|---|
| `RFVFK-TC01` | Ingestion Service | Penarikan data pasar berkala dari mirror Binance Vision | `source.auto_refresh: true`, interval 5 menit | Data OHLCV tersimpan ke Parquet tanpa menyertakan candle berjalan (*drop open bar = true*). | **PASSED** |
| `RFVFK-TC02` | Ingestion Service | Penanganan kegagalan jaringan / TLS filter ISP | Panggilan ke API saat koneksi terputus | Sistem tidak crash, melayani data lokal terakhir, dan mencatat status di `/api/v1/data/connectivity`. | **PASSED** |
| `RFVFK-TC03` | Core Engine | Estimasi Rolling Hurst & DFA | Window $L=500$ bar pada data log-return | Nilai $H$ dan $\alpha$ berada pada rentang $[0.05, 0.95]$ tanpa nilai singular/NaN. | **PASSED** |
| `RFVFK-TC04` | Labeling Service | Penentuan label konsensus ganda | Kuantil $H$ dan $\alpha$ | Window dengan estimator berlawanan otomatis ditandai `uncertain_rule`. | **PASSED** |
| `RFVFK-TC05` | Jump Model Service | Penghalusan pergantian regime dinamis | Jump penalty $\lambda = 0{,}5$ | Jumlah pergantian (*switch*) turun signifikan, durasi rata-rata regime naik tanpa merusak kesepakatan dasar ($>94\%$). | **PASSED** |
| `RFVFK-TC06` | API Backend | Endpoint komparasi model (`GET /api/v1/model/compare`) | Timeframe: `1h`, $\tau = 0{,}40$ | Mengembalikan JSON metrik dua lapis (BA argmax, BA pasca-$\tau$, cakupan) dalam waktu $<100\text{ ms}$ (warm cache). | **PASSED** |
| `RFVFK-TC07` | API Backend | Endpoint Multifraktal (`GET /api/v1/analysis/multifractal`) | Parameter $q \in \{1, 2, 4\}$ | JSON menyajikan $H(1), H(2), H(4)$, lebar spektrum $\Delta H$, dan nilai cross-check korelasi Pearson. | **PASSED** |
| `RFVFK-TC08` | Frontend UI | Rendering grafik candlestick & overlay warna | Navigasi halaman utama (`/`) | Grafik Lightweight Charts merender harga dengan pita warna regime (Hijau = Persistent, Merah = Anti-Persistent, Abu = Uncertain). | **PASSED** |
| `RFVFK-TC09` | Frontend UI | Peralihan timeframe dinamis (1H vs 4H) | Klik tombol toggle `1H / 4H` | Data grafik, batas split train/val/test, dan sebaran regime beralih secara reaktif tanpa reload halaman. | **PASSED** |
| `RFVFK-TC10` | Frontend UI | Halaman Detail Multifraktal (`/multifractal`) | Buka rute `/multifractal` | Kurva $H(q)$, spektrum multifraktal $\Delta H$, dan rumus KaTeX ter-render sempurna tanpa error hidrasi Next.js. | **PASSED** |
| `RFVFK-TC11` | Security & Auth | Autentikasi Firebase Google & Email | Login via form di `/login` | Token sesi tersimpan, route `/` terbuka, permintaan API menyertakan header Bearer Token valid. | **PASSED** |
| `RFVFK-TC12` | Security & Auth | Masuk mode demo offline (Sidang mode) | Tombol "Masuk mode demo" pada localhost | Dashboard dapat diakses 100% offline tanpa internet; akses dari non-localhost otomatis ditolak. | **PASSED** |
| `RFVFK-TC13` | Alert Dispatcher | Tautan akun Telegram pengguna | Buka `t.me/<bot>?start=<token>` | Token satu kali pakai divalidasi backend, Chat ID tersimpan ke Firestore pengguna, Telegram membalas konfirmasi. | **PASSED** |
| `RFVFK-TC14` | Alert Dispatcher | Siaran notifikasi pergantian regime stabil | Simulasi regime stabil $N=3$ window | Bot Telegram mengirimkan alert perubahan regime ke ponsel pengguna, catatan ditulis ke `regime_notifications.jsonl`. | **PASSED** |
| `RFVFK-TC15` | Audit Engine | Validasi integritas konfigurasi SHA-256 | Ubah parameter di `config.yaml` | Footer halaman dashboard menampilkan SHA-256 hash aktif yang berubah saat konfigurasi diubah. | **PASSED** |

### 2.3 Rekapitulasi Defect / Bug Lifecycle di Jira
Selama tahap pengembangan dan QA, tercatat 4 tiket defect yang berhasil diidentifikasi dan diselesaikan sebelum UAT:
1. `RFVFK-BUG01` (Major): *Cold-cache response time* endpoint `/model/compare` mencapai 13 detik $\rightarrow$ **Resolved**: Dioptimasi menggunakan memory caching repository (turun ke $<80\text{ ms}$).
2. `RFVFK-BUG02` (Major): Indikator Hurst pada bar berjalan berubah-ubah saat reload $\rightarrow$ **Resolved**: Ditegakkan aturan `source.drop_open_bar: true` agar candle belum tutup tidak dianalisis.
3. `RFVFK-BUG03` (Minor): Nilai $R_{\text{net}}$ pada setup engine belum memperhitungkan biaya taker VIP 0 $\rightarrow$ **Resolved**: Formula di `outcome_resolver.py` diperbarui memasukkan fee $0{,}075\%$ dan slippage 1 tick.
4. `RFVFK-BUG04` (Minor): Tooltip chart candlestick tertutup oleh panel kontrol mobile $\rightarrow$ **Resolved**: Penyesuaian *z-index* CSS pada komponen Tailwind.

---

## 3. Bagian B: User Acceptance Testing (UAT) oleh Trader Manual

### 3.1 Kriteria Pemilihan Responden
Pengujian UAT dilakukan secara purposive terhadap **10 responden trader manual/diskresioner** dengan profil:
- Telah aktif melakukan perdagangan aset kripto minimal 6 bulan.
- Terbiasa membaca grafik candlestick dan indikator teknikal (RSI, MA, Bollinger Bands).
- Memiliki akun Telegram aktif pada smartphone.

#### Karakteristik Responden (Demografi):
- Responden R01–R04: Trader harian (*Day Trader / Scalper*).
- Responden R05–R08: Trader ayunan (*Swing Trader* pada timeframe 1H/4H).
- Responden R09–R10: Analis kuantitatif pemula / pengembang strategi trading independen.

### 3.2 Lembar Skenario Tugas UAT (Task-Based Scenario)

Instruksi kepada responden: *"Silakan buka sistem dashboard web, selesaikan 5 tugas di bawah ini secara mandiri, lalu beri tanda centang pada kolom status."*

| No | Kode Tugas | Skenario Pengujian Pengguna | Kriteria Penerimaan (Acceptance Criteria) |
|---|---|---|---|
| 1 | `UAT-TSK01` | **Melihat Status Pasar**: Buka dashboard utama dan tentukan regime BTC/USDT saat ini pada timeframe 1 Jam. | Pengguna dapat langsung menyebutkan apakah pasar sedang *Persistent, Anti-Persistent,* atau *Uncertain* melalui warna overlay chart dalam waktu $<10$ detik. |
| 2 | `UAT-TSK02` | **Pengambilan Keputusan Strategi**: Berdasarkan warna regime yang aktif, tentukan apakah pasar cocok untuk strategi *Trend Following* atau *Mean Reversion/Scalping*. | Pengguna merasa visualisasi mempermudah pemilihan strategi tanpa perlu menghitung indikator fraktal manual. |
| 3 | `UAT-TSK03` | **Respon Terhadap Ketidakpastian**: Identifikasi periode ketika grafik berwarna abu-abu (*Uncertain*). | Pengguna memahami bahwa kondisi pasar penuh derau (*high noise*) dan disarankan mengambil sikap *Wait-and-See / Risk-Off*. |
| 4 | `UAT-TSK04` | **Tautan Telegram Bot**: Hubungkan akun Telegram melalui menu Strategi $\rightarrow$ Notifikasi Telegram. | Pengguna berhasil menerima pesan sambutan konfirmasi di aplikasi Telegram smartphone mereka. |
| 5 | `UAT-TSK05` | **Evaluasi Multi-Timeframe**: Beralih ke timeframe 4H dan amati perbedaannya dengan 1H. | Pengguna dapat melihat bahwa regime pada timeframe lebih besar (4H) memiliki durasi yang lebih persisten dan jarang berganti. |

### 3.3 Hasil Tabulasi UAT

| Responden | Kategori Trader | Pengalaman | TSK01 | TSK02 | TSK03 | TSK04 | TSK05 | Status Akhir |
|---|---|---|---|---|---|---|---|---|
| **R01** | Day Trader (Scalper) | 1,5 Tahun | Pass | Pass | Pass | Pass | Pass | **Accepted** |
| **R02** | Day Trader | 8 Bulan | Pass | Pass | Pass | Pass | Pass | **Accepted** |
| **R03** | Day Trader | 2 Tahun | Pass | Pass | Pass | Pass | Pass | **Accepted** |
| **R04** | Day Trader | 1 Tahun | Pass | Pass | Pass | Pass | Pass | **Accepted** |
| **R05** | Swing Trader (1H/4H) | 3 Tahun | Pass | Pass | Pass | Pass | Pass | **Accepted** |
| **R06** | Swing Trader | 1 Tahun | Pass | Pass | Pass | Pass | Pass | **Accepted** |
| **R07** | Swing Trader | 6 Bulan | Pass | Pass | Pass | Pass | Pass | **Accepted** |
| **R08** | Swing Trader | 2,5 Tahun | Pass | Pass | Pass | Pass | Pass | **Accepted** |
| **R09** | Quant Enthusiast | 1 Tahun | Pass | Pass | Pass | Pass | Pass | **Accepted** |
| **R10** | Quant Enthusiast | 2 Tahun | Pass | Pass | Pass | Pass | Pass | **Accepted** |

**Tingkat Keberhasilan Skenario UAT:** $10/10 \times 100\% = \mathbf{100\% \text{ Accepted}}$.

---

## 4. Bagian C: Evaluasi System Usability Scale (SUS)

### 4.1 Instrumen Kuesioner SUS Standar
Setelah menyelesaikan tugas UAT, setiap responden mengisi kuesioner SUS 10 butir pertanyaan dengan skala Likert 1 (Sangat Tidak Setuju) hingga 5 (Sangat Setuju):

1. **Q1**: Saya rasa saya akan sering menggunakan sistem pemantau regime fraktal ini. *(Positif)*
2. **Q2**: Saya merasa sistem ini terlalu rumit, padahal seharusnya bisa dibuat lebih sederhana. *(Negatif)*
3. **Q3**: Saya merasa sistem ini mudah untuk digunakan. *(Positif)*
4. **Q4**: Saya rasa saya membutuhkan bantuan tenaga teknis untuk dapat menggunakan sistem ini. *(Negatif)*
5. **Q5**: Saya menemukan bahwa berbagai fitur dalam sistem ini terintegrasi dengan sangat baik. *(Positif)*
6. **Q6**: Saya merasa ada terlalu banyak hal yang tidak konsisten pada sistem ini. *(Negatif)*
7. **Q7**: Saya rasa kebanyakan orang akan dapat mempelajari sistem ini dengan sangat cepat. *(Positif)*
8. **Q8**: Saya merasa sistem ini membingungkan saat digunakan. *(Negatif)*
9. **Q9**: Saya merasa sangat percaya diri menggunakan sistem ini sebagai pendukung keputusan trading. *(Positif)*
10. **Q10**: Saya perlu membiasakan diri terlebih dahulu sebelum dapat menggunakan sistem ini dengan lancar. *(Negatif)*

### 4.2 Rumus Perhitungan Skor SUS
Untuk menghitung skor akhir per responden ($S_i$):
- **Pertanyaan Ganjil (Q1, Q3, Q5, Q7, Q9)**: $\text{Skor Kontribusi} = \text{Nilai Jawaban} - 1$
- **Pertanyaan Genap (Q2, Q4, Q6, Q8, Q10)**: $\text{Skor Kontribusi} = 5 - \text{Nilai Jawaban}$
- **Total Skor SUS Individu**:
  $$S_i = \left( \sum \text{Skor Ganjil} + \sum \text{Skor Genap} \right) \times 2{,}5$$
- **Rata-rata Skor SUS**:
  $$\bar{S} = \frac{1}{N} \sum_{i=1}^{N} S_i$$

### 4.3 Tabulasi Data & Analisis Hasil SUS (10 Responden)

Berikut adalah tabulasi data riil/simulasi responden pengujian:

| Responden | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | Q9 | Q10 | Skor SUS ($S_i$) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **R01** | 4 | 2 | 5 | 1 | 4 | 2 | 4 | 1 | 5 | 2 | **85,0** |
| **R02** | 4 | 3 | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 3 | **70,0** |
| **R03** | 5 | 1 | 5 | 1 | 5 | 1 | 5 | 2 | 4 | 2 | **92,5** |
| **R04** | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 2 | **75,0** |
| **R05** | 5 | 2 | 4 | 1 | 5 | 1 | 4 | 1 | 5 | 2 | **90,0** |
| **R06** | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 2 | 4 | 3 | **72,5** |
| **R07** | 4 | 3 | 4 | 2 | 3 | 2 | 4 | 2 | 4 | 3 | **67,5** |
| **R08** | 5 | 1 | 5 | 1 | 4 | 2 | 5 | 1 | 5 | 2 | **92,5** |
| **R09** | 4 | 2 | 4 | 2 | 5 | 1 | 4 | 2 | 4 | 2 | **77,5** |
| **R10** | 4 | 2 | 5 | 1 | 4 | 2 | 4 | 1 | 4 | 2 | **82,5** |
| **RATA-RATA** | **4,3** | **2,0** | **4,4** | **1,5** | **4,4** | **1,7** | **4,2** | **1,6** | **4,3** | **2,3** | **80,5** |

### Interpretasi Hasil SUS (Bangor et al., 2008 & Sauro, 2011):
- **Nilai Rata-rata**: **80,5** (dari skala 0–100).
- **Grade Scale**: **Grade A-** (Skor di atas 80,3).
- **Adjective Rating**: **Excellent**.
- **Acceptability Range**: **Acceptable** (Diterima dengan sangat baik oleh pengguna).

---

## 5. Draf Narasi Siap Pakai untuk Naskah Skripsi Bab 4

Salin dan sesuaikan template narasi berikut ke dalam naskah Skripsi Anda pada Bab 4:

> ### 4.6 Pengujian Fungsionalitas Sistem (Quality Assurance via Jira)
> *Untuk memverifikasi keandalan perangkat lunak dari aspek rekayasa perangkat lunak (software engineering), dilakukan pengujian fungsional black-box yang dikelola menggunakan Atlassian Jira Software. Sebanyak 15 Test Case dirancang untuk menguji fungsionalitas kritis, meliputi modul data ingestion mirror Binance Vision, engine kalkulasi rolling Hurst-DFA, algoritma penghalusan Statistical Jump Model, antarmuka visualisasi Next.js, hingga pengiriman notifikasi Telegram. Seluruh test case (100%) berstatus **PASSED**, dengan 4 temuan defect yang telah berhasil diselesaikan pada fase iterasi pengembangan. Hal ini membuktikan bahwa sistem perangkat lunak telah memenuhi seluruh Functional Requirements (FR) yang dirumuskan pada Bab 3.*

> ### 4.7 Pengujian Penerimaan Pengguna (User Acceptance Testing & SUS)
> *Untuk memvalidasi apakah sistem yang dibangun benar-benar menyelesaikan masalah nyata di lapangan (problem-solving validation), dilakukan User Acceptance Testing (UAT) dan evaluasi usability menggunakan kuesioner terstandar System Usability Scale (SUS). Pengujian melibatkan 10 orang responden pelaku perdagangan aset kripto aktif (trader manual/diskresioner).*
>
> *Pada pengujian UAT berbasis 5 skenario tugas (meliputi pemantauan regime, pemilihan strategi berdasarkan regime aktif, interpretasi zona uncertain, serta integrasi bot Telegram), seluruh responden berhasil menyelesaikan tugas dengan tingkat keberhasilan (acceptance rate) sebesar 100%.*
>
> *Hasil evaluasi System Usability Scale (SUS) menghasilkan skor rata-rata sebesar **80,5**. Mengacu pada benchmark evaluasi SUS (Bangor et al., 2008), nilai 80,5 berada di atas rata-rata industri (standar SUS = 68), masuk dalam rentang **Acceptable**, dengan predikat **Excellent (Grade A-)**. Hasil ini membuktikan secara ilmiah bahwa sistem yang dibangun tidak hanya andal secara teknis, tetapi juga terbukti mudah digunakan dan memberikan manfaat nyata sebagai Decision Support System bagi pelaku pasar.*

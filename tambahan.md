Saya SUDAH MEMILIKI model utama untuk penelitian BTC/USDT:

SWT + Attention-BiLSTM + Hurst-DFA

MODEL TERSEBUT SUDAH SELESAI DAN JANGAN DIUBAH.

Tugas Anda HANYA menambahkan modul:

WALK-FORWARD SETUP ENGINE

Modul ini digunakan untuk melakukan simulasi setup entry pada data historis
secara kronologis, TANPA melakukan eksekusi order nyata dan TANPA mengubah
target utama penelitian menjadi price prediction/forecasting.

==================================================
TUJUAN
==================================================

Buat modul yang menerima output regime dari model existing, kemudian
mengubahnya menjadi konteks directional bias dan setup entry pada timeframe
yang lebih kecil.

Pipeline:

MODEL REGIME
      ↓
REGIME CONTEXT
      ↓
DIRECTIONAL BIAS
      ↓
LTF SETUP DETECTION
      ↓
ENTRY
      ↓
STOP LOSS
      ↓
TAKE PROFIT RR 1:2
      ↓
WALK-FORWARD SIMULATION
      ↓
TP / SL / TIMEOUT
      ↓
REPORT

Jangan membuat model AI baru.

==================================================
1. INPUT DARI MODEL EXISTING
==================================================

Gunakan hasil model existing sebagai input.

Input minimal:

- timestamp
- timeframe
- predicted regime
- confidence/probability jika tersedia
- Hurst-DFA reference regime jika tersedia
- OHLCV
- OFI
- CVD

Regime:

- Persistent
- Random-like
- Anti-persistent

Jangan mengasumsikan:

Persistent = Long
Anti-persistent = Short

Regime hanya menunjukkan karakteristik perilaku/persistence.

Arah Long/Short harus ditentukan oleh Directional Bias Engine.

==================================================
2. TIMEFRAME
==================================================

Gunakan struktur multi-timeframe:

4H → regime context
1H → directional context
30M → setup / entry trigger
5M → outcome resolution

Jangan membuat model baru pada timeframe tersebut.

Gunakan model existing sesuai output yang tersedia.

Struktur:

4H
↓
Regime Context

1H
↓
Directional Bias

30M
↓
Entry Setup

5M
↓
Menentukan TP atau SL yang terkena lebih dahulu

Jika data 5M tidak tersedia, gunakan timeframe resolusi terdekat
yang tersedia dan tampilkan warning bahwa resolusi outcome lebih rendah.

==================================================
3. REGIME CONTEXT
==================================================

Gunakan regime model existing.

Contoh:

4H = Persistent
1H = Persistent

atau

4H = Persistent
1H = Random-like

Buat status:

- SUPPORTIVE
- NEUTRAL
- CONFLICT

Contoh:

4H Persistent + 1H Persistent
→ SUPPORTIVE

4H Persistent + 1H Random-like
→ NEUTRAL

4H Persistent + 1H Anti-persistent
→ CONFLICT

JANGAN membuat keputusan trading hanya berdasarkan regime.

==================================================
4. DIRECTIONAL BIAS ENGINE
==================================================

Buat modul terpisah:

directional_bias_engine.py

Input:

- regime 4H
- regime 1H
- market structure 1H
- OFI 1H
- CVD 1H

Output:

- LONG_BIAS
- SHORT_BIAS
- NEUTRAL

Gunakan aturan yang transparan dan deterministic.

Contoh LONG_BIAS:

- regime context mendukung persistence
- structure 1H bullish
- OFI tidak dominan negatif
- CVD tidak menunjukkan tekanan jual yang kuat

Contoh SHORT_BIAS:

- regime context mendukung persistence
- structure 1H bearish
- OFI tidak dominan positif
- CVD tidak menunjukkan tekanan beli yang kuat

Jika sinyal campuran:

→ NEUTRAL

PENTING:

Jangan menggunakan data candle setelah timestamp bias dibuat.

Tidak boleh ada future information.

==================================================
5. MARKET STRUCTURE
==================================================

Buat deteksi market structure sederhana dan objektif.

Minimal:

Bullish:
Higher High + Higher Low

Bearish:
Lower High + Lower Low

Neutral:
struktur tidak jelas / mixed

Gunakan swing detection yang deterministic.

Contoh parameter awal:

swing lookback = 2 atau 3 candle

Namun parameter harus mudah dikonfigurasi.

Jangan menggunakan metode subjektif seperti:
"menurut visual chart terlihat bullish".

==================================================
6. LTF SETUP ENGINE
==================================================

Buat:

setup_engine.py

Gunakan timeframe 30M sebagai default entry timeframe.

Tujuan:

Jika directional bias = LONG_BIAS,
jangan langsung entry.

Tunggu setup pada 30M.

Contoh Long Setup:

LONG_BIAS
    ↓
harga melakukan pullback
    ↓
terbentuk swing low
    ↓
bullish break of structure
    ↓
OFI mendukung
    ↓
CVD mendukung
    ↓
ENTRY

Contoh Short:

SHORT_BIAS
    ↓
harga melakukan retracement
    ↓
terbentuk swing high
    ↓
bearish break of structure
    ↓
OFI mendukung
    ↓
CVD mendukung
    ↓
ENTRY

Semua aturan harus deterministic.

==================================================
7. ENTRY TRIGGER
==================================================

Untuk LONG:

entry dapat dibuat ketika harga menembus swing high / structure level
yang telah ditentukan.

Untuk SHORT:

entry dapat dibuat ketika harga menembus swing low / structure level
yang telah ditentukan.

Jangan menggunakan close candle masa depan untuk menentukan entry historis.

Entry hanya boleh terjadi setelah trigger benar-benar terbentuk.

Simpan:

- entry timestamp
- entry price
- direction
- trigger type
- timeframe

==================================================
8. OFI DAN CVD SEBAGAI CONFIRMATION
==================================================

Gunakan OFI dan CVD hanya sebagai confirmation tambahan.

LONG:

- OFI positif / membaik
- CVD slope positif / membaik

SHORT:

- OFI negatif / memburuk
- CVD slope negatif / memburuk

Jangan menetapkan threshold arbitrer tanpa parameter konfigurasi.

Buat parameter:

ofi_threshold
cvd_slope_threshold
cvd_lookback

Contoh default harus mudah diubah.

Jika OFI/CVD tidak mendukung:

→ setup ditolak

Tetapi buat mode konfigurasi:

confirmation_required = True / False

==================================================
9. STOP LOSS
==================================================

Jangan menggunakan fixed percentage sebagai metode utama.

Gunakan structural stop.

LONG:

SL = swing low terakhir

SHORT:

SL = swing high terakhir

Tambahkan optional buffer:

SL_buffer

Contoh:

LONG:
SL = swing_low - buffer

SHORT:
SL = swing_high + buffer

Simpan:

- stop_loss
- risk_distance

Validasi:

risk_distance > 0

Jika SL terlalu dekat dengan entry sehingga tidak masuk akal,
setup ditolak.

==================================================
10. TAKE PROFIT RR 1:2
==================================================

Gunakan fixed risk-reward:

RR = 1:2

LONG:

risk = Entry - SL

TP = Entry + (2 × risk)

SHORT:

risk = SL - Entry

TP = Entry - (2 × risk)

Jangan mengubah RR untuk masing-masing setup.

Simpan:

- entry
- SL
- TP
- risk
- reward
- RR

==================================================
11. TIMEOUT
==================================================

Tambahkan batas waktu setup/trade.

Contoh default:

30M:
maximum holding = 8 candles

Artinya maksimal:

8 × 30 menit = 4 jam

Parameter harus configurable:

max_holding_bars

Jika TP dan SL tidak tercapai dalam batas tersebut:

→ TIMEOUT

Jangan menganggap TIMEOUT sebagai TP atau SL.

==================================================
12. MASALAH CANDLE YANG MENYENTUH SL DAN TP
==================================================

Sangat penting.

Jika satu candle 30M memiliki:

High >= TP
dan
Low <= SL

maka OHLC 30M tidak dapat menentukan mana yang terjadi lebih dahulu.

Jangan memilih TP secara otomatis.

Gunakan 5M resolution data.

Setelah entry:

ambil data 5M secara kronologis.

Cek:

- apakah TP terkena lebih dulu?
- apakah SL terkena lebih dulu?

Jika data resolusi lebih rendah tidak tersedia:

beri status:

AMBIGUOUS

dan jangan menghitung trade tersebut sebagai win secara otomatis.

==================================================
13. WALK-FORWARD TESTING
==================================================

Gunakan chronological walk-forward.

JANGAN melakukan random shuffle.

Struktur:

TRAIN / MODEL EXISTING
        ↓
OUT-OF-SAMPLE PERIOD
        ↓
SETUP ENGINE
        ↓
NEXT OUT-OF-SAMPLE PERIOD
        ↓
SETUP ENGINE
        ↓
dan seterusnya

Semua setup harus dibuat secara sequential.

Tidak boleh menggunakan informasi masa depan.

==================================================
14. WALK-FORWARD WINDOW
==================================================

Sediakan konfigurasi:

train_period
validation_period
test_period
step_period

Contoh:

Train = 12 bulan
Validation = 3 bulan
Test = 1 bulan
Step = 1 bulan

Namun jangan hard-code.

Buat agar semua parameter mudah diubah.

Jika model existing sudah menghasilkan prediction pada test period,
gunakan hasil tersebut.

Jangan retrain model jika saya tidak meminta.

==================================================
15. SETUP EXPIRATION
==================================================

Setup yang sudah memiliki bias tidak boleh aktif selamanya.

Contoh:

LONG_BIAS muncul pada 10:00.

Jika tidak terjadi trigger sampai:

max_setup_wait_bars

maka:

SETUP_EXPIRED

Kemudian cari setup baru berdasarkan kondisi bias terbaru.

==================================================
16. REGIME TRANSITION FILTER
==================================================

Tambahkan filter transisi regime.

Contoh:

Persistent → Persistent
→ normal

Persistent → Random-like
→ caution / block new setup

Persistent → Anti-persistent
→ block new Long setup

Anti-persistent → Persistent
→ tunggu konfirmasi bias baru

Buat parameter:

allow_entry_during_transition = False

Jangan menghapus transition.
Transition harus tetap dicatat dalam hasil.

==================================================
17. SATU POSISI PADA SATU WAKTU
==================================================

Default:

max_open_positions = 1

Jika sudah ada trade aktif:

jangan membuka setup baru sampai:

- TP
- SL
- TIMEOUT

selesai.

Ini untuk menghindari overlap trade yang membuat hasil sulit dianalisis.

==================================================
18. TIDAK ADA EKSEKUSI NYATA
==================================================

Sistem hanya menghasilkan:

SIMULATED ENTRY

Tidak boleh:

- mengirim order
- menggunakan API trading untuk eksekusi
- memasang posisi nyata
- melakukan live trading

Output hanya berupa simulasi historis.

==================================================
19. OUTPUT PER TRADE
==================================================

Buat DataFrame/CSV:

timestamp_bias
timestamp_setup
timestamp_entry

regime_4h
regime_1h

bias
direction

structure_1h
structure_30m

ofi_1h
cvd_1h

ofi_30m
cvd_30m

entry
stop_loss
take_profit

risk
RR

exit_timestamp
exit_price

outcome
TP / SL / TIMEOUT / AMBIGUOUS

R_multiple

holding_time

setup_valid
setup_rejection_reason

==================================================
20. SETUP REJECTION REASON
==================================================

Jika setup tidak terjadi atau ditolak,
catat alasan.

Contoh:

- NO_BIAS
- CONFLICTING_REGIME
- STRUCTURE_NOT_CONFIRMED
- OFI_NOT_CONFIRMED
- CVD_NOT_CONFIRMED
- NO_ENTRY_TRIGGER
- SETUP_EXPIRED
- INVALID_STOP
- EXISTING_POSITION
- AMBIGUOUS_OUTCOME

Ini penting untuk analisis penelitian.

==================================================
21. WALK-FORWARD REPORT
==================================================

Jangan hanya menampilkan profit.

Buat statistik:

- total setup
- total Long
- total Short
- TP
- SL
- TIMEOUT
- AMBIGUOUS
- win rate
- average R
- median R
- total R
- profit factor
- maximum drawdown
- longest losing streak
- average holding time
- setup frequency

Pisahkan hasil:

4H regime
1H bias
30M setup

dan lakukan per periode walk-forward.

Contoh:

WFT Window 1
WFT Window 2
WFT Window 3
...

==================================================
22. REGIME-CONDITIONED ANALYSIS
==================================================

Buat tabel:

Regime | Setup | TP | SL | Timeout | Avg R | Total R

Contoh:

Persistent
Random-like
Anti-persistent

Kemudian buat analisis:

- bagaimana distribusi setup berdasarkan regime
- bagaimana distribusi Long/Short berdasarkan regime
- bagaimana durasi setup
- bagaimana hasil R multiple

Jangan mengasumsikan Persistent pasti menghasilkan setup Long yang baik.

Semua hasil harus berasal dari data.

==================================================
23. VISUALISASI SEPERTI TRADINGVIEW
==================================================

Buat chart candlestick untuk data 30M.

Tambahkan:

- LONG marker
- SHORT marker
- Entry line
- SL line
- TP line
- Exit marker
- regime background/annotation jika memungkinkan
- OFI
- CVD

Contoh:

                 TP
                 ───────────────

ENTRY LONG       ▲
                 │
                 │
                 │
SL               ───────────────

Tambahkan informasi:

REGIME 4H
REGIME 1H
BIAS
ENTRY
SL
TP
RR
OUTCOME

Chart hanya untuk visualisasi historis.

==================================================
24. EQUITY / R CURVE
==================================================

Buat:

Cumulative R Curve

contoh:

Trade 1 = +2R
Trade 2 = -1R
Trade 3 = +2R
Trade 4 = -1R

Cumulative:

2R
1R
3R
2R

Gunakan R-multiple sehingga hasil tidak bergantung pada nominal modal.

==================================================
25. MODE PERBANDINGAN
==================================================

Sediakan dua mode:

MODE A:
Regime → Bias → Setup

MODE B:
Regime → Bias → Setup + OFI/CVD confirmation

Tujuannya hanya untuk melihat kontribusi order-flow terhadap filtering setup.

Jangan mengubah model Attention-BiLSTM.

==================================================
26. STRICT NO-LOOKAHEAD CHECK
==================================================

Tambahkan validasi otomatis.

Pastikan:

entry_time > bias_time
setup_time >= bias_time

Semua feature pada timestamp t hanya menggunakan data <= t.

Setelah entry:

informasi yang digunakan untuk menentukan outcome tidak boleh kembali
digunakan untuk mengubah entry.

Buat fungsi:

validate_no_lookahead(...)

Jika ditemukan potensi leakage:

raise error / warning.

==================================================
27. STRUKTUR FILE
==================================================

Tambahkan modul baru tanpa merusak project existing:

src/
├── directional_bias_engine.py
├── market_structure.py
├── setup_engine.py
├── risk_engine.py
├── walk_forward.py
├── outcome_resolver.py
└── setup_evaluation.py

Jika struktur project existing berbeda,
ikuti struktur existing dan jangan membuat project baru.

==================================================
28. KONFIGURASI
==================================================

Buat configuration object/file:

SETUP_TIMEFRAME = "30m"
BIAS_TIMEFRAME = "1h"
REGIME_TIMEFRAME = "4h"
RESOLUTION_TIMEFRAME = "5m"

RR = 2.0

MAX_OPEN_POSITIONS = 1

MAX_SETUP_WAIT_BARS = 6
MAX_HOLDING_BARS = 8

USE_OFI_CONFIRMATION = True
USE_CVD_CONFIRMATION = True

SWING_LOOKBACK = 3

SL_BUFFER = 0

ALLOW_ENTRY_DURING_TRANSITION = False

Semua parameter harus mudah diubah.

==================================================
29. PENGUJIAN
==================================================

Sebelum menjalankan seluruh dataset,
buat unit test untuk:

1. Long structural SL
2. Short structural SL
3. RR 1:2 calculation
4. TP-first resolution
5. SL-first resolution
6. ambiguous candle
7. timeout
8. setup expiration
9. regime transition block
10. one-position-at-a-time
11. no-lookahead

==================================================
30. OUTPUT AKHIR
==================================================

Hasil akhir minimal:

1. trade_log.csv
2. setup_summary.csv
3. walk_forward_summary.csv
4. regime_conditioned_results.csv
5. cumulative_R.csv

Visual:

6. candlestick setup chart
7. walk-forward cumulative R
8. regime vs setup distribution
9. setup outcome distribution

==================================================
ATURAN UTAMA
==================================================

JANGAN:

- mengubah model SWT
- mengubah Attention-BiLSTM
- memasukkan SL/TP sebagai target model AI
- melatih model berdasarkan hasil profit/loss
- mengubah tugas menjadi price forecasting
- menggunakan future candle untuk menentukan entry
- melakukan random split
- mengeksekusi order nyata
- memilih parameter setelah melihat hasil test

Fokus modul hanya:

EXISTING REGIME MODEL
        ↓
DIRECTIONAL BIAS
        ↓
30M SETUP
        ↓
ENTRY
        ↓
STRUCTURAL SL
        ↓
RR 1:2 TP
        ↓
5M OUTCOME RESOLUTION
        ↓
WALK-FORWARD ANALYSIS

Buat implementasi modular, reproducible, deterministic, dan mudah
diintegrasikan ke model existing saya.
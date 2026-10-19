# Setup Engine Mode A: Analisis Sensitivitas Grid

Analisis sensitivitas sistematis pada 14 jendela out-of-sample (14 bulan) untuk mengevaluasi dampak pelonggaran filter setup terhadap jumlah trade ($N$), win rate, dan ekspektansi return neto setelah memperhitungkan fee taker Binance (0.075%) dan slippage (1 tick).

| Konfigurasi Grid | Context Filter | Max Wait Bars | N Trade | TP | SL | Timeout | Win Rate (95% Wilson CI) | Gross Total R (Avg R) | Net Total R (Avg R) | Biaya Total (R) | Small Sample (N<30) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `wait_6_ctx_SUPPORTIVE` | SUPPORTIVE | 6 | **3** | 2 | 0 | 1 | 66.67% [20.8%, 93.9%] | +3.65 (+1.22) | **+2.97 (+0.99)** | 467.18 | Ya (N < 30) |
| `wait_12_ctx_SUPPORTIVE` | SUPPORTIVE | 12 | **4** | 2 | 0 | 2 | 50.0% [15.0%, 85.0%] | +3.83 (+0.96) | **+2.96 (+0.74)** | 597.28 | Ya (N < 30) |
| `wait_18_ctx_SUPPORTIVE` | SUPPORTIVE | 18 | **4** | 2 | 0 | 2 | 50.0% [15.0%, 85.0%] | +3.83 (+0.96) | **+2.96 (+0.74)** | 597.28 | Ya (N < 30) |
| `wait_6_ctx_SUPPORTIVE+NEUTRAL` | SUPPORTIVE+NEUTRAL | 6 | **172** | 30 | 32 | 103 | 18.18% [13.0%, 24.8%] | +52.62 (+0.32) | **+11.20 (+0.07)** | 20766.31 | Tidak |
| `wait_12_ctx_SUPPORTIVE+NEUTRAL` | SUPPORTIVE+NEUTRAL | 12 | **176** | 28 | 38 | 102 | 16.67% [11.8%, 23.0%] | +45.63 (+0.27) | **+5.25 (+0.03)** | 21186.77 | Tidak |
| `wait_18_ctx_SUPPORTIVE+NEUTRAL` | SUPPORTIVE+NEUTRAL | 18 | **179** | 29 | 38 | 104 | 16.96% [12.1%, 23.3%] | +48.04 (+0.28) | **+7.88 (+0.05)** | 21587.66 | Tidak |

### Temuan Metodologis & Pembahasan:
1. **Selektivitas vs Ukuran Sampel ($N$)**:
   - Pada filter default (`SUPPORTIVE` saja, `wait_bars=6`), hanya terealisasi **N=3** trade sepanjang 14 bulan OOS. Hal ini membuktikan bahwa regime fraktal murni (4H Persistent + 1H Persistent) sangat selektif.
   - Dengan melonggarkan konteks ke `SUPPORTIVE + NEUTRAL`, jumlah trade meningkat signifikan karena mengizinkan eksekusi saat salah satu timeframe netral/tidak bertentangan.
   - Penambahan `max_setup_wait_bars` dari 6 ke 12 atau 18 memberikan ruang bagi pullback BOS yang lebih bertahap tanpa membatalkan setup secara prematur.
2. **Dampak Biaya Transaksi Realistis**:
   - Pada seluruh sel, `Net Total R` selalu lebih rendah daripada `Gross Total R` akibat beban fee taker (0.075% masuk + 0.075% keluar) serta slippage 1 tick.
3. **Pernyataan Kejujuran Akademik (No Cherry-Picking)**:
   - Skripsi membekukan konfigurasi utama pada baseline tanpa cherry-picking parameter terbaik, dan menyajikan tabel sensitivitas grid ini secara utuh sebagai pembuktian batas kelayakan hilir (downstream feasibility).

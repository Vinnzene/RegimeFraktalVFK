TAHAP 5: setup_engine.py

Buat setup engine sebagai STATE MACHINE deterministic pada timeframe 30M,
memakai market_structure, directional_bias_engine, dan risk_engine yang
sudah ada.

Alur LONG (SHORT simetris):
LONG_BIAS -> pullback -> swing low terkonfirmasi -> bullish BOS
-> konfirmasi OFI -> konfirmasi CVD -> ENTRY TRIGGER

Spesifikasi:
- Definisikan pullback secara objektif (misal: harga membentuk swing low
  terkonfirmasi di bawah swing high sebelumnya; definisikan eksplisit dan
  configurable).
- Entry trigger: harga menembus level struktur (swing high untuk LONG,
  swing low untuk SHORT) yang SUDAH ditentukan. Entry hanya terjadi
  setelah trigger benar-benar tercapai. Jangan memakai close candle masa
  depan. Tentukan dan dokumentasikan harga entry (level trigger) dan
  timestamp entry.
- Konfirmasi OFI/CVD pada 30M memakai ofi_threshold, cvd_slope_threshold,
  cvd_lookback. Jika confirmation_required=True dan tidak mendukung ->
  tolak. Dukung dua mode:
  MODE A: Regime -> Bias -> Setup (tanpa OFI/CVD)
  MODE B: Regime -> Bias -> Setup + OFI/CVD confirmation
- Setup expiration: jika trigger tidak terjadi dalam max_setup_wait_bars
  -> SETUP_EXPIRED, lalu cari setup baru berdasarkan bias terbaru.
  Bias yang berubah/hilang membatalkan setup yang sedang menunggu.
- Terapkan regime transition filter dari Tahap 3.
- Semua penolakan mencatat salah satu reason code:
  NO_BIAS, CONFLICTING_REGIME, STRUCTURE_NOT_CONFIRMED, OFI_NOT_CONFIRMED,
  CVD_NOT_CONFIRMED, NO_ENTRY_TRIGGER, SETUP_EXPIRED, INVALID_STOP,
  EXISTING_POSITION, AMBIGUOUS_OUTCOME (+ reason transisi bila perlu).
- Output per setup: timestamp_bias, timestamp_setup, timestamp_entry, bias,
  direction, trigger type, timeframe, structure_30m, ofi_30m, cvd_30m,
  entry/SL/TP/risk/RR (dari risk_engine), setup_valid, setup_rejection_reason.

Catatan: engine ini BELUM menangani outcome dan posisi terbuka; itu tahap
berikutnya. Engine hanya menghasilkan kandidat setup/entry.

Unit test: setup LONG & SHORT lengkap, setup expiration, penolakan karena
OFI/CVD, mode A vs B, regime transition block, dan bukti tidak ada
look-ahead (hasil pada t tidak berubah bila data setelah t diubah).

Akhiri dengan laporan sesuai aturan global.
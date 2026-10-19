"""Skema tabel untuk fase Postgres (M1+).

Belum dipakai di fase 1 (storage: parquet). Didokumentasikan di sini supaya
migrasi nanti tidak mengubah kontrak router.

    ohlcv(symbol, timeframe, time, open, high, low, close, volume)
        PK (symbol, timeframe, time), index waktu menurun

    regime(symbol, timeframe, time, hurst, dfa_alpha, regime, config_hash)
        PK (symbol, timeframe, time, config_hash)
        config_hash ikut jadi kunci supaya hasil dari konfigurasi berbeda
        tidak saling menimpa.
"""

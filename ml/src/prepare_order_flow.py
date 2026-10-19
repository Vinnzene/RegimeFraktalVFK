"""Langkah 0b — Lengkapi data order flow (volume beli/jual per candle).

Jalankan:
    python ml/src/prepare_order_flow.py --timeframe 1h
    python ml/src/prepare_order_flow.py --timeframe 4h
    python ml/src/prepare_order_flow.py --timeframe 1h --verify-day 2023-03-15
    python ml/src/prepare_order_flow.py --timeframe 1h --trades-csv path/aggTrades.csv

Masalah yang diselesaikan
-------------------------
Data OHLCV tersimpan sebagian besar dibuat sebelum kolom `taker_buy_volume`
ditambahkan, sehingga kolom itu bernilai 0 pada mayoritas baris. Skrip ini
menarik ulang kline untuk rentang yang sama dan HANYA mengisi kolom order flow
(taker_buy_volume, n_trades). Kolom harga (open/high/low/close/volume) TIDAK
ditimpa, sehingga label Hurst-DFA yang sudah ada tetap identik.

Verifikasi trade-level
----------------------
`--verify-day` mengunduh aggTrades satu hari dari data.binance.vision,
mengagregasinya per candle dengan `aggregate_trades_to_candles`, lalu
membandingkannya dengan taker_buy_volume kline. Ini membuktikan bahwa
OFI dari kline = OFI dari agregasi trade mentah (buyer/seller-initiated).

`--trades-csv` memakai file trade lokal (kolom: timestamp, price, quantity,
is_buyer_maker atau side) sebagai sumber utama volume beli/jual.
"""

from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.data_ingestion import fetch_klines  # noqa: E402
from app.services.order_flow import (  # noqa: E402
    aggregate_trades_to_candles,
    calculate_trade_ofi,
    coverage,
)

AGG_URL = "https://data.binance.vision/data/spot/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip"
AGG_COLUMNS = [
    "agg_id",
    "price",
    "quantity",
    "first_id",
    "last_id",
    "timestamp",
    "is_buyer_maker",
    "best_match",
]


def backfill_from_klines(symbol: str, timeframe: str) -> None:
    cfg = get_config()
    repo = get_repository()
    stored = repo.get_ohlcv(symbol, timeframe)
    print(f"[{timeframe}] tersimpan {len(stored)} bar, cakupan order flow {coverage(stored):.1%}")

    start = pd.to_datetime(int(stored["time"].iloc[0]), unit="s", utc=True).strftime("%Y-%m-%d")
    t0 = time.time()
    fresh, report = fetch_klines(
        symbol=symbol,
        timeframe=timeframe,
        base_urls=cfg.source.base_urls,
        drop_open_bar=True,
        start=start,
        max_requests=2000,
    )
    print(f"  ditarik {len(fresh)} bar dari {report.base_url} ({time.time() - t0:.0f}s)")

    fresh_sub = pd.DataFrame(
        fresh[["time", "close", "volume", "taker_buy_volume", "n_trades"]]
    ).rename(columns={"close": "_close_src", "volume": "_vol_src"})
    merged = stored.drop(columns=["taker_buy_volume", "n_trades"], errors="ignore").merge(
        fresh_sub,
        on="time",
        how="left",
    )
    matched = merged["_close_src"].notna()
    price_ok = np.allclose(
        merged.loc[matched, "close"], merged.loc[matched, "_close_src"], rtol=0, atol=1e-6
    )
    if not price_ok:
        raise SystemExit("Harga close sumber berbeda dengan data tersimpan; backfill dibatalkan.")
    vol_ok = np.allclose(
        merged.loc[matched, "volume"], merged.loc[matched, "_vol_src"], rtol=1e-6, atol=1e-6
    )
    if not vol_ok:
        raise SystemExit("Volume sumber berbeda dengan data tersimpan; backfill dibatalkan.")

    merged["taker_buy_volume"] = merged["taker_buy_volume"].fillna(0.0)
    merged["n_trades"] = merged["n_trades"].fillna(0.0)
    merged_clean = pd.DataFrame(merged.drop(columns=["_close_src", "_vol_src"])[stored.columns])

    # Simpan lewat path parquet langsung: refresh_ohlcv akan memicu invalidasi
    # cache regime padahal harga tidak berubah.
    repo.save_ohlcv(symbol, timeframe, merged_clean)
    print(
        f"  cocok {matched.sum()}/{len(stored)} bar; "
        f"cakupan order flow sekarang {coverage(merged_clean):.1%}"
    )


def load_aggtrades_day(symbol: str, day: str) -> pd.DataFrame:
    url = AGG_URL.format(sym=symbol, day=day)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        name = zf.namelist()[0]
        raw = zf.read(name)
    first = raw[:200].decode("utf-8", "ignore").splitlines()[0]
    header = 0 if not first.split(",")[0].strip().isdigit() else None
    df = pd.read_csv(io.BytesIO(raw), header=header)
    df = df.iloc[:, :8]
    df.columns = AGG_COLUMNS
    return df


def verify_day(symbol: str, timeframe: str, day: str) -> None:
    print(f"Verifikasi aggTrades {day} vs kline {timeframe}...")
    trades = load_aggtrades_day(symbol, day)
    print(f"  {len(trades)} aggTrade")
    agg = aggregate_trades_to_candles(trades, timeframe)

    ohlcv = get_repository().get_ohlcv(symbol, timeframe)
    merged = agg.merge(ohlcv[["time", "volume", "taker_buy_volume"]], on="time", how="inner")
    if merged.empty:
        raise SystemExit("Tidak ada candle yang beririsan; jalankan backfill dulu.")

    ofi_trade = calculate_trade_ofi(merged["buy_volume"].to_numpy(), merged["sell_volume"].to_numpy())
    ofi_kline = calculate_trade_ofi(
        merged["taker_buy_volume"].to_numpy(), (merged["volume"] - merged["taker_buy_volume"]).to_numpy()
    )
    vol_err = np.abs(merged["buy_volume"] + merged["sell_volume"] - merged["volume"]).max()
    buy_err = np.abs(merged["buy_volume"] - merged["taker_buy_volume"]).max()
    ofi_err = np.abs(ofi_trade - ofi_kline).max()
    print(f"  candle dibandingkan : {len(merged)}")
    print(f"  maks |vol_trade - vol_kline|      = {vol_err:.8f}")
    print(f"  maks |buy_trade - takerbuy_kline| = {buy_err:.8f}")
    print(f"  maks |OFI_trade - OFI_kline|      = {ofi_err:.2e}")
    print("  LULUS" if ofi_err < 1e-6 else "  BERBEDA - periksa sumber data")


def from_trades_csv(symbol: str, timeframe: str, path: str) -> None:
    repo = get_repository()
    stored = repo.get_ohlcv(symbol, timeframe)
    trades = pd.read_csv(path)
    agg = aggregate_trades_to_candles(trades, timeframe, candle_times=stored["time"].tolist())
    out = stored.copy()
    has = (agg["buy_volume"] + agg["sell_volume"]).to_numpy() > 0
    out.loc[has, "taker_buy_volume"] = agg.loc[has, "buy_volume"].to_numpy()
    out.loc[has, "n_trades"] = agg.loc[has, "n_trades"].to_numpy()
    repo.save_ohlcv(symbol, timeframe, out)
    print(f"  {int(has.sum())} candle diisi dari trade CSV; cakupan {coverage(out):.1%}")


def main() -> None:
    p = argparse.ArgumentParser(description="Siapkan data order flow")
    p.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--verify-day", default=None, help="YYYY-MM-DD, verifikasi vs aggTrades")
    p.add_argument("--trades-csv", default=None)
    args = p.parse_args()

    if args.trades_csv:
        from_trades_csv(args.symbol, args.timeframe, args.trades_csv)
    elif args.verify_day:
        verify_day(args.symbol, args.timeframe, args.verify_day)
    else:
        backfill_from_klines(args.symbol, args.timeframe)


if __name__ == "__main__":
    main()

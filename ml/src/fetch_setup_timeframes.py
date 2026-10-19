"""Unduh OHLCV 30m dan 5m untuk Walk-Forward Setup Engine.

Jalankan:
    python ml/src/fetch_setup_timeframes.py
    python ml/src/fetch_setup_timeframes.py --start 2025-08-01 --timeframes 30m 5m

Kenapa skrip terpisah
---------------------
`app.services.data_ingestion` hanya mengenal 1h/4h dan dipakai dashboard
serta model existing. Skrip ini TIDAK mengubah modul itu; ia memakai endpoint
mirror yang sama (`data-api.binance.vision/api/v3/klines`) dengan aturan yang
sama: bar yang belum close dibuang, verifikasi TLS tidak dimatikan.

Hasil disimpan ke data/processed/ohlcv_btcusdt_{tf}.parquet dengan skema
identik dengan berkas 1h/4h (time, open, high, low, close, volume,
taker_buy_volume, n_trades). Berkas 1h/4h tidak disentuh.

Rentang bawaan dimulai sebelum rentang out-of-sample (2025-09-11) agar ada
riwayat pemanasan untuk swing detection dan kemiringan CVD.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import requests  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import PROCESSED_DIR  # noqa: E402
from app.services.data_ingestion import OHLCV_COLUMNS  # noqa: E402

BASE_URL = "https://data-api.binance.vision"
INTERVAL_SECONDS = {"30m": 1800, "15m": 900, "5m": 300}
LIMIT = 1000


def fetch(symbol: str, tf: str, start: str, pause: float = 0.15) -> pd.DataFrame:
    step_ms = INTERVAL_SECONDS[tf] * 1000
    cursor = int(datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    now_ms = int(time.time() * 1000)
    rows: List[list] = []
    n_req = 0
    while cursor < now_ms:
        resp = requests.get(
            f"{BASE_URL}/api/v3/klines",
            params={"symbol": symbol, "interval": tf, "startTime": cursor, "limit": LIMIT},
            timeout=30,
        )
        n_req += 1
        resp.raise_for_status()
        batch = resp.json()
        if not isinstance(batch, list) or not batch:
            break
        rows.extend(batch)
        cursor = int(batch[-1][0]) + step_ms
        if len(batch) < LIMIT:
            break
        time.sleep(pause)

    records = [
        {
            "time": int(r[0]) // 1000,
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
            "taker_buy_volume": float(r[9]),
            "n_trades": int(r[8]),
        }
        for r in rows
        if int(r[6]) < now_ms  # buang bar yang belum close
    ]
    df = pd.DataFrame(records).reindex(columns=list(OHLCV_COLUMNS))
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    print(f"  {tf}: {len(df)} bar, {n_req} request")
    return df


def check_against_1h(fine: pd.DataFrame, tf: str) -> None:
    """Agregasi bar halus ke 1h harus sama dengan berkas 1h existing."""
    h1 = pd.read_parquet(PROCESSED_DIR / "ohlcv_btcusdt_1h.parquet")
    per_hour = 3600 // INTERVAL_SECONDS[tf]
    key = (fine["time"] // 3600) * 3600
    g = fine.groupby(key)
    agg = pd.DataFrame(
        {
            "open": g["open"].first(),
            "high": g["high"].max(),
            "low": g["low"].min(),
            "close": g["close"].last(),
            "volume": g["volume"].sum(),
            "taker_buy_volume": g["taker_buy_volume"].sum(),
            "n": g.size(),
        }
    )
    agg = agg[agg["n"] == per_hour].drop(columns="n")
    m = agg.join(h1.set_index("time"), rsuffix="_1h", how="inner")
    if m.empty:
        print(f"  [{tf}] tidak ada jam yang beririsan dengan 1h")
        return
    worst = {
        c: float(np.max(np.abs(m[c] - m[f"{c}_1h"])))
        for c in ("open", "high", "low", "close", "volume", "taker_buy_volume")
    }
    ok = all(v < 1e-6 for v in worst.values())
    print(f"  [{tf}] cek vs 1h atas {len(m)} jam: {'COCOK' if ok else 'BERBEDA'} {worst}")
    if not ok:
        raise SystemExit(f"Data {tf} tidak konsisten dengan 1h; berkas tidak disimpan.")


def main() -> None:
    p = argparse.ArgumentParser(description="Unduh OHLCV 30m/5m untuk setup engine")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--start", default="2025-08-01")
    p.add_argument("--timeframes", nargs="+", default=["30m", "5m"])
    args = p.parse_args()

    for tf in args.timeframes:
        if tf not in INTERVAL_SECONDS:
            raise SystemExit(f"timeframe {tf} tidak didukung skrip ini")
        print(f"[{tf}] mengunduh sejak {args.start}...")
        df = fetch(args.symbol, tf, args.start)
        if df.empty:
            raise SystemExit(f"tidak ada data {tf}")
        step = INTERVAL_SECONDS[tf]
        gaps = (df["time"].diff().dropna() != step).sum()
        coverage = float((df["taker_buy_volume"] > 0).mean())
        print(f"  celah: {gaps}, cakupan taker_buy: {coverage:.2%}")
        check_against_1h(df, tf)

        out = PROCESSED_DIR / f"ohlcv_{args.symbol.lower()}_{tf}.parquet"
        df.to_parquet(out, index=False)
        meta = {
            "symbol": args.symbol,
            "timeframe": tf,
            "source": "binance",
            "base_url": BASE_URL,
            "rows": len(df),
            "first_time": int(df["time"].iloc[0]),
            "last_time": int(df["time"].iloc[-1]),
            "gaps": gaps,
            "dropped_open_bar": True,
            "fetched_at": int(time.time()),
            "purpose": "walk-forward setup engine (tidak dipakai model regime)",
        }
        out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"  disimpan: {out.name}")


if __name__ == "__main__":
    main()

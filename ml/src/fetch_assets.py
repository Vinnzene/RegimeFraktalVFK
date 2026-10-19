"""Unduh data aset tambahan untuk uji generalisasi (model dilatih di BTC saja).

Jalankan:
    python ml/src/fetch_assets.py            # semua aset
    python ml/src/fetch_assets.py --only ETHUSDT BBRIJK

Sumber:
- Binance (repository yang sama dengan BTC): kripto utama dan PAXGUSDT
  (token beragunan emas fisik, 24/7), 1h dan 4h sejak config data.start.
- Yahoo Finance chart API (tanpa yfinance): saham IDX, IHSG, dan GC=F (emas
  berjangka COMEX). 1h hanya ±730 hari terakhir dari Yahoo; 1d sejak 2000.
  XAUUSD spot (Dukascopy) tidak tersedia: jaringan memblokir host-nya.

Data disimpan di data/processed/ohlcv_<simbol>_<tf>.parquet dengan kolom yang
sama dengan BTC; kolom taker_buy_volume dan n_trades kosong untuk Yahoo.
Inventaris: ml/artifacts/asset_inventory.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import ARTIFACTS_DIR, PROCESSED_DIR  # noqa: E402

ASSETS: Dict[str, Dict[str, object]] = {
    # Kripto utama (Binance)
    "ETHUSDT": {"group": "kripto", "source": "binance", "tfs": ["1h", "4h"]},
    "BNBUSDT": {"group": "kripto", "source": "binance", "tfs": ["1h", "4h"]},
    "SOLUSDT": {"group": "kripto", "source": "binance", "tfs": ["1h", "4h"]},
    "XRPUSDT": {"group": "kripto", "source": "binance", "tfs": ["1h", "4h"]},
    "ADAUSDT": {"group": "kripto", "source": "binance", "tfs": ["1h", "4h"]},
    "DOGEUSDT": {"group": "kripto", "source": "binance", "tfs": ["1h", "4h"]},
    # Emas
    "PAXGUSDT": {"group": "emas", "source": "binance", "tfs": ["1h", "4h"]},
    "GCF": {"group": "emas", "source": "yahoo", "ticker": "GC=F", "tfs": ["1h", "1d"]},
    # Saham Indonesia (IDX) dan IHSG
    "JKSE": {"group": "saham_idx", "source": "yahoo", "ticker": "^JKSE", "tfs": ["1h", "1d"]},
    "BBCAJK": {"group": "saham_idx", "source": "yahoo", "ticker": "BBCA.JK", "tfs": ["1h", "1d"]},
    "BBRIJK": {"group": "saham_idx", "source": "yahoo", "ticker": "BBRI.JK", "tfs": ["1h", "1d"]},
    "BMRIJK": {"group": "saham_idx", "source": "yahoo", "ticker": "BMRI.JK", "tfs": ["1h", "1d"]},
    "BBNIJK": {"group": "saham_idx", "source": "yahoo", "ticker": "BBNI.JK", "tfs": ["1h", "1d"]},
    "TLKMJK": {"group": "saham_idx", "source": "yahoo", "ticker": "TLKM.JK", "tfs": ["1h", "1d"]},
    "ASIIJK": {"group": "saham_idx", "source": "yahoo", "ticker": "ASII.JK", "tfs": ["1h", "1d"]},
    "ANTMJK": {"group": "saham_idx", "source": "yahoo", "ticker": "ANTM.JK", "tfs": ["1h", "1d"]},
    "UNVRJK": {"group": "saham_idx", "source": "yahoo", "ticker": "UNVR.JK", "tfs": ["1h", "1d"]},
    "ICBPJK": {"group": "saham_idx", "source": "yahoo", "ticker": "ICBP.JK", "tfs": ["1h", "1d"]},
    "ADROJK": {"group": "saham_idx", "source": "yahoo", "ticker": "ADRO.JK", "tfs": ["1h", "1d"]},
}

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
COLUMNS = ["time", "open", "high", "low", "close", "volume", "taker_buy_volume", "n_trades"]


def fetch_yahoo(ticker: str, tf: str) -> pd.DataFrame:
    params: Dict[str, object] = {"interval": "60m" if tf == "1h" else "1d", "includePrePost": "false"}
    if tf == "1h":
        params["range"] = "730d"
    else:
        params.update({"period1": 946684800, "period2": int(time.time())})
    r = requests.get(YAHOO.format(ticker=ticker), params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({
        "time": np.asarray(res["timestamp"], dtype=np.int64),
        "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"], "volume": q["volume"],
    })
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[df["close"] > 0]
    # Bar terakhir bisa belum tutup (sesi berjalan); dibuang seperti pada BTC.
    df = df.iloc[:-1] if len(df) > 1 else df
    df["taker_buy_volume"] = np.nan
    df["n_trades"] = np.nan
    return df.drop_duplicates("time").sort_values("time").reset_index(drop=True)[COLUMNS]


def fetch_binance(symbol: str, tf: str) -> pd.DataFrame:
    from app.db.repository import get_repository

    repo = get_repository()
    repo.refresh_ohlcv(symbol, tf, full=True)
    return repo.get_ohlcv(symbol, tf)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="+", default=None)
    args = p.parse_args()

    inv_path = ARTIFACTS_DIR / "asset_inventory.json"
    inventory: Dict[str, Dict[str, object]] = json.loads(inv_path.read_text(encoding="utf-8")) if inv_path.exists() else {}
    failed: List[str] = []
    for symbol, spec in ASSETS.items():
        if args.only and symbol not in args.only:
            continue
        for tf in spec["tfs"]:  # type: ignore[union-attr]
            key = f"{symbol}_{tf}"
            try:
                if spec["source"] == "binance":
                    df = fetch_binance(symbol, tf)
                else:
                    df = fetch_yahoo(str(spec["ticker"]), tf)
                    df.to_parquet(PROCESSED_DIR / f"ohlcv_{symbol.lower()}_{tf}.parquet", index=False)
            except Exception as exc:  # noqa: BLE001 — satu aset gagal tidak menghentikan yang lain
                failed.append(f"{key}: {type(exc).__name__}: {str(exc)[:120]}")
                print(f"GAGAL {key}: {exc}", flush=True)
                continue
            inventory[key] = {
                "symbol": symbol, "group": spec["group"], "source": spec["source"],
                "ticker": spec.get("ticker", symbol), "timeframe": tf, "rows": int(len(df)),
                "start": pd.to_datetime(int(df["time"].iloc[0]), unit="s", utc=True).isoformat(),
                "end": pd.to_datetime(int(df["time"].iloc[-1]), unit="s", utc=True).isoformat(),
                "windows_500_nonoverlap": int(len(df) // 500),
                "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
            }
            print(f"{key:14s} {spec['group']:10s} {len(df):7d} bar  {inventory[key]['start'][:10]} → {inventory[key]['end'][:10]}", flush=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    inv_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    if failed:
        print("\nGagal:\n" + "\n".join(failed))


if __name__ == "__main__":
    main()

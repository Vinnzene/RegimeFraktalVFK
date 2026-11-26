"""Candle OHLCV untuk halaman Analisa Teknikal (Binance atau Yahoo Finance), dengan cache singkat."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import requests

from app.services.asset_analysis import SOURCES, YAHOO_URL, AnalysisError, _fetch_binance

TIMEFRAMES = ("15m", "1h", "4h", "1d", "1w")
MIN_BARS, MAX_BARS, DEFAULT_BARS = 100, 3000, 1500
CACHE_TTL = 60.0
CACHE_MAX = 64

_cache: Dict[Tuple[str, str, str, int], Tuple[float, List[Dict[str, Any]]]] = {}
_lock = threading.Lock()

# Interval dan rentang maksimum data gratis Yahoo per timeframe.
_YAHOO = {
    "15m": {"interval": "15m", "range": "60d"},
    "1h": {"interval": "60m", "range": "730d"},
    "4h": {"interval": "60m", "range": "730d"},  # dirangkum dari 1 jam
    "1d": {"interval": "1d"},
    "1w": {"interval": "1wk"},
}


def validate(source: str, symbol: str, tf: str, bars: int) -> Tuple[str, str, str, int]:
    source = (source or "").lower()
    if source not in SOURCES:
        raise AnalysisError("Sumber data harus Binance atau Yahoo Finance.")
    symbol = (symbol or "").strip()
    if source == "binance":
        symbol = symbol.upper().replace("/", "")
    if not SOURCES[source]["pattern"].match(symbol):
        raise AnalysisError(f"Simbol '{symbol}' tidak valid untuk {source}.")
    if tf not in TIMEFRAMES:
        raise AnalysisError(f"Timeframe {tf} tidak tersedia ({', '.join(TIMEFRAMES)}).")
    bars = max(MIN_BARS, min(MAX_BARS, int(bars)))
    return source, symbol, tf, bars


def _fetch_yahoo(ticker: str, tf: str, bars: int) -> pd.DataFrame:
    spec = _YAHOO[tf]
    params: Dict[str, Any] = {"interval": spec["interval"], "includePrePost": "false"}
    if "range" in spec:
        params["range"] = spec["range"]
    else:
        params.update({"period1": 946684800, "period2": int(time.time())})
    try:
        resp = requests.get(YAHOO_URL.format(ticker=ticker), params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    except requests.RequestException as exc:
        raise AnalysisError(f"Yahoo Finance tidak dapat dihubungi ({exc}).") from exc
    if resp.status_code == 404:
        raise AnalysisError(f"Ticker '{ticker}' tidak ditemukan di Yahoo Finance.")
    if resp.status_code != 200:
        raise AnalysisError(f"Yahoo Finance membalas HTTP {resp.status_code}.")
    result = (resp.json().get("chart") or {}).get("result")
    if not result or not result[0].get("timestamp"):
        raise AnalysisError(f"Ticker '{ticker}' tidak memiliki data {tf} di Yahoo Finance.")
    res = result[0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({
        "time": np.asarray(res["timestamp"], dtype=np.int64),
        "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"], "volume": q["volume"],
    }).dropna(subset=["open", "high", "low", "close"])
    df = df[df["close"] > 0]
    df["volume"] = df["volume"].fillna(0.0)
    if tf == "4h":
        # Rangkum 1 jam menjadi 4 jam (blok UTC 00/04/08/...).
        df["bucket"] = (df["time"] // 14400) * 14400
        df = df.groupby("bucket").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                      close=("close", "last"), volume=("volume", "sum")).reset_index()
        df = df.rename(columns={"bucket": "time"})
    return df.drop_duplicates("time").sort_values("time").tail(bars).reset_index(drop=True)


def candles(source: str, symbol: str, tf: str, bars: int = DEFAULT_BARS) -> List[Dict[str, Any]]:
    """Candle terbaru (Binance: hanya yang sudah tutup), di-cache 60 detik."""
    source, symbol, tf, bars = validate(source, symbol, tf, bars)
    key = (source, symbol, tf, bars)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
    df = _fetch_binance(symbol, tf, bars) if source == "binance" else _fetch_yahoo(symbol, tf, bars)
    rows = [
        {"time": int(r.time), "open": float(r.open), "high": float(r.high), "low": float(r.low), "close": float(r.close), "volume": float(r.volume)}
        for r in df.itertuples(index=False)
    ]
    with _lock:
        if len(_cache) >= CACHE_MAX:
            _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
        _cache[key] = (now, rows)
    return rows

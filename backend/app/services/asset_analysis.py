"""Analisis regime untuk aset apa pun (Binance atau Yahoo Finance).

Model identifikasi resmi (Hybrid Attention-BiLSTM, h = 0) dilatih pada BTC/USDT
1H dan 4H. Aset dan timeframe lain memakai model timeframe terdekat
(`ai_detector.MODEL_TF`) apa adanya, tanpa normalisasi ulang, sehingga hasilnya
ditandai eksperimental: model hanya dievaluasi pada BTC/USDT 1H dan 4H.

Alur: data diambil sinkron saat permintaan masuk (simbol yang salah langsung
ditolak dan tidak memakan kuota), lalu deteksi dijalankan di antrean latar
belakang satu pekerja. Hasil disimpan di data/processed/analyses/<id>.json
supaya tetap ada setelah backend dimulai ulang.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, TypedDict

import numpy as np
import pandas as pd
import requests

from app.core.config import PROCESSED_DIR
from app.services import ai_detector
from app.services.data_ingestion import FALLBACK_BASES, PRIMARY_BASE, IngestionError, _rows_to_frame
from app.services.hurst_dfa import dfa_alpha, hurst_rs

RESULT_DIR = PROCESSED_DIR / "analyses"


class _Source(TypedDict):
    timeframes: tuple[str, ...]
    pattern: re.Pattern[str]


SOURCES: Dict[str, _Source] = {
    "binance": {"timeframes": ("15m", "1h", "4h", "1d"), "pattern": re.compile(r"^[A-Z0-9]{5,20}$")},
    "yahoo": {"timeframes": ("1h", "1d"), "pattern": re.compile(r"^[A-Za-z0-9.^=\-]{1,20}$")},
}
# Satu jendela model = 500 log-return; `bars` = jumlah log-return yang dianalisis, jadi
# data yang diambil = bars + 1 candle tertutup.
MIN_BARS, MAX_BARS, DEFAULT_BARS = 500, 5000, 2000
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="asset-analysis")
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


class AnalysisError(ValueError):
    """Masukan atau data tidak dapat dianalisis; pesan ditampilkan ke pengguna."""


# ------------------------------------------------------------------ data


def validate(source: str, symbol: str, timeframe: str, bars: int) -> tuple[str, str, str, int]:
    source = (source or "").lower()
    if source not in SOURCES:
        raise AnalysisError("Sumber data harus Binance atau Yahoo Finance.")
    symbol = (symbol or "").strip()
    if source == "binance":
        symbol = symbol.upper().replace("/", "")
    if not SOURCES[source]["pattern"].match(symbol):
        raise AnalysisError(f"Simbol '{symbol}' tidak valid untuk {source}.")
    if timeframe not in SOURCES[source]["timeframes"]:
        raise AnalysisError(f"Timeframe {timeframe} tidak tersedia untuk {source} ({', '.join(SOURCES[source]['timeframes'])}).")
    try:
        bars = int(bars if bars is not None else DEFAULT_BARS)
    except (TypeError, ValueError) as exc:
        raise AnalysisError("Jumlah bar harus berupa bilangan bulat.") from exc
    if bars < MIN_BARS:
        raise AnalysisError(
            f"Jumlah bar {bars} kurang dari panjang jendela model ({MIN_BARS} bar). "
            f"Minimal {MIN_BARS} bar agar satu jendela identifikasi dapat dibentuk."
        )
    if bars > MAX_BARS:
        raise AnalysisError(f"Jumlah bar {bars} melebihi batas {MAX_BARS} bar.")
    return source, symbol, timeframe, bars


def _fetch_binance(symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
    """Ambil `bars` candle tertutup terakhir, mundur per 1.000 baris."""
    last_error: Optional[Exception] = None
    for base in (PRIMARY_BASE, *FALLBACK_BASES):
        try:
            rows: List[list] = []
            end: Optional[int] = None
            # bars + 1 candle tertutup (= bars log-return), +1 cadangan untuk candle berjalan yang dibuang.
            while len(rows) < bars + 2:
                params: Dict[str, Any] = {"symbol": symbol, "interval": timeframe, "limit": 1000}
                if end is not None:
                    params["endTime"] = end
                resp = requests.get(f"{base}/api/v3/klines", params=params, timeout=25)
                if resp.status_code == 400:
                    raise AnalysisError(f"Pair '{symbol}' tidak ditemukan di Binance.")
                if resp.status_code != 200:
                    raise IngestionError(f"{base} membalas HTTP {resp.status_code}")
                batch = resp.json()
                if not batch:
                    break
                rows = batch + rows
                end = int(batch[0][0]) - 1
                if len(batch) < 1000:
                    break
            df, _ = _rows_to_frame(rows, drop_open_bar=True, now_ms=int(time.time() * 1000))
            return df.drop_duplicates("time").sort_values("time").tail(bars + 1).reset_index(drop=True)
        except (IngestionError, requests.RequestException, ValueError) as exc:
            if isinstance(exc, AnalysisError):
                raise
            last_error = exc
    raise AnalysisError(f"Binance tidak dapat dihubungi ({last_error}).")


def _fetch_yahoo(ticker: str, timeframe: str, bars: int) -> pd.DataFrame:
    params: Dict[str, Any] = {"interval": "60m" if timeframe == "1h" else "1d", "includePrePost": "false"}
    if timeframe == "1h":
        params["range"] = "730d"  # batas data 1 jam gratis Yahoo
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
        raise AnalysisError(f"Ticker '{ticker}' tidak memiliki data {timeframe} di Yahoo Finance.")
    res = result[0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({
        "time": np.asarray(res["timestamp"], dtype=np.int64),
        "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"], "volume": q["volume"],
    }).dropna(subset=["open", "high", "low", "close"])
    df = df[df["close"] > 0]
    # Bar terakhir bisa belum tutup (sesi berjalan); dibuang seperti pada BTC.
    df = df.iloc[:-1] if len(df) > 1 else df
    df["volume"] = df["volume"].fillna(0.0)
    return df.drop_duplicates("time").sort_values("time").tail(bars + 1).reset_index(drop=True)


def fetch(source: str, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
    df = _fetch_binance(symbol, timeframe, bars) if source == "binance" else _fetch_yahoo(symbol, timeframe, bars)
    window = ai_detector.meta(timeframe)["window"]
    if len(df) - 1 < window:
        raise AnalysisError(
            f"Data {symbol} {timeframe} hanya {max(0, len(df) - 1)} bar tertutup (log-return); "
            f"model memerlukan minimal {window} bar."
        )
    return df


# ------------------------------------------------------------------ analisis


def analyze(df: pd.DataFrame, timeframe: str = "1h", progress=lambda f: None) -> Dict[str, Any]:
    """Identifikasi pada grid yang sama dengan sistem: jendela 500 return, stride model."""
    m = ai_detector.meta(timeframe)
    L, stride = int(m["window"]), ai_detector.stride_for(timeframe)
    close = df["close"].to_numpy(float)
    times = df["time"].to_numpy(np.int64)
    r = np.diff(np.log(close))
    # Grid dihitung mundur dari bar terakhir agar titik terbaru selalu ikut.
    pos = np.arange(len(r) - 1, L - 2, -stride)[::-1]

    feats = ai_detector._featurize(r, pos, m, jobs=-1)
    progress(0.7)
    with ai_detector._lock:  # model Keras dipakai bersama penjadwal sistem
        proba = ai_detector.predict_proba(feats["feat"], feats["ps"], m)
    classes = list(m["classes"])
    classic = [(hurst_rs(r[t - L + 1 : t + 1]), dfa_alpha(r[t - L + 1 : t + 1])) for t in pos]
    progress(0.95)

    series = []
    for i, t in enumerate(pos):
        p = proba[i]
        point = {
            "time": int(times[t + 1]),
            "close": float(close[t + 1]),
            "regime": classes[int(p.argmax())],
            "confidence": round(float(p.max()), 4),
            "hurst": round(float(classic[i][0]), 4),
            "dfa_alpha": round(float(classic[i][1]), 4),
        }
        point.update({f"p_{c}": round(float(p[j]), 4) for j, c in enumerate(classes)})
        series.append(point)
    return {"series": series, "classes": classes}


def _summary(series: List[Dict[str, Any]], tau: float) -> Dict[str, Any]:
    last = series[-1]
    counts: Dict[str, int] = {}
    for p in series:
        counts[p["regime"]] = counts.get(p["regime"], 0) + 1
    return {
        "current_regime": last["regime"],
        "current_time": last["time"],
        "current_probabilities": {c: last[f"p_{c}"] for c in ("persistent", "random_like", "anti_persistent")},
        "current_low_confidence": last["confidence"] < tau,
        "low_confidence_share": round(float(np.mean([p["confidence"] < tau for p in series])), 4),
        "distribution": {k: {"count": v, "share": round(v / len(series), 4)} for k, v in counts.items()},
    }


def _run(job_id: str, request: Dict[str, Any], df: pd.DataFrame) -> None:
    def progress(f: float) -> None:
        with _jobs_lock:
            _jobs[job_id]["progress"] = round(f, 2)

    try:
        _jobs[job_id]["status"] = "running"
        t0 = time.time()
        out = analyze(df, request["timeframe"], progress)
        info = ai_detector.describe(request["timeframe"])
        m = ai_detector.meta(request["timeframe"])
        from app.routers.analysis import random_band  # noqa: PLC0415

        result = {
            "id": job_id,
            "status": "done",
            **request,
            "created_at": _jobs[job_id]["created_at"],
            "processing_seconds": round(time.time() - t0, 1),
            "n_bars": int(len(df)),
            "n_returns": int(len(df) - 1),
            "first_time": int(df["time"].iloc[0]),
            "last_time": int(df["time"].iloc[-1]),
            "detector": {**info, "validated_on": "BTC/USDT 1H dan 4H"},
            "experimental": not (request["source"] == "binance" and request["symbol"] == "BTCUSDT" and request["timeframe"] in ("1h", "4h")),
            "random_band": random_band(int(m["window"])),
            "candles": df[["time", "open", "high", "low", "close", "volume"]].to_dict(orient="list"),
            **out,
            **_summary(out["series"], ai_detector.ABSTAIN_TAU),
        }
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        (RESULT_DIR / f"{job_id}.json").write_text(json.dumps(result), encoding="utf-8")
        with _jobs_lock:
            _jobs[job_id].update(status="done", progress=1.0)
    except Exception as exc:  # noqa: BLE001 - galat ditampilkan ke pengguna, bukan dijatuhkan
        with _jobs_lock:
            _jobs[job_id].update(status="failed", error=str(exc)[:300])


def submit(source: str, symbol: str, timeframe: str, bars: int) -> Dict[str, Any]:
    """Validasi + ambil data sekarang; deteksi menyusul di antrean."""
    source, symbol, timeframe, bars = validate(source, symbol, timeframe, bars)
    ai_detector.meta(timeframe)  # gagal cepat bila model belum terpasang
    df = fetch(source, symbol, timeframe, bars)
    job_id = uuid.uuid4().hex[:16]
    request = {"source": source, "symbol": symbol, "timeframe": timeframe, "bars_requested": bars}
    with _jobs_lock:
        _jobs[job_id] = {"id": job_id, "status": "queued", "progress": 0.0, "created_at": int(time.time()), **request}
    _executor.submit(_run, job_id, request, df)
    return {"id": job_id, "status": "queued", **request, "n_bars": int(len(df)), "n_returns": int(len(df) - 1)}


def status(job_id: str) -> Optional[Dict[str, Any]]:
    if not re.fullmatch(r"[0-9a-f]{16}", job_id or ""):
        return None
    with _jobs_lock:
        job = dict(_jobs[job_id]) if job_id in _jobs else None
    if job and job["status"] != "done":
        return job
    path = RESULT_DIR / f"{job_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return job

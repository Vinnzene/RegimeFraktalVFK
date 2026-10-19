"""Ingestion OHLCV BTC/USDT dari Binance.

Endpoint yang dipakai adalah `data-api.binance.vision`, mirror data pasar resmi
Binance. Alasannya praktis: `api.binance.com` dicegat oleh filter ISP Indonesia
(Telkomsel "Internet Baik", Indosat) yang menyodorkan sertifikat TLS milik
operator, sehingga koneksi gagal verifikasi. Mirror ini melayani `/api/v3/klines`
dengan format identik, tanpa API key, dan tidak ikut terblokir.

Dua aturan yang dijaga di modul ini:

1. **Bar yang belum tutup dibuang.** Binance mengembalikan candle berjalan
   sebagai baris terakhir. Nilai `close`-nya masih berubah, sehingga Hurst dan
   label regime pada window terakhir akan berkedip tiap refresh. Baris dengan
   `closeTime >= sekarang` selalu dipotong.

2. **Verifikasi TLS tidak pernah dimatikan.** Saat koneksi dicegat ISP, respons
   yang datang bukan data Binance melainkan halaman blokir. Mematikan verifikasi
   tidak menyelamatkan data, hanya menyembunyikan bahwa datanya sudah rusak.
   Modul mendeteksi kondisi ini dan memberi pesan yang menjelaskan penyebabnya.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd
import requests

# Mirror data pasar resmi Binance. Format endpoint identik dengan api.binance.com.
PRIMARY_BASE = "https://data-api.binance.vision"
FALLBACK_BASES = [
    "https://api.binance.com",
    "https://api-gcp.binance.com",
]

INTERVAL_MAP = {"1h": "1h", "4h": "4h"}
INTERVAL_MS = {"1h": 3_600_000, "4h": 14_400_000}
MAX_LIMIT = 1000

# Kolom 8 dan 9 pada respons kline Binance memuat jumlah transaksi dan volume
# beli sisi taker. Keduanya cukup untuk menghitung Order Flow Imbalance tanpa
# mengunduh arsip aggTrades, yang untuk rentang 2019-2026 berukuran ~30 GB.
OHLCV_COLUMNS = [
    "time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "taker_buy_volume",
    "n_trades",
]


class IngestionError(RuntimeError):
    """Kegagalan pengambilan data yang perlu dijelaskan ke pengguna."""


class TLSInterceptionError(IngestionError):
    """Koneksi dicegat perangkat jaringan, bukan gagal biasa.

    Dipisahkan dari error lain karena solusinya berbeda: bukan mengulang
    request, melainkan mengganti jaringan atau memakai VPN.
    """


@dataclass
class FetchReport:
    """Ringkasan satu operasi ingestion, disimpan bersama data."""

    symbol: str
    timeframe: str
    source: str
    base_url: str
    rows: int
    requests_made: int
    first_time: Optional[int] = None
    last_time: Optional[int] = None
    dropped_open_bar: bool = False
    fetched_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "source": self.source,
            "base_url": self.base_url,
            "rows": self.rows,
            "requests_made": self.requests_made,
            "first_time": self.first_time,
            "last_time": self.last_time,
            "dropped_open_bar": self.dropped_open_bar,
            "fetched_at": self.fetched_at,
        }


def _classify_ssl_error(exc: Exception, base_url: str) -> IngestionError:
    """Ubah SSLError mentah menjadi pesan yang bisa ditindaklanjuti."""
    detail = str(exc)
    intercepted = any(
        marker in detail
        for marker in (
            "CERTIFICATE_VERIFY_FAILED",
            "certificate has expired",
            "hostname",
            "CertificateError",
            "SSLCertVerificationError",
        )
    )
    if intercepted:
        return TLSInterceptionError(
            f"Koneksi ke {base_url} dicegat perangkat jaringan. Sertifikat yang "
            "diterima bukan milik server tujuan — ini pola pemblokiran ISP "
            "terhadap domain exchange kripto. Verifikasi TLS sengaja TIDAK "
            "dimatikan karena respons yang datang adalah halaman blokir, bukan "
            "data harga. Solusi: ganti jaringan, aktifkan VPN, atau pakai "
            "importer CSV dari data.binance.vision."
        )
    return IngestionError(f"Gagal menghubungi {base_url}: {detail[:200]}")


def _request_klines(
    base_url: str,
    symbol: str,
    timeframe: str,
    start_time: Optional[int] = None,
    limit: int = MAX_LIMIT,
    timeout: int = 25,
) -> List[list]:
    params: Dict[str, str | int] = {
        "symbol": symbol,
        "interval": INTERVAL_MAP[timeframe],
        "limit": min(limit, MAX_LIMIT),
    }
    if start_time is not None:
        params["startTime"] = start_time

    try:
        resp = requests.get(f"{base_url}/api/v3/klines", params=params, timeout=timeout)
    except requests.exceptions.SSLError as exc:
        raise _classify_ssl_error(exc, base_url) from exc
    except requests.exceptions.RequestException as exc:
        raise IngestionError(f"Gagal menghubungi {base_url}: {exc}") from exc

    if resp.status_code == 429:
        raise IngestionError(
            f"{base_url} membatasi laju permintaan (HTTP 429). Tunggu beberapa "
            "menit sebelum menarik ulang."
        )
    if resp.status_code != 200:
        raise IngestionError(f"{base_url} membalas HTTP {resp.status_code}: {resp.text[:160]}")

    try:
        payload = resp.json()
    except ValueError as exc:
        # Respons non-JSON hampir selalu berarti halaman blokir ISP.
        raise IngestionError(
            f"{base_url} membalas dengan konten non-JSON — kemungkinan halaman "
            "blokir jaringan, bukan data harga."
        ) from exc

    if not isinstance(payload, list):
        raise IngestionError(f"Bentuk respons {base_url} tidak dikenal: {str(payload)[:160]}")
    return payload


def _rows_to_frame(rows: List[list], drop_open_bar: bool, now_ms: int) -> tuple[pd.DataFrame, bool]:
    """Ubah payload kline menjadi DataFrame; buang bar yang belum tutup."""
    records = []
    dropped = False
    for r in rows:
        close_time = int(r[6])
        if drop_open_bar and close_time >= now_ms:
            # Candle berjalan: close belum final, ikut menghitungnya membuat
            # Hurst dan label regime window terakhir berubah tiap refresh.
            dropped = True
            continue
        records.append(
            {
                "time": int(r[0]) // 1000,
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]),
                # Volume yang dieksekusi taker di sisi beli. Sisanya (volume -
                # taker_buy) adalah volume jual sisi taker, sehingga
                # OFI = (buy - sell) / volume dapat dihitung langsung.
                "taker_buy_volume": float(r[9]) if len(r) > 9 else 0.0,
                "n_trades": int(r[8]) if len(r) > 8 else 0,
            }
        )
    return pd.DataFrame(records, columns=OHLCV_COLUMNS), dropped


def parse_start(start: Optional[str]) -> Optional[int]:
    """Ubah tanggal mulai (YYYY-MM-DD) menjadi epoch milidetik UTC."""
    if not start:
        return None
    try:
        return int(
            datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
        )
    except ValueError as exc:
        raise IngestionError(
            f"data.start '{start}' tidak valid — pakai format YYYY-MM-DD."
        ) from exc


def fetch_klines(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    years: float = 3.0,
    base_urls: Optional[List[str]] = None,
    drop_open_bar: bool = True,
    max_requests: int = 400,
    pause: float = 0.2,
    start: Optional[str] = None,
) -> tuple[pd.DataFrame, FetchReport]:
    """Tarik riwayat OHLCV dengan paging maju.

    Titik awal diambil dari `start` (YYYY-MM-DD) bila ada; jika tidak, mundur
    sejauh `years` tahun dari sekarang. Binance membatasi 1000 baris per
    permintaan, jadi rentang panjang diambil bertahap: mulai dari titik terjauh,
    lalu maju memakai `openTime` terakhir sebagai penanda halaman berikutnya.
    """
    if timeframe not in INTERVAL_MAP:
        raise IngestionError(f"timeframe '{timeframe}' tidak didukung.")

    candidates = base_urls or [PRIMARY_BASE, *FALLBACK_BASES]
    now_ms = int(time.time() * 1000)
    explicit_start = parse_start(start)
    start_ms = explicit_start if explicit_start is not None else now_ms - int(
        years * 365 * 24 * 3_600_000
    )
    step_ms = INTERVAL_MS[timeframe]

    last_error: Optional[Exception] = None
    for base_url in candidates:
        try:
            collected: List[list] = []
            cursor = start_ms
            requests_made = 0

            while requests_made < max_requests:
                batch = _request_klines(base_url, symbol, timeframe, cursor, MAX_LIMIT)
                requests_made += 1
                if not batch:
                    break

                collected.extend(batch)
                last_open = int(batch[-1][0])
                if len(batch) < MAX_LIMIT or last_open + step_ms > now_ms:
                    break
                cursor = last_open + step_ms
                time.sleep(pause)

            if not collected:
                raise IngestionError(f"{base_url} tidak mengembalikan data untuk {symbol}.")

            df, dropped = _rows_to_frame(collected, drop_open_bar, now_ms)
            df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
            if df.empty:
                raise IngestionError("Semua baris terbuang setelah pembersihan.")

            report = FetchReport(
                symbol=symbol,
                timeframe=timeframe,
                source="binance",
                base_url=base_url,
                rows=len(df),
                requests_made=requests_made,
                first_time=int(df["time"].iloc[0]),
                last_time=int(df["time"].iloc[-1]),
                dropped_open_bar=dropped,
            )
            return df, report

        except IngestionError as exc:
            last_error = exc
            continue

    raise last_error or IngestionError("Tidak ada sumber data yang dapat dihubungi.")


def fetch_latest(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    limit: int = MAX_LIMIT,
    base_urls: Optional[List[str]] = None,
    drop_open_bar: bool = True,
) -> tuple[pd.DataFrame, FetchReport]:
    """Ambil sejumlah bar terakhir saja — dipakai scheduler untuk refresh berkala."""
    candidates = base_urls or [PRIMARY_BASE, *FALLBACK_BASES]
    now_ms = int(time.time() * 1000)

    last_error: Optional[Exception] = None
    for base_url in candidates:
        try:
            rows = _request_klines(base_url, symbol, timeframe, None, limit)
            df, dropped = _rows_to_frame(rows, drop_open_bar, now_ms)
            df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
            if df.empty:
                raise IngestionError("Tidak ada bar tertutup pada respons terbaru.")
            report = FetchReport(
                symbol=symbol,
                timeframe=timeframe,
                source="binance",
                base_url=base_url,
                rows=len(df),
                requests_made=1,
                first_time=int(df["time"].iloc[0]),
                last_time=int(df["time"].iloc[-1]),
                dropped_open_bar=dropped,
            )
            return df, report
        except IngestionError as exc:
            last_error = exc
            continue

    raise last_error or IngestionError("Tidak ada sumber data yang dapat dihubungi.")


def ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Lengkapi kolom yang belum ada dengan nol.

    Kolom order flow ditambahkan setelah sebagian data terlanjur tersimpan.
    Tanpa penyeragaman ini, penggabungan menghasilkan DataFrame dengan kolom
    bercampur dan pembacaan berikutnya gagal dengan KeyError.
    """
    out = df.copy()
    for col in OHLCV_COLUMNS:
        if col not in out.columns:
            out[col] = 0.0
    return out[OHLCV_COLUMNS]


def merge_ohlcv(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    """Gabungkan data baru ke data lama; baris baru menang bila waktunya sama."""
    incoming = ensure_schema(incoming)
    if existing is None or existing.empty:
        return incoming.reset_index(drop=True)
    combined = pd.concat([ensure_schema(existing), incoming], ignore_index=True)
    combined = combined.drop_duplicates(subset="time", keep="last")
    return combined.sort_values("time").reset_index(drop=True)


def check_connectivity(base_urls: Optional[List[str]] = None) -> Dict[str, object]:
    """Uji cepat ketersediaan sumber, untuk ditampilkan di UI."""
    candidates = base_urls or [PRIMARY_BASE, *FALLBACK_BASES]
    results = []
    for base_url in candidates:
        try:
            _request_klines(base_url, "BTCUSDT", "1h", None, 1, timeout=8)
            results.append({"base_url": base_url, "reachable": True, "error": None})
        except TLSInterceptionError as exc:
            results.append(
                {"base_url": base_url, "reachable": False, "error": str(exc), "intercepted": True}
            )
        except IngestionError as exc:
            results.append({"base_url": base_url, "reachable": False, "error": str(exc)})
    return {
        "any_reachable": any(r["reachable"] for r in results),
        "sources": results,
    }

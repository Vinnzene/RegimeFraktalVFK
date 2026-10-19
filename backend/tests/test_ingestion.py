"""Test ingestion data pasar — tanpa menyentuh jaringan.

Semua respons Binance dipalsukan supaya test deterministik dan tetap jalan di
jaringan yang memblokir exchange (kondisi normal di Indonesia).
"""

from __future__ import annotations

import time
from typing import List, cast

import pandas as pd
import pytest
import requests

from app.services import data_ingestion
from app.services.data_ingestion import (
    IngestionError,
    TLSInterceptionError,
    _classify_ssl_error,
    _rows_to_frame,
    merge_ohlcv,
)

HOUR_MS = 3_600_000


def make_kline(open_ms: int, close: float = 30000.0) -> list:
    """Bentuk satu baris kline sesuai format Binance."""
    return [
        open_ms,
        f"{close - 10:.8f}",
        f"{close + 20:.8f}",
        f"{close - 30:.8f}",
        f"{close:.8f}",
        "12.5",
        open_ms + HOUR_MS - 1,  # closeTime
        "0",
        100,
        "0",
        "0",
        "0",
    ]


# --- Bar yang belum tutup ----------------------------------------------------------


def test_bar_belum_tutup_dibuang() -> None:
    now_ms = int(time.time() * 1000)
    rows = [
        make_kline(now_ms - 3 * HOUR_MS),
        make_kline(now_ms - 2 * HOUR_MS),
        make_kline(now_ms),  # candle berjalan: closeTime > sekarang
    ]
    df, dropped = _rows_to_frame(rows, drop_open_bar=True, now_ms=now_ms)
    assert dropped is True
    assert len(df) == 2, "hanya bar tertutup yang boleh masuk"


def test_bar_belum_tutup_ikut_bila_flag_dimatikan() -> None:
    now_ms = int(time.time() * 1000)
    rows = [make_kline(now_ms - HOUR_MS), make_kline(now_ms)]
    df, dropped = _rows_to_frame(rows, drop_open_bar=False, now_ms=now_ms)
    assert dropped is False
    assert len(df) == 2


def test_kolom_ohlcv_lengkap_dan_bertipe_angka() -> None:
    now_ms = int(time.time() * 1000)
    df, _ = _rows_to_frame([make_kline(now_ms - 5 * HOUR_MS)], True, now_ms)
    assert list(df.columns) == [
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "taker_buy_volume",
        "n_trades",
    ]
    assert df["close"].dtype.kind == "f"
    assert df["time"].dtype.kind in "iu"


def test_kolom_order_flow_terbaca_dari_kline() -> None:
    """Kline Binance memuat takerBuyBaseAssetVolume pada indeks 9.

    Ini yang membuat OFI dapat dihitung tanpa mengunduh arsip aggTrades,
    yang untuk rentang 2019-2026 berukuran puluhan gigabyte.
    """
    now_ms = int(time.time() * 1000)
    row = make_kline(now_ms - 5 * HOUR_MS)
    row[8] = 1234  # numberOfTrades
    row[9] = "7.5"  # takerBuyBaseAssetVolume
    df, _ = _rows_to_frame([row], True, now_ms)
    assert df["n_trades"].iloc[0] == 1234
    assert df["taker_buy_volume"].iloc[0] == pytest.approx(7.5)


def test_skema_lama_dinaikkan_tanpa_migrasi() -> None:
    """Berkas lama tanpa kolom order flow harus tetap terbaca."""
    from app.services.data_ingestion import ensure_schema

    lama = pd.DataFrame(
        {
            "time": [1, 2],
            "open": [1.0, 2.0],
            "high": [1.0, 2.0],
            "low": [1.0, 2.0],
            "close": [1.0, 2.0],
            "volume": [1.0, 2.0],
        }
    )
    out = ensure_schema(lama)
    assert "taker_buy_volume" in out.columns
    assert (out["taker_buy_volume"] == 0).all()


# --- Deteksi intersepsi TLS ---------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "certificate verify failed: certificate has expired",
        "hostname 'api.binance.com' doesn't match '*.ioh.co.id'",
        "SSLCertVerificationError(1, 'CERTIFICATE_VERIFY_FAILED')",
    ],
)
def test_error_ssl_dikenali_sebagai_intersepsi(message: str) -> None:
    err = _classify_ssl_error(Exception(message), "https://api.binance.com")
    assert isinstance(err, TLSInterceptionError)
    assert "dicegat" in str(err)


def test_pesan_intersepsi_menjelaskan_kenapa_verifikasi_tidak_dimatikan() -> None:
    err = _classify_ssl_error(Exception("certificate has expired"), "https://api.binance.com")
    teks = str(err)
    assert "halaman blokir" in teks
    assert "VPN" in teks or "ganti jaringan" in teks


# --- Paging dan penggabungan --------------------------------------------------------


def test_paging_menggabungkan_beberapa_halaman(monkeypatch: pytest.MonkeyPatch) -> None:
    base_ms = int(time.time() * 1000) - 3000 * HOUR_MS
    calls: List[int] = []

    def fake_request(base_url, symbol, timeframe, start_time=None, limit=1000, timeout=25):
        calls.append(start_time or 0)
        if len(calls) == 1:
            return [make_kline(base_ms + i * HOUR_MS) for i in range(1000)]
        if len(calls) == 2:
            return [make_kline(base_ms + (1000 + i) * HOUR_MS) for i in range(1000)]
        return [make_kline(base_ms + (2000 + i) * HOUR_MS) for i in range(10)]

    monkeypatch.setattr(data_ingestion, "_request_klines", fake_request)
    df, report = data_ingestion.fetch_klines("BTCUSDT", "1h", years=1.0)

    assert report.requests_made == 3
    assert len(df) == 2010
    assert df["time"].is_monotonic_increasing


def test_duplikat_waktu_dibuang(monkeypatch: pytest.MonkeyPatch) -> None:
    base_ms = int(time.time() * 1000) - 100 * HOUR_MS
    rows = [make_kline(base_ms), make_kline(base_ms), make_kline(base_ms + HOUR_MS)]
    monkeypatch.setattr(
        data_ingestion, "_request_klines", lambda *a, **k: rows
    )
    df, _ = data_ingestion.fetch_klines("BTCUSDT", "1h", years=0.5)
    assert len(df) == 2


def test_merge_mempertahankan_urutan_dan_menimpa_duplikat() -> None:
    lama = pd.DataFrame(
        {"time": [1, 2, 3], "open": [1.0] * 3, "high": [1.0] * 3, "low": [1.0] * 3,
         "close": [10.0, 20.0, 30.0], "volume": [1.0] * 3}
    )
    baru = pd.DataFrame(
        {"time": [3, 4], "open": [1.0] * 2, "high": [1.0] * 2, "low": [1.0] * 2,
         "close": [99.0, 40.0], "volume": [1.0] * 2}
    )
    out = merge_ohlcv(lama, baru)
    assert len(out) == 4
    assert out.loc[out["time"] == 3, "close"].iloc[0] == 99.0, "baris baru harus menang"
    assert out["time"].is_monotonic_increasing


# --- Fallback antar sumber ----------------------------------------------------------


def test_pindah_ke_sumber_cadangan_saat_sumber_utama_gagal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_ms = int(time.time() * 1000) - 50 * HOUR_MS

    def fake_request(base_url, symbol, timeframe, start_time=None, limit=1000, timeout=25):
        if "vision" in base_url:
            raise TLSInterceptionError("dicegat")
        return [make_kline(base_ms + i * HOUR_MS) for i in range(5)]

    monkeypatch.setattr(data_ingestion, "_request_klines", fake_request)
    df, report = data_ingestion.fetch_klines(
        "BTCUSDT",
        "1h",
        years=0.5,
        base_urls=["https://data-api.binance.vision", "https://api.binance.com"],
    )
    assert report.base_url == "https://api.binance.com"
    assert len(df) == 5


def test_semua_sumber_gagal_melempar_error_terakhir(monkeypatch: pytest.MonkeyPatch) -> None:
    def always_fail(*args, **kwargs):
        raise TLSInterceptionError("semua dicegat")

    monkeypatch.setattr(data_ingestion, "_request_klines", always_fail)
    with pytest.raises(IngestionError):
        data_ingestion.fetch_klines("BTCUSDT", "1h", years=0.5)


def test_respons_non_json_dianggap_halaman_blokir(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 200
        text = "<html>Situs diblokir</html>"

        def json(self):
            raise ValueError("bukan JSON")

    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse())
    with pytest.raises(IngestionError, match="non-JSON"):
        data_ingestion._request_klines("https://x", "BTCUSDT", "1h")


def test_timeframe_tidak_didukung_ditolak() -> None:
    with pytest.raises(IngestionError):
        data_ingestion.fetch_klines("BTCUSDT", "13m")


# --- Integrasi repository -----------------------------------------------------------


def test_refresh_mock_menghasilkan_metadata() -> None:
    from app.db.repository import get_repository

    repo = get_repository()
    meta = repo.refresh_ohlcv("BTCUSDT", "1h", full=True)
    assert meta["source"] == "mock"
    assert cast(int, meta["rows"]) > 0


def test_data_status_melaporkan_kesegaran() -> None:
    from app.db.repository import get_repository

    repo = get_repository()
    repo.get_ohlcv("BTCUSDT", "1h")
    status = repo.data_status("BTCUSDT", "1h")
    assert status["available"] is True
    assert "stale" in status
    assert status["timeframe"] == "1h"


def test_endpoint_status_menyertakan_scheduler() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    body = TestClient(app).get("/api/v1/data/status").json()
    assert "scheduler" in body
    assert "timeframes" in body
    assert body["drop_open_bar"] is True

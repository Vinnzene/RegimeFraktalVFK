"""Endpoint candle Analisa Teknikal: validasi, rangkuman 4 jam Yahoo, dan cache."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import market_data
from app.services.asset_analysis import AnalysisError

client = TestClient(app)


def test_validasi_menolak_timeframe_dan_simbol_salah() -> None:
    with pytest.raises(AnalysisError):
        market_data.validate("binance", "BTCUSDT", "2h", 500)
    with pytest.raises(AnalysisError):
        market_data.validate("binance", "BT", "1h", 500)
    assert market_data.validate("binance", "btc/usdt", "1w", 99999) == ("binance", "BTCUSDT", "1w", 3000)


def test_endpoint_memakai_cache(monkeypatch) -> None:
    market_data._cache.clear()
    calls = []

    def fake(symbol, tf, bars):
        calls.append(symbol)
        return pd.DataFrame({"time": [0, 3600], "open": [1.0, 2.0], "high": [2.0, 3.0], "low": [0.5, 1.5], "close": [1.5, 2.5], "volume": [1.0, 2.0]})

    monkeypatch.setattr(market_data, "_fetch_binance", fake)
    for _ in range(2):
        r = client.get("/api/v1/market/candles", params={"source": "binance", "symbol": "ETHUSDT", "tf": "4h", "bars": 200})
        assert r.status_code == 200
        assert r.json()["count"] == 2
    assert calls == ["ETHUSDT"]  # panggilan kedua dari cache


def test_endpoint_400_untuk_masukan_salah() -> None:
    r = client.get("/api/v1/market/candles", params={"source": "binance", "symbol": "BTCUSDT", "tf": "2h"})
    assert r.status_code == 400


def test_yahoo_4h_dirangkum_dari_1h(monkeypatch) -> None:
    class Resp:
        status_code = 200

        def json(self):
            ts = [0, 3600, 7200, 10800, 14400]
            return {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [{
                "open": [1, 2, 3, 4, 5], "high": [2, 3, 9, 5, 6], "low": [0.5, 1, 2, 3, 4],
                "close": [2, 3, 4, 5, 6], "volume": [1, 1, 1, 1, 1]}]}}]}}

    monkeypatch.setattr(market_data.requests, "get", lambda *a, **k: Resp())
    df = market_data._fetch_yahoo("^JKSE", "4h", 100)
    assert df["time"].tolist() == [0, 14400]
    first = df.iloc[0]
    assert (first.open, first.high, first.low, first.close, first.volume) == (1, 9, 0.5, 5, 4)

"""Analisis aset: validasi masukan, token internal, dan alur antrean tanpa jaringan."""

import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.services.asset_analysis as aa
from app.main import app

client = TestClient(app)


@pytest.mark.parametrize(
    "args, pesan",
    [
        (("kraken", "BTCUSDT", "1h", 2000), "Sumber data"),
        (("binance", "BTC-USDT!", "1h", 2000), "tidak valid"),
        (("yahoo", "BBCA.JK", "4h", 2000), "tidak tersedia"),
        (("binance", "ETHUSDT", "1h", 200), "Jumlah bar"),
    ],
)
def test_validasi_menolak_masukan_salah(args, pesan):
    with pytest.raises(aa.AnalysisError, match=pesan):
        aa.validate(*args)


def test_simbol_binance_dinormalisasi():
    assert aa.validate("binance", "eth/usdt", "4h", 1500) == ("binance", "ETHUSDT", "4h", 1500)


def test_token_internal_wajib_bila_diisi(monkeypatch):
    monkeypatch.setenv("ANALYSIS_INTERNAL_TOKEN", "rahasia-uji")
    r = client.post("/internal/analyses", json={"source": "binance", "symbol": "ETHUSDT", "timeframe": "1h"})
    assert r.status_code == 403
    r = client.get("/internal/analyses/0123456789abcdef", headers={"X-Internal-Token": "rahasia-uji"})
    assert r.status_code == 404


def test_id_tidak_sah_tidak_membaca_berkas():
    assert aa.status("../../etc/passwd") is None


def test_alur_antrean_tanpa_jaringan(monkeypatch, tmp_path):
    """Data palsu menggantikan fetch; detektor dan analisis berjalan sungguhan."""
    rng = np.random.default_rng(0)
    n = 900
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    df = pd.DataFrame({"time": np.arange(n) * 3600 + 1_700_000_000, "open": close, "high": close,
                       "low": close, "close": close, "volume": np.ones(n)})
    monkeypatch.setattr(aa, "fetch", lambda *a: df)
    monkeypatch.setattr(aa, "RESULT_DIR", tmp_path)
    try:
        aa.ai_detector.meta()
    except aa.ai_detector.DetectorUnavailable:
        pytest.skip("artefak detektor tidak tersedia di lingkungan ini")

    job = aa.submit("binance", "ETHUSDT", "1h", 1000)
    for _ in range(300):
        res = aa.status(job["id"])
        if res["status"] in ("done", "failed"):
            break
        time.sleep(0.5)
    assert res["status"] == "done", res.get("error")
    assert res["experimental"] is True
    assert res["series"][-1]["time"] == int(df["time"].iloc[-1])
    assert abs(sum(res["current_probabilities"].values()) - 1) < 0.01
    assert (tmp_path / f"{job['id']}.json").exists()

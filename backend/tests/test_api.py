"""Uji kontrak endpoint dan aturan domain yang tidak boleh dilanggar."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_menyertakan_config_hash() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert len(r.json()["config_hash"]) == 64


def test_config_endpoint_mengembalikan_5_kategori() -> None:
    r = client.get("/api/v1/meta/config")
    body = r.json()
    assert body["config"]["analysis"]["input"] == "log_return"
    assert "uncertain_rule" in body["regime_categories"]
    assert "uncertain_lowconf" in body["regime_categories"]


def test_ohlcv_mock_berada_di_rentang_btc_wajar() -> None:
    r = client.get("/api/v1/ohlcv", params={"tf": "1h", "limit": 500})
    candles = r.json()["candles"]
    closes = [c["close"] for c in candles]
    assert 20000 < min(closes) and max(closes) < 75000


def test_regime_memunculkan_uncertain_rule() -> None:
    """uncertain_rule harus benar-benar muncul, bukan nol."""
    r = client.get("/api/v1/analysis/regime", params={"tf": "1h"})
    dist = r.json()["distribution"]
    assert dist["uncertain_rule"]["count"] > 0


def test_swt_endpoint_menandai_causal() -> None:
    r = client.get("/api/v1/analysis/swt", params={"tf": "1h"})
    assert r.json()["parameters"]["causal"] is True


def test_transition_matrix_baris_berjumlah_satu() -> None:
    r = client.get("/api/v1/analysis/transition-matrix", params={"tf": "1h"})
    for row in r.json()["matrix"]:
        s = sum(row)
        assert s == 0 or abs(s - 1.0) < 0.01


def test_ohlcv_columnar_tidak_membuang_candle() -> None:
    """Format kolom hanya memadatkan representasi, bukan jumlah data."""
    rec = client.get("/api/v1/ohlcv", params={"tf": "1h"}).json()
    col = client.get("/api/v1/ohlcv", params={"tf": "1h", "format": "columnar"}).json()

    assert col["format"] == "columnar"
    assert col["count"] == rec["count"] == col["total_count"]
    for key in ("time", "open", "high", "low", "close", "volume"):
        assert len(col["columns"][key]) == rec["count"]

    first, last = rec["candles"][0], rec["candles"][-1]
    assert col["columns"]["time"][0] == first["time"]
    assert col["columns"]["time"][-1] == last["time"]
    assert abs(col["columns"]["close"][-1] - last["close"]) < 0.01


def test_multifractal_melaporkan_tiga_orde_q() -> None:
    r = client.get("/api/v1/analysis/multifractal", params={"tf": "1h"})
    assert r.status_code == 200
    body = r.json()
    assert body["parameters"]["q"] == [1.0, 2.0, 4.0]
    assert body["parameters"]["causal"] is True
    assert body["parameters"]["estimator"] == "structure_function"

    row = next(r for r in body["series"] if r.get("hq_2") is not None)
    for key in ("hq_1", "hq_2", "hq_4", "hq_width"):
        assert key in row


def test_multifractal_lebar_spektrum_konsisten_dengan_hq() -> None:
    """hq_width wajib sama dengan H(1) - H(4) pada baris yang sama.

    Tanpa pemeriksaan ini, lebar spektrum bisa saja dihitung dari baris lain
    akibat salah sejajar saat penjarangan — kesalahan yang tidak memunculkan
    error apa pun tetapi membuat panel multifraktalitas menipu.
    """
    r = client.get("/api/v1/analysis/multifractal", params={"tf": "1h"})
    rows = [
        x
        for x in r.json()["series"]
        if x.get("hq_1") is not None and x.get("hq_4") is not None
    ]
    assert rows, "tidak ada baris H(q) yang berhasil dihitung"
    for x in rows[:50]:
        assert abs(x["hq_width"] - (x["hq_1"] - x["hq_4"])) < 1e-9


def test_hurst_dfa_random_band_nearest_window():
    """Pita acak memilih jendela terdekat dan lebih lebar dari median."""
    from app.routers.analysis import random_band

    band = random_band(500)
    assert band is not None and band["window"] == 500 and band["scenario"] == "S4"
    for est in ("hurst_rs", "dfa_alpha"):
        assert band[est]["lower"] < band[est]["median"] < band[est]["upper"]
    assert random_band(480)["window"] == 500
    assert random_band(None) is None

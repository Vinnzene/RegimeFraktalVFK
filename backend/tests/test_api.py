"""Uji kontrak endpoint dan aturan domain yang tidak boleh dilanggar."""

import pytest
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


def test_predict_mengembalikan_probabilitas_dan_final_label() -> None:
    r = client.post("/api/v1/model/predict", json={"tf": "1h"})
    body = r.json()
    assert set(body["raw_probabilities"]) == {
        "persistent",
        "random_like",
        "anti_persistent",
    }
    assert abs(sum(body["raw_probabilities"].values()) - 1.0) < 0.01
    assert body["final_label"] in {
        "persistent",
        "random_like",
        "anti_persistent",
        "uncertain_lowconf",
    }


def test_tau_tinggi_memaksa_uncertain_lowconf() -> None:
    r = client.post("/api/v1/model/predict", json={"tf": "1h", "tau": 1.0})
    assert r.json()["final_label"] == "uncertain_lowconf"


def test_compare_wajib_punya_baseline_persistence() -> None:
    r = client.get("/api/v1/model/compare", params={"tf": "1h"})
    models = r.json()["models"]
    assert "persistence" in models
    assert set(models) >= {
        "rule_based",
        "swt_bilstm",
        "swt_attention_bilstm",
        "persistence",
    }


def test_backtest_menolak_ground_truth_sebagai_sumber_sinyal() -> None:
    r = client.post(
        "/api/v1/backtest/run",
        json={"tf": "1h", "regime_source": "ground_truth"},
    )
    assert r.status_code == 400
    assert "masa depan" in r.json()["detail"]


def test_backtest_menyertakan_buy_and_hold_dan_disclaimer() -> None:
    r = client.post("/api/v1/backtest/run", json={"tf": "1h"})
    body = r.json()
    assert body["regime_source"] == "model_prediction_at_t"
    assert "buy_hold" in body["equity_curve"][0]
    assert "BUKAN jaminan profit" in body["disclaimer"]
    assert client.get(f"/api/v1/backtest/{body['id']}/result").status_code == 200


def test_split_boundaries_punya_zona_purge() -> None:
    r = client.get("/api/v1/data/split-boundaries", params={"tf": "1h"})
    names = [s["segment"] for s in r.json()["segments"]]
    assert "purge_1" in names and "purge_2" in names


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

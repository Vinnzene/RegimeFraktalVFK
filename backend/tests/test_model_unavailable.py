"""Tanpa izin eksplisit, model neural yang artefaknya hilang tidak diganti angka buatan."""

from fastapi.testclient import TestClient

import app.services.inference as inference
from app.main import app

client = TestClient(app)


def _tanpa_artefak(monkeypatch):
    monkeypatch.setenv("ALLOW_MODEL_PLACEHOLDER", "false")
    monkeypatch.setattr(inference, "predict_sequences", lambda *a, **k: None)
    inference._PROBA_CACHE.clear()
    inference._SOURCE.clear()


def test_predict_menjawab_503_bukan_stand_in(monkeypatch):
    _tanpa_artefak(monkeypatch)
    r = client.post("/api/v1/model/predict", json={"tf": "1h", "model_key": "swt_attention_bilstm"})
    assert r.status_code == 503
    assert r.json()["model_key"] == "swt_attention_bilstm"


def test_compare_menandai_model_tidak_tersedia(monkeypatch):
    _tanpa_artefak(monkeypatch)
    import app.routers.model as model_router

    model_router._COMPARE_CACHE.clear()
    monkeypatch.setattr(model_router.disk_cache, "read", lambda key: None)
    written = []
    monkeypatch.setattr(model_router.disk_cache, "write", lambda key, value: written.append(key))

    body = client.get("/api/v1/model/compare", params={"tf": "1h"}).json()
    assert set(body["unavailable_models"]) == {"swt_bilstm", "swt_attention_bilstm"}
    assert body["models"]["swt_bilstm"]["prediction_source"] == "unavailable"
    assert body["models"]["rule_based"]["prediction_source"] == "rule_based"
    assert written == [], "hasil tidak lengkap tidak boleh disimpan ke cache disk"
    model_router._COMPARE_CACHE.clear()


def test_stand_in_tetap_bisa_diizinkan(monkeypatch):
    monkeypatch.setattr(inference, "predict_sequences", lambda *a, **k: None)
    inference._PROBA_CACHE.clear()
    inference._SOURCE.clear()
    r = client.post("/api/v1/model/predict", json={"tf": "1h", "model_key": "swt_attention_bilstm"})
    assert r.status_code == 200
    assert r.json()["prediction_source"] == "placeholder"
    inference._PROBA_CACHE.clear()

"""Data studi wavelet hanya lewat endpoint internal bertoken."""

import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_wavelet_butuh_token(monkeypatch) -> None:
    monkeypatch.setenv("ANALYSIS_INTERNAL_TOKEN", "rahasia")
    assert client.get("/internal/wavelet").status_code == 403
    assert client.get("/internal/wavelet", headers={"X-Internal-Token": "salah"}).status_code == 403


def test_wavelet_membaca_artefak(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ANALYSIS_INTERNAL_TOKEN", "rahasia")
    import app.core.config as config

    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    hdr = {"X-Internal-Token": "rahasia"}
    assert client.get("/internal/wavelet", headers=hdr).status_code == 404
    (tmp_path / "wavelet_label_study.json").write_text(json.dumps({"synthetic": []}), encoding="utf-8")
    r = client.get("/internal/wavelet", headers=hdr)
    assert r.status_code == 200 and r.json() == {"synthetic": []}


def test_tidak_ada_rute_publik() -> None:
    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/internal/wavelet" in paths
    assert not any(p.startswith("/api/v1") and "wavelet" in p for p in paths)

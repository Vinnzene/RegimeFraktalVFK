"""Data diagnosis fitting hanya lewat endpoint internal bertoken."""

import json

from fastapi.testclient import TestClient

from app.main import app
from app.routers import internal

client = TestClient(app)


def test_fitting_butuh_token(monkeypatch) -> None:
    monkeypatch.setenv("ANALYSIS_INTERNAL_TOKEN", "rahasia")
    assert client.get("/internal/fitting").status_code == 403
    assert client.get("/internal/fitting", headers={"X-Internal-Token": "salah"}).status_code == 403


def test_fitting_membaca_artefak(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ANALYSIS_INTERNAL_TOKEN", "rahasia")
    import app.core.config as config

    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    hdr = {"X-Internal-Token": "rahasia"}
    assert client.get("/internal/fitting", headers=hdr).status_code == 404
    (tmp_path / "fit_diagnostics.json").write_text(json.dumps({"timeframes": {"1h": {}}}), encoding="utf-8")
    r = client.get("/internal/fitting", headers=hdr)
    assert r.status_code == 200 and "timeframes" in r.json()
    assert r.json()["label_validity"] is None
    (tmp_path / "label_validity.json").write_text(json.dumps({"btc": {}}), encoding="utf-8")
    assert client.get("/internal/fitting", headers=hdr).json()["label_validity"] == {"btc": {}}


def test_tidak_ada_rute_publik() -> None:
    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/internal/fitting" in paths
    assert not any(p.startswith("/api/v1") and "fitting" in p for p in paths)
    assert internal.fitting_router.prefix == "/internal/fitting"

"""Halaman Uji Ketahanan Metode terkunci kecuali pemilik membukanya."""

from fastapi.testclient import TestClient

from app.main import app
from app.routers import model as model_router

client = TestClient(app)


def test_uji_ketahanan_terkunci_secara_bawaan(monkeypatch) -> None:
    monkeypatch.setattr(model_router, "_uji_ketahanan_terbuka", lambda: False)
    r = client.get("/api/v1/model/robustness")
    assert r.status_code == 403
    st = client.get("/api/v1/model/robustness/status").json()
    assert st["terbuka"] is False and st["pesan"]


def test_uji_ketahanan_bisa_dibuka_pemilik(monkeypatch) -> None:
    monkeypatch.setattr(model_router, "_uji_ketahanan_terbuka", lambda: True)
    st = client.get("/api/v1/model/robustness/status").json()
    assert st["terbuka"] is True
    r = client.get("/api/v1/model/robustness")
    assert r.status_code in (200, 404)  # 404 hanya bila robustness_tests.json belum dibuat


def test_nilai_kunci_dibaca_dari_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(model_router, "PROJECT_ROOT", tmp_path)  # tanpa backend/.env
    monkeypatch.delenv("UJI_KETAHANAN_TERBUKA", raising=False)
    assert model_router._uji_ketahanan_terbuka() is False
    monkeypatch.setenv("UJI_KETAHANAN_TERBUKA", "1")
    assert model_router._uji_ketahanan_terbuka() is True
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / ".env").write_text("UJI_KETAHANAN_TERBUKA=0\n", encoding="utf-8")
    assert model_router._uji_ketahanan_terbuka() is False


def test_endpoint_internal_untuk_akun_disetujui(monkeypatch) -> None:
    """Rute Next.js membaca data lewat /internal (tidak diteruskan Caddy)."""
    monkeypatch.setattr(model_router, "_uji_ketahanan_terbuka", lambda: False)
    monkeypatch.setenv("ANALYSIS_INTERNAL_TOKEN", "rahasia")
    assert client.get("/internal/robustness").status_code == 403
    assert client.get("/internal/robustness", headers={"X-Internal-Token": "salah"}).status_code == 403
    r = client.get("/internal/robustness", headers={"X-Internal-Token": "rahasia"})
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "timeframes" in r.json()

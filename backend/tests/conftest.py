"""Isolasi test dari konfigurasi produksi dan dari jaringan.

config.yaml sekarang memakai data Binance asli (use_mock: false). Test tidak
boleh ikut menembak jaringan: hasilnya akan bergantung pada koneksi, lambat,
dan angkanya berubah tiap hari. Semua test dijalankan pada data mock di
direktori sementara, terpisah dari data/processed/ milik dashboard.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

import app.db.repository as repository_module
from app.core.config import AppConfig, load_config, set_config_override


@pytest.fixture(autouse=True, scope="session")
def isolated_environment():
    tmp_dir = Path(tempfile.mkdtemp(prefix="regimefraktal-test-"))
    # Test berjalan tanpa jaminan artefak .keras; stand-in diizinkan di sini
    # saja. Perilaku produksi (dilarang) diuji di test_model_unavailable.py.
    os.environ["ALLOW_MODEL_PLACEHOLDER"] = "true"

    base = load_config()
    payload = base.canonical()
    payload["runtime"] = {"use_mock": True, "storage": "parquet"}
    payload["source"] = {**payload.get("source", {}), "auto_refresh": False}
    test_config = AppConfig(**payload)

    set_config_override(test_config)
    repository_module.reset_repository()
    repository_module._repository = repository_module.ParquetRepository(
        base_dir=tmp_dir, config=test_config
    )

    yield test_config

    set_config_override(None)
    repository_module.reset_repository()
    shutil.rmtree(tmp_dir, ignore_errors=True)

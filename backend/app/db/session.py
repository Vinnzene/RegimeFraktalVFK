"""Placeholder koneksi database.

Fase 1 memakai Parquet (lihat app/db/repository.py) sehingga tidak ada koneksi
DB sama sekali dan docker-compose tidak menjalankan service db. Modul ini
disediakan sebagai titik masuk PostgresRepository pada fase M1+ ketika data
exchange asli dan scheduler mulai dipakai.
"""

from __future__ import annotations

from app.core.config import get_config


def get_engine():  # pragma: no cover - belum dipakai di fase 1
    cfg = get_config()
    if cfg.runtime.storage != "postgres":
        raise RuntimeError(
            "runtime.storage bukan 'postgres'. Fase 1 memakai Parquet."
        )
    raise NotImplementedError(
        "Aktifkan pada fase M1+: buat engine SQLAlchemy dan PostgresRepository."
    )

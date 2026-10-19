"""Cache berbasis berkas untuk hasil perhitungan berat.

Masalah yang diatasi: `/model/compare` memerlukan ~17 detik dan
`/model/consistency` ~4,5 detik pada panggilan pertama, karena keduanya
menjalankan inference atas belasan ribu window. Cache di memori menyelesaikan
panggilan kedua dan seterusnya, tetapi hilang setiap kali proses dimulai ulang —
dan saat sidang, restart berarti penguji menunggu.

Kunci cache menyertakan `config_hash`, sehingga hasil otomatis gugur ketika
parameter berubah. Artefak model ikut diperiksa lewat mtime: melatih ulang
model membuat entri lama tidak lagi dipakai meski konfigurasinya sama.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from app.core.config import ARTIFACTS_DIR, PROCESSED_DIR, get_config

CACHE_DIR = PROCESSED_DIR / "cache"


def _artifacts_fingerprint() -> str:
    """Sidik jari seluruh artefak model berdasarkan nama dan waktu ubah.

    Tanpa ini, hasil lama tetap disajikan setelah model dilatih ulang —
    kesalahan yang sulit disadari karena tidak memunculkan error apa pun.
    """
    if not ARTIFACTS_DIR.exists():
        return "no-artifacts"
    parts = []
    for p in sorted(ARTIFACTS_DIR.glob("*.keras")):
        try:
            parts.append(f"{p.name}:{int(p.stat().st_mtime)}")
        except OSError:
            continue
    blob = "|".join(parts) or "empty"
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def cache_key(name: str, **params: object) -> str:
    """Kunci deterministik dari nama, parameter, config_hash, dan artefak."""
    cfg = get_config()
    payload = {
        "name": name,
        "params": {k: str(v) for k, v in sorted(params.items())},
        "config": cfg.config_hash,
        "artifacts": _artifacts_fingerprint(),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode()).hexdigest()[:16]
    return f"{name}_{digest}"


def read(key: str, max_age_seconds: Optional[int] = None) -> Optional[dict]:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    if max_age_seconds is not None:
        try:
            if time.time() - path.stat().st_mtime > max_age_seconds:
                return None
        except OSError:
            return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def write(key: str, value: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.json"
    tmp = path.with_suffix(".tmp")
    try:
        # Tulis ke berkas sementara lalu pindahkan, agar pembaca lain tidak
        # pernah menemukan berkas yang separuh tertulis.
        tmp.write_text(json.dumps(value), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def cached(name: str, compute: Callable[[], dict], **params: object) -> dict:
    """Ambil dari cache bila ada, jika tidak hitung lalu simpan."""
    key = cache_key(name, **params)
    hit = read(key)
    if hit is not None:
        hit["_cache"] = "disk"
        return hit

    value = compute()
    if isinstance(value, dict):
        write(key, value)
        value = {**value, "_cache": "miss"}
    return value


def clear(prefix: Optional[str] = None) -> int:
    """Hapus entri cache; kembalikan jumlah berkas yang dihapus."""
    if not CACHE_DIR.exists():
        return 0
    removed = 0
    for p in CACHE_DIR.glob("*.json"):
        if prefix and not p.name.startswith(prefix):
            continue
        try:
            p.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def stats() -> Dict[str, object]:
    if not CACHE_DIR.exists():
        return {"entries": 0, "size_kb": 0.0}
    files = list(CACHE_DIR.glob("*.json"))
    size = sum(f.stat().st_size for f in files if f.exists())
    return {
        "entries": len(files),
        "size_kb": round(size / 1024, 1),
        "path": str(CACHE_DIR),
    }

"""Penyimpanan langganan notifikasi Telegram.

Struktur Firestore (ditulis dashboard Next.js dan backend ini):

    users/{uid}
        email, name, photo, created_at, last_login
        telegram: {chat_id, username, first_name, linked_at, enabled, timeframes}
    link_tokens/{token}
        uid, email, created_at, expires_at

Alur penautan: dashboard membuat `link_tokens/{token}` sekali pakai lalu membuka
`t.me/<bot>?start=<token>`. Saat pengguna menekan Start, bot menerima token,
mencocokkannya ke uid, dan menyimpan chat_id. Pengguna tidak perlu tahu chat
ID-nya sendiri.

`MemoryStore` dipakai test dan saat Firebase belum dikonfigurasi tidak ada store
sama sekali (`get_store()` -> None), sehingga backend tetap jalan normal.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from app.core.config import PROJECT_ROOT

DEFAULT_TIMEFRAMES = ["1h"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SubscriptionStore(Protocol):
    def consume_link_token(self, token: str, now: datetime) -> Optional[Dict[str, Any]]:
        """Kembalikan {uid, email} bila token sah lalu hapus; None bila tidak ada/kedaluwarsa."""

    def link_chat(self, uid: str, chat_id: int, username: str | None, first_name: str | None, now: datetime) -> None: ...

    def disable_chat(self, chat_id: int) -> bool: ...

    def recipients(self, timeframe: str) -> List[int]: ...


class MemoryStore:
    """Implementasi di memori untuk test."""

    def __init__(self) -> None:
        self.users: Dict[str, Dict[str, Any]] = {}
        self.tokens: Dict[str, Dict[str, Any]] = {}

    def consume_link_token(self, token: str, now: datetime) -> Optional[Dict[str, Any]]:
        doc = self.tokens.pop(token, None)
        if not doc or doc["expires_at"] < now:
            return None
        return {"uid": doc["uid"], "email": doc.get("email")}

    def link_chat(self, uid: str, chat_id: int, username: str | None, first_name: str | None, now: datetime) -> None:
        user = self.users.setdefault(uid, {})
        prev = user.get("telegram") or {}
        user["telegram"] = {
            "chat_id": chat_id,
            "username": username,
            "first_name": first_name,
            "linked_at": now,
            "enabled": True,
            "timeframes": prev.get("timeframes") or list(DEFAULT_TIMEFRAMES),
        }

    def disable_chat(self, chat_id: int) -> bool:
        hit = False
        for user in self.users.values():
            tg = user.get("telegram")
            if tg and tg.get("chat_id") == chat_id and tg.get("enabled"):
                tg["enabled"] = False
                hit = True
        return hit

    def recipients(self, timeframe: str) -> List[int]:
        out = []
        for user in self.users.values():
            tg = user.get("telegram") or {}
            if tg.get("enabled") and timeframe in (tg.get("timeframes") or []) and tg.get("chat_id"):
                out.append(int(tg["chat_id"]))
        return sorted(set(out))


class FirestoreStore:
    def __init__(self, db: Any) -> None:
        self.db = db

    def consume_link_token(self, token: str, now: datetime) -> Optional[Dict[str, Any]]:
        from google.cloud import firestore

        ref = self.db.collection("link_tokens").document(token)

        @firestore.transactional
        def take(tx: Any) -> Optional[Dict[str, Any]]:
            snap = ref.get(transaction=tx)
            if not snap.exists:
                return None
            data = snap.to_dict() or {}
            tx.delete(ref)
            expires = data.get("expires_at")
            if expires is None or expires < now:
                return None
            return {"uid": data.get("uid"), "email": data.get("email")}

        return take(self.db.transaction())

    def link_chat(self, uid: str, chat_id: int, username: str | None, first_name: str | None, now: datetime) -> None:
        ref = self.db.collection("users").document(uid)
        snap = ref.get()
        prev = ((snap.to_dict() or {}).get("telegram") or {}) if snap.exists else {}
        ref.set(
            {
                "telegram": {
                    "chat_id": chat_id,
                    "username": username,
                    "first_name": first_name,
                    "linked_at": now,
                    "enabled": True,
                    "timeframes": prev.get("timeframes") or list(DEFAULT_TIMEFRAMES),
                }
            },
            merge=True,
        )

    def disable_chat(self, chat_id: int) -> bool:
        hit = False
        for snap in self.db.collection("users").where("telegram.chat_id", "==", chat_id).stream():
            snap.reference.update({"telegram.enabled": False})
            hit = True
        return hit

    def recipients(self, timeframe: str) -> List[int]:
        # Hanya filter array-contains di server (tanpa indeks komposit);
        # status aktif disaring di sini.
        out = []
        for snap in self.db.collection("users").where("telegram.timeframes", "array_contains", timeframe).stream():
            tg = (snap.to_dict() or {}).get("telegram") or {}
            if tg.get("enabled") and tg.get("chat_id"):
                out.append(int(tg["chat_id"]))
        return sorted(set(out))


_store: Optional[SubscriptionStore] = None
_store_checked = False


def service_account_path() -> Optional[Path]:
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_store() -> Optional[SubscriptionStore]:
    """Store Firestore bila service account tersedia; None bila belum dikonfigurasi."""
    global _store, _store_checked
    if _store_checked:
        return _store
    _store_checked = True
    path = service_account_path()
    if not path or not path.exists():
        return None
    import firebase_admin
    from firebase_admin import credentials, firestore

    app = firebase_admin.get_app() if firebase_admin._apps else firebase_admin.initialize_app(credentials.Certificate(str(path)))
    _store = FirestoreStore(firestore.client(app))
    return _store

"""Bot Telegram: kirim notifikasi dan tautkan chat ke akun dashboard.

Memakai long polling (`getUpdates`), bukan webhook, supaya bot jalan di laptop
tanpa alamat publik. Satu token bot hanya boleh punya satu pembaca
`getUpdates`; jangan jalankan dua backend dengan token yang sama.

Perintah:
    /start <kode>  tautkan chat ini ke akun (kode dibuat di dashboard)
    /status        kondisi regime terbaru
    /stop          berhenti menerima notifikasi
"""

from __future__ import annotations

import html
import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import requests
from dotenv import load_dotenv

from app.core.config import PROJECT_ROOT
from app.services.telegram_store import SubscriptionStore, get_store, utcnow

load_dotenv(PROJECT_ROOT / "backend" / ".env")
log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


@dataclass(frozen=True)
class BotSettings:
    token: str
    username: str
    dashboard_url: str

    @property
    def configured(self) -> bool:
        return bool(self.token)


def settings() -> BotSettings:
    return BotSettings(
        token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
        username=os.environ.get("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@"),
        dashboard_url=os.environ.get("DASHBOARD_URL", "http://localhost:3000").strip(),
    )


def call(method: str, payload: Dict[str, Any], timeout: float = 15) -> Dict[str, Any]:
    s = settings()
    if not s.configured:
        raise RuntimeError("TELEGRAM_BOT_TOKEN belum diisi")
    r = requests.post(API.format(token=s.token, method=method), json=payload, timeout=timeout)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method}: {data.get('description', r.status_code)}")
    return data


def send_message(chat_id: int, text: str) -> None:
    call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})


HELP = (
    "Bot ini mengirim notifikasi saat regime BTC/USDT berganti.\n\n"
    "Untuk berlangganan, buka dashboard → <b>Notifikasi Telegram</b> → <b>Hubungkan Telegram</b>.\n\n"
    "/status — kondisi regime terbaru\n/stop — berhenti menerima notifikasi"
)


def handle_update(
    update: Dict[str, Any],
    store: Optional[SubscriptionStore],
    reply: Callable[[int, str], None],
    status_text: Callable[[], str],
) -> Optional[str]:
    """Proses satu update Telegram. Mengembalikan nama aksi (untuk test/log)."""
    msg = update.get("message") or {}
    chat = msg.get("chat") or {}
    text = (msg.get("text") or "").strip()
    chat_id = chat.get("id")
    if chat_id is None or not text.startswith("/"):
        return None
    if chat.get("type") != "private":
        reply(chat_id, "Bot hanya melayani chat pribadi.")
        return "not_private"

    command, _, arg = text.partition(" ")
    command = command.split("@")[0].lower()
    arg = arg.strip()

    if command == "/start" and arg:
        if store is None:
            reply(chat_id, "Penautan belum tersedia: server belum terhubung ke Firebase.")
            return "no_store"
        owner = store.consume_link_token(arg, utcnow())
        if not owner:
            reply(chat_id, "Kode tidak berlaku atau sudah kedaluwarsa. Buat kode baru dari dashboard, lalu coba lagi.")
            return "bad_token"
        store.link_chat(owner["uid"], int(chat_id), chat.get("username"), chat.get("first_name"), utcnow())
        who = html.escape(owner.get("email") or "akun Anda")
        reply(
            chat_id,
            f"Terhubung ke <b>{who}</b>.\n\nAnda akan menerima notifikasi saat regime BTC/USDT berganti "
            "(timeframe dapat diatur di dashboard).\n\n/status — kondisi terbaru\n/stop — berhenti",
        )
        return "linked"
    if command == "/start":
        reply(chat_id, HELP)
        return "help"
    if command == "/status":
        reply(chat_id, status_text())
        return "status"
    if command == "/stop":
        stopped = store.disable_chat(int(chat_id)) if store else False
        reply(
            chat_id,
            "Notifikasi dihentikan. Aktifkan lagi dari dashboard kapan saja."
            if stopped
            else "Chat ini belum berlangganan notifikasi.",
        )
        return "stopped" if stopped else "not_subscribed"
    reply(chat_id, HELP)
    return "help"


_thread: Optional[threading.Thread] = None
_stop = threading.Event()


def _poll(status_text: Callable[[], str]) -> None:
    offset = 0
    while not _stop.is_set():
        try:
            data = call("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message"]}, timeout=35)
        except Exception as exc:  # noqa: BLE001 — jaringan putus tidak boleh mematikan bot
            log.warning("getUpdates gagal: %s", exc)
            _stop.wait(10)
            continue
        for update in data.get("result", []):
            offset = max(offset, int(update["update_id"]) + 1)
            try:
                handle_update(update, get_store(), send_message, status_text)
            except Exception as exc:  # noqa: BLE001
                log.exception("update %s gagal: %s", update.get("update_id"), exc)


def start(status_text: Callable[[], str]) -> Dict[str, object]:
    global _thread
    s = settings()
    if not s.configured:
        return {"running": False, "reason": "TELEGRAM_BOT_TOKEN belum diisi"}
    if _thread and _thread.is_alive():
        return {"running": True}
    _stop.clear()
    _thread = threading.Thread(target=_poll, args=(status_text,), daemon=True, name="telegram-bot")
    _thread.start()
    return {"running": True, "firestore": get_store() is not None}


def stop() -> None:
    _stop.set()

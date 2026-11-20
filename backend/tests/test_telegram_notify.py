"""Notifikasi Telegram: konfirmasi regime, siaran, dan penautan chat."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import List, Tuple

import pandas as pd

from app.services import regime_notifier as rn
from app.services.telegram_bot import handle_update
from app.services.telegram_store import MemoryStore, utcnow

P, R, A, U = "persistent", "random_like", "anti_persistent", "uncertain_rule"


def frame(labels: List[str]) -> pd.DataFrame:
    n = len(labels)
    return pd.DataFrame(
        {
            "time": [1_700_000_000 + 4 * 3600 * i for i in range(n)],
            "close": [80_000.0 + i for i in range(n)],
            "hurst": [0.6] * n,
            "dfa_alpha": [0.55] * n,
            "regime": labels,
        }
    )


def test_confirmed_regime_needs_k_identical_main_labels():
    assert rn.confirmed_regime([R, P, P, P], 3) == P
    assert rn.confirmed_regime([P, P, R], 3) is None
    assert rn.confirmed_regime([U, U, U], 3) is None  # uncertain tidak pernah dikonfirmasi
    assert rn.confirmed_regime([P, U, P], 3) is None  # uncertain memutus rentetan
    assert rn.confirmed_regime([P, P], 3) is None


def test_detect_only_on_change():
    assert rn.detect([P, P, P], P, 3) is None
    assert rn.detect([A, A, A], P, 3) == A
    assert rn.detect([A, A, R], P, 3) is None


class Sender:
    def __init__(self, fail: Tuple[int, ...] = ()) -> None:
        self.sent: List[Tuple[int, str]] = []
        self.fail = fail

    def __call__(self, chat_id: int, text: str) -> None:
        if chat_id in self.fail:
            raise RuntimeError("blocked")
        self.sent.append((chat_id, text))


def subscribed_store(*chats: Tuple[str, int, List[str]]) -> MemoryStore:
    store = MemoryStore()
    for uid, chat_id, tfs in chats:
        store.link_chat(uid, chat_id, None, None, utcnow())
        store.users[uid]["telegram"]["timeframes"] = tfs
    return store


def test_first_run_records_state_without_broadcast(tmp_path):
    store = subscribed_store(("u1", 11, ["1h"]))
    send = Sender()
    state, logp = tmp_path / "state.json", tmp_path / "log.jsonl"
    events = rn.check({"1h": frame([R, P, P, P])}, store, send, "http://x", state, logp, k=3)
    assert events == [] and send.sent == []
    assert json.loads(state.read_text())["1h"]["confirmed"] == P
    assert not logp.exists()


def test_change_is_broadcast_logged_and_not_repeated(tmp_path):
    store = subscribed_store(("u1", 11, ["1h"]), ("u2", 22, ["4h"]), ("u3", 33, ["1h", "4h"]))
    store.users["u3"]["telegram"]["enabled"] = False
    send = Sender()
    state, logp = tmp_path / "state.json", tmp_path / "log.jsonl"
    rn.check({"1h": frame([P, P, P])}, store, send, "http://x", state, logp, k=3)

    events = rn.check({"1h": frame([P, P, P, A, A, A])}, store, send, "http://x", state, logp, k=3)
    assert [e["to"] for e in events] == [A]
    assert [c for c, _ in send.sent] == [11]  # hanya pelanggan 1H yang aktif
    assert "Cenderung Berbalik" in send.sent[0][1] and "Mean-reversion" in send.sent[0][1]
    logged = [json.loads(line) for line in logp.read_text().splitlines()]
    assert logged[0]["from"] == P and logged[0]["to"] == A and logged[0]["sent"] == 1

    # Pemeriksaan berikutnya dengan regime yang sama tidak mengirim ulang.
    assert rn.check({"1h": frame([P, P, P, A, A, A, A])}, store, send, "http://x", state, logp, k=3) == []
    assert len(send.sent) == 1


def test_one_failed_recipient_does_not_block_others(tmp_path):
    store = subscribed_store(("u1", 11, ["1h"]), ("u2", 22, ["1h"]))
    send = Sender(fail=(11,))
    state, logp = tmp_path / "state.json", tmp_path / "log.jsonl"
    rn.check({"1h": frame([P, P, P])}, store, send, "http://x", state, logp, k=3)
    (event,) = rn.check({"1h": frame([R, R, R])}, store, send, "http://x", state, logp, k=3)
    assert event["sent"] == 1 and event["failed"] == 1
    assert [c for c, _ in send.sent] == [22]


def update(text: str, chat_id: int = 99, chat_type: str = "private") -> dict:
    return {"update_id": 1, "message": {"text": text, "chat": {"id": chat_id, "type": chat_type, "username": "budi"}}}


def test_start_with_valid_token_links_chat_once():
    store = MemoryStore()
    store.tokens["abc"] = {"uid": "u1", "email": "a@b.c", "expires_at": utcnow() + timedelta(minutes=10)}
    replies: List[Tuple[int, str]] = []
    reply = lambda c, t: replies.append((c, t))  # noqa: E731

    assert handle_update(update("/start abc"), store, reply, lambda: "") == "linked"
    assert store.users["u1"]["telegram"]["chat_id"] == 99
    assert store.recipients("1h") == [99]
    # Kode sekali pakai.
    assert handle_update(update("/start abc"), store, reply, lambda: "") == "bad_token"


def test_expired_token_rejected():
    store = MemoryStore()
    store.tokens["old"] = {"uid": "u1", "email": None, "expires_at": utcnow() - timedelta(seconds=1)}
    assert handle_update(update("/start old"), store, lambda c, t: None, lambda: "") == "bad_token"
    assert "u1" not in store.users


def test_stop_status_and_group_chats():
    store = subscribed_store(("u1", 99, ["1h"]))
    replies: List[str] = []
    reply = lambda c, t: replies.append(t)  # noqa: E731
    assert handle_update(update("/status"), store, reply, lambda: "STATUS") == "status"
    assert replies[-1] == "STATUS"
    assert handle_update(update("/stop"), store, reply, lambda: "") == "stopped"
    assert store.recipients("1h") == []
    assert handle_update(update("/start abc", chat_type="group"), store, reply, lambda: "") == "not_private"
    assert handle_update(update("halo"), store, reply, lambda: "") is None


def test_state_from_old_label_source_is_reset_without_broadcast(tmp_path):
    store = subscribed_store(("u1", 11, ["1h"]))
    send = Sender()
    state, logp = tmp_path / "state.json", tmp_path / "log.jsonl"
    # Keadaan lama dicatat dari label konsensus Hurst–DFA (tanpa kolom source).
    state.write_text(json.dumps({"1h": {"confirmed": P, "since": 0.0}}))
    assert rn.check({"1h": frame([A, A, A])}, store, send, "http://x", state, logp, k=3) == []
    assert send.sent == []
    entry = json.loads(state.read_text())["1h"]
    assert entry["confirmed"] == A and entry["source"] == rn.SOURCE


# ---------------------------------------------------------------- ringkasan harian

from datetime import datetime, timezone  # noqa: E402


def conf_frame(labels: List[str], conf: float) -> pd.DataFrame:
    df = frame(labels)
    df["confidence"] = conf
    return df


def at_wib(day: int, hour: int) -> datetime:
    # 20 Nov 2026 hh:00 WIB = (hh − 7):00 UTC
    return datetime(2026, 11, day, hour, 0, tzinfo=timezone.utc) - timedelta(hours=7)


def test_daily_sent_once_per_day_after_hour(tmp_path):
    store = subscribed_store(("u1", 11, ["1h"]), ("u2", 22, ["4h"]))
    send = Sender()
    regimes = {"1h": conf_frame([A, A, A], 0.9), "4h": conf_frame([P, P, P], 0.6)}
    kw = dict(state_path=tmp_path / "daily.json", log_path=tmp_path / "log.jsonl", hour=7)
    assert rn.daily_once(regimes, store, send, "http://x", 0.75, now=at_wib(20, 6), **kw) is None  # sebelum 07.00
    ev = rn.daily_once(regimes, store, send, "http://x", 0.75, now=at_wib(20, 7), **kw)
    assert ev and ev["sent"] == 2 and ev["date"] == "2026-11-20"
    assert {c for c, _ in send.sent} == {11, 22}  # semua pelanggan aktif, apa pun timeframenya
    assert rn.daily_once(regimes, store, send, "http://x", 0.75, now=at_wib(20, 18), **kw) is None  # hari yang sama
    assert rn.daily_once(regimes, store, send, "http://x", 0.75, now=at_wib(21, 7), **kw)["sent"] == 2  # hari berikutnya
    assert len(send.sent) == 4
    logged = [json.loads(x) for x in (tmp_path / "log.jsonl").read_text().splitlines()]
    assert [x["type"] for x in logged] == ["daily_status", "daily_status"]


def test_daily_respects_opt_out_and_pause(tmp_path):
    store = subscribed_store(("u1", 11, ["1h"]), ("u2", 22, ["1h"]), ("u3", 33, ["1h"]))
    assert store.set_daily(22, False)
    store.disable_chat(33)
    assert store.daily_recipients() == [11]
    # Menautkan ulang tidak mengaktifkan kembali ringkasan yang sudah dimatikan.
    store.link_chat("u2", 22, None, None, utcnow())
    assert store.daily_recipients() == [11]
    send = Sender()
    rn.daily_once({"1h": conf_frame([A, A], 0.9)}, store, send, "http://x", 0.75, now=at_wib(20, 8),
                  state_path=tmp_path / "d.json", log_path=tmp_path / "l.jsonl", hour=7)
    assert [c for c, _ in send.sent] == [11]


def test_daily_disabled_without_hour_or_store(tmp_path):
    send = Sender()
    regimes = {"1h": conf_frame([A], 0.9)}
    kw = dict(state_path=tmp_path / "d.json", log_path=tmp_path / "l.jsonl")
    assert rn.daily_once(regimes, subscribed_store(("u1", 11, ["1h"])), send, "x", 0.75, now=at_wib(20, 9), hour=None, **kw) is None
    assert rn.daily_once(regimes, None, send, "x", 0.75, now=at_wib(20, 9), hour=7, **kw) is None
    assert send.sent == []


def test_daily_message_content():
    regimes = {"1h": conf_frame([P, A, A, A], 0.87), "4h": conf_frame([P, P], 0.6)}
    text = rn.format_daily(regimes, "https://rfraktal.my.id", 0.75, at_wib(20, 7))
    assert "Ringkasan harian BTC/USDT" in text and "20 Nov 2026" in text
    assert "1H: <b>Cenderung Berbalik</b> · keyakinan 87%" in text
    assert "4H: <b>Tren Berlanjut</b> · keyakinan 60% (ragu)" in text
    assert "1H dan 4H berbeda" in text
    assert "/harian off" in text and "Bukan saran investasi" in text


def test_harian_command():
    store = subscribed_store(("u1", 11, ["1h"]))
    send = Sender()
    assert handle_update(update("/harian off", chat_id=11), store, send, lambda: "") == "daily_off"
    assert store.daily_recipients() == []
    assert handle_update(update("/harian on", chat_id=11), store, send, lambda: "") == "daily_on"
    assert store.daily_recipients() == [11]
    assert handle_update(update("/harian", chat_id=11), store, send, lambda: "") == "daily_help"
    assert handle_update(update("/harian off", chat_id=99), store, send, lambda: "") == "not_subscribed"

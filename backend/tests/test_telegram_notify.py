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

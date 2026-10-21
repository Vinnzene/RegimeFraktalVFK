"""Notifikasi pergantian regime ke pelanggan Telegram.

Aturan konfirmasi: regime baru diumumkan hanya bila K window terakhir
(bawaan 3, `NOTIFY_CONFIRM_WINDOWS`) berlabel sama, termasuk salah satu dari tiga
regime utama, dan berbeda dari regime terkonfirmasi sebelumnya. Label regime
sering "berkedip" antar window bertetangga (lihat jump_model.py); tanpa
konfirmasi pelanggan menerima pesan bolak-balik. Window `uncertain_rule` tidak
memicu notifikasi dan memutus rentetan konfirmasi.

Label berasal dari detektor AI resmi (`ai_detector.py`), sama dengan dashboard.
Saat pertama kali berjalan, atau saat sumber label berganti (keadaan lama
dicatat dari label konsensus Hurst–DFA), regime terkini hanya dicatat sebagai
keadaan awal tanpa mengirim pesan, supaya tidak ada siaran palsu.

Setiap notifikasi dicatat ke data/signals/regime_notifications.jsonl. Berkas
ini adalah catatan uji maju (forward test): sinyal tercatat sebelum harga
sesudahnya terjadi, sehingga tidak dapat disesuaikan belakangan.
"""

from __future__ import annotations

import html
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import pandas as pd

from app.core.config import PROJECT_ROOT, get_config
from app.services.telegram_store import SubscriptionStore

log = logging.getLogger(__name__)

SIGNAL_DIR = PROJECT_ROOT / "data" / "signals"
STATE_PATH = SIGNAL_DIR / "notifier_state.json"
LOG_PATH = SIGNAL_DIR / "regime_notifications.jsonl"
MAIN = ("persistent", "random_like", "anti_persistent")

PLAIN = {
    "persistent": "Tren Berlanjut",
    "random_like": "Acak / Tanpa Pola",
    "anti_persistent": "Cenderung Berbalik",
    "uncertain_rule": "Belum Jelas",
}

# Sama dengan peta keputusan di dashboard (frontend/lib/strategy.ts): strategi
# menurut teori + ringkasan bukti Fase 2 di BTC 1H setelah biaya.
STRATEGY = {
    "persistent": (
        "Trend-following (teori)",
        "Belum teruji: di BTC 1H kondisi ini sangat jarang terdeteksi.",
    ),
    "anti_persistent": (
        "Mean-reversion (teori)",
        "Harga lebih sering berbalik, tetapi mean-reversion sederhana tetap rugi setelah biaya di uji Fase 2.",
    ),
    "random_like": (
        "Tidak trading",
        "Didukung uji Fase 2: momentum dan mean-reversion sama-sama rugi besar saat kondisi ini.",
    ),
}
SOURCE = "ai"

_lock = threading.Lock()


def confirm_windows() -> int:
    try:
        return max(1, int(os.environ.get("NOTIFY_CONFIRM_WINDOWS", "3")))
    except ValueError:
        return 3


def confirmed_regime(labels: Sequence[str], k: int) -> Optional[str]:
    """Regime utama yang menempati K label terakhir secara berturut-turut, atau None."""
    if len(labels) < k:
        return None
    tail = list(labels[-k:])
    first = tail[0]
    if first in MAIN and all(lab == first for lab in tail):
        return first
    return None


def detect(labels: Sequence[str], prev: Optional[str], k: int) -> Optional[str]:
    """Regime baru bila terkonfirmasi dan berbeda dari `prev`; selain itu None."""
    now = confirmed_regime(labels, k)
    return now if now is not None and now != prev else None


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %b %Y %H:%M UTC")


def _fmt_num(v: Any, digits: int) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "–"
    return f"{float(v):,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def format_message(event: Dict[str, Any], dashboard_url: str) -> str:
    tf = event["timeframe"].upper()
    to = event["to"]
    strategy, action = STRATEGY[to]
    prev = PLAIN.get(event.get("from") or "", "–")
    lines = [
        f"<b>BTC/USDT {tf} — regime berganti</b>",
        f"{html.escape(prev)} → <b>{html.escape(PLAIN[to])}</b>",
        "",
        f"Harga: {_fmt_num(event.get('price'), 2)} USDT",
        f"Terkonfirmasi {event['confirm_windows']} window berturut-turut (sejak {_fmt_time(event['first_window_time'])})",
        f"Keyakinan detektor AI: {_fmt_num(None if event.get('confidence') is None else event['confidence'] * 100, 0)}%",
        "",
        f"Strategi: <b>{html.escape(strategy)}</b>",
        html.escape(action),
        "",
        f"Bukan saran investasi. Detail: {html.escape(dashboard_url.rstrip('/'))}/strategi",
    ]
    return "\n".join(lines)


def _load_state(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def check(
    regimes: Dict[str, pd.DataFrame],
    store: Optional[SubscriptionStore],
    send: Callable[[int, str], None],
    dashboard_url: str,
    state_path: Path = STATE_PATH,
    log_path: Path = LOG_PATH,
    k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Periksa tiap timeframe, kirim notifikasi bila ada pergantian terkonfirmasi.

    `regimes` memetakan timeframe ke tabel regime detektor AI (kolom time,
    close, regime, confidence). Mengembalikan daftar event yang dikirim.
    """
    k = k or confirm_windows()
    events: List[Dict[str, Any]] = []
    with _lock:
        state = _load_state(state_path)
        for tf, df in regimes.items():
            if df is None or df.empty:
                continue
            labels = df["regime"].astype(str).tolist()
            entry = state.get(tf)
            current = confirmed_regime(labels, k)
            if entry is None or entry.get("source") != SOURCE:
                # Keadaan awal: catat tanpa siaran.
                state[tf] = {
                    "confirmed": current,
                    "since": float(df["time"].iloc[-k]) if current else None,
                    "source": SOURCE,
                }
                continue
            new = detect(labels, entry.get("confirmed"), k)
            if new is None:
                continue
            last = df.iloc[-1]
            event: Dict[str, Any] = {
                "timeframe": tf,
                "from": entry.get("confirmed"),
                "to": new,
                "confirm_windows": k,
                "first_window_time": float(df["time"].iloc[-k]),
                "last_window_time": float(last["time"]),
                "price": float(last["close"]) if "close" in df.columns else None,
                "confidence": float(last["confidence"]) if pd.notna(last.get("confidence")) else None,
                "detected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            chat_ids = store.recipients(tf) if store else []
            text = format_message(event, dashboard_url)
            sent, failed = 0, 0
            for chat_id in chat_ids:
                try:
                    send(chat_id, text)
                    sent += 1
                except Exception as exc:  # noqa: BLE001 — satu penerima gagal tidak menghentikan yang lain
                    failed += 1
                    log.warning("kirim ke %s gagal: %s", chat_id, exc)
            event.update({"recipients": len(chat_ids), "sent": sent, "failed": failed})
            state[tf] = {"confirmed": new, "since": event["first_window_time"], "source": SOURCE}
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event) + "\n")
            events.append(event)
        _save_state(state_path, state)
    return events


def status_text() -> str:
    """Ringkasan regime terbaru semua timeframe, untuk perintah /status."""
    from app.services import ai_detector

    cfg = get_config()
    lines = ["<b>Kondisi regime BTC/USDT terbaru (detektor AI)</b>"]
    for tf in cfg.data.timeframes:
        try:
            df = ai_detector.series(cfg.data.symbol, tf)
        except Exception:  # noqa: BLE001
            lines.append(f"{tf.upper()}: belum tersedia")
            continue
        if df.empty:
            lines.append(f"{tf.upper()}: belum tersedia")
            continue
        last = df.iloc[-1]
        name = PLAIN.get(str(last["regime"]), str(last["regime"]))
        lines.append(
            f"{tf.upper()}: <b>{html.escape(name)}</b> ({_fmt_num(last['confidence'] * 100, 0)}%) · "
            f"harga {_fmt_num(last.get('close'), 2)} · {_fmt_time(float(last['time']))}"
        )
    lines.append("\nBukan saran investasi.")
    return "\n".join(lines)

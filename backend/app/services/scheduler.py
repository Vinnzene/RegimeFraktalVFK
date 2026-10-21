"""Penyegaran data berkala.

Memakai thread daemon sederhana, bukan APScheduler: kebutuhannya hanya satu
tugas periodik, dan menghindari satu dependensi berarti lebih sedikit yang bisa
gagal saat demo sidang.

Kegagalan jaringan sengaja tidak menghentikan scheduler. Saat sidang berlangsung
di jaringan yang memblokir exchange, dashboard harus tetap menyajikan data
terakhir yang tersimpan, bukan mati.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional, cast

from app.core.config import get_config
from app.db.repository import get_repository
from app.services.data_ingestion import IngestionError

_thread: Optional[threading.Thread] = None
_warm_thread: Optional[threading.Thread] = None
_stop = threading.Event()
_history: List[Dict[str, object]] = []
_MAX_HISTORY = 20


def _record(entry: Dict[str, object]) -> None:
    _history.append(entry)
    while len(_history) > _MAX_HISTORY:
        _history.pop(0)


def refresh_once() -> List[Dict[str, object]]:
    """Segarkan seluruh timeframe satu putaran."""
    cfg = get_config()
    repo = get_repository()
    results: List[Dict[str, object]] = []

    for tf in cfg.data.timeframes:
        started = int(time.time())
        try:
            meta = repo.refresh_ohlcv(cfg.data.symbol, tf, full=False)
            results.append(
                {
                    "timeframe": tf,
                    "ok": True,
                    "rows": meta.get("rows"),
                    "rows_added": meta.get("rows_added"),
                    "last_time": meta.get("last_time"),
                    "at": started,
                }
            )
        except IngestionError as exc:
            # Dicatat, tidak dilempar: data lama tetap dilayani.
            results.append({"timeframe": tf, "ok": False, "error": str(exc)[:200], "at": started})
        except Exception as exc:  # noqa: BLE001
            results.append(
                {"timeframe": tf, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:200], "at": started}
            )

    _record({"at": int(time.time()), "results": results})
    return results


def warm_cache() -> List[Dict[str, object]]:
    """Hitung hasil berat lebih awal supaya permintaan pertama tidak menunggu.

    Tanpa ini, permintaan pertama harus menanggung seluruh perhitungan:
    regime ~60 detik, `/model/compare` ~17 detik, `/model/consistency` ~4,5
    detik. Dashboard menunggu respons itu sebelum menggambar apa pun, sehingga
    halaman tampak berat padahal datanya sudah tersedia.

    Dijalankan di thread latar belakang agar startup tidak terblokir.
    """
    cfg = get_config()
    repo = get_repository()
    results: List[Dict[str, object]] = []

    for tf in cfg.data.timeframes:
        started = time.time()
        try:
            df = repo.get_regime(cfg.data.symbol, tf)
            results.append(
                {
                    "timeframe": tf,
                    "ok": True,
                    "windows": len(df),
                    "seconds": round(time.time() - started, 1),
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"timeframe": tf, "ok": False, "error": str(exc)[:200]})

    # Detektor AI resmi: hitung titik deteksi baru (seluruh riwayat bila cache
    # masih kosong) sebelum dashboard memintanya.
    for tf in cfg.data.timeframes:
        started = time.time()
        try:
            from app.services import ai_detector

            ai = ai_detector.update_cache(cfg.data.symbol, tf)
            results.append(
                {"timeframe": tf, "ok": True, "warmed": "ai_detector", "windows": len(ai), "seconds": round(time.time() - started, 1)}
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"timeframe": tf, "ok": False, "warmed": "ai_detector", "error": str(exc)[:200]})

    # Panaskan pula endpoint model. Diimpor di dalam fungsi agar modul
    # scheduler tidak menarik TensorFlow saat startup.
    for tf in cfg.data.timeframes:
        started = time.time()
        try:
            from app.routers.model import compare as compare_endpoint
            from app.services.identification import consistency_report

            compare_endpoint(tf=tf, symbol=cfg.data.symbol)
            for mode in ("multiclass", "binary"):
                consistency_report(cfg.data.symbol, tf, mode)
            results.append(
                {
                    "timeframe": tf,
                    "ok": True,
                    "warmed": "compare+consistency",
                    "seconds": round(time.time() - started, 1),
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {"timeframe": tf, "ok": False, "warmed": "model", "error": str(exc)[:200]}
            )

    _record({"at": int(time.time()), "warm_cache": results})
    # Catat keadaan regime awal untuk notifier (tanpa siaran) setelah regime siap.
    notify_once()
    return results


def notify_once() -> List[Dict[str, object]]:
    """Kirim notifikasi Telegram bila regime berganti sejak pemeriksaan terakhir.

    Tidak melakukan apa pun bila bot belum dikonfigurasi. Kegagalan dicatat,
    tidak dilempar, agar penyegaran data tetap berjalan.
    """
    from app.services import ai_detector, regime_notifier, telegram_bot
    from app.services.telegram_store import get_store

    bot = telegram_bot.settings()
    if not bot.configured:
        return []
    cfg = get_config()
    try:
        # Label dari detektor AI resmi, sama dengan yang tampil di dashboard.
        regimes = {tf: ai_detector.update_cache(cfg.data.symbol, tf) for tf in cfg.data.timeframes}
        events = regime_notifier.check(regimes, get_store(), telegram_bot.send_message, bot.dashboard_url)
    except Exception as exc:  # noqa: BLE001
        _record({"at": int(time.time()), "notify_error": f"{type(exc).__name__}: {exc}"[:200]})
        return []
    if events:
        _record({"at": int(time.time()), "notified": [{k: e[k] for k in ("timeframe", "from", "to", "sent")} for e in events]})
    return cast(List[Dict[str, object]], events)


def _loop(interval_seconds: int) -> None:
    while not _stop.is_set():
        if _stop.wait(interval_seconds):
            break
        refresh_once()
        notify_once()


def start(warm: bool = True) -> Dict[str, object]:
    """Jalankan pemanasan cache dan, bila diaktifkan, penyegaran berkala.

    Pemanasan dijalankan terpisah dari penyegaran: dashboard tetap responsif
    meski `auto_refresh` dimatikan untuk demo yang benar-benar statis.
    """
    global _thread, _warm_thread
    cfg = get_config()

    if warm and not (_warm_thread and _warm_thread.is_alive()):
        _warm_thread = threading.Thread(
            target=warm_cache, daemon=True, name="regime-warm-cache"
        )
        _warm_thread.start()

    if not cfg.source.auto_refresh or cfg.runtime.use_mock:
        return {"running": False, "warming": warm, "reason": "auto_refresh nonaktif atau mode mock"}
    if _thread and _thread.is_alive():
        return {"running": True, "warming": warm, "reason": "sudah berjalan"}

    _stop.clear()
    interval = cfg.source.refresh_minutes * 60
    _thread = threading.Thread(target=_loop, args=(interval,), daemon=True, name="ohlcv-refresh")
    _thread.start()
    return {"running": True, "warming": warm, "interval_seconds": interval}


def stop() -> None:
    _stop.set()


def status() -> Dict[str, object]:
    cfg = get_config()
    running = bool(_thread and _thread.is_alive())
    last = _history[-1] if _history else None
    return {
        "running": running,
        "warming": bool(_warm_thread and _warm_thread.is_alive()),
        "auto_refresh": cfg.source.auto_refresh,
        "refresh_minutes": cfg.source.refresh_minutes,
        "next_run_estimate": (cast(int, last["at"]) + cfg.source.refresh_minutes * 60)
        if last and running
        else None,
        "last_run": last,
        "history": list(reversed(_history[-5:])),
    }

"""regimefraktalVFK — backend FastAPI.

Backend hanya melakukan analisis + inference. Training model dilakukan
terpisah di folder ml/ dan hasilnya dibaca dari ml/artifacts/.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_config
from app.db.repository import InvalidIdentifier
from app.routers import analysis, backtest, internal, meta, model, ohlcv
from app.services import regime_notifier, scheduler, telegram_bot
from app.services.inference import ModelUnavailable


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Nyalakan penyegaran berkala saat startup, hentikan saat shutdown.

    Kegagalan jaringan tidak boleh menggagalkan startup: dashboard tetap
    melayani data terakhir yang tersimpan.
    """
    try:
        scheduler.start()
    except Exception:  # noqa: BLE001
        pass
    try:
        telegram_bot.start(regime_notifier.status_text)
    except Exception:  # noqa: BLE001
        pass
    yield
    scheduler.stop()
    telegram_bot.stop()


app = FastAPI(
    lifespan=lifespan,
    title="regimefraktalVFK API",
    description=(
        "API identifikasi regime fraktal dinamis BTC/USDT "
        "(Hurst-DFA + SWT + Attention-BiLSTM). Alat visualisasi riset, "
        "bukan aplikasi trading."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Respons analisis berupa JSON deret angka yang sangat repetitif, sehingga
# kompresi memangkasnya secara drastis. Ambang 1 KB agar respons kecil tidak
# menanggung ongkos kompresi tanpa manfaat.
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(InvalidIdentifier)
async def invalid_identifier_handler(_: Request, exc: InvalidIdentifier) -> JSONResponse:
    """symbol/timeframe di luar daftar sah adalah kesalahan klien, bukan 500."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ModelUnavailable)
async def model_unavailable_handler(_: Request, exc: ModelUnavailable) -> JSONResponse:
    """Artefak model hilang di produksi: jawab 503, jangan isi angka buatan."""
    return JSONResponse(status_code=503, content={"detail": str(exc), "model_key": exc.model_key})


app.include_router(meta.router)
app.include_router(internal.router)
app.include_router(ohlcv.router)
app.include_router(analysis.router)
app.include_router(model.router)
app.include_router(backtest.router)


@app.get("/health")
def health() -> dict:
    cfg = get_config()
    return {
        "status": "ok",
        "config_hash": cfg.config_hash,
        "short_hash": cfg.short_hash,
        "use_mock": cfg.runtime.use_mock,
        "storage": cfg.runtime.storage,
        "provider": cfg.source.provider,
        "auto_refresh": cfg.source.auto_refresh,
        "scheduler_running": scheduler.status()["running"],
        "telegram_bot": telegram_bot.status(),
    }

"""Endpoint data OHLCV: baca, refresh, status kesegaran, batas split."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import get_config
from app.db.repository import get_repository
from app.services import scheduler
from app.services.data_ingestion import (
    IngestionError,
    TLSInterceptionError,
)

router = APIRouter(prefix="/api/v1", tags=["data"])


class RefreshRequest(BaseModel):
    symbol: Optional[str] = None
    tf: Optional[str] = None
    full: bool = Field(
        False,
        description="True menarik ulang seluruh rentang source.years; False hanya bar terbaru.",
    )


CHART_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


@router.get("/ohlcv")
def read_ohlcv(
    symbol: str = Query("BTCUSDT"),
    tf: str = Query("1h"),
    limit: Optional[int] = Query(None, ge=10, le=200000),
    format: str = Query(
        "records",
        pattern="^(records|columnar)$",
        description=(
            "records = list objek per candle (bawaan, kompatibel). "
            "columnar = satu array per kolom; ~3x lebih kecil, untuk chart."
        ),
    ),
) -> dict:
    """Candle OHLCV."""
    cfg = get_config()
    repo = get_repository()
    try:
        df = repo.get_ohlcv(symbol, tf)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TLSInterceptionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except IngestionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    total = len(df)
    if limit:
        df = df.tail(limit)
    status = repo.data_status(symbol, tf)
    body = {
        "symbol": symbol,
        "timeframe": tf,
        "config_hash": cfg.config_hash,
        "is_mock": cfg.runtime.use_mock,
        "source": status.get("source"),
        "last_time": status.get("last_time"),
        "age_seconds": status.get("age_seconds"),
        "stale": status.get("stale"),
        "count": len(df),
        "total_count": total,
    }
    if format == "columnar":
        cols = [c for c in CHART_COLUMNS if c in df.columns]
        # .tolist() mengubah ke tipe Python bawaan dalam satu langkah C.
        body["format"] = "columnar"
        body["columns"] = {
            c: (
                df[c].astype("int64").tolist()
                if c == "time"
                else df[c].round(4 if c == "volume" else 2).tolist()
            )
            for c in cols
        }
        return body
    body["candles"] = df.to_dict(orient="records")
    return body


@router.post("/data/refresh")
def refresh_data(req: RefreshRequest | None = None) -> dict:
    """Tarik data terbaru dari exchange."""
    cfg = get_config()
    repo = get_repository()
    body = req or RefreshRequest()
    symbol = body.symbol or cfg.data.symbol
    timeframes = [body.tf] if body.tf else list(cfg.data.timeframes)

    refreshed = []
    errors = []
    for tf in timeframes:
        try:
            meta = repo.refresh_ohlcv(symbol, tf, full=body.full)
            refreshed.append({"timeframe": tf, **meta})
        except TLSInterceptionError as exc:
            errors.append({"timeframe": tf, "error": str(exc), "intercepted": True})
        except IngestionError as exc:
            errors.append({"timeframe": tf, "error": str(exc)})

    if errors and not refreshed:
        raise HTTPException(
            status_code=502,
            detail={"message": "Semua sumber data gagal dihubungi.", "errors": errors},
        )

    return {
        "status": "ok" if not errors else "partial",
        "source": "mock" if cfg.runtime.use_mock else cfg.source.provider,
        "mode": "full" if body.full else "incremental",
        "refreshed": refreshed,
        "errors": errors,
    }


@router.get("/data/status")
def data_status(symbol: str = Query("BTCUSDT")) -> dict:
    """Kesegaran data per timeframe + status scheduler."""
    cfg = get_config()
    repo = get_repository()
    return {
        "config_hash": cfg.config_hash,
        "symbol": symbol,
        "is_mock": cfg.runtime.use_mock,
        "provider": cfg.source.provider,
        "years": cfg.source.years,
        "drop_open_bar": cfg.source.drop_open_bar,
        "timeframes": [repo.data_status(symbol, tf) for tf in cfg.data.timeframes],
        "scheduler": scheduler.status(),
    }



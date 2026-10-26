"""Endpoint internal untuk server Next.js: analisis aset.

Tidak berada di bawah /api/v1, sehingga Caddy tidak meneruskannya ke publik;
hanya rute Next.js (yang memeriksa login dan kuota harian) yang memanggilnya
lewat jaringan Docker. Bila ANALYSIS_INTERNAL_TOKEN diisi, header
X-Internal-Token wajib cocok sebagai lapisan pengaman kedua.
"""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services import asset_analysis
from app.services.ai_detector import DetectorUnavailable

router = APIRouter(prefix="/internal/analyses", tags=["internal"])


def _check_token(token: Optional[str]) -> None:
    expected = os.environ.get("ANALYSIS_INTERNAL_TOKEN", "").strip()
    if expected and not hmac.compare_digest(expected, (token or "").strip()):
        raise HTTPException(status_code=403, detail="Token internal tidak cocok.")


class AnalysisRequest(BaseModel):
    source: str
    symbol: str
    timeframe: str
    bars: int = asset_analysis.DEFAULT_BARS


@router.post("")
def create(req: AnalysisRequest, x_internal_token: Optional[str] = Header(None)) -> dict:
    _check_token(x_internal_token)
    try:
        return asset_analysis.submit(req.source, req.symbol, req.timeframe, req.bars)
    except asset_analysis.AnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DetectorUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Detektor belum tersedia: {exc}") from exc


@router.get("/{job_id}")
def read(job_id: str, x_internal_token: Optional[str] = Header(None)) -> dict:
    _check_token(x_internal_token)
    job = asset_analysis.status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analisis tidak ditemukan.")
    return job

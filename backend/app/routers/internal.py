"""Endpoint internal untuk server Next.js: analisis aset dan data Uji Ketahanan."""

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
        # 422: permintaan terbaca tetapi tidak dapat diproses (mis. jumlah bar < panjang jendela).
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DetectorUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Detektor belum tersedia: {exc}") from exc


@router.get("/{job_id}")
def read(job_id: str, x_internal_token: Optional[str] = Header(None)) -> dict:
    _check_token(x_internal_token)
    job = asset_analysis.status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analisis tidak ditemukan.")
    return job


robustness_router = APIRouter(prefix="/internal/robustness", tags=["internal"])


@robustness_router.get("")
def robustness(x_internal_token: Optional[str] = Header(None)) -> dict:
    """Data Uji Ketahanan Metode untuk rute Next.js `/api/robustness`."""
    _check_token(x_internal_token)
    from app.routers.model import load_robustness

    return load_robustness()


fitting_router = APIRouter(prefix="/internal/fitting", tags=["internal"])


@fitting_router.get("")
def fitting(x_internal_token: Optional[str] = Header(None)) -> dict:
    """Diagnosis overfitting/underfitting untuk halaman admin `/admin/fitting`."""
    _check_token(x_internal_token)
    import json

    from app.core.config import ARTIFACTS_DIR

    path = ARTIFACTS_DIR / "fit_diagnostics.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="fit_diagnostics.json belum dibuat (jalankan ml/src/fit_diagnostics.py).")
    return json.loads(path.read_text(encoding="utf-8"))

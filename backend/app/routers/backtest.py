"""Endpoint backtest.

Sumber regime default adalah PREDIKSI MODEL pada waktu t. Opsi rule-based
memakai Hurst-DFA dari window <= t. Label ground truth Y_{t+h} sengaja TIDAK
disediakan sebagai sumber sinyal, karena berasal dari window masa depan.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from typing import Dict, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import get_config
from app.db.repository import get_repository
from app.services.backtest_diagnostics import full_diagnostics
from app.services.backtest_engine import run_backtest
from app.services.inference import probabilities_for, to_dicts
from app.services.regime_labeling import apply_tau
from app.services.splitting import bars_to_rows, split_indices, stride_bars_of

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])

# Penyimpanan hasil dibatasi: tiap entri memuat equity curve hingga ~1500 titik
# dan halaman backtest mudah memicu banyak run (ganti fee, model, tau).
MAX_RESULTS = 50
_RESULTS: "OrderedDict[str, dict]" = OrderedDict()

ALLOWED_SOURCES = {"model_prediction_at_t", "rule_based_causal"}


def _store_result(run_id: str, result: dict) -> None:
    """Simpan dengan eviction LRU agar memori proses tidak tumbuh tanpa batas."""
    _RESULTS[run_id] = result
    _RESULTS.move_to_end(run_id)
    while len(_RESULTS) > MAX_RESULTS:
        _RESULTS.popitem(last=False)


class BacktestRequest(BaseModel):
    symbol: str = "BTCUSDT"
    tf: str = "1h"
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    model_key: str = "swt_attention_bilstm"
    regime_source: str = "model_prediction_at_t"
    fee_bps: float = Field(4.0, ge=0.0, le=100.0)
    tau: Optional[float] = Field(None, ge=1 / 3, le=1.0)


@router.post("/run")
def run(req: BacktestRequest) -> dict:
    cfg = get_config()
    if req.regime_source not in ALLOWED_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=(
                "regime_source harus salah satu dari "
                f"{sorted(ALLOWED_SOURCES)}. Label ground truth Hurst-DFA "
                "(Y_t+h) tidak boleh dipakai sebagai sinyal karena berasal "
                "dari window masa depan."
            ),
        )

    repo = get_repository()
    df = repo.get_regime(req.symbol, req.tf)
    if req.start_time:
        df = df[df["time"] >= req.start_time]
    if req.end_time:
        df = df[df["time"] <= req.end_time]
    if len(df) < 5:
        raise HTTPException(status_code=400, detail="Rentang terlalu pendek untuk backtest.")

    tau = req.tau if req.tau is not None else cfg.model.tau

    if req.regime_source == "model_prediction_at_t":
        probs_matrix, pred_source = probabilities_for(req.symbol, req.tf, df, req.model_key)
        regimes = [str(apply_tau(p, tau)["final_label"]) for p in to_dicts(probs_matrix)]
        origin = "model terlatih" if pred_source == "trained_artifact" else "stand-in"
        source_note = f"prediksi {req.model_key} pada t ({origin}, tau={tau})"
        pred_note = pred_source
    else:
        # Rule-based causal: label Hurst-DFA dari window yang berakhir di t.
        regimes = df["regime"].tolist()
        source_note = "Hurst-DFA rule-based dari window <= t"
        pred_note = "rule_based"

    result = run_backtest(
        times=df["time"].tolist(),
        closes=df["close"].tolist(),
        regimes=regimes,
        timeframe=req.tf,
        fee_bps=req.fee_bps,
        regime_source=req.regime_source,
        # Satu baris deret regime mewakili stride_bars bar; tanpa ini faktor
        # anualisasi Sharpe/volatilitas terlalu besar.
        bars_per_row=stride_bars_of(df),
    )
    run_id = uuid.uuid4().hex[:12]
    result.update(
        {
            "id": run_id,
            "timeframe": req.tf,
            "symbol": req.symbol,
            "model_key": req.model_key if req.regime_source == "model_prediction_at_t" else None,
            "regime_source_note": source_note,
            "prediction_source": pred_note,
            "tau": tau,
            "config_hash": cfg.config_hash,
        }
    )
    _store_result(run_id, result)
    return result


@router.get("/diagnostics")
def diagnostics(
    tf: str = Query("1h"),
    symbol: str = Query("BTCUSDT"),
    regime_source: str = Query("rule_based_causal"),
    model_key: str = Query("swt_attention_bilstm"),
    fee_bps: float = Query(4.0, ge=0.0, le=100.0),
    simulations: int = Query(200, ge=20, le=1000),
) -> dict:
    """Bukti pendukung di balik angka backtest.

    Equity curve yang menurun tidak menjelaskan penyebabnya. Endpoint ini
    memisahkan kontribusi arah posisi, volatility drag, dan biaya; lalu menguji
    apakah hasilnya berbeda dari posisi acak dan apakah asumsi arah pada aturan
    Bab 3 benar-benar berlaku pada data.
    """
    cfg = get_config()
    if regime_source not in ALLOWED_SOURCES:
        raise HTTPException(
            status_code=400, detail=f"regime_source harus salah satu dari {sorted(ALLOWED_SOURCES)}"
        )

    repo = get_repository()
    df = repo.get_regime(symbol, tf)
    if len(df) < 30:
        raise HTTPException(status_code=400, detail="Data terlalu pendek untuk diagnostik.")

    if regime_source == "model_prediction_at_t":
        probs_matrix, _ = probabilities_for(symbol, tf, df, model_key)
        regimes = [str(apply_tau(p, cfg.model.tau)["final_label"]) for p in to_dicts(probs_matrix)]
    else:
        regimes = df["regime"].tolist()

    stride = stride_bars_of(df)
    split = split_indices(len(df), cfg.split.ratios, bars_to_rows(cfg.model.purge_gap, stride))

    result = full_diagnostics(
        closes=df["close"].tolist(),
        regimes=regimes,
        segments={k: split[k] for k in ("train", "validation", "test")},  # type: ignore[misc]
        fee_bps=fee_bps,
        n_simulations=simulations,
    )
    result.update(
        {
            "timeframe": tf,
            "regime_source": regime_source,
            "model_key": model_key if regime_source == "model_prediction_at_t" else None,
            "fee_bps": fee_bps,
            "config_hash": cfg.config_hash,
        }
    )
    return result


@router.get("/{run_id}/result")
def get_result(run_id: str) -> dict:
    if run_id not in _RESULTS:
        raise HTTPException(status_code=404, detail="Hasil backtest tidak ditemukan.")
    return _RESULTS[run_id]

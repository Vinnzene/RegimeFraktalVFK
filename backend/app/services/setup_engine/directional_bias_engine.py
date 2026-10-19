"""Directional Bias Engine — LONG_BIAS / SHORT_BIAS / NEUTRAL per bar 1H.

Input (semua sudah ada sebelum waktu keputusan):
    - prediksi regime 4H dan 1H dari model existing (stream prediksi dengan
      kolom available_at, predicted_regime, confidence)
    - OHLCV + OFI + CVD 1H (kontrak market)
    - market structure 1H (tahap 2)

Waktu keputusan: `timestamp_bias` = close_time bar 1H. Seluruh input yang
dipakai pada bar itu tersedia paling lambat pada saat tersebut:
    - regime: prediksi dengan available_at <= timestamp_bias
    - struktur: swing dengan confirmation_time <= timestamp_bias
    - OFI/CVD: bar 1H yang close_time <= timestamp_bias

ATURAN (urutan evaluasi; alasan pertama yang gagal dicatat)
---------------------------------------------------------
Arah kandidat ditentukan oleh struktur, BUKAN oleh regime:
    struktur BULLISH -> kandidat LONG, BEARISH -> kandidat SHORT,
    NEUTRAL -> NEUTRAL (STRUCTURE_NOT_CONFIRMED)

Kandidat LONG menjadi LONG_BIAS bila SEMUA terpenuhi:
    1. regime 4H dan 1H tersedia & confidence >= regime.min_confidence
       (else REGIME_MISSING / LOW_CONFIDENCE)
    2. context bukan CONFLICT (else CONFLICTING_REGIME) dan termasuk
       context.bias_allowed_contexts (else CONTEXT_NOT_SUPPORTIVE)
    3. OFI 1H (rata-rata confirmation.ofi_lookback bar) >= −ofi_threshold
       — "tidak dominan negatif" (else OFI_AGAINST)
    4. kemiringan CVD 1H >= −cvd_slope_threshold
       — "tidak ada tekanan jual kuat" (else CVD_AGAINST)
    5. transisi regime tidak memblokir arah LONG (else TRANSITION_BLOCKED)
    6. bila transisi terakhir berstatus WAIT_NEW_BIAS: kandidat harus
       TERBENTUK BARU setelah transisi selesai (else WAITING_NEW_BIAS)
SHORT simetris (OFI <= +thr, slope <= +thr).

Kemiringan CVD pada bar t dengan lookback L:
    cvd_slope = (CVD_t − CVD_{t−L}) / Σ volume(t−L+1 .. t)  ∈ [−1, 1]
yaitu delta bersih L bar terakhir sebagai porsi volume — bebas skala dan
tidak bergantung titik awal kumulatif CVD.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.services.setup_engine.config import SetupEngineConfig, timeframe_seconds
from app.services.setup_engine.data_contract import DataContractError, LookAheadError, normalize_regime
from app.services.setup_engine.market_structure import MarketStructure
from app.services.setup_engine.regime_context import (
    RegimeContext,
    TransitionStatus,
    direction_blocked,
    regime_context,
    strictest,
    track_transitions,
)


class Bias(str, Enum):
    LONG_BIAS = "LONG_BIAS"
    SHORT_BIAS = "SHORT_BIAS"
    NEUTRAL = "NEUTRAL"


class BiasReason(str, Enum):
    OK = "OK"
    REGIME_MISSING = "REGIME_MISSING"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    STRUCTURE_NOT_CONFIRMED = "STRUCTURE_NOT_CONFIRMED"
    CONFLICTING_REGIME = "CONFLICTING_REGIME"
    CONTEXT_NOT_SUPPORTIVE = "CONTEXT_NOT_SUPPORTIVE"
    OFI_AGAINST = "OFI_AGAINST"
    CVD_AGAINST = "CVD_AGAINST"
    TRANSITION_BLOCKED = "TRANSITION_BLOCKED"
    WAITING_NEW_BIAS = "WAITING_NEW_BIAS"


# ------------------------------------------------------------ order flow


def rolling_ofi(ofi: np.ndarray, lookback: int) -> np.ndarray:
    """Rata-rata OFI `lookback` bar terakhir (termasuk bar t). Awal data: NaN."""
    return pd.Series(np.asarray(ofi, dtype=float)).rolling(lookback, min_periods=lookback).mean().to_numpy()


def cvd_slope(cvd: np.ndarray, volume: np.ndarray, lookback: int) -> np.ndarray:
    """(CVD_t − CVD_{t−L}) / Σ volume(t−L+1..t). NaN bila riwayat < L+1 bar."""
    c = pd.Series(np.asarray(cvd, dtype=float))
    v = pd.Series(np.asarray(volume, dtype=float))
    net = c - c.shift(lookback)
    tot = v.rolling(lookback, min_periods=lookback).sum()
    out = net / tot.where(tot > 0)
    return out.to_numpy()


# --------------------------------------------------------- regime streams


def prediction_stream(pred: pd.DataFrame, cfg: SetupEngineConfig) -> pd.DataFrame:
    """Prediksi regime + status transisi, satu baris per prediksi.

    `pred` minimal memuat available_at, predicted_regime, dan opsional
    confidence. Prediksi dengan confidence < regime.min_confidence dianggap
    UNCERTAIN sebelum pelacakan transisi.
    """
    for c in ("available_at", "predicted_regime"):
        if c not in pred.columns:
            raise DataContractError(f"stream prediksi butuh kolom {c}")
    s = pred.dropna(subset=["predicted_regime"]).sort_values("available_at", kind="mergesort")
    s = s.drop_duplicates("available_at", keep="last").reset_index(drop=True)
    conf = s["confidence"].to_numpy(dtype=float) if "confidence" in s else np.full(len(s), np.nan)
    reg = [normalize_regime(r).value for r in s["predicted_regime"]]
    low = np.isfinite(conf) & (conf < cfg.regime.min_confidence)
    effective = ["UNCERTAIN" if lo else r for r, lo in zip(reg, low)]
    tr = track_transitions(effective, s["available_at"].tolist(), cfg)
    out = pd.DataFrame(
        {
            "available_at": s["available_at"].to_numpy(),
            "regime": reg,
            "confidence": conf,
            "low_confidence": low,
        }
    )
    return pd.concat([out, tr], axis=1)


def _attach_stream(bars: pd.DataFrame, stream: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Lekatkan stream prediksi ke bar 1H: available_at <= close_time, dengan batas umur."""
    diffs = stream["available_at"].diff().dropna()
    max_age = diffs.mode().iloc[0] if len(diffs) else pd.Timedelta(0)
    right = stream.add_prefix(prefix)
    left = bars[["close_time"]].copy()
    left["_o"] = np.arange(len(left))
    m = pd.merge_asof(
        left.sort_values("close_time"),
        right.sort_values(f"{prefix}available_at"),
        left_on="close_time",
        right_on=f"{prefix}available_at",
        direction="backward",
    ).sort_values("_o")
    m = m.drop(columns=["_o", "close_time"]).reset_index(drop=True)
    avail = m[f"{prefix}available_at"]
    if (avail.notna() & (avail > bars["close_time"].reset_index(drop=True))).any():
        raise LookAheadError(f"prediksi {prefix} dilekatkan sebelum tersedia")
    stale = avail.notna() & (bars["close_time"].reset_index(drop=True) - avail >= max_age)
    if stale.any():
        m.loc[stale, :] = np.nan
    return m


# ------------------------------------------------------------------ engine


def compute_bias(
    market_1h: pd.DataFrame,
    pred_4h: pd.DataFrame,
    pred_1h: pd.DataFrame,
    cfg: SetupEngineConfig,
) -> pd.DataFrame:
    """Bias per bar 1H. Lihat docstring modul untuk aturan lengkap."""
    tf = str(market_1h["timeframe"].iloc[0])
    if tf != cfg.timeframes.bias:
        raise DataContractError(f"market bias harus {cfg.timeframes.bias}, bukan {tf}")
    for c in ("timestamp", "close_time", "high", "low", "close", "volume", "ofi", "cvd"):
        if c not in market_1h.columns:
            raise DataContractError(f"market 1H butuh kolom {c}")
    bars = market_1h.reset_index(drop=True)
    n = len(bars)

    ms = MarketStructure.from_config(bars, cfg)
    struct = ms.structure_series()["structure"].to_numpy()

    c = cfg.confirmation
    if c.required and (cfg.bias.use_ofi or cfg.bias.use_cvd):
        has_real_ofi = "ofi" in bars.columns and not bars["ofi"].isna().all() and (bars["ofi"].abs().sum() > 0)
        has_real_cvd = "cvd" in bars.columns and not bars["cvd"].isna().all() and (bars["cvd"].abs().sum() > 0)
        if not (has_real_ofi or has_real_cvd):
            raise ValueError(
                "Mode B requires valid order flow data (OFI/CVD). "
                "Binance spot book archives returned HTTP 404; use Mode A instead."
            )

    if cfg.bias.use_ofi and "ofi" in bars.columns:
        ofi_1h = rolling_ofi(bars["ofi"].to_numpy(), c.ofi_lookback)
    else:
        ofi_1h = np.full(n, np.nan)

    if cfg.bias.use_cvd and "cvd" in bars.columns:
        slope = cvd_slope(bars["cvd"].to_numpy(), bars["volume"].to_numpy(), c.cvd_lookback)
    else:
        slope = np.full(n, np.nan)

    s4 = _attach_stream(bars, prediction_stream(pred_4h, cfg), "r4_")
    s1 = _attach_stream(bars, prediction_stream(pred_1h, cfg), "r1_")

    watch = set(cfg.transition.timeframes)
    rules = cfg.transition.rules

    rows: List[Dict[str, object]] = []
    prev_candidate = Bias.NEUTRAL.value
    candidate_since: pd.Timestamp = bars["close_time"].iloc[0] if n else pd.Timestamp(0, tz="UTC")
    waiting = False
    waiting_since: Optional[pd.Timestamp] = None
    seen_done: Dict[str, Optional[pd.Timestamp]] = {"r4_": None, "r1_": None}

    for j in range(n):
        t = bars["close_time"].iloc[j]
        r4 = s4["r4_regime"].iloc[j]
        r1 = s1["r1_regime"].iloc[j]
        have4 = isinstance(r4, str)
        have1 = isinstance(r1, str)
        low4 = bool(s4["r4_low_confidence"].iloc[j]) if have4 else False
        low1 = bool(s1["r1_low_confidence"].iloc[j]) if have1 else False
        eff4 = "UNCERTAIN" if low4 else r4
        eff1 = "UNCERTAIN" if low1 else r1
        ctx = regime_context(eff4, eff1, cfg).value if (have4 and have1) else RegimeContext.NEUTRAL.value

        st4 = s4["r4_transition_status"].iloc[j] if have4 and "regime" in watch else TransitionStatus.NORMAL.value
        st1 = s1["r1_transition_status"].iloc[j] if have1 and "bias" in watch else TransitionStatus.NORMAL.value
        st4 = st4 if isinstance(st4, str) else TransitionStatus.NORMAL.value
        st1 = st1 if isinstance(st1, str) else TransitionStatus.NORMAL.value
        status = strictest(st4, st1)
        t4 = s4["r4_transition_type"].iloc[j] if have4 else ""
        t1 = s1["r1_transition_type"].iloc[j] if have1 else ""
        parts = []
        if isinstance(t4, str) and t4:
            parts.append(f"4H:{t4}")
        if isinstance(t1, str) and t1:
            parts.append(f"1H:{t1}")
        ttype = "|".join(parts)

        # Transisi yang baru SELESAI dengan aturan WAIT_NEW_BIAS -> tunggu bias baru.
        for p, frame, tf_key in (("r4_", s4, "regime"), ("r1_", s1, "bias")):
            if tf_key not in watch:
                continue
            done = frame[f"{p}last_transition_completed_at"].iloc[j]
            if isinstance(done, pd.Timestamp) and not pd.isna(done) and done != seen_done[p]:
                seen_done[p] = done
                ltype = frame[f"{p}last_transition_type"].iloc[j]
                if rules.get(ltype) == TransitionStatus.WAIT_NEW_BIAS.value:
                    waiting, waiting_since = True, done

        if struct[j] == "BULLISH":
            candidate = Bias.LONG_BIAS.value
        elif struct[j] == "BEARISH":
            candidate = Bias.SHORT_BIAS.value
        else:
            candidate = Bias.NEUTRAL.value
        if candidate != prev_candidate:
            candidate_since = t

        reason = BiasReason.OK.value
        if candidate == Bias.NEUTRAL.value:
            reason = BiasReason.STRUCTURE_NOT_CONFIRMED.value
        elif not (have4 and have1):
            reason = BiasReason.REGIME_MISSING.value
        elif low4 or low1:
            reason = BiasReason.LOW_CONFIDENCE.value
        elif ctx == RegimeContext.CONFLICT.value:
            reason = BiasReason.CONFLICTING_REGIME.value
        elif ctx not in cfg.context.bias_allowed_contexts:
            reason = BiasReason.CONTEXT_NOT_SUPPORTIVE.value
        else:
            sign = 1.0 if candidate == Bias.LONG_BIAS.value else -1.0
            if cfg.bias.use_ofi and not (np.isfinite(ofi_1h[j]) and sign * ofi_1h[j] >= -c.ofi_threshold):
                reason = BiasReason.OFI_AGAINST.value
            elif cfg.bias.use_cvd and not (np.isfinite(slope[j]) and sign * slope[j] >= -c.cvd_slope_threshold):
                reason = BiasReason.CVD_AGAINST.value
            elif direction_blocked(status, "LONG" if sign > 0 else "SHORT", cfg):
                reason = BiasReason.TRANSITION_BLOCKED.value
            elif waiting and waiting_since is not None and not cfg.regime.allow_entry_during_transition:
                # Bias "baru" = arah struktur yang mulai SETELAH transisi selesai.
                if candidate_since > waiting_since:
                    waiting, waiting_since = False, None
                else:
                    reason = BiasReason.WAITING_NEW_BIAS.value

        bias = candidate if reason == BiasReason.OK.value else Bias.NEUTRAL.value
        rows.append(
            {
                "timestamp": bars["timestamp"].iloc[j],
                "timestamp_bias": t,
                "regime_4h": r4 if have4 else None,
                "regime_4h_confidence": s4["r4_confidence"].iloc[j],
                "regime_4h_available_at": s4["r4_available_at"].iloc[j],
                "regime_1h": r1 if have1 else None,
                "regime_1h_confidence": s1["r1_confidence"].iloc[j],
                "regime_1h_available_at": s1["r1_available_at"].iloc[j],
                "stable_regime_4h": s4["r4_stable_regime"].iloc[j],
                "stable_regime_1h": s1["r1_stable_regime"].iloc[j],
                "regime_context": ctx,
                "structure_1h": struct[j],
                "ofi_1h": ofi_1h[j],
                "cvd_1h": bars["cvd"].iloc[j] if (cfg.bias.use_cvd and "cvd" in bars.columns) else np.nan,
                "cvd_slope_1h": slope[j],
                "transition_type": ttype,
                "transition_status": status,
                "transition_status_4h": st4,
                "transition_status_1h": st1,
                "waiting_new_bias": waiting,
                "candidate_bias": candidate,
                "candidate_since": candidate_since,
                "bias": bias,
                "bias_reason": reason,
            }
        )
        prev_candidate = candidate

    out = pd.DataFrame(rows)
    validate_bias_no_lookahead(out)
    return out


def validate_bias_no_lookahead(bias: pd.DataFrame) -> None:
    """Semua prediksi regime yang dipakai tersedia paling lambat di timestamp_bias."""
    for c in ("regime_4h_available_at", "regime_1h_available_at"):
        a = pd.to_datetime(bias[c], utc=True)
        bad = a.notna() & (a > bias["timestamp_bias"])
        if bad.any():
            raise LookAheadError(f"{c} > timestamp_bias pada {bad.sum()} baris")
    if not (bias["timestamp_bias"] > bias["timestamp"]).all():
        raise LookAheadError("timestamp_bias harus setelah open time bar")


def bias_events(bias: pd.DataFrame) -> pd.DataFrame:
    """Baris saat bias BERUBAH (awal setiap episode bias). Dipakai setup engine."""
    changed = bias["bias"].ne(bias["bias"].shift())
    return bias.loc[changed].reset_index(drop=True)

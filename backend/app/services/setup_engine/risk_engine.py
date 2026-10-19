"""Risk engine: structural stop loss dan take profit dengan RR tetap.

Seluruh fungsi murni (pure): tidak membaca file, tidak menyimpan state, dan
keluaran hanya bergantung pada argumen.

ATURAN
------
Stop loss struktural (bukan persentase tetap):

    LONG : SL = harga swing LOW terakhir yang terkonfirmasi  − sl_buffer
    SHORT: SL = harga swing HIGH terakhir yang terkonfirmasi + sl_buffer

Swing wajib sudah terkonfirmasi saat entry
(`swing.confirmation_time <= entry_time`). Melanggar ini adalah look-ahead
dan menimbulkan `LookAheadError` (kesalahan program, bukan setup yang ditolak).

Risk dan validasi:

    risk = |entry − SL|
    LONG  wajib SL < entry, SHORT wajib SL > entry
    risk/entry >= risk.min_risk_distance_pct   (SL tidak terlalu dekat)
    risk/entry <= risk.max_risk_distance_pct   (SL tidak terlalu jauh)

Pelanggaran -> plan tidak valid dengan rejection_reason = INVALID_STOP dan
`invalid_detail` yang menjelaskan sebabnya.

Take profit dengan RR dari config (`risk.rr`, sama untuk semua setup):

    LONG : TP = entry + rr × risk
    SHORT: TP = entry − rr × risk
    reward = rr × risk

Tidak ada parameter untuk mengganti RR per setup — RR hanya dibaca dari config.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional

import pandas as pd

from app.services.setup_engine.config import SetupEngineConfig
from app.services.setup_engine.data_contract import LookAheadError
from app.services.setup_engine.market_structure import Swing, SwingKind

INVALID_STOP = "INVALID_STOP"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class InvalidStopDetail(str, Enum):
    NO_SWING = "NO_SWING"              # belum ada swing terkonfirmasi
    INVALID_ENTRY = "INVALID_ENTRY"    # entry <= 0 atau bukan angka
    WRONG_SIDE = "WRONG_SIDE"          # LONG dengan SL >= entry / SHORT dengan SL <= entry
    ZERO_RISK = "ZERO_RISK"            # risk == 0
    RISK_TOO_SMALL = "RISK_TOO_SMALL"  # risk/entry < min_risk_distance_pct
    RISK_TOO_LARGE = "RISK_TOO_LARGE"  # risk/entry > max_risk_distance_pct


@dataclass(frozen=True)
class RiskPlan:
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    risk: float
    reward: float
    rr: float
    risk_pct: float
    swing_price: float
    swing_time: Optional[pd.Timestamp]
    swing_confirmation_time: Optional[pd.Timestamp]
    valid: bool
    rejection_reason: Optional[str]
    invalid_detail: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _direction(direction: Direction | str) -> Direction:
    try:
        return Direction(str(direction.value if isinstance(direction, Direction) else direction).upper())
    except ValueError as exc:
        raise ValueError(f"direction harus LONG atau SHORT, bukan {direction!r}") from exc


def structural_stop(direction: Direction | str, swing_price: float, sl_buffer: float) -> float:
    """SL = swing_low − buffer (LONG) atau swing_high + buffer (SHORT)."""
    if sl_buffer < 0:
        raise ValueError("sl_buffer tidak boleh negatif")
    d = _direction(direction)
    return float(swing_price - sl_buffer) if d is Direction.LONG else float(swing_price + sl_buffer)


def take_profit(direction: Direction | str, entry: float, risk: float, rr: float) -> float:
    """TP = entry ± rr × risk."""
    d = _direction(direction)
    return float(entry + rr * risk) if d is Direction.LONG else float(entry - rr * risk)


def _reject(
    d: Direction,
    entry: float,
    sl: float,
    rr: float,
    detail: InvalidStopDetail,
    swing: Optional[Swing],
) -> RiskPlan:
    risk = abs(entry - sl) if math.isfinite(entry) and math.isfinite(sl) else float("nan")
    return RiskPlan(
        direction=d.value,
        entry=float(entry),
        stop_loss=float(sl),
        take_profit=float("nan"),
        risk=float(risk),
        reward=float("nan"),
        rr=float(rr),
        risk_pct=float(risk / entry) if math.isfinite(risk) and entry > 0 else float("nan"),
        swing_price=float(swing.price) if swing else float("nan"),
        swing_time=swing.pivot_time if swing else None,
        swing_confirmation_time=swing.confirmation_time if swing else None,
        valid=False,
        rejection_reason=INVALID_STOP,
        invalid_detail=detail.value,
    )


def build_risk_plan(
    direction: Direction | str,
    entry: float,
    swing: Optional[Swing],
    entry_time: pd.Timestamp,
    cfg: SetupEngineConfig,
) -> RiskPlan:
    """Rencana SL/TP untuk satu entry.

    `swing` adalah swing LOW (untuk LONG) atau swing HIGH (untuk SHORT)
    terakhir yang terkonfirmasi pada `entry_time` — biasanya hasil
    `MarketStructure.get_last_confirmed_swing_low/high(entry_time)`.
    """
    d = _direction(direction)
    rr = float(cfg.risk.rr)
    entry = float(entry)

    if swing is not None:
        want = SwingKind.LOW if d is Direction.LONG else SwingKind.HIGH
        if swing.kind is not want:
            raise ValueError(f"{d.value} membutuhkan swing {want.value}, diberikan {swing.kind.value}")
        if swing.confirmation_time > pd.Timestamp(entry_time):
            raise LookAheadError(
                f"swing {swing.pivot_time} baru terkonfirmasi {swing.confirmation_time}, "
                f"setelah entry {entry_time}"
            )

    if not math.isfinite(entry) or entry <= 0:
        return _reject(d, entry, float("nan"), rr, InvalidStopDetail.INVALID_ENTRY, swing)
    if swing is None:
        return _reject(d, entry, float("nan"), rr, InvalidStopDetail.NO_SWING, swing)

    sl = structural_stop(d, swing.price, cfg.risk.sl_buffer)
    if (d is Direction.LONG and sl > entry) or (d is Direction.SHORT and sl < entry):
        return _reject(d, entry, sl, rr, InvalidStopDetail.WRONG_SIDE, swing)
    risk = abs(entry - sl)
    if risk == 0:
        return _reject(d, entry, sl, rr, InvalidStopDetail.ZERO_RISK, swing)
    pct = risk / entry
    if pct < cfg.risk.min_risk_distance_pct:
        return _reject(d, entry, sl, rr, InvalidStopDetail.RISK_TOO_SMALL, swing)
    if pct > cfg.risk.max_risk_distance_pct:
        return _reject(d, entry, sl, rr, InvalidStopDetail.RISK_TOO_LARGE, swing)

    return RiskPlan(
        direction=d.value,
        entry=entry,
        stop_loss=sl,
        take_profit=take_profit(d, entry, risk, rr),
        risk=float(risk),
        reward=float(rr * risk),
        rr=rr,
        risk_pct=float(pct),
        swing_price=float(swing.price),
        swing_time=swing.pivot_time,
        swing_confirmation_time=swing.confirmation_time,
        valid=True,
        rejection_reason=None,
        invalid_detail=None,
    )

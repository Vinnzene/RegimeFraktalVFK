"""Regime context (4H x 1H) dan filter transisi regime.

Regime hanya menggambarkan karakter persistence, BUKAN arah. Modul ini tidak
pernah menghasilkan LONG/SHORT; arah ditentukan `directional_bias_engine`.

REGIME CONTEXT
--------------
Lookup table eksplisit `context.table[regime_4h][regime_1h]` dari config.
Nilai: SUPPORTIVE / NEUTRAL / CONFLICT.

TRANSISI REGIME
---------------
Prediksi model berstride (4H: tiap 16 jam, 1H: tiap 4 jam) dan bisa
berkedip. Karena itu dibedakan:

    raw regime        : prediksi terbaru apa adanya
    stable regime     : regime terakhir yang muncul N prediksi berturut-turut
                        (N = transition.confirm_predictions)

Transisi FROM->TO dimulai saat raw regime pertama kali berbeda dari stable
regime, dan selesai saat raw regime baru terkonfirmasi N kali (stable
berganti) atau raw kembali ke regime lama (transisi batal). Selama transisi,
status diambil dari `transition.rules["FROM->TO"]`:

    NORMAL         tidak ada pembatasan
    BLOCK_LONG     setup LONG baru diblokir
    BLOCK_SHORT    setup SHORT baru diblokir
    BLOCK_ALL      semua setup baru diblokir (caution)
    WAIT_NEW_BIAS  setup diblokir sampai bias baru terbentuk SETELAH transisi

`allow_entry_during_transition=True` mematikan pemblokiran, tetapi kolom
transition_type / transition_status TETAP diisi. Transisi tidak pernah
dihapus dari output.

Semua perhitungan berurutan maju (causal): status pada prediksi ke-i hanya
bergantung pada prediksi 0..i.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.services.setup_engine.config import SetupEngineConfig
from app.services.setup_engine.data_contract import Regime, normalize_regime


class RegimeContext(str, Enum):
    SUPPORTIVE = "SUPPORTIVE"
    NEUTRAL = "NEUTRAL"
    CONFLICT = "CONFLICT"


class TransitionStatus(str, Enum):
    NORMAL = "NORMAL"
    BLOCK_LONG = "BLOCK_LONG"
    BLOCK_SHORT = "BLOCK_SHORT"
    BLOCK_ALL = "BLOCK_ALL"
    WAIT_NEW_BIAS = "WAIT_NEW_BIAS"


def regime_context(regime_4h: object, regime_1h: object, cfg: SetupEngineConfig) -> RegimeContext:
    """Lookup tabel konteks. Nilai regime tak terdefinisi -> NEUTRAL."""
    try:
        r4 = normalize_regime(regime_4h).value
        r1 = normalize_regime(regime_1h).value
    except Exception:  # noqa: BLE001 - regime kosong/tidak dikenal = tidak ada konteks
        return RegimeContext.NEUTRAL
    return RegimeContext(cfg.context.table[r4][r1])


def context_table_frame(cfg: SetupEngineConfig) -> pd.DataFrame:
    """Tabel konteks lengkap untuk ditampilkan/dilaporkan."""
    t = cfg.context.table
    order = ["PERSISTENT", "RANDOM_LIKE", "ANTI_PERSISTENT", "UNCERTAIN"]
    return pd.DataFrame([[t[r][c] for c in order] for r in order], index=order, columns=order).rename_axis(
        index="4H \\ 1H"
    )


@dataclass(frozen=True)
class TransitionRow:
    stable_regime: str
    transition_type: str      # "FROM->TO" atau "" bila tidak dalam transisi
    transition_status: str    # NORMAL / BLOCK_* / WAIT_NEW_BIAS
    transition_started_at: Optional[pd.Timestamp]
    last_transition_type: str        # transisi terakhir yang SELESAI (stable berganti)
    last_transition_completed_at: Optional[pd.Timestamp]


def track_transitions(
    regimes: Sequence[object],
    times: Sequence[pd.Timestamp],
    cfg: SetupEngineConfig,
) -> pd.DataFrame:
    """Lacak transisi regime pada deret prediksi (urut waktu ketersediaan).

    Kolom keluaran per prediksi:
        raw_regime, stable_regime, transition_type, transition_status,
        transition_started_at, last_transition_type,
        last_transition_completed_at, pending_count
    """
    n_confirm = cfg.transition.confirm_predictions
    rules = cfg.transition.rules
    rows: List[Dict[str, object]] = []

    stable = "NONE"
    candidate: Optional[str] = None
    count = 0
    started: Optional[pd.Timestamp] = None
    last_type = ""
    last_done: Optional[pd.Timestamp] = None

    for raw_v, t in zip(regimes, times):
        raw = normalize_regime(raw_v).value
        if raw == stable:
            candidate, count, started = None, 0, None
        else:
            if raw == candidate:
                count += 1
            else:
                candidate, count = raw, 1
                started = started if started is not None else pd.Timestamp(t)
            if count >= n_confirm:
                last_type = f"{stable}->{raw}"
                last_done = pd.Timestamp(t)
                stable, candidate, count, started = raw, None, 0, None

        if candidate is not None:
            ttype = f"{stable}->{candidate}"
            status = rules[ttype]
        else:
            ttype, status = "", TransitionStatus.NORMAL.value
        rows.append(
            {
                "raw_regime": raw,
                "stable_regime": stable,
                "transition_type": ttype,
                "transition_status": status,
                "transition_started_at": started,
                "last_transition_type": last_type,
                "last_transition_completed_at": last_done,
                "pending_count": count,
            }
        )
    out = pd.DataFrame(rows)
    for c in ("transition_started_at", "last_transition_completed_at"):
        out[c] = pd.to_datetime(out[c], utc=True)
    return out


def direction_blocked(status: str, direction: str, cfg: SetupEngineConfig) -> bool:
    """Apakah setup baru `direction` ('LONG'/'SHORT') diblokir oleh status transisi.

    WAIT_NEW_BIAS memblokir di sini; pembebasannya (bias baru terbentuk setelah
    transisi) ditangani `directional_bias_engine`.
    """
    if cfg.regime.allow_entry_during_transition:
        return False
    if status == TransitionStatus.BLOCK_ALL.value or status == TransitionStatus.WAIT_NEW_BIAS.value:
        return True
    if status == TransitionStatus.BLOCK_LONG.value:
        return direction == "LONG"
    if status == TransitionStatus.BLOCK_SHORT.value:
        return direction == "SHORT"
    return False


def strictest(a: str, b: str) -> str:
    """Gabungkan status dua timeframe; yang lebih ketat menang."""
    order = {
        TransitionStatus.NORMAL.value: 0,
        TransitionStatus.BLOCK_LONG.value: 1,
        TransitionStatus.BLOCK_SHORT.value: 1,
        TransitionStatus.WAIT_NEW_BIAS.value: 2,
        TransitionStatus.BLOCK_ALL.value: 3,
    }
    if {a, b} == {TransitionStatus.BLOCK_LONG.value, TransitionStatus.BLOCK_SHORT.value}:
        return TransitionStatus.BLOCK_ALL.value
    return a if order[a] >= order[b] else b

"""Konfigurasi Walk-Forward Setup Engine.

Mengikuti konvensi `app.core.config`: model pydantic bertingkat, divalidasi
saat load, dan memiliki hash kanonik untuk jejak reproducibility.

Sumber nilai: `setup_engine.yaml` di root project. File itu sengaja terpisah
dari `config.yaml` agar `config_hash` model regime existing tidak berubah.

Nama parameter dari spesifikasi (SETUP_TIMEFRAME, RR, MAX_HOLDING_BARS, ...)
tersedia juga sebagai properti huruf besar lewat `SetupEngineConfig.flat()`
supaya mudah dicocokkan dengan dokumen penelitian.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import PROJECT_ROOT

SETUP_CONFIG_PATH = PROJECT_ROOT / "setup_engine.yaml"

# Durasi bar dalam detik. Satu-satunya tempat definisi.
TIMEFRAME_SECONDS: Dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "1d": 86400,
}

_PERIOD_RE = re.compile(r"^(\d+)\s*([DWMY])$", re.IGNORECASE)


def timeframe_seconds(tf: str) -> int:
    """Durasi satu bar dalam detik. ValueError bila timeframe tidak dikenal."""
    try:
        return TIMEFRAME_SECONDS[tf]
    except KeyError as exc:
        raise ValueError(f"timeframe '{tf}' tidak dikenal; pilih {sorted(TIMEFRAME_SECONDS)}") from exc


def parse_period(text: str) -> pd.DateOffset:
    """'12M' -> 12 bulan kalender, '2W' -> 14 hari, '30D', '1Y'.

    Bulan memakai DateOffset kalender (bukan 30 hari) agar jendela
    walk-forward jatuh di tanggal yang sama setiap bulan.
    """
    m = _PERIOD_RE.match(str(text).strip())
    if not m:
        raise ValueError(f"periode '{text}' tidak valid; format <angka><D|W|M|Y>, mis. '12M'")
    n, unit = int(m.group(1)), m.group(2).upper()
    if n <= 0:
        raise ValueError(f"periode '{text}' harus > 0")
    return {
        "D": pd.DateOffset(days=n),
        "W": pd.DateOffset(weeks=n),
        "M": pd.DateOffset(months=n),
        "Y": pd.DateOffset(years=n),
    }[unit]


class TimeframeConfig(BaseModel):
    """Hierarki timeframe: regime > bias > setup > resolution (makin halus)."""

    regime: str = "4h"       # REGIME_TIMEFRAME: konteks regime dari model existing
    bias: str = "1h"         # BIAS_TIMEFRAME: directional bias
    setup: str = "30m"       # SETUP_TIMEFRAME: setup & entry trigger
    resolution: str = "5m"   # RESOLUTION_TIMEFRAME: penentu urutan TP/SL

    @field_validator("regime", "bias", "setup", "resolution")
    @classmethod
    def _known(cls, v: str) -> str:
        timeframe_seconds(v)
        return v

    @model_validator(mode="after")
    def _ordered(self) -> "TimeframeConfig":
        r, b, s, x = (timeframe_seconds(t) for t in (self.regime, self.bias, self.setup, self.resolution))
        if not (r >= b >= s >= x):
            raise ValueError("timeframes harus berurutan: regime >= bias >= setup >= resolution")
        for hi, lo, name in ((r, b, "regime/bias"), (b, s, "bias/setup"), (s, x, "setup/resolution")):
            if hi % lo != 0:
                raise ValueError(f"timeframe {name} harus kelipatan bulat agar batas bar sejajar")
        return self


class RiskConfig(BaseModel):
    """Structural stop + TP dengan RR tetap."""

    rr: float = 2.0                       # RR: TP = entry ± rr × risk; sama untuk semua setup
    sl_buffer: float = 0.0                # SL_BUFFER: tambahan di luar swing, unit harga (USDT)
    min_risk_distance_pct: float = 0.001  # risk/entry di bawah ini -> INVALID_STOP (SL terlalu dekat)
    max_risk_distance_pct: float = 0.05   # risk/entry di atas ini -> INVALID_STOP (SL tidak masuk akal)

    @field_validator("rr")
    @classmethod
    def _rr(cls, v: float) -> float:
        if not (0.1 <= v <= 20.0):
            raise ValueError("risk.rr harus di rentang 0.1 - 20")
        return v

    @field_validator("sl_buffer")
    @classmethod
    def _buffer(cls, v: float) -> float:
        if v < 0:
            raise ValueError("risk.sl_buffer tidak boleh negatif")
        return v

    @model_validator(mode="after")
    def _risk_bounds(self) -> "RiskConfig":
        if not (0.0 < self.min_risk_distance_pct < self.max_risk_distance_pct <= 0.5):
            raise ValueError("risk: 0 < min_risk_distance_pct < max_risk_distance_pct <= 0.5")
        return self


class ExecutionConfig(BaseModel):
    """Batas simulasi posisi. Tidak ada eksekusi nyata."""

    max_open_positions: int = 1   # MAX_OPEN_POSITIONS
    max_setup_wait_bars: int = 6  # MAX_SETUP_WAIT_BARS (bar setup TF)
    max_holding_bars: int = 8     # MAX_HOLDING_BARS (bar setup TF)
    taker_fee_pct: float = 0.00075 # TAKER_FEE_PCT: 0.075% standar Binance VIP 0 spot
    slippage_ticks: int = 1       # SLIPPAGE_TICKS: 1 tick = 0.01 USDT
    tick_size: float = 0.01       # TICK_SIZE: tick size BTCUSDT (USDT)

    @field_validator("max_open_positions")
    @classmethod
    def _positions(cls, v: int) -> int:
        if v != 1:
            # Spesifikasi menetapkan satu posisi pada satu waktu agar hasil
            # dapat dianalisis tanpa overlap. Nilai lain belum didukung engine.
            raise ValueError("execution.max_open_positions saat ini hanya mendukung 1")
        return v

    @field_validator("max_setup_wait_bars", "max_holding_bars")
    @classmethod
    def _bars(cls, v: int) -> int:
        if not (1 <= v <= 500):
            raise ValueError("jumlah bar harus di rentang 1 - 500")
        return v

    @field_validator("taker_fee_pct")
    @classmethod
    def _fee(cls, v: float) -> float:
        if not (0.0 <= v <= 0.05):
            raise ValueError("execution.taker_fee_pct harus di rentang 0.0 - 0.05 (maks 5%)")
        return v

    @field_validator("slippage_ticks")
    @classmethod
    def _slippage(cls, v: int) -> int:
        if v < 0:
            raise ValueError("execution.slippage_ticks tidak boleh negatif")
        return v

    @field_validator("tick_size")
    @classmethod
    def _tick_sz(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("execution.tick_size harus positif")
        return v


class StructureConfig(BaseModel):
    """Deteksi swing pivot."""

    swing_lookback: int = 3  # SWING_LOOKBACK: pivot terkonfirmasi setelah k bar kanan close

    @field_validator("swing_lookback")
    @classmethod
    def _lookback(cls, v: int) -> int:
        if not (1 <= v <= 20):
            raise ValueError("structure.swing_lookback harus di rentang 1 - 20")
        return v


class ConfirmationConfig(BaseModel):
    """OFI/CVD hanya sebagai konfirmasi tambahan, bukan pemicu.
    Default Mode A (Base): required=False, use_ofi=False, use_cvd=False.
    """

    use_ofi: bool = False            # USE_OFI_CONFIRMATION
    use_cvd: bool = False            # USE_CVD_CONFIRMATION
    required: bool = False           # CONFIRMATION_REQUIRED: false = dicatat saja / nonaktif
    ofi_threshold: float = 0.0       # LONG butuh OFI >= +thr, SHORT OFI <= -thr
    ofi_lookback: int = 3            # rata-rata OFI N bar close terakhir
    cvd_lookback: int = 6            # jendela kemiringan CVD (bar)
    cvd_slope_threshold: float = 0.0 # kemiringan CVD ternormalisasi volume

    @field_validator("ofi_threshold")
    @classmethod
    def _ofi(cls, v: float) -> float:
        if not (0.0 <= v < 1.0):
            raise ValueError("confirmation.ofi_threshold harus di [0, 1) karena OFI ∈ [-1, 1]")
        return v

    @field_validator("cvd_slope_threshold")
    @classmethod
    def _cvd(cls, v: float) -> float:
        if not (0.0 <= v < 1.0):
            raise ValueError("confirmation.cvd_slope_threshold harus di [0, 1)")
        return v

    @field_validator("ofi_lookback", "cvd_lookback")
    @classmethod
    def _lb(cls, v: int) -> int:
        if not (1 <= v <= 500):
            raise ValueError("lookback harus di rentang 1 - 500")
        return v


class RegimeSourceConfig(BaseModel):
    """Sumber prediksi regime dari model existing."""

    source: str = "model_A"                     # kolom prediksi pada timeline artefak
    min_confidence: float = 0.0                 # max(P) di bawah ini -> diperlakukan tidak pasti
    allow_entry_during_transition: bool = False # ALLOW_ENTRY_DURING_TRANSITION

    @field_validator("source")
    @classmethod
    def _src(cls, v: str) -> str:
        if v not in {"model_A", "model_B", "model_C", "model_D", "hurst_dfa"}:
            raise ValueError("regime.source harus model_A..model_D atau hurst_dfa")
        return v

    @field_validator("min_confidence")
    @classmethod
    def _conf(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("regime.min_confidence harus di [0, 1]")
        return v


REGIME_KEYS = ("PERSISTENT", "RANDOM_LIKE", "ANTI_PERSISTENT", "UNCERTAIN")
CONTEXT_VALUES = ("SUPPORTIVE", "NEUTRAL", "CONFLICT")
TRANSITION_STATUSES = ("NORMAL", "BLOCK_LONG", "BLOCK_SHORT", "BLOCK_ALL", "WAIT_NEW_BIAS")


def _default_context_table() -> Dict[str, Dict[str, str]]:
    """Baris = regime 4H, kolom = regime 1H.

    SUPPORTIVE hanya bila kedua skala persistent. CONFLICT bila satu skala
    persistent dan skala lain anti-persistent (sifat berlawanan). Kombinasi
    lain, termasuk apa pun yang melibatkan UNCERTAIN, NEUTRAL.
    """
    P, R, A, U = REGIME_KEYS
    return {
        P: {P: "SUPPORTIVE", R: "NEUTRAL", A: "CONFLICT", U: "NEUTRAL"},
        R: {P: "NEUTRAL", R: "NEUTRAL", A: "NEUTRAL", U: "NEUTRAL"},
        A: {P: "CONFLICT", R: "NEUTRAL", A: "NEUTRAL", U: "NEUTRAL"},
        U: {P: "NEUTRAL", R: "NEUTRAL", A: "NEUTRAL", U: "NEUTRAL"},
    }


def _default_transition_rules() -> Dict[str, str]:
    """Status selama transisi FROM->TO belum terkonfirmasi.

    Empat baris pertama dari spesifikasi; sisanya dilengkapi. NONE = belum ada
    regime terkonfirmasi (awal data).
    """
    return {
        "PERSISTENT->RANDOM_LIKE": "BLOCK_ALL",
        "PERSISTENT->ANTI_PERSISTENT": "BLOCK_LONG",
        "ANTI_PERSISTENT->PERSISTENT": "WAIT_NEW_BIAS",
        "RANDOM_LIKE->PERSISTENT": "WAIT_NEW_BIAS",
        "RANDOM_LIKE->ANTI_PERSISTENT": "BLOCK_ALL",
        "ANTI_PERSISTENT->RANDOM_LIKE": "BLOCK_ALL",
        "PERSISTENT->UNCERTAIN": "BLOCK_ALL",
        "RANDOM_LIKE->UNCERTAIN": "BLOCK_ALL",
        "ANTI_PERSISTENT->UNCERTAIN": "BLOCK_ALL",
        "UNCERTAIN->PERSISTENT": "WAIT_NEW_BIAS",
        "UNCERTAIN->RANDOM_LIKE": "BLOCK_ALL",
        "UNCERTAIN->ANTI_PERSISTENT": "BLOCK_ALL",
        "NONE->PERSISTENT": "WAIT_NEW_BIAS",
        "NONE->RANDOM_LIKE": "WAIT_NEW_BIAS",
        "NONE->ANTI_PERSISTENT": "WAIT_NEW_BIAS",
        "NONE->UNCERTAIN": "WAIT_NEW_BIAS",
    }


class ContextConfig(BaseModel):
    """Regime context 4H x 1H dan konteks yang mengizinkan bias terbentuk."""

    table: Dict[str, Dict[str, str]] = Field(default_factory=_default_context_table)
    bias_allowed_contexts: list = Field(default_factory=lambda: ["SUPPORTIVE"])

    @field_validator("table")
    @classmethod
    def _complete(cls, v: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        if set(v) != set(REGIME_KEYS):
            raise ValueError(f"context.table harus memuat baris {REGIME_KEYS}")
        for row, cols in v.items():
            if set(cols) != set(REGIME_KEYS):
                raise ValueError(f"context.table[{row}] harus memuat kolom {REGIME_KEYS}")
            for col, val in cols.items():
                if val not in CONTEXT_VALUES:
                    raise ValueError(f"context.table[{row}][{col}]={val!r} bukan {CONTEXT_VALUES}")
        return v

    @field_validator("bias_allowed_contexts")
    @classmethod
    def _allowed(cls, v: list) -> list:
        if not v or any(x not in ("SUPPORTIVE", "NEUTRAL") for x in v):
            raise ValueError("context.bias_allowed_contexts hanya boleh SUPPORTIVE/NEUTRAL (CONFLICT tidak)")
        return v


class TransitionConfig(BaseModel):
    """Filter transisi regime. Transisi selalu dicatat, apa pun parameternya."""

    rules: Dict[str, str] = Field(default_factory=_default_transition_rules)
    confirm_predictions: int = 2          # regime baru sah setelah N prediksi berturut-turut
    timeframes: list = Field(default_factory=lambda: ["regime", "bias"])  # skala yang dipantau

    @field_validator("rules")
    @classmethod
    def _rules(cls, v: Dict[str, str]) -> Dict[str, str]:
        need = {
            f"{a}->{b}" for a in ("NONE",) + REGIME_KEYS for b in REGIME_KEYS if a != b
        }
        missing = need - set(v)
        if missing:
            raise ValueError(f"transition.rules belum lengkap: {sorted(missing)}")
        extra = set(v) - need
        if extra:
            raise ValueError(f"transition.rules memuat kunci tak dikenal: {sorted(extra)}")
        bad = {k: s for k, s in v.items() if s not in TRANSITION_STATUSES}
        if bad:
            raise ValueError(f"status transisi tidak valid: {bad}")
        return v

    @field_validator("confirm_predictions")
    @classmethod
    def _confirm(cls, v: int) -> int:
        if not (1 <= v <= 20):
            raise ValueError("transition.confirm_predictions harus 1 - 20")
        return v

    @field_validator("timeframes")
    @classmethod
    def _tfs(cls, v: list) -> list:
        if not v or any(x not in ("regime", "bias") for x in v):
            raise ValueError("transition.timeframes berisi 'regime' dan/atau 'bias'")
        return v


class BiasConfig(BaseModel):
    """Directional bias 1H. Ambang OFI/CVD memakai `confirmation.*`. Default Mode A."""

    use_ofi: bool = False   # Mode A: False; jika True cek OFI 1H
    use_cvd: bool = False   # Mode A: False; jika True cek CVD 1H


class WalkForwardConfig(BaseModel):
    """Jendela walk-forward kronologis. Model existing TIDAK dilatih ulang."""

    train_period: str = "12M"       # informasi konteks; tidak dipakai untuk retrain
    validation_period: str = "3M"
    test_period: str = "1M"         # panjang tiap jendela evaluasi out-of-sample
    step_period: str = "1M"         # pergeseran antar jendela
    anchor: str = "oos"             # oos: jendela hanya di rentang out-of-sample model

    @field_validator("train_period", "validation_period", "test_period", "step_period")
    @classmethod
    def _period(cls, v: str) -> str:
        parse_period(v)
        return v.upper()

    @field_validator("anchor")
    @classmethod
    def _anchor(cls, v: str) -> str:
        if v not in {"oos", "full"}:
            raise ValueError("walk_forward.anchor harus 'oos' atau 'full'")
        return v


class SetupEngineConfig(BaseModel):
    timeframes: TimeframeConfig = Field(default_factory=TimeframeConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    structure: StructureConfig = Field(default_factory=StructureConfig)
    confirmation: ConfirmationConfig = Field(default_factory=ConfirmationConfig)
    regime: RegimeSourceConfig = Field(default_factory=RegimeSourceConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    transition: TransitionConfig = Field(default_factory=TransitionConfig)
    bias: BiasConfig = Field(default_factory=BiasConfig)
    walk_forward: WalkForwardConfig = Field(default_factory=WalkForwardConfig)

    model_config = {"extra": "forbid"}

    def canonical(self) -> Dict[str, Any]:
        return json.loads(self.model_dump_json())

    @property
    def setup_hash(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def flat(self) -> Dict[str, Any]:
        """Nama parameter sesuai dokumen spesifikasi (huruf besar)."""
        return {
            "SETUP_TIMEFRAME": self.timeframes.setup,
            "BIAS_TIMEFRAME": self.timeframes.bias,
            "REGIME_TIMEFRAME": self.timeframes.regime,
            "RESOLUTION_TIMEFRAME": self.timeframes.resolution,
            "RR": self.risk.rr,
            "MAX_OPEN_POSITIONS": self.execution.max_open_positions,
            "MAX_SETUP_WAIT_BARS": self.execution.max_setup_wait_bars,
            "MAX_HOLDING_BARS": self.execution.max_holding_bars,
            "TAKER_FEE_PCT": self.execution.taker_fee_pct,
            "SLIPPAGE_TICKS": self.execution.slippage_ticks,
            "TICK_SIZE": self.execution.tick_size,
            "USE_OFI_CONFIRMATION": self.confirmation.use_ofi,
            "USE_CVD_CONFIRMATION": self.confirmation.use_cvd,
            "CONFIRMATION_REQUIRED": self.confirmation.required,
            "SWING_LOOKBACK": self.structure.swing_lookback,
            "SL_BUFFER": self.risk.sl_buffer,
            "ALLOW_ENTRY_DURING_TRANSITION": self.regime.allow_entry_during_transition,
            "OFI_THRESHOLD": self.confirmation.ofi_threshold,
            "CVD_SLOPE_THRESHOLD": self.confirmation.cvd_slope_threshold,
            "CVD_LOOKBACK": self.confirmation.cvd_lookback,
            "MIN_RISK_DISTANCE_PCT": self.risk.min_risk_distance_pct,
            "TRANSITION_CONFIRM_PREDICTIONS": self.transition.confirm_predictions,
            "TRAIN_PERIOD": self.walk_forward.train_period,
            "VALIDATION_PERIOD": self.walk_forward.validation_period,
            "TEST_PERIOD": self.walk_forward.test_period,
            "STEP_PERIOD": self.walk_forward.step_period,
        }


def load_setup_config(path: Optional[Path] = None) -> SetupEngineConfig:
    """Muat dan validasi `setup_engine.yaml`; default bila file tidak ada."""
    target = path or SETUP_CONFIG_PATH
    if not target.exists():
        return SetupEngineConfig()
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return SetupEngineConfig(**raw)


@lru_cache(maxsize=1)
def get_setup_config() -> SetupEngineConfig:
    return load_setup_config()

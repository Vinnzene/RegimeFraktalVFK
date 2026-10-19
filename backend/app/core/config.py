"""Loader config.yaml + perhitungan config_hash.

config.yaml adalah satu-satunya sumber parameter. Hash SHA-256 dihitung dari
representasi kanonik (JSON terurut) sehingga stabil terhadap perubahan urutan
key atau komentar, tapi berubah begitu ada nilai parameter yang berbeda.
Hash inilah yang ditempel di footer setiap panel frontend agar setiap angka
di dashboard bisa ditelusuri ke konfigurasi yang menghasilkannya.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"

REGIME_CLASSES: List[str] = ["persistent", "random_like", "anti_persistent"]
REGIME_CATEGORIES: List[str] = REGIME_CLASSES + ["uncertain_rule", "uncertain_lowconf"]


class DataConfig(BaseModel):
    symbol: str = "BTCUSDT"
    timeframes: List[str] = Field(default_factory=lambda: ["1h", "4h"])
    start: Optional[str] = None
    end: Optional[str] = None


class SourceConfig(BaseModel):
    """Sumber data pasar.

    `drop_open_bar` sengaja divalidasi keras: bar yang belum tutup membuat nilai
    Hurst dan label regime pada window terakhir berubah setiap refresh, sehingga
    tampilan bisa berkedip di tengah sidang.
    """

    provider: str = "binance"
    base_urls: List[str] = Field(
        default_factory=lambda: [
            "https://data-api.binance.vision",
            "https://api.binance.com",
        ]
    )
    years: float = 3.0
    drop_open_bar: bool = True
    auto_refresh: bool = True
    refresh_minutes: int = 15

    @field_validator("drop_open_bar")
    @classmethod
    def _must_drop_open_bar(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "source.drop_open_bar harus true. Bar berjalan belum final, "
                "memakainya membuat label regime tidak stabil."
            )
        return v

    @field_validator("years")
    @classmethod
    def _years_range(cls, v: float) -> float:
        if not (0.1 <= v <= 10.0):
            raise ValueError("source.years harus di rentang 0.1 - 10.0")
        return v

    @field_validator("refresh_minutes")
    @classmethod
    def _refresh_range(cls, v: int) -> int:
        if not (1 <= v <= 1440):
            raise ValueError("source.refresh_minutes harus di rentang 1 - 1440")
        return v


class AnalysisConfig(BaseModel):
    L: int = 500
    J: int = 4
    stride_bars: int = 4
    threshold_mode: str = "quantile"
    threshold_quantiles: List[float] = Field(default_factory=lambda: [1 / 3, 2 / 3])
    hurst_threshold: List[float] = Field(default_factory=lambda: [0.45, 0.55])
    dfa_threshold: List[float] = Field(default_factory=lambda: [0.45, 0.55])
    input: str = "log_return"

    @field_validator("threshold_mode")
    @classmethod
    def _known_mode(cls, v: str) -> str:
        if v not in {"fixed", "quantile"}:
            raise ValueError("analysis.threshold_mode harus 'fixed' atau 'quantile'")
        return v

    @field_validator("threshold_quantiles")
    @classmethod
    def _quantile_pair(cls, v: List[float]) -> List[float]:
        if len(v) != 2 or not (0.0 < v[0] < v[1] < 1.0):
            raise ValueError("analysis.threshold_quantiles harus [lower, upper] di (0, 1)")
        return v

    @field_validator("stride_bars")
    @classmethod
    def _stride_range(cls, v: int) -> int:
        if not (1 <= v <= 500):
            raise ValueError("analysis.stride_bars harus di rentang 1 - 500")
        return v

    @field_validator("input")
    @classmethod
    def _must_be_log_return(cls, v: str) -> str:
        # Harga level punya unit root: estimasi Hurst akan selalu ~0.9-1.0 dan
        # seluruh window terklasifikasi Persistent. Guard ini disengaja keras.
        if v != "log_return":
            raise ValueError(
                "analysis.input harus 'log_return'. Harga level menghasilkan "
                "H ~ 0.9-1.0 untuk semua window (unit root)."
            )
        return v

    @field_validator("hurst_threshold", "dfa_threshold")
    @classmethod
    def _threshold_pair(cls, v: List[float]) -> List[float]:
        if len(v) != 2 or not (0.0 < v[0] < v[1] < 1.0):
            raise ValueError("threshold harus [lower, upper] dengan 0 < lower < upper < 1")
        return v


class ModelConfig(BaseModel):
    h: int = 500
    stride: int = 1
    purge_gap: int = 1000
    tau: float = 0.5
    seed: int = 42

    @field_validator("tau")
    @classmethod
    def _tau_range(cls, v: float) -> float:
        # Batas bawah 1/3 karena softmax 3 kelas: max(P) tidak pernah < 1/3.
        if not (1.0 / 3.0 <= v <= 1.0):
            raise ValueError("model.tau harus di rentang [0.334, 1.0] untuk softmax 3 kelas")
        return v


class SplitConfig(BaseModel):
    ratios: List[float] = Field(default_factory=lambda: [0.7, 0.15, 0.15])

    @field_validator("ratios")
    @classmethod
    def _sum_to_one(cls, v: List[float]) -> List[float]:
        if len(v) != 3 or abs(sum(v) - 1.0) > 1e-9:
            raise ValueError("split.ratios harus 3 angka dengan jumlah 1.0")
        return v


class RuntimeConfig(BaseModel):
    use_mock: bool = True
    storage: str = "parquet"

    @field_validator("storage")
    @classmethod
    def _known_storage(cls, v: str) -> str:
        if v not in {"parquet", "postgres"}:
            raise ValueError("runtime.storage harus 'parquet' atau 'postgres'")
        return v


class AppConfig(BaseModel):
    data: DataConfig = Field(default_factory=DataConfig)
    source: SourceConfig = Field(default_factory=SourceConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    split: SplitConfig = Field(default_factory=SplitConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    def canonical(self) -> Dict[str, Any]:
        return json.loads(self.model_dump_json())

    @property
    def config_hash(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @property
    def short_hash(self) -> str:
        return self.config_hash[:12]


def load_config(path: Path | None = None) -> AppConfig:
    target = path or CONFIG_PATH
    if not target.exists():
        return AppConfig()
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return AppConfig(**raw)


@lru_cache(maxsize=1)
def _cached_config() -> AppConfig:
    return load_config()


# Override eksplisit, dipakai test agar tidak menembak jaringan atau menimpa
# data produksi. Pemeriksaan dilakukan di dalam get_config() supaya modul yang
# mengimpor fungsi ini secara langsung tetap melihat nilai yang sama.
_override: Optional[AppConfig] = None


def set_config_override(config: Optional[AppConfig]) -> None:
    global _override
    _override = config


def get_config() -> AppConfig:
    if _override is not None:
        return _override
    return _cached_config()


def reload_config() -> AppConfig:
    _cached_config.cache_clear()
    return get_config()

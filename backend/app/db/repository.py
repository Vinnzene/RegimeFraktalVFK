"""Abstraksi penyimpanan.

Seluruh router HANYA berbicara ke interface `Repository`. Fase 1 memakai
`ParquetRepository` (tanpa Postgres, tanpa service db di docker-compose).
Saat data exchange asli & scheduler masuk (roadmap M1+), cukup tambahkan
`PostgresRepository` dengan interface sama — router tidak perlu diubah.
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd

from app.core.config import PROCESSED_DIR, AppConfig, get_config
from app.mock.generator import generate_ohlcv
from app.services.data_ingestion import (
    OHLCV_COLUMNS as INGESTION_OHLCV_COLUMNS,
)
from app.services.data_ingestion import (
    IngestionError,
    ensure_schema,
    fetch_klines,
    fetch_latest,
    merge_ohlcv,
)
from app.services.hurst_dfa import rolling_hurst_dfa, to_log_return
from app.services.regime_labeling import label_series

# Skema kolom diambil dari data_ingestion agar hanya ada satu definisi.
# Mendefinisikannya ulang di sini pernah membuat kolom order flow hilang saat
# penyimpanan, padahal ingestion sudah mengambilnya.
OHLCV_COLUMNS = INGESTION_OHLCV_COLUMNS

REGIME_COLUMNS = [
    "time",
    "index",
    "close",
    "hurst",
    "dfa_alpha",
    "regime",
    "effective_window",
    "stride_bars",
    "hurst_lower",
    "hurst_upper",
    "dfa_lower",
    "dfa_upper",
    "threshold_mode",
]

_SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{1,20}$")

# Callback yang dijalankan saat OHLCV berubah. Router mendaftarkan cache-nya
# di sini supaya hasil turunan tidak menyajikan angka dari data lama.
_INVALIDATION_HOOKS: List[callable] = []  # type: ignore[valid-type]


def register_invalidation_hook(fn) -> None:
    if fn not in _INVALIDATION_HOOKS:
        _INVALIDATION_HOOKS.append(fn)


def run_invalidation_hooks(symbol: str, timeframe: str) -> None:
    for fn in _INVALIDATION_HOOKS:
        try:
            fn(symbol, timeframe)
        except Exception:  # noqa: BLE001 - invalidasi tidak boleh menggagalkan refresh
            continue


class InvalidIdentifier(ValueError):
    """symbol atau timeframe tidak lolos validasi."""


def validate_identifiers(symbol: str, timeframe: str, config: AppConfig) -> Tuple[str, str]:
    """Validasi sebelum nilai apa pun menyentuh filesystem.

    Tanpa ini, `symbol` dari query string masuk langsung ke nama file dan bisa
    keluar dari data/processed/ lewat komponen '..'. Selain itu setiap symbol
    baru memicu generate + compute_regime penuh, sehingga nilai bebas juga
    menjadi jalur pengurasan disk dan CPU.
    """
    if not _SYMBOL_RE.match(symbol or ""):
        raise InvalidIdentifier(
            f"symbol '{symbol}' tidak valid — hanya huruf/angka, maksimal 20 karakter."
        )
    if timeframe not in config.data.timeframes:
        raise InvalidIdentifier(
            f"timeframe '{timeframe}' tidak dikenal — pilih {config.data.timeframes}."
        )
    return symbol.upper(), timeframe


class Repository(ABC):
    """Kontrak penyimpanan yang dipakai seluruh router."""

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str) -> pd.DataFrame: ...

    @abstractmethod
    def save_ohlcv(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None: ...

    @abstractmethod
    def get_regime(self, symbol: str, timeframe: str) -> pd.DataFrame: ...

    @abstractmethod
    def save_regime(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None: ...

    @abstractmethod
    def has_ohlcv(self, symbol: str, timeframe: str) -> bool: ...

    @abstractmethod
    def refresh_ohlcv(self, symbol: str, timeframe: str, full: bool = False) -> Dict[str, object]: ...

    @abstractmethod
    def data_status(self, symbol: str, timeframe: str) -> Dict[str, object]: ...


class ParquetRepository(Repository):
    """Implementasi berbasis file Parquet di data/processed/."""

    def __init__(self, base_dir: Path | None = None, config: AppConfig | None = None) -> None:
        self.base_dir = base_dir or PROCESSED_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or get_config()
        # Memo satu proses: beberapa endpoint dalam satu page-load meminta
        # regime yang sama; tanpa ini pipeline Hurst/DFA berjalan berulang.
        self._regime_memo: Dict[Tuple[str, str, str], pd.DataFrame] = {}

    def _path(self, kind: str, symbol: str, timeframe: str) -> Path:
        symbol, timeframe = validate_identifiers(symbol, timeframe, self.config)
        path = (self.base_dir / f"{kind}_{symbol.lower()}_{timeframe}.parquet").resolve()
        base = self.base_dir.resolve()
        # Sabuk pengaman kedua: walau regex sudah menolak '..', batas direktori
        # tetap diperiksa agar perubahan validator di masa depan tidak diam-diam
        # membuka path traversal.
        if base not in path.parents:
            raise InvalidIdentifier("path hasil resolusi keluar dari data/processed.")
        return path

    def has_ohlcv(self, symbol: str, timeframe: str) -> bool:
        return self._path("ohlcv", symbol, timeframe).exists()

    def _meta_path(self, symbol: str, timeframe: str) -> Path:
        return self._path("ohlcv", symbol, timeframe).with_suffix(".meta.json")

    def read_meta(self, symbol: str, timeframe: str) -> Dict[str, object]:
        path = self._meta_path(symbol, timeframe)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}

    def write_meta(self, symbol: str, timeframe: str, meta: Dict[str, object]) -> None:
        self._meta_path(symbol, timeframe).write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

    def get_ohlcv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        path = self._path("ohlcv", symbol, timeframe)
        if not path.exists():
            if self.config.runtime.use_mock:
                df = generate_ohlcv(timeframe, seed=self.config.model.seed)
                self.save_ohlcv(symbol, timeframe, df)
                self.write_meta(
                    symbol,
                    timeframe,
                    {"source": "mock", "rows": len(df), "fetched_at": int(time.time())},
                )
                return df
            # Data asli belum pernah ditarik: ambil sekarang agar dashboard
            # tidak kosong pada penggunaan pertama.
            self.refresh_ohlcv(symbol, timeframe, full=True)
            return pd.read_parquet(path)
        return pd.read_parquet(path)

    def save_ohlcv(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        # Kolom order flow ditambahkan belakangan; berkas lama yang belum
        # memilikinya diisi nol agar skema tetap seragam tanpa perlu migrasi.
        out = df.copy()
        for col in OHLCV_COLUMNS:
            if col not in out.columns:
                out[col] = 0.0
        out[OHLCV_COLUMNS].to_parquet(self._path("ohlcv", symbol, timeframe), index=False)

    def has_orderflow(self, symbol: str, timeframe: str) -> bool:
        """Apakah data tersimpan sudah memuat kolom order flow yang terisi."""
        try:
            df = self.get_ohlcv(symbol, timeframe)
        except Exception:  # noqa: BLE001
            return False
        if "taker_buy_volume" not in df.columns:
            return False
        return bool((df["taker_buy_volume"] > 0).any())

    def refresh_ohlcv(
        self, symbol: str, timeframe: str, full: bool = False
    ) -> Dict[str, object]:
        """Tarik data terbaru dari sumber dan gabungkan ke data tersimpan.

        `full=True` menarik ulang seluruh rentang `source.years`; selain itu
        hanya bar terakhir yang diambil lalu digabung, jauh lebih ringan untuk
        refresh berkala.
        """
        symbol, timeframe = validate_identifiers(symbol, timeframe, self.config)
        cfg = self.config

        if cfg.runtime.use_mock:
            df = generate_ohlcv(timeframe, seed=cfg.model.seed)
            self.save_ohlcv(symbol, timeframe, df)
            meta: Dict[str, object] = {
                "source": "mock",
                "rows": len(df),
                "fetched_at": int(time.time()),
                "last_bar_time": int(df["time"].iloc[-1]),
            }
            self.write_meta(symbol, timeframe, meta)
            self._invalidate(symbol, timeframe)
            return meta

        path = self._path("ohlcv", symbol, timeframe)
        existing = pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=OHLCV_COLUMNS)
        need_full = full or existing.empty

        if need_full:
            incoming, report = fetch_klines(
                symbol=symbol,
                timeframe=timeframe,
                years=cfg.source.years,
                base_urls=cfg.source.base_urls,
                drop_open_bar=cfg.source.drop_open_bar,
                start=cfg.data.start,
            )
        else:
            incoming, report = fetch_latest(
                symbol=symbol,
                timeframe=timeframe,
                base_urls=cfg.source.base_urls,
                drop_open_bar=cfg.source.drop_open_bar,
            )

        merged = merge_ohlcv(existing, incoming)
        added = len(merged) - len(existing)
        self.save_ohlcv(symbol, timeframe, merged)

        meta = report.to_dict()
        meta.update(
            {
                "rows": len(merged),
                "rows_added": added,
                "invalidated": added > 0,
                "first_time": int(merged["time"].iloc[0]),
                "last_time": int(merged["time"].iloc[-1]),
                "mode": "full" if need_full else "incremental",
            }
        )
        self.write_meta(symbol, timeframe, meta)
        # Hanya batalkan cache bila benar-benar ada bar baru. Scheduler berjalan
        # tiap beberapa menit sementara bar 1H hanya tutup sekali per jam, jadi
        # sebagian besar putaran tidak menambah data. Membatalkan cache tanpa
        # alasan memaksa perhitungan ulang Hurst/DFA untuk puluhan ribu window
        # (~60 detik) dan membuat dashboard tampak kosong saat dibuka.
        if added > 0:
            self._invalidate(symbol, timeframe)
        return meta

    def data_status(self, symbol: str, timeframe: str) -> Dict[str, object]:
        """Ringkasan kesegaran data untuk ditampilkan di UI."""
        symbol, timeframe = validate_identifiers(symbol, timeframe, self.config)
        meta = self.read_meta(symbol, timeframe)
        path = self._path("ohlcv", symbol, timeframe)
        now = int(time.time())

        last_bar = meta.get("last_time") or meta.get("last_bar_time")
        age_seconds = (now - int(cast(Any, last_bar))) if last_bar else None
        bar_seconds = 3600 if timeframe == "1h" else 14400
        # Toleransi 2 bar: satu bar berjalan (memang dibuang) plus jeda scheduler.
        stale = age_seconds is not None and age_seconds > bar_seconds * 2

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "available": path.exists(),
            "source": meta.get("source", "unknown"),
            "base_url": meta.get("base_url"),
            "rows": meta.get("rows"),
            "first_time": meta.get("first_time"),
            "last_time": last_bar,
            "fetched_at": meta.get("fetched_at"),
            "age_seconds": age_seconds,
            "stale": stale,
            "dropped_open_bar": meta.get("dropped_open_bar"),
            "is_mock": self.config.runtime.use_mock,
            "server_time": now,
        }

    def _invalidate(self, symbol: str, timeframe: str) -> None:
        """Buang turunan di memori yang dihitung dari OHLCV lama.

        Berkas regime di disk sengaja TIDAK dihapus. Dulu dihapus, sehingga
        setiap bar baru — sekali per jam pada 1H — memaksa perhitungan ulang
        Hurst/DFA atas seluruh ~17 ribu window (~40 detik), dan pengunjung
        berikutnya menunggu selama itu. Berkas lama kini dipakai sebagai dasar
        perhitungan incremental; kebasiannya dideteksi di `get_regime` lewat
        sidik jari data sumber, bukan lewat ada-tidaknya berkas.
        """
        self._regime_memo.pop((symbol, timeframe, self.config.config_hash), None)
        run_invalidation_hooks(symbol, timeframe)

    def get_regime(self, symbol: str, timeframe: str) -> pd.DataFrame:
        symbol, timeframe = validate_identifiers(symbol, timeframe, self.config)
        key = (symbol, timeframe, self.config.config_hash)
        if key in self._regime_memo:
            return self._regime_memo[key]

        path = self._path("regime", symbol, timeframe)
        previous: Optional[pd.DataFrame] = None
        if path.exists():
            cached = pd.read_parquet(path)
            if cached.attrs.get("config_hash") == self.config.config_hash:
                n_bars = len(self.get_ohlcv(symbol, timeframe))
                if cached.attrs.get("n_bars") == n_bars:
                    self._regime_memo[key] = cached
                    return cached
                previous = cached

        df = self.compute_regime(symbol, timeframe, previous=previous)
        self.save_regime(symbol, timeframe, df)
        self._regime_memo[key] = df
        return df

    def save_regime(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        # config_hash disimpan di attrs; pyarrow mempertahankannya lewat
        # metadata Parquet sehingga hasil dari konfigurasi berbeda tidak
        # saling menimpa saat dibaca ulang. n_bars ikut disimpan untuk
        # mendeteksi hasil yang tertinggal dari data OHLCV terbaru.
        df.attrs["config_hash"] = self.config.config_hash
        df.to_parquet(self._path("regime", symbol, timeframe), index=False)

    @staticmethod
    def _reusable_metrics(
        previous: Optional[pd.DataFrame],
        ohlcv: pd.DataFrame,
        window: int,
        step: int,
    ) -> Optional[pd.DataFrame]:
        """Ambil H/alpha lama yang masih sah untuk data OHLCV sekarang.

        Nilai Hurst dan DFA pada indeks t hanya bergantung pada data <= t
        (causal), sehingga baris lama tetap benar selama bar yang mendasarinya
        tidak berubah. Tiga syarat diperiksa; bila satu saja gagal, hasil lama
        dibuang dan perhitungan penuh dijalankan:

        1. window dan stride sama — keduanya menentukan posisi window.
        2. Waktu dan harga penutupan setiap baris lama cocok dengan OHLCV
           sekarang. Ini menangkap riwayat yang ditarik ulang atau digeser,
           misalnya refresh penuh dengan tanggal awal berbeda.
        3. Deret tidak memendek.

        Label TIDAK diambil dari hasil lama: pada threshold_mode = quantile,
        ambang dihitung dari distribusi seluruh deret, jadi label lama bisa
        bergeser begitu window baru masuk. Yang dipakai ulang hanya H dan
        alpha; pelabelan selalu diulang atas seluruh deret (murah).
        """
        if previous is None or previous.empty:
            return None
        try:
            if int(previous["effective_window"].iloc[0]) != window:
                return None
            if int(previous["stride_bars"].iloc[0]) != step:
                return None
        except (KeyError, ValueError, TypeError):
            return None

        bar_idx = previous["index"].to_numpy().astype(int) + 1
        if bar_idx.size == 0 or bar_idx.max() >= len(ohlcv):
            return None
        times = ohlcv["time"].to_numpy()[bar_idx]
        closes = ohlcv["close"].to_numpy()[bar_idx]
        if not np.array_equal(times, previous["time"].to_numpy()):
            return None
        if not np.allclose(closes, previous["close"].to_numpy(), rtol=0, atol=1e-9):
            return None
        return previous[["index", "hurst", "dfa_alpha"]].reset_index(drop=True)

    def compute_regime(
        self,
        symbol: str,
        timeframe: str,
        previous: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Pipeline label ground truth: harga -> log-return -> rolling H/alpha -> label.

        Bila `previous` diberikan dan masih sah, hanya window baru yang
        dihitung. Tanpa ini setiap bar baru memicu perhitungan ulang ~17 ribu
        window (~40 detik pada 1H); dengan ini cukup beberapa window baru.
        """
        cfg = self.config
        ohlcv = self.get_ohlcv(symbol, timeframe)
        log_ret = to_log_return(ohlcv["close"].to_numpy())

        window = min(cfg.analysis.L, max(64, len(log_ret) // 4))
        step = max(1, cfg.analysis.stride_bars)

        reused = self._reusable_metrics(previous, ohlcv, window, step)
        if reused is not None:
            last = int(reused["index"].iloc[-1])
            new_positions = list(range(last + step, len(log_ret), step))
            fresh = (
                rolling_hurst_dfa(log_ret, window=window, positions=new_positions)
                if new_positions
                else pd.DataFrame(columns=["index", "hurst", "dfa_alpha"])
            )
            metrics = (
                pd.concat([reused, fresh], ignore_index=True) if len(fresh) else reused
            )
        else:
            metrics = rolling_hurst_dfa(log_ret, window=window, step=step)

        if metrics.empty:
            # Skema penuh, bukan sebagian: konsumen di router menyeleksi kolom
            # close/effective_window/stride_bars dan akan KeyError bila hilang.
            empty = pd.DataFrame(columns=REGIME_COLUMNS)
            empty.attrs["config_hash"] = cfg.config_hash
            empty.attrs["n_bars"] = len(ohlcv)
            return empty

        labeled = label_series(
            metrics,
            cfg.analysis.hurst_threshold,
            cfg.analysis.dfa_threshold,
            mode=cfg.analysis.threshold_mode,
            quantiles=cfg.analysis.threshold_quantiles,
        )
        # +1 karena log-return memangkas satu bar di awal.
        bar_idx = (labeled["index"].to_numpy() + 1).astype(int)
        labeled["time"] = ohlcv["time"].to_numpy()[bar_idx]
        labeled["close"] = ohlcv["close"].to_numpy()[bar_idx]
        labeled["effective_window"] = window
        # stride_bars = jarak antar-baris hasil dalam satuan BAR. Wajib ikut
        # disimpan: purge_gap dan horizon h dinyatakan dalam bar, sedangkan
        # DataFrame ini berindeks window. Tanpa angka ini, konversi satuan di
        # router hanya bisa ditebak — dan tebakannya pernah salah.
        labeled["stride_bars"] = step
        result = labeled[REGIME_COLUMNS]
        result.attrs["config_hash"] = cfg.config_hash
        result.attrs["n_bars"] = len(ohlcv)
        return result


_repository: Optional[Repository] = None


def get_repository() -> Repository:
    """Factory sesuai runtime.storage. Postgres belum diimplementasi (fase M1+)."""
    global _repository
    if _repository is None:
        cfg = get_config()
        if cfg.runtime.storage == "postgres":
            raise NotImplementedError(
                "PostgresRepository belum ada. Fase 1 memakai storage: parquet."
            )
        _repository = ParquetRepository(config=cfg)
    return _repository


def reset_repository() -> None:
    global _repository
    _repository = None

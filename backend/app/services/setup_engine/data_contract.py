"""Data contract, normalisasi, dan alignment multi-timeframe tanpa look-ahead.

KONVENSI TIMESTAMP
==================
Seluruh frame di engine ini memakai konvensi yang sama dengan Binance dan
data existing project:

    timestamp    = waktu BUKA bar (open time), tz-aware UTC
    close_time   = timestamp + durasi timeframe (eksklusif)
    available_at = saat informasi bar/prediksi itu BOLEH dipakai

Untuk bar OHLCV:            available_at = close_time
Untuk prediksi regime:      available_at = close_time bar terakhir di window
                            (window Hurst-DFA/SWT berakhir di bar `index+1`,
                            yang timestamp-nya = kolom `time` pada artefak)

Keputusan pada bar timeframe rendah (LTF) dibuat di `close_time` bar itu.
Bar timeframe tinggi (HTF) hanya boleh dilekatkan ke bar LTF bila
`htf.available_at <= ltf.close_time`. Contoh 4H→30M:

    bar 4H 00:00–04:00  tersedia pukul 04:00
    bar 30M 03:30–04:00 (close 04:00) -> boleh memakai bar 4H 00:00 (sama-sama
                                         diketahui pada 04:00)
    bar 30M 00:00–00:30 (close 00:30) -> TIDAK boleh memakai bar 4H 00:00;
                                         yang dipakai bar 4H 20:00 hari sebelumnya

Memakai open time HTF sebagai kunci join akan membocorkan high/low/close dan
regime 4H ke empat jam pertama bar itu — kesalahan klasik backtest MTF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, cast

import numpy as np
import pandas as pd

from app.services.setup_engine.config import timeframe_seconds


class DataContractError(ValueError):
    """Frame tidak memenuhi data contract."""


class LookAheadError(RuntimeError):
    """Terdeteksi potensi pemakaian informasi masa depan."""


class Regime(str, Enum):
    """Label regime ternormalisasi.

    Tiga kelas utama sesuai penelitian. UNCERTAIN dipertahankan, bukan dibuang:
    label referensi Hurst-DFA memuat `uncertain_rule` dan post-processing tau
    menghasilkan `uncertain_lowconf`. Menghapusnya akan menyembunyikan
    ketidakpastian yang justru dilaporkan penelitian.
    """

    PERSISTENT = "PERSISTENT"
    RANDOM_LIKE = "RANDOM_LIKE"
    ANTI_PERSISTENT = "ANTI_PERSISTENT"
    UNCERTAIN = "UNCERTAIN"


_REGIME_ALIASES: Dict[str, Regime] = {
    "persistent": Regime.PERSISTENT,
    "random_like": Regime.RANDOM_LIKE,
    "randomlike": Regime.RANDOM_LIKE,
    "random": Regime.RANDOM_LIKE,
    "anti_persistent": Regime.ANTI_PERSISTENT,
    "antipersistent": Regime.ANTI_PERSISTENT,
    "uncertain": Regime.UNCERTAIN,
    "uncertain_rule": Regime.UNCERTAIN,
    "uncertain_lowconf": Regime.UNCERTAIN,
}


def normalize_regime(value: object) -> Regime:
    """Petakan berbagai penulisan regime ke enum `Regime`.

    Menerima 'Persistent', 'random-like', 'Random_Like', 'ANTI-PERSISTENT',
    'uncertain_rule', atau instance `Regime`. Nilai tak dikenal -> error,
    tidak diam-diam dijadikan UNCERTAIN.
    """
    if isinstance(value, Regime):
        return value
    if value is None or (isinstance(value, float) and np.isnan(value)):
        raise DataContractError("label regime kosong (None/NaN)")
    key = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if key in _REGIME_ALIASES:
        return _REGIME_ALIASES[key]
    upper = str(value).strip().upper()
    if upper in Regime.__members__:
        return Regime[upper]
    raise DataContractError(f"label regime tidak dikenal: {value!r}")


def normalize_regime_series(values: Iterable[object]) -> pd.Series:
    return pd.Series([normalize_regime(v).value for v in values], dtype="object")


# ---------------------------------------------------------------- contracts


@dataclass(frozen=True)
class FrameContract:
    name: str
    required: Tuple[str, ...]
    optional: Tuple[str, ...] = field(default_factory=tuple)


MARKET_CONTRACT = FrameContract(
    name="market",
    required=("timestamp", "timeframe", "open", "high", "low", "close", "volume", "ofi", "cvd"),
    optional=("buy_volume", "sell_volume", "delta_volume", "n_trades", "close_time", "available_at"),
)

REGIME_CONTRACT = FrameContract(
    name="regime",
    required=("timestamp", "timeframe", "predicted_regime"),
    optional=("confidence", "reference_regime", "close_time", "available_at", "evaluated"),
)

# Kontrak gabungan sesuai spesifikasi "input minimal" — dipakai untuk HTF
# (4H, 1H) setelah prediksi regime dilekatkan ke bar OHLCV.
CONTEXT_CONTRACT = FrameContract(
    name="context",
    required=MARKET_CONTRACT.required + ("predicted_regime",),
    optional=("confidence", "reference_regime", "regime_available_at"),
)


def to_utc_timestamp(values: pd.Series | Sequence, unit: Optional[str] = None) -> pd.Series:
    """Konversi ke datetime64[ns, UTC].

    - int/float: diinterpretasi epoch; unit ditebak dari besaran (s/ms/us)
      bila `unit` tidak diberikan.
    - datetime tz-aware: dikonversi ke UTC.
    - datetime naive: DITOLAK — zona waktunya tidak bisa dipastikan.
    """
    s = pd.Series(values)
    if pd.api.types.is_datetime64_any_dtype(s):
        if s.dt.tz is None:
            raise DataContractError(
                "timestamp naive (tanpa zona waktu) ditolak; berikan tz-aware atau epoch"
            )
        return s.dt.tz_convert("UTC")
    if pd.api.types.is_numeric_dtype(s):
        arr = s.to_numpy(dtype="int64")
        if unit is None:
            peak = int(np.abs(arr).max()) if arr.size else 0
            unit = "us" if peak > 10**15 else "ms" if peak > 10**12 else "s"
        return pd.Series(pd.to_datetime(arr, unit=unit, utc=True), index=s.index)
    parsed = pd.to_datetime(s, utc=False)
    if getattr(parsed.dt, "tz", None) is None:
        raise DataContractError("timestamp string tanpa zona waktu ditolak")
    return parsed.dt.tz_convert("UTC")


def validate_frame(df: pd.DataFrame, contract: FrameContract, timeframe: Optional[str] = None) -> pd.DataFrame:
    """Validasi frame terhadap kontrak; kembalikan salinan yang dirapikan.

    Pemeriksaan:
    1. kolom wajib ada,
    2. timestamp tz-aware UTC,
    3. monoton naik ketat (tanpa duplikat),
    4. timeframe tunggal dan dikenal,
    5. kolom harga/volume numerik dan finite; high >= max(open, close),
       low <= min(open, close) untuk kontrak market,
    6. kolom regime ternormalisasi ke enum.
    """
    missing = [c for c in contract.required if c not in df.columns]
    if missing:
        raise DataContractError(f"[{contract.name}] kolom wajib hilang: {missing}")

    out = df.copy()
    ts = out["timestamp"]
    if not pd.api.types.is_datetime64_any_dtype(ts) or ts.dt.tz is None:
        raise DataContractError(f"[{contract.name}] timestamp harus datetime tz-aware")
    if str(ts.dt.tz) != "UTC":
        out["timestamp"] = ts.dt.tz_convert("UTC")
    if out["timestamp"].duplicated().any():
        n = int(out["timestamp"].duplicated().sum())
        raise DataContractError(f"[{contract.name}] {n} timestamp duplikat")
    if not out["timestamp"].is_monotonic_increasing:
        raise DataContractError(f"[{contract.name}] timestamp tidak monoton naik")

    tfs = out["timeframe"].unique().tolist()
    if len(tfs) != 1:
        raise DataContractError(f"[{contract.name}] timeframe harus tunggal, ditemukan {tfs}")
    tf = str(tfs[0])
    timeframe_seconds(tf)
    if timeframe is not None and tf != timeframe:
        raise DataContractError(f"[{contract.name}] timeframe {tf} != yang diminta {timeframe}")

    if contract is MARKET_CONTRACT or contract is CONTEXT_CONTRACT:
        num = ["open", "high", "low", "close", "volume", "ofi", "cvd"]
        for c in num:
            if not pd.api.types.is_numeric_dtype(out[c]):
                raise DataContractError(f"[{contract.name}] kolom {c} harus numerik")
            if not np.isfinite(out[c].to_numpy(dtype=float)).all():
                raise DataContractError(f"[{contract.name}] kolom {c} memuat NaN/inf")
        o, h, l, c_ = (out[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
        tol = 1e-9 * np.maximum(1.0, np.abs(c_))
        if (h + tol < np.maximum(o, c_)).any() or (l - tol > np.minimum(o, c_)).any():
            raise DataContractError(f"[{contract.name}] high/low tidak konsisten dengan open/close")
        if (out["volume"].to_numpy(dtype=float) < 0).any():
            raise DataContractError(f"[{contract.name}] volume negatif")
        ofi = out["ofi"].to_numpy(dtype=float)
        if (np.abs(ofi) > 1 + 1e-9).any():
            raise DataContractError(f"[{contract.name}] OFI di luar [-1, 1]")

    for col in ("predicted_regime", "reference_regime"):
        if col in out.columns:
            mask = out[col].notna()
            out.loc[mask, col] = [normalize_regime(v).value for v in out.loc[mask, col]]
            if col == "predicted_regime" and not mask.all():
                raise DataContractError(f"[{contract.name}] predicted_regime memuat nilai kosong")

    if "confidence" in out.columns:
        conf = out["confidence"].to_numpy(dtype=float)
        finite = np.isfinite(conf)
        if ((conf[finite] < 0) | (conf[finite] > 1)).any():
            raise DataContractError(f"[{contract.name}] confidence di luar [0, 1]")

    step = pd.Timedelta(seconds=timeframe_seconds(tf))
    out["close_time"] = out["timestamp"] + step
    if "available_at" not in out.columns:
        out["available_at"] = out["close_time"]
    elif (out["available_at"] < out["close_time"]).any():
        raise LookAheadError(
            f"[{contract.name}] available_at lebih awal dari close_time bar — informasi belum final"
        )
    return out.reset_index(drop=True)


def detect_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Daftar celah antar bar (bar hilang) untuk dilaporkan, tidak diisi."""
    tf = str(df["timeframe"].iloc[0])
    step = pd.Timedelta(seconds=timeframe_seconds(tf))
    d = df["timestamp"].diff()
    idx = np.where(d > step)[0]
    return pd.DataFrame(
        {
            "gap_start": df["timestamp"].iloc[idx - 1].to_numpy() + step,
            "gap_end": df["timestamp"].iloc[idx].to_numpy(),
            "missing_bars": ((cast(Any, d.iloc[idx]) / step) - 1).astype(int).to_numpy(),
        }
    )


# ---------------------------------------------------------------- alignment


def align_htf_to_ltf(
    ltf: pd.DataFrame,
    htf: pd.DataFrame,
    columns: Sequence[str],
    prefix: str,
) -> pd.DataFrame:
    """Lekatkan kolom HTF ke setiap bar LTF tanpa look-ahead.

    Setiap bar LTF mendapat baris HTF TERAKHIR dengan
    `htf.available_at <= ltf.close_time`. Join memakai `merge_asof` arah
    backward pada waktu ketersediaan, BUKAN pada open time.

    Kolom hasil diberi awalan `prefix` (mis. 'h4_'), plus
    `{prefix}timestamp` dan `{prefix}available_at` untuk audit. Bar LTF yang
    belum punya HTF tersedia mendapat NaN.

    Setelah join, invarian diperiksa ulang dan `LookAheadError` dilempar bila
    ada satu baris pun yang melanggar.
    """
    for frame, name in ((ltf, "ltf"), (htf, "htf")):
        for c in ("timestamp", "close_time", "available_at"):
            if c not in frame.columns:
                raise DataContractError(f"{name} belum divalidasi: kolom {c} hilang")
    missing = [c for c in columns if c not in htf.columns]
    if missing:
        raise DataContractError(f"kolom HTF tidak ada: {missing}")

    right = htf[["timestamp", "available_at", *columns]].rename(
        columns={c: f"{prefix}{c}" for c in ("timestamp", "available_at", *columns)}
    )
    right = right.sort_values(f"{prefix}available_at", kind="mergesort")
    left = ltf.reset_index(drop=True).copy()
    left["_order"] = np.arange(len(left))
    left = left.sort_values("close_time", kind="mergesort")

    merged = pd.merge_asof(
        left,
        right,
        left_on="close_time",
        right_on=f"{prefix}available_at",
        direction="backward",
        allow_exact_matches=True,
    )
    merged = merged.sort_values("_order").drop(columns="_order").reset_index(drop=True)
    assert_no_lookahead_alignment(merged, prefix)
    return merged


def assert_no_lookahead_alignment(aligned: pd.DataFrame, prefix: str) -> None:
    """Invarian alignment: HTF yang dilekatkan sudah tersedia saat bar LTF close."""
    avail = aligned[f"{prefix}available_at"]
    ok = avail.isna() | (avail <= aligned["close_time"])
    if not ok.all():
        bad = aligned.loc[~ok, ["timestamp", "close_time", f"{prefix}available_at"]].head(3)
        raise LookAheadError(f"alignment {prefix} bocor ke masa depan:\n{bad}")


# ---------------------------------------------------------------- resampling


def resample_ohlcv(fine: pd.DataFrame, target_tf: str) -> pd.DataFrame:
    """Agregasi bar halus (tervalidasi) ke timeframe lebih kasar.

    Hanya bar target yang SEMUA sub-bar-nya ada yang dikeluarkan; bar tidak
    lengkap dibuang (dilaporkan lewat `detect_gaps`), bukan ditambal. Bar
    target selalu tertutup penuh, jadi tidak ada informasi parsial.
    """
    src_tf = str(fine["timeframe"].iloc[0])
    src_s, dst_s = timeframe_seconds(src_tf), timeframe_seconds(target_tf)
    if dst_s < src_s or dst_s % src_s:
        raise DataContractError(f"tidak bisa resample {src_tf} -> {target_tf}")
    need = dst_s // src_s
    key = fine["timestamp"].dt.floor(f"{dst_s}s")
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    for c in ("buy_volume", "sell_volume", "delta_volume", "n_trades"):
        if c in fine.columns:
            agg[c] = "sum"
    g = fine.groupby(key, sort=True)
    out = g.agg(agg)
    out["_n"] = g.size()
    if "cvd" in fine.columns:
        out["cvd"] = g["cvd"].last()
    out = out[out["_n"] == need].drop(columns="_n")
    out.index.name = "timestamp"
    out = out.reset_index()
    out["timeframe"] = target_tf
    if {"buy_volume", "sell_volume"} <= set(out.columns):
        tot = out["buy_volume"] + out["sell_volume"]
        out["ofi"] = np.where(tot > 0, (out["buy_volume"] - out["sell_volume"]) / tot.replace(0, np.nan), 0.0)
    return out


def choose_resolution_timeframe(
    requested: str,
    setup_tf: str,
    available: Iterable[str],
) -> Tuple[str, Optional[str]]:
    """Pilih timeframe resolusi outcome; fallback ke resolusi terdekat.

    Urutan: `requested` bila tersedia; jika tidak, timeframe tersedia TERHALUS
    yang lebih halus dari `setup_tf` dan membaginya rata; jika tidak ada,
    `setup_tf` sendiri. Dua kasus terakhir memberi pesan warning.

    Bila hasilnya sama dengan `setup_tf`, candle yang menyentuh TP dan SL
    sekaligus tidak dapat diurutkan dan akan berstatus AMBIGUOUS.
    """
    avail = set(available)
    setup_s = timeframe_seconds(setup_tf)
    if requested in avail:
        return requested, None
    finer = sorted(
        (tf for tf in avail if timeframe_seconds(tf) < setup_s and setup_s % timeframe_seconds(tf) == 0),
        key=timeframe_seconds,
    )
    if finer:
        tf = finer[0]
        return tf, (
            f"Data {requested} tidak tersedia; outcome memakai {tf}. "
            "Resolusi outcome lebih rendah dari yang direncanakan."
        )
    return setup_tf, (
        f"Data {requested} tidak tersedia dan tidak ada timeframe lebih halus dari {setup_tf}. "
        "Resolusi outcome lebih rendah: candle yang menyentuh TP dan SL sekaligus "
        "akan berstatus AMBIGUOUS."
    )


def summarize_frame(df: pd.DataFrame) -> Dict[str, object]:
    """Ringkasan untuk laporan eksplorasi."""
    gaps = detect_gaps(df)
    return {
        "timeframe": str(df["timeframe"].iloc[0]),
        "rows": len(df),
        "start": str(df["timestamp"].iloc[0]),
        "end": str(df["timestamp"].iloc[-1]),
        "gaps": len(gaps),
        "missing_bars": int(gaps["missing_bars"].sum()) if len(gaps) else 0,
        "columns": list(df.columns),
    }


def required_columns_report(df: pd.DataFrame, contract: FrameContract) -> Dict[str, List[str]]:
    return {
        "missing_required": [c for c in contract.required if c not in df.columns],
        "missing_optional": [c for c in contract.optional if c not in df.columns],
    }

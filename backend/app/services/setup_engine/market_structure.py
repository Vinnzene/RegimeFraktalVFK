"""Market structure objektif: swing pivot, HH/HL/LH/LL, Break of Structure.

Semua aturan mekanis dan deterministic; tidak ada penilaian visual.

SWING PIVOT (lookback k)
------------------------
Bar i adalah SWING HIGH bila

    high[i] >  max(high[i-k .. i-1])     (kiri: ketat)
    high[i] >= max(high[i+1 .. i+k])     (kanan: boleh sama)

dan SWING LOW bila

    low[i]  <  min(low[i-k .. i-1])
    low[i]  <= min(low[i+1 .. i+k])

Aturan tie-break (equal highs/lows): kiri ketat, kanan non-ketat. Pada
puncak/lembah datar (beberapa bar dengan nilai sama berurutan) hanya bar
PERTAMA yang menjadi pivot â€” bar berikutnya gagal syarat kiri ketat. Satu bar
boleh sekaligus swing high dan swing low (outside bar); keduanya dicatat.
Swing tidak dipaksa berselang-seling high/low.

KONFIRMASI (anti look-ahead)
----------------------------
Pivot i baru diketahui setelah k bar di kanannya selesai:

    confirmation_time = close_time[i + k]

Pada waktu t hanya swing dengan confirmation_time <= t yang boleh dipakai.
Pivot di k bar terakhir data belum terkonfirmasi dan tidak pernah dipakai.

KLASIFIKASI STRUKTUR pada waktu t
---------------------------------
Memakai DUA swing high terkonfirmasi terakhir dan DUA swing low terkonfirmasi
terakhir:

    BULLISH : last_high >  prev_high  DAN  last_low >  prev_low   (HH + HL)
    BEARISH : last_high <  prev_high  DAN  last_low <  prev_low   (LH + LL)
    NEUTRAL : selain itu (campuran, ada yang sama persis, atau swing < 2)

Swing yang sama persis (equal high / equal low) dihitung bukan HH maupun LH,
sehingga struktur menjadi NEUTRAL.

BREAK OF STRUCTURE (BOS)
------------------------
Level yang boleh ditembus bar j adalah swing terakhir yang SUDAH terkonfirmasi
saat bar j DIBUKA (confirmation_time <= timestamp[j]). Swing yang baru
terkonfirmasi di close bar j tidak dapat ditembus oleh bar j sendiri.

    bullish BOS : harga bar j  > level swing high terakhir
    bearish BOS : harga bar j  < level swing low terakhir

`mode="close"` memakai close bar j (diputuskan di close bar j);
`mode="wick"` memakai high/low bar j (sentuhan intrabar). Sama persis dengan
level BUKAN break. Setiap swing hanya dapat ditembus SEKALI; hanya swing
terakhir yang dipantau (swing lama yang belum tertembus diabaikan setelah
swing baru terkonfirmasi).

Catatan: bila data memiliki celah (bar hilang), indeks pivot dihitung per
baris, sedangkan waktu konfirmasi tetap diambil dari close_time bar ke-(i+k)
yang sebenarnya â€” tidak ada informasi masa depan yang dipakai.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from app.services.setup_engine.config import SetupEngineConfig, timeframe_seconds
from app.services.setup_engine.data_contract import DataContractError


class Structure(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class SwingKind(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"


@dataclass(frozen=True)
class Swing:
    kind: SwingKind
    pivot_index: int
    pivot_time: pd.Timestamp          # open time bar pivot
    price: float
    confirmation_index: int           # = pivot_index + lookback
    confirmation_time: pd.Timestamp   # close_time bar konfirmasi


@dataclass(frozen=True)
class StructureState:
    time: pd.Timestamp
    label: Structure
    last_high: Optional[Swing]
    prev_high: Optional[Swing]
    last_low: Optional[Swing]
    prev_low: Optional[Swing]


def detect_pivots(high: np.ndarray, low: np.ndarray, lookback: int) -> Tuple[np.ndarray, np.ndarray]:
    """Indeks swing high dan swing low (belum memperhitungkan waktu konfirmasi)."""
    if lookback < 1:
        raise ValueError("lookback harus >= 1")
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = high.size
    if low.size != n:
        raise ValueError("panjang high dan low berbeda")
    if not (np.isfinite(high).all() and np.isfinite(low).all()):
        raise ValueError("high/low memuat NaN/inf")
    k = lookback
    if n < 2 * k + 1:
        empty = np.empty(0, dtype=np.int64)
        return empty, empty
    hmax = sliding_window_view(high, k).max(axis=1)  # hmax[j] = max(high[j:j+k])
    lmin = sliding_window_view(low, k).min(axis=1)
    idx = np.arange(k, n - k)
    is_high = (high[idx] > hmax[idx - k]) & (high[idx] >= hmax[idx + 1])
    is_low = (low[idx] < lmin[idx - k]) & (low[idx] <= lmin[idx + 1])
    return idx[is_high].astype(np.int64), idx[is_low].astype(np.int64)


def classify_structure(
    last_high: Optional[float],
    prev_high: Optional[float],
    last_low: Optional[float],
    prev_low: Optional[float],
) -> Structure:
    """HH+HL -> BULLISH, LH+LL -> BEARISH, selain itu NEUTRAL."""
    if last_high is None or prev_high is None or last_low is None or prev_low is None:
        return Structure.NEUTRAL
    if last_high > prev_high and last_low > prev_low:
        return Structure.BULLISH
    if last_high < prev_high and last_low < prev_low:
        return Structure.BEARISH
    return Structure.NEUTRAL


def _ns(t: pd.Timestamp | str) -> int:
    ts = pd.Timestamp(t)
    if ts.tzinfo is None:
        raise DataContractError("waktu query harus tz-aware (UTC)")
    return ts.tz_convert("UTC").value


def _times_at(ts: pd.Series, idx: np.ndarray) -> pd.Series:
    """Timestamp pada indeks `idx` (âˆ’1 -> NaT), dtype selalu datetime64[ns, UTC]."""
    out = pd.Series(pd.NaT, index=range(idx.size), dtype="datetime64[ns, UTC]")
    ok = idx >= 0
    if ok.any():
        out[ok] = ts.to_numpy()[idx[ok]]
    return out


class MarketStructure:
    """Market structure untuk satu timeframe.

    Frame wajib memuat `timestamp` (open time, tz-aware), `high`, `low`,
    `close`, serta `close_time` atau `timeframe`. Frame hasil
    `data_contract.validate_frame` sudah memenuhi ini.
    """

    def __init__(self, df: pd.DataFrame, lookback: int = 3) -> None:
        for c in ("timestamp", "high", "low", "close"):
            if c not in df.columns:
                raise DataContractError(f"market structure butuh kolom {c}")
        ts = df["timestamp"]
        if not pd.api.types.is_datetime64_any_dtype(ts) or ts.dt.tz is None:
            raise DataContractError("timestamp harus datetime tz-aware")
        if not ts.is_monotonic_increasing or ts.duplicated().any():
            raise DataContractError("timestamp harus monoton naik tanpa duplikat")
        if "close_time" in df.columns:
            close_time = df["close_time"]
        elif "timeframe" in df.columns:
            close_time = ts + pd.Timedelta(seconds=timeframe_seconds(str(df["timeframe"].iloc[0])))
        else:
            raise DataContractError("butuh kolom close_time atau timeframe")

        self.lookback = int(lookback)
        self._ts = ts.dt.tz_convert("UTC").reset_index(drop=True)
        self._close_time = pd.Series(close_time).dt.tz_convert("UTC").reset_index(drop=True)
        self._open_ns = self._ts.astype("int64").to_numpy()
        self._close_ns = self._close_time.astype("int64").to_numpy()
        if (self._close_ns <= self._open_ns).any():
            raise DataContractError("close_time harus setelah timestamp")
        self._high = df["high"].to_numpy(dtype=float)
        self._low = df["low"].to_numpy(dtype=float)
        self._close = df["close"].to_numpy(dtype=float)

        hi, lo = detect_pivots(self._high, self._low, self.lookback)
        self._hi_idx, self._lo_idx = hi, lo
        self._hi_conf_ns = self._close_ns[hi + self.lookback] if hi.size else np.empty(0, np.int64)
        self._lo_conf_ns = self._close_ns[lo + self.lookback] if lo.size else np.empty(0, np.int64)

    @classmethod
    def from_config(cls, df: pd.DataFrame, cfg: SetupEngineConfig) -> "MarketStructure":
        return cls(df, lookback=cfg.structure.swing_lookback)

    # ---------------------------------------------------------- swings

    def _swing(self, kind: SwingKind, ordinal: int) -> Swing:
        idx = self._hi_idx if kind is SwingKind.HIGH else self._lo_idx
        i = int(idx[ordinal])
        c = i + self.lookback
        price = self._high[i] if kind is SwingKind.HIGH else self._low[i]
        return Swing(
            kind=kind,
            pivot_index=i,
            pivot_time=self._ts.iloc[i],
            price=float(price),
            confirmation_index=c,
            confirmation_time=self._close_time.iloc[c],
        )

    def swings_frame(self) -> pd.DataFrame:
        """Seluruh swing (terkonfirmasi di dalam data), urut waktu konfirmasi."""
        rows = [self._swing(SwingKind.HIGH, j) for j in range(self._hi_idx.size)]
        rows += [self._swing(SwingKind.LOW, j) for j in range(self._lo_idx.size)]
        cols = ["kind", "pivot_index", "pivot_time", "price", "confirmation_index", "confirmation_time"]
        if not rows:
            return pd.DataFrame(columns=cols)
        out = pd.DataFrame([{**r.__dict__, "kind": r.kind.value} for r in rows])[cols]
        return out.sort_values(["confirmation_time", "kind"], kind="mergesort").reset_index(drop=True)

    def _count_confirmed(self, kind: SwingKind, t_ns: int) -> int:
        conf = self._hi_conf_ns if kind is SwingKind.HIGH else self._lo_conf_ns
        return int(np.searchsorted(conf, t_ns, side="right"))

    def confirmed_swings(self, t: pd.Timestamp | str) -> pd.DataFrame:
        """Swing dengan confirmation_time <= t."""
        sf = self.swings_frame()
        if sf.empty:
            return sf
        return sf[sf["confirmation_time"] <= pd.Timestamp(t)].reset_index(drop=True)

    def get_last_confirmed_swing_high(self, t: pd.Timestamp | str, back: int = 0) -> Optional[Swing]:
        """Swing high terkonfirmasi ke-(back+1) dari belakang pada waktu t."""
        n = self._count_confirmed(SwingKind.HIGH, _ns(t))
        return self._swing(SwingKind.HIGH, n - 1 - back) if n - 1 - back >= 0 else None

    def get_last_confirmed_swing_low(self, t: pd.Timestamp | str, back: int = 0) -> Optional[Swing]:
        n = self._count_confirmed(SwingKind.LOW, _ns(t))
        return self._swing(SwingKind.LOW, n - 1 - back) if n - 1 - back >= 0 else None

    # ------------------------------------------------------- structure

    def structure_at(self, t: pd.Timestamp | str) -> StructureState:
        """Struktur pada waktu t dari swing terkonfirmasi <= t."""
        lh = self.get_last_confirmed_swing_high(t)
        ph = self.get_last_confirmed_swing_high(t, back=1)
        ll = self.get_last_confirmed_swing_low(t)
        pl = self.get_last_confirmed_swing_low(t, back=1)
        label = classify_structure(
            lh.price if lh else None,
            ph.price if ph else None,
            ll.price if ll else None,
            pl.price if pl else None,
        )
        return StructureState(pd.Timestamp(t), label, lh, ph, ll, pl)

    def _levels(self, kind: SwingKind, counts: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        idx = self._hi_idx if kind is SwingKind.HIGH else self._lo_idx
        src = self._high if kind is SwingKind.HIGH else self._low
        last = np.full(counts.size, np.nan)
        prev = np.full(counts.size, np.nan)
        pivot = np.full(counts.size, -1, dtype=np.int64)
        m1 = counts >= 1
        m2 = counts >= 2
        if idx.size:
            pivot[m1] = idx[counts[m1] - 1]
            last[m1] = src[pivot[m1]]
            prev[m2] = src[idx[counts[m2] - 2]]
        return last, prev, pivot

    def structure_series(self) -> pd.DataFrame:
        """Struktur pada CLOSE setiap bar (hanya swing terkonfirmasi <= close_time)."""
        ch = np.searchsorted(self._hi_conf_ns, self._close_ns, side="right")
        cl = np.searchsorted(self._lo_conf_ns, self._close_ns, side="right")
        lh, ph, hp = self._levels(SwingKind.HIGH, ch)
        ll, pl, lp = self._levels(SwingKind.LOW, cl)
        bull = (ch >= 2) & (cl >= 2) & (lh > ph) & (ll > pl)
        bear = (ch >= 2) & (cl >= 2) & (lh < ph) & (ll < pl)
        label = np.where(bull, Structure.BULLISH.value, np.where(bear, Structure.BEARISH.value, Structure.NEUTRAL.value))
        ts = self._ts
        return pd.DataFrame(
            {
                "timestamp": ts,
                "close_time": self._close_time,
                "structure": label,
                "swing_high": lh,
                "swing_high_prev": ph,
                "swing_high_time": _times_at(ts, hp),
                "swing_low": ll,
                "swing_low_prev": pl,
                "swing_low_time": _times_at(ts, lp),
                "n_swing_high": ch,
                "n_swing_low": cl,
            }
        )

    # ------------------------------------------------------------- BOS

    def bos_series(self, mode: str = "close") -> pd.DataFrame:
        """Break of Structure per bar. Lihat docstring modul untuk aturannya."""
        if mode not in {"close", "wick"}:
            raise ValueError("mode BOS harus 'close' atau 'wick'")
        up_px = self._close if mode == "close" else self._high
        dn_px = self._close if mode == "close" else self._low
        # Level yang sudah terkonfirmasi saat bar DIBUKA.
        ch = np.searchsorted(self._hi_conf_ns, self._open_ns, side="right")
        cl = np.searchsorted(self._lo_conf_ns, self._open_ns, side="right")
        n = self._open_ns.size
        bull = np.zeros(n, dtype=bool)
        bear = np.zeros(n, dtype=bool)
        bull_lvl = np.full(n, np.nan)
        bear_lvl = np.full(n, np.nan)
        bull_piv = np.full(n, -1, dtype=np.int64)
        bear_piv = np.full(n, -1, dtype=np.int64)
        broken_hi = -1
        broken_lo = -1
        for j in range(n):
            if ch[j] > 0:
                s = int(ch[j]) - 1
                piv = int(self._hi_idx[s])
                lvl = self._high[piv]
                if s != broken_hi and up_px[j] > lvl:
                    bull[j], bull_lvl[j], bull_piv[j] = True, lvl, piv
                    broken_hi = s
            if cl[j] > 0:
                s = int(cl[j]) - 1
                piv = int(self._lo_idx[s])
                lvl = self._low[piv]
                if s != broken_lo and dn_px[j] < lvl:
                    bear[j], bear_lvl[j], bear_piv[j] = True, lvl, piv
                    broken_lo = s
        ts = self._ts
        return pd.DataFrame(
            {
                "timestamp": ts,
                "close_time": self._close_time,
                "bos_bullish": bull,
                "bos_bullish_level": bull_lvl,
                "bos_bullish_swing_time": _times_at(ts, bull_piv),
                "bos_bearish": bear,
                "bos_bearish_level": bear_lvl,
                "bos_bearish_swing_time": _times_at(ts, bear_piv),
            }
        )

    def timeline(self, bos_mode: str = "close") -> pd.DataFrame:
        """structure_series + bos_series dalam satu frame per bar."""
        s = self.structure_series()
        b = self.bos_series(bos_mode).drop(columns=["timestamp", "close_time"])
        return pd.concat([s, b], axis=1)

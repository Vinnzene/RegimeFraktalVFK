"""Split data time-based + purge gap.

Split dilakukan berurutan waktu TANPA shuffle. Di setiap batas (train|val dan
val|test) dibuang `purge_gap` bar (= L + h). Alasannya: dengan stride=1 window
training yang berdekatan dengan batas masih tumpang tindih dengan window test —
baik lewat input (panjang L) maupun lewat target (jarak h). Tanpa purge, angka
test terlihat bagus karena kebocoran, bukan karena modelnya bekerja.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, cast

import pandas as pd

DEFAULT_STRIDE_BARS = 1


def stride_bars_of(df: pd.DataFrame, default: int = DEFAULT_STRIDE_BARS) -> int:
    """Baca jarak antar-baris (satuan bar) dari hasil compute_regime.

    Deret regime berindeks WINDOW, sedangkan purge_gap dan horizon h di
    config.yaml dinyatakan dalam BAR. Setiap konversi antar keduanya harus
    lewat angka ini; menebaknya dari effective_window pernah menghasilkan
    horizon yang meleset 125x.
    """
    if "stride_bars" in df.columns and len(df):
        try:
            return max(1, int(df["stride_bars"].iloc[0]))
        except (TypeError, ValueError):
            return default
    return default


def bars_to_rows(bars: int, stride_bars: int) -> int:
    """Ubah besaran satuan bar menjadi jumlah baris pada deret berindeks window."""
    return max(1, round(bars / max(stride_bars, 1)))


def split_indices(n: int, ratios: Sequence[float], purge_gap: int) -> Dict[str, Any]:
    """Hitung batas indeks train/val/test beserta dua zona purge.

    Dua zona purge dialokasikan LEBIH DULU dari total, baru sisanya dibagi
    menurut rasio. Menghitung batas dari rasio dulu lalu menyisipkan purge akan
    memakan jatah validation dan test — pada dataset pendek keduanya bisa habis
    sama sekali tanpa error yang terlihat.

    Bila purge tidak muat, lebarnya dikecilkan secara proporsional agar setiap
    segmen tetap memperoleh minimal satu baris.
    """
    if n <= 0:
        zero = [0, 0]
        return {
            "n": 0,
            "purge_gap": 0,
            "requested_purge_gap": purge_gap,
            "train": zero,
            "purge_1": zero,
            "validation": zero,
            "purge_2": zero,
            "test": zero,
        }

    # Sisakan minimal 1 baris untuk train, validation, dan test.
    max_total_purge = max(0, n - 3)
    gap = max(0, min(purge_gap, max_total_purge // 2))

    usable = n - 2 * gap
    train_len = max(1, int(usable * ratios[0]))
    val_len = max(1, int(usable * ratios[1]))
    # Sisa diberikan ke test agar tidak ada baris yang hilang akibat pembulatan.
    if train_len + val_len > usable - 1:
        train_len = max(1, usable - 2)
        val_len = 1

    train_end = train_len
    purge1_end = train_end + gap
    val_end = purge1_end + val_len
    purge2_end = val_end + gap

    return {
        "n": n,
        "purge_gap": gap,
        "requested_purge_gap": purge_gap,
        "train": [0, train_end],
        "purge_1": [train_end, purge1_end],
        "validation": [purge1_end, val_end],
        "purge_2": [val_end, purge2_end],
        "test": [purge2_end, n],
    }


def split_boundaries(
    timestamps: Sequence[int],
    ratios: Sequence[float],
    purge_gap: int,
) -> Dict[str, object]:
    """Versi berbasis timestamp untuk digambar sebagai band di chart."""
    n = len(timestamps)
    idx = split_indices(n, ratios, purge_gap)

    def _stamp(pair: List[int]) -> Optional[Dict[str, Any]]:
        start, end = pair
        if start >= n or end <= start:
            return None
        return {
            "start_index": start,
            "end_index": end,
            "start_time": timestamps[start],
            "end_time": timestamps[min(end, n - 1)],
        }

    segments = []
    for name in ("train", "purge_1", "validation", "purge_2", "test"):
        stamped = _stamp(idx[name])  # type: ignore[arg-type]
        if stamped:
            stamped["segment"] = name
            segments.append(stamped)

    return {
        "n": n,
        "purge_gap": purge_gap,
        "ratios": list(ratios),
        "segments": segments,
    }


def assign_segment(df: pd.DataFrame, ratios: Sequence[float], purge_gap: int) -> pd.DataFrame:
    """Tambahkan kolom `segment` (train/purge/validation/test) ke DataFrame."""
    idx = split_indices(len(df), ratios, purge_gap)
    out = df.copy()
    out["segment"] = "test"
    seg_col = int(cast(Any, out.columns.get_loc("segment")))
    for name in ("train", "purge_1", "validation", "purge_2", "test"):
        start, end = idx[name]  # type: ignore[misc]
        label = "purge" if name.startswith("purge") else name
        out.iloc[start:end, seg_col] = label
    return out

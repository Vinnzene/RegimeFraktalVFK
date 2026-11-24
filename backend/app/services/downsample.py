"""Penjarangan deret untuk pengiriman ke browser."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np


def downsample_uniform(rows: Sequence[dict], target: int) -> List[dict]:
    """Ambil tiap ke-k sehingga jumlah baris mendekati `target`."""
    n = len(rows)
    if target <= 0 or n <= target:
        return list(rows)
    step = max(1, n // target)
    out = list(rows[::step])
    if out and out[-1] is not rows[-1]:
        out.append(rows[-1])
    return out


def downsample_lttb(
    rows: Sequence[dict],
    target: int,
    x_key: str = "time",
    y_key: str = "hurst",
) -> List[dict]:
    """Largest Triangle Three Buckets — mempertahankan bentuk visual deret."""
    n = len(rows)
    if target <= 2 or n <= target:
        return list(rows)

    def val(row: dict) -> float:
        v = row.get(y_key)
        try:
            f = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
        return f if np.isfinite(f) else 0.0

    def pos(row: dict) -> float:
        v = row.get(x_key)
        try:
            return float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    bucket_size = (n - 2) / (target - 2)
    out = [rows[0]]
    a = 0

    for i in range(target - 2):
        # Rata-rata bucket berikutnya sebagai titik ketiga segitiga.
        start_next = int((i + 1) * bucket_size) + 1
        end_next = min(int((i + 2) * bucket_size) + 1, n)
        if start_next >= end_next:
            start_next, end_next = min(start_next, n - 1), n
        nxt = rows[start_next:end_next] or [rows[-1]]
        avg_x = sum(pos(r) for r in nxt) / len(nxt)
        avg_y = sum(val(r) for r in nxt) / len(nxt)

        start = int(i * bucket_size) + 1
        end = min(int((i + 1) * bucket_size) + 1, n)
        ax, ay = pos(rows[a]), val(rows[a])

        best, best_area = start, -1.0
        for j in range(start, end):
            area = abs(
                (ax - avg_x) * (val(rows[j]) - ay) - (ax - pos(rows[j])) * (avg_y - ay)
            )
            if area > best_area:
                best_area, best = area, j
        out.append(rows[best])
        a = best

    out.append(rows[-1])
    return out


def apply_downsample(
    rows: Sequence[dict],
    limit: Optional[int],
    method: str = "uniform",
    y_key: str = "hurst",
) -> Dict[str, Any]:
    """Terapkan penjarangan dan laporkan metadatanya."""
    n = len(rows)
    if not limit or n <= limit:
        return {"rows": list(rows), "downsampled": False, "original_count": n}

    if method == "lttb":
        out = downsample_lttb(rows, limit, y_key=y_key)
    else:
        out = downsample_uniform(rows, limit)

    return {
        "rows": out,
        "downsampled": True,
        "original_count": n,
        "method": method,
    }

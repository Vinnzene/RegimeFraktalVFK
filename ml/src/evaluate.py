"""Evaluasi 3 model + Baseline Persistence.

Baseline Persistence ("regime t+h = regime t") wajib dilaporkan. Tanpa angka
pembanding ini, nilai balanced accuracy model tidak bisa dinilai: pada deret
yang regimenya bertahan lama, tebakan naif saja sudah tinggi.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.model_registry import (  # noqa: E402
    balanced_accuracy,
    evaluate_against_truth,
    matthews_corrcoef,
)
from app.services.regime_labeling import UNCERTAIN_RULE, build_targets  # noqa: E402
from dataset import build_dataset  # noqa: E402


def persistence_predictions(labels: Sequence[str]) -> List[str]:
    """Prediksi naif untuk t+h: salin regime pada t."""
    return list(labels)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluasi model regime")
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    parser.add_argument("--symbol", default="BTCUSDT")
    args = parser.parse_args()

    cfg = get_config()
    close = get_repository().get_ohlcv(args.symbol, args.timeframe)["close"].to_numpy()
    data = build_dataset(close)

    labels: List[str] = data["labels"]  # type: ignore[assignment]
    targets: List[Optional[str]] = data["targets"]  # type: ignore[assignment]

    pairs = [
        (t, p)
        for t, p in zip(targets, persistence_predictions(labels))
        if t is not None and t != UNCERTAIN_RULE
    ]
    yt = [t for t, _ in pairs]
    yp = [p for _, p in pairs]

    print(f"config_hash        : {cfg.short_hash}")
    print(f"h (bar)            : {cfg.model.h}")
    print(f"h (window)         : {data['h_windows']}")
    print(f"n dievaluasi       : {len(pairs)}")
    print("--- Baseline Persistence (regime t+h = regime t) ---")
    print(f"balanced accuracy  : {balanced_accuracy(yt, yp)}")
    print(f"MCC                : {matthews_corrcoef(yt, yp)}")
    print()
    print("Angka di atas adalah ambang minimum. Model usulan hanya bermakna")
    print("bila mengungguli baseline ini secara konsisten pada walk-forward.")


if __name__ == "__main__":
    main()

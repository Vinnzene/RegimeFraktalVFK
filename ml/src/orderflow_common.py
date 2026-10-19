"""Penyiapan data bersama untuk eksperimen order flow (sanity check, ablation, analisis).

Satu fungsi saja yang membangun dataset, sehingga sanity check memeriksa
tensor yang PERSIS sama dengan yang dipakai training.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.order_flow import coverage  # noqa: E402
from dataset import build_dataset  # noqa: E402

# Ablation: kanal order flow yang dipakai tiap model. Indeks merujuk ke
# ORDER_FLOW_CHANNELS = ("ofi", "cvd").
ABLATION_MODELS: Dict[str, Dict[str, Any]] = {
    "A": {"name": "SWT + Attention-BiLSTM", "ofi": False, "cvd": False, "channels": []},
    "B": {"name": "SWT + Attention-BiLSTM + OFI", "ofi": True, "cvd": False, "channels": [0]},
    "C": {"name": "SWT + Attention-BiLSTM + CVD", "ofi": False, "cvd": True, "channels": [1]},
    "D": {"name": "SWT + Attention-BiLSTM + OFI + CVD", "ofi": True, "cvd": True, "channels": [0, 1]},
}


def ablation_purge_bars(seq_len: int, stride_bars: int, window: int, cvd_window: int) -> int:
    """Purge yang menutup jangkauan input terjauh di antara keempat model.

    Sekuens SWT/OFI/CVD memakai seq_len BAR berurutan yang berakhir di t, dan
    tiap langkah menoleh ke belakang sejauh max(window_SWT, window_CVD). Label
    Hurst-DFA memakai window_label bar. Jadi input sampel bertitik akhir t
    menyentuh bar hingga t − (seq_len − 1) − max(window, cvd_window) + 1.
    Purge ≥ angka itu (dibulatkan ke atas satu stride) menjamin sampel test
    tidak berbagi satu bar pun dengan sampel train, baik lewat input maupun label.
    """
    return max(window, cvd_window) + seq_len + stride_bars


def load_orderflow_dataset(
    timeframe: str,
    symbol: str = "BTCUSDT",
    seq_len: int = 32,
    classes: Sequence[str] | None = None,
    cvd_window: int | None = None,
    cvd_method: str = "zscore",
) -> Dict[str, Any]:
    cfg = get_config()
    ohlcv = get_repository().get_ohlcv(symbol, timeframe)
    cov = coverage(ohlcv)
    if cov < 0.99:
        raise SystemExit(
            f"Cakupan order flow {timeframe} hanya {cov:.1%}. Jalankan dulu:\n"
            f"  python ml/src/prepare_order_flow.py --timeframe {timeframe}"
        )
    close = ohlcv["close"].to_numpy()
    window = min(cfg.analysis.L, max(64, (len(close) - 1) // 4))
    stride = max(1, cfg.analysis.stride_bars)
    cw = cvd_window or window
    purge = ablation_purge_bars(seq_len, stride, window, cw)

    data = build_dataset(
        close,
        seq_len=seq_len,
        h_bars=0,
        classes=list(classes) if classes else list(REGIME_CLASSES),
        with_structural=False,
        with_multifractal=False,
        with_orderflow_seq=True,
        ohlcv=ohlcv,
        cvd_window=cw,
        cvd_method=cvd_method,
        purge_bars_override=purge,
    )
    data["ohlcv"] = ohlcv
    data["coverage"] = cov
    data["timeframe"] = timeframe
    return data


def select_channels(X_of: np.ndarray, channels: List[int]) -> np.ndarray:
    return X_of[:, :, channels]

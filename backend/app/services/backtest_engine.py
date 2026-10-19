"""Backtest eksploratif berbasis sinyal regime.

ATURAN KRITIS — sumber regime:
    Backtest WAJIB memakai regime hasil PREDIKSI MODEL yang tersedia pada
    waktu t. Label ground truth Hurst-DFA TIDAK boleh dipakai, karena label
    tersebut berasal dari window masa depan (Y_{t+h}); memakainya membuat
    equity curve terlihat bagus hanya karena kebocoran informasi.
    Baseline rule-based memakai Hurst-DFA dari window <= t saja.

Aturan posisi (ditetapkan di muka, tidak bisa dipilih user):
    persistent        -> ikuti arah return terakhir (trend-following)
    anti_persistent   -> lawan arah return terakhir (kontrarian)
    random_like       -> flat, tidak ambil posisi
    uncertain_*       -> flat
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from app.services.regime_labeling import ANTI_PERSISTENT, PERSISTENT

BARS_PER_YEAR = {"1h": 24 * 365, "4h": 6 * 365}


def position_from_regime(regime: str, last_return: float) -> int:
    """Terjemahkan regime + arah return terakhir menjadi posisi -1/0/+1."""
    direction = 1 if last_return > 0 else (-1 if last_return < 0 else 0)
    if regime == PERSISTENT:
        return direction
    if regime == ANTI_PERSISTENT:
        return -direction
    return 0


def run_backtest(
    times: Sequence[int],
    closes: Sequence[float],
    regimes: Sequence[str],
    timeframe: str = "1h",
    fee_bps: float = 4.0,
    regime_source: str = "model_prediction_at_t",
    bars_per_row: int = 1,
) -> Dict[str, object]:
    """Jalankan strategi regime dan bandingkan dengan Buy & Hold.

    `bars_per_row` menyatakan berapa bar yang diwakili satu baris masukan.
    Deret regime berindeks window, jadi satu baris bisa mewakili beberapa bar;
    faktor anualisasi harus dibagi angka ini agar Sharpe dan volatilitas tidak
    membesar palsu sebesar sqrt(bars_per_row).
    """
    close = np.asarray(closes, dtype=float)
    n = close.size
    if n < 3:
        return {"error": "data terlalu pendek untuk backtest"}

    ret = np.zeros(n)
    ret[1:] = np.diff(close) / close[:-1]

    positions = np.zeros(n, dtype=float)
    for t in range(1, n - 1):
        # Posisi untuk bar t+1 hanya boleh memakai informasi s.d. bar t.
        positions[t + 1] = position_from_regime(regimes[t], ret[t])

    gross = positions * ret
    turnover = np.abs(np.diff(np.concatenate([[0.0], positions])))
    cost = turnover * (fee_bps / 10_000.0)
    net = gross - cost

    equity = np.cumprod(1.0 + net)
    buy_hold = close / close[0]

    # Jumlah periode per tahun mengikuti satuan BARIS, bukan satuan bar.
    ann = BARS_PER_YEAR.get(timeframe, 24 * 365) / max(bars_per_row, 1)
    vol = float(np.std(net, ddof=1) * np.sqrt(ann)) if n > 2 else 0.0
    sharpe = float(np.mean(net) * ann / vol) if vol > 0 else 0.0

    def _max_dd(curve: np.ndarray) -> float:
        peak = np.maximum.accumulate(curve)
        return float(np.min(curve / peak - 1.0))

    trades = int(np.sum(np.abs(np.diff(positions)) > 0))
    exposure = float(np.mean(np.abs(positions)))

    step = max(1, n // 1500)
    curve = [
        {
            "time": int(times[i]),
            "strategy": round(float(equity[i]), 6),
            "buy_hold": round(float(buy_hold[i]), 6),
        }
        for i in range(0, n, step)
    ]

    return {
        "regime_source": regime_source,
        "disclaimer": (
            "Backtest bersifat eksploratif untuk melihat kegunaan praktis "
            "informasi regime, BUKAN jaminan profit atau rekomendasi trading."
        ),
        "rules": {
            "persistent": "ikuti arah return terakhir (trend-following)",
            "anti_persistent": "lawan arah return terakhir (kontrarian)",
            "random_like": "flat (tidak ambil posisi)",
            "uncertain_rule": "flat",
            "uncertain_lowconf": "flat",
        },
        "equity_curve": curve,
        "metrics": {
            "cumulative_return": round(float(equity[-1] - 1.0), 4),
            "buy_hold_return": round(float(buy_hold[-1] - 1.0), 4),
            "max_drawdown": round(_max_dd(equity), 4),
            "buy_hold_max_drawdown": round(_max_dd(buy_hold), 4),
            "sharpe_ratio": round(sharpe, 4),
            "volatility_annualized": round(vol, 4),
            "turnover_total": round(float(np.sum(turnover)), 4),
            "transaction_cost_total": round(float(np.sum(cost)), 6),
            "fee_bps": fee_bps,
            "n_trades": trades,
            "exposure": round(exposure, 4),
            "n_bars": n,
            "bars_per_row": bars_per_row,
            "periods_per_year": round(ann, 2),
        },
    }

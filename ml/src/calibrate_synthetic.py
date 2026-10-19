"""Kalibrasi volatilitas stokastik S3/S4 ke BTC 1H (praregistrasi Fase 1 §3).

Jalankan:
    python ml/src/calibrate_synthetic.py

Hanya memakai statistik deskriptif return BTC 1H (autokorelasi |r| dan
kurtosis), bukan label maupun hasil strategi. Grid (phi, eta) dipilih agar
autokorelasi |r| deret S4 berada dalam ±0,05 dari BTC pada lag 1, 5, 24, 100;
di antara yang lolos dipilih simpangan maksimum terkecil.

Keluaran: ml/artifacts/synthetic_calibration.json
"""

from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR  # noqa: E402
from synthetic_regimes import CryptoParams, make_series  # noqa: E402

LAGS = (1, 5, 24, 100)
TOL = 0.05
PHIS = (0.95, 0.97, 0.98, 0.99, 0.995, 0.998)
ETAS = (0.10, 0.15, 0.20, 0.30, 0.40, 0.50)
N_SERIES = 12
LENGTH = 20_000


def abs_acf(r: np.ndarray, lags=LAGS) -> np.ndarray:
    a = np.abs(r - r.mean())
    a = a - a.mean()
    d = float((a * a).sum())
    return np.array([float((a[:-k] * a[k:]).sum()) / d for k in lags])


def main() -> None:
    btc = pd.read_parquet(ROOT / "data" / "processed" / "ohlcv_btcusdt_1h.parquet")
    r_btc = np.diff(np.log(btc["close"].to_numpy()))
    target = abs_acf(r_btc)
    kurt_btc = float(pd.Series(r_btc).kurt())
    print(f"BTC |r| ACF {np.round(target, 3)} kurtosis {kurt_btc:.1f}")

    rows = []
    for phi, eta in product(PHIS, ETAS):
        p = CryptoParams(sv_phi=phi, sv_eta=eta)
        rng = np.random.default_rng(9_000)
        acfs, kurts = [], []
        for _ in range(N_SERIES):
            r, _ = make_series("S4", LENGTH, 0.5, rng, p)
            acfs.append(abs_acf(r))
            kurts.append(float(pd.Series(r).kurt()))
        acf = np.mean(acfs, axis=0)
        dev = float(np.max(np.abs(acf - target)))
        rows.append({"phi": phi, "eta": eta, "acf": np.round(acf, 4).tolist(),
                     "max_dev": round(dev, 4), "kurtosis": round(float(np.median(kurts)), 1)})
        print(f"phi={phi} eta={eta} acf={np.round(acf, 3)} max_dev={dev:.3f} kurt={np.median(kurts):.1f}")

    ok = [r for r in rows if r["max_dev"] <= TOL]
    best = min(ok or rows, key=lambda r: r["max_dev"])
    out = {
        "target": {"lags": list(LAGS), "abs_acf": np.round(target, 4).tolist(), "kurtosis": round(kurt_btc, 1)},
        "tolerance": TOL,
        "grid": rows,
        "selected": best,
        "within_tolerance": bool(ok),
    }
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "synthetic_calibration.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"terpilih: {best} | lolos toleransi: {bool(ok)}")


if __name__ == "__main__":
    main()

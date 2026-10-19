"""Diagnostik backtest — menjelaskan MENGAPA hasilnya seperti itu.

Equity curve yang menurun saja tidak memberi tahu apa pun: kerugian bisa berasal
dari arah posisi yang salah, dari biaya transaksi, atau semata dari volatility
drag. Modul ini memisahkan ketiganya dan menguji apakah hasilnya berbeda dari
kebetulan.

Empat alat yang disediakan:

1. `decompose_returns`   — pisahkan edge, drag, dan biaya.
2. `random_benchmark`    — bandingkan dengan posisi acak ber-exposure sama.
3. `direction_diagnostics` — uji asumsi inti aturan Bab 3: apakah return
   benar-benar berlanjut saat regime persistent?
4. `segment_stability`   — periksa apakah pola bertahan di train/val/test.

Alat ketiga yang paling menentukan. Aturan Bab 3 menerjemahkan Hurst menjadi
prediksi ARAH, padahal Hurst mengukur persistensi struktur skala dan volatilitas,
bukan tanda return. Diagnostik ini membuat asumsi tersebut dapat diuji, bukan
diterima begitu saja.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from app.services.backtest_engine import position_from_regime
from app.services.regime_labeling import ANTI_PERSISTENT, PERSISTENT


def _returns(closes: np.ndarray) -> np.ndarray:
    ret = np.zeros(closes.size)
    if closes.size > 1:
        ret[1:] = np.diff(closes) / closes[:-1]
    return ret


def build_positions(regimes: Sequence[str], ret: np.ndarray) -> np.ndarray:
    """Posisi menurut aturan Bab 3; bar t+1 hanya memakai informasi sampai t."""
    n = ret.size
    pos = np.zeros(n)
    for t in range(1, n - 1):
        pos[t + 1] = position_from_regime(regimes[t], ret[t])
    return pos


def decompose_returns(
    gross: np.ndarray,
    cost: np.ndarray,
) -> Dict[str, object]:
    """Pisahkan log-return kumulatif menjadi edge, drag, dan biaya.

    Untuk return kecil, log(1+r) ~ r - r^2/2, sehingga pertumbuhan majemuk dapat
    dipisah menjadi komponen rata-rata (edge) dan penalti varians (volatility
    drag). Tanpa pemisahan ini, strategi ber-edge nol tetap terlihat "rugi"
    padahal kerugiannya murni efek matematis.
    """
    n = gross.size
    if n == 0:
        return {"n": 0}

    mu = float(gross.mean())
    var = float(gross.var())
    edge = mu * n
    drag = -0.5 * var * n
    cost_total = float(cost.sum())

    net = gross - cost
    with np.errstate(divide="ignore", invalid="ignore"):
        actual_log = float(np.log(max(float(np.prod(1.0 + net)), 1e-12)))

    return {
        "n": n,
        "mean_per_step": round(mu, 8),
        "std_per_step": round(float(gross.std()), 8),
        "edge_component": round(edge, 4),
        "drag_component": round(drag, 4),
        "cost_component": round(-cost_total, 4),
        "approx_log_equity": round(edge + drag - cost_total, 4),
        "actual_log_equity": round(actual_log, 4),
        "catatan": (
            "edge = kontribusi arah posisi; drag = penalti volatilitas yang "
            "melekat pada pertumbuhan majemuk; cost = biaya transaksi. "
            "Edge negatif berarti arah posisi memang salah, bukan sekadar "
            "tergerus biaya."
        ),
    }


def random_benchmark(
    ret: np.ndarray,
    pos: np.ndarray,
    n_simulations: int = 200,
    seed: int = 42,
) -> Dict[str, object]:
    """Bandingkan dengan posisi acak yang ber-exposure identik.

    Ini pembanding yang sahih: sinyal tanpa informasi akan mendarat di sekitar
    median sebaran acak. Hasil yang jauh di bawah persentil 5 justru menandakan
    sinyalnya sistematis terbalik — sesuatu yang berbeda dari sekadar tidak
    berguna.
    """
    active = np.abs(pos) > 0
    n_active = int(active.sum())
    if n_active == 0:
        return {"n_simulations": 0, "catatan": "tidak ada posisi aktif"}

    rng = np.random.default_rng(seed)
    outcomes = np.empty(n_simulations)
    for i in range(n_simulations):
        rand_pos = np.zeros(ret.size)
        rand_pos[active] = rng.choice([-1.0, 1.0], size=n_active)
        outcomes[i] = float(np.prod(1.0 + rand_pos * ret) - 1.0)

    strategy = float(np.prod(1.0 + pos * ret) - 1.0)
    percentile = float((outcomes < strategy).mean() * 100)

    return {
        "n_simulations": n_simulations,
        "exposure": round(float(np.abs(pos).mean()), 4),
        "strategy_return": round(strategy, 4),
        "random_median": round(float(np.median(outcomes)), 4),
        "random_p5": round(float(np.percentile(outcomes, 5)), 4),
        "random_p95": round(float(np.percentile(outcomes, 95)), 4),
        "percentile_of_strategy": round(percentile, 1),
        "verdict": (
            "sistematis lebih buruk dari acak"
            if percentile < 5
            else "sistematis lebih baik dari acak"
            if percentile > 95
            else "tidak berbeda dari acak"
        ),
        "catatan": (
            "Sinyal tanpa informasi mendarat di sekitar persentil 50. Nilai di "
            "bawah 5 menandakan arah posisi terbalik secara sistematis — itu "
            "berarti ada informasi, hanya dipakai dengan tanda yang keliru."
        ),
    }


def direction_diagnostics(
    regimes: Sequence[str],
    ret: np.ndarray,
) -> Dict[str, object]:
    """Uji asumsi inti aturan Bab 3 secara langsung.

    Aturan itu berdiri di atas satu klaim: saat regime persistent, arah return
    cenderung berlanjut. Di sini klaim tersebut diukur — P(searah) dibandingkan
    terhadap 0.5 yang berarti tidak ada informasi arah sama sekali.
    """
    if ret.size < 10:
        return {"n": 0}

    r0, r1 = ret[1:-1], ret[2:]
    reg = np.asarray(regimes)[1 : ret.size - 1]

    lag1 = float(np.corrcoef(r0, r1)[0, 1]) if r0.size > 2 else float("nan")

    per_regime: List[Dict[str, object]] = []
    for name in sorted(set(reg.tolist())):
        mask = reg == name
        if mask.sum() < 30:
            continue
        same = float((np.sign(r0[mask]) == np.sign(r1[mask])).mean())
        expected = (
            "berlanjut (P > 0.5)"
            if name == PERSISTENT
            else "berbalik (P < 0.5)"
            if name == ANTI_PERSISTENT
            else "tidak diasumsikan"
        )
        consistent: Optional[bool] = None
        if name == PERSISTENT:
            consistent = same > 0.5
        elif name == ANTI_PERSISTENT:
            consistent = same < 0.5

        per_regime.append(
            {
                "regime": name,
                "n": int(mask.sum()),
                "p_same_direction": round(same, 4),
                "assumed_by_rule": expected,
                "assumption_holds": consistent,
            }
        )

    return {
        "lag1_autocorrelation": round(lag1, 4),
        "per_regime": per_regime,
        "catatan": (
            "Hurst mengukur persistensi struktur skala dan volatilitas, bukan "
            "tanda return. Aturan Bab 3 menerjemahkannya menjadi prediksi arah; "
            "tabel ini menguji apakah terjemahan tersebut berlaku pada data."
        ),
    }


def segment_stability(
    ret: np.ndarray,
    pos: np.ndarray,
    segments: Dict[str, Sequence[int]],
) -> List[Dict[str, object]]:
    """Periksa apakah hasil bertahan di train, validation, dan test.

    Pola yang hanya muncul di satu segmen adalah kebetulan, bukan temuan.
    """
    out: List[Dict[str, object]] = []
    gross = pos * ret

    for name in ("train", "validation", "test"):
        rng = segments.get(name)
        if not rng:
            continue
        lo, hi = int(rng[0]), int(rng[1])
        if hi - lo < 30:
            continue
        g = gross[lo:hi]
        active = np.abs(pos[lo:hi]) > 0
        hit = float((g[active] > 0).mean()) if active.sum() else float("nan")
        out.append(
            {
                "segment": name,
                "n": hi - lo,
                "cumulative_return": round(float(np.prod(1.0 + g) - 1.0), 4),
                "hit_rate": round(hit, 4) if np.isfinite(hit) else None,
                "exposure": round(float(np.abs(pos[lo:hi]).mean()), 4),
            }
        )
    return out


def full_diagnostics(
    closes: Sequence[float],
    regimes: Sequence[str],
    segments: Dict[str, Sequence[int]],
    fee_bps: float = 4.0,
    n_simulations: int = 200,
    seed: int = 42,
) -> Dict[str, object]:
    """Rangkai seluruh diagnostik untuk satu konfigurasi backtest."""
    close = np.asarray(closes, dtype=float)
    if close.size < 30:
        return {"available": False, "reason": "data terlalu pendek"}

    ret = _returns(close)
    pos = build_positions(regimes, ret)
    gross = pos * ret
    turnover = np.abs(np.diff(np.concatenate([[0.0], pos])))
    cost = turnover * (fee_bps / 10_000.0)

    return {
        "available": True,
        "decomposition": decompose_returns(gross, cost),
        "random_benchmark": random_benchmark(ret, pos, n_simulations, seed),
        "direction": direction_diagnostics(regimes, ret),
        "stability": segment_stability(ret, pos, segments),
    }

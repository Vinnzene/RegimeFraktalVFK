"""Pita acak estimator Hurst R/S dan DFA-1: sebaran nilai pada deret tanpa memori.

    python ml/src/random_band.py

Deret sintetis dengan H = 0,5 (S1 bersih dan S4 berkarakter kripto, generator
Fase 1) diukur dengan estimator yang sama persis dengan backend. Persentil
2,5–97,5% menjadi "pita acak": nilai di dalam pita tidak dapat dibedakan dari
pasar tanpa memori pada panjang jendela tersebut. Dipakai dashboard untuk
memberi label pembanding klasik yang jujur, alih-alih sekadar di atas/di bawah 0,5.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent))

from app.services.hurst_dfa import dfa_alpha, hurst_rs  # noqa: E402
from synthetic_regimes import make_series  # noqa: E402

OUT = ROOT / "ml" / "artifacts"
WINDOWS = (128, 256, 500, 1000)
SCENARIOS = ("S1", "S4")
N_SERIES = 2000
SEED = 20261026


def _one(scenario: str, n: int, seed: int) -> tuple[float, float]:
    r, _ = make_series(scenario, n, 0.5, np.random.default_rng(seed))
    return hurst_rs(r), dfa_alpha(r)


def band(scenario: str, n: int) -> dict:
    seeds = np.random.SeedSequence([SEED, n, SCENARIOS.index(scenario)]).generate_state(N_SERIES)
    vals = np.array(Parallel(n_jobs=-1, batch_size=64)(delayed(_one)(scenario, n, int(s)) for s in seeds))
    out = {}
    for j, name in enumerate(("hurst_rs", "dfa_alpha")):
        v = vals[:, j][np.isfinite(vals[:, j])]
        lo, med, hi = np.percentile(v, [2.5, 50, 97.5])
        out[name] = {"lower": round(float(lo), 4), "median": round(float(med), 4), "upper": round(float(hi), 4)}
    return out


def main() -> None:
    res = {s: {str(n): band(s, n) for n in WINDOWS} for s in SCENARIOS}
    meta = {
        "description": "Persentil 2,5/50/97,5 estimator pada deret sintetis H = 0,5 (tanpa memori).",
        "h_true": 0.5, "n_series": N_SERIES, "seed": SEED, "percentiles": [2.5, 50, 97.5],
        "scenarios": {"S1": "fGn Gaussian", "S4": "fGn + ekor tebal + volatilitas stokastik + lonjakan (mirip kripto)"},
        "dashboard_default": {"scenario": "S4", "window": 500},
        "bands": res,
    }
    (OUT / "random_band.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    lines = ["# Pita acak estimator Hurst R/S dan DFA-1", "",
             f"Deret sintetis H = 0,5, {N_SERIES} deret per sel, persentil 2,5 / 50 / 97,5. Seed {SEED}.", "",
             "| Skenario | Jendela | R/S bawah | R/S median | R/S atas | DFA bawah | DFA median | DFA atas |",
             "|---|---|---|---|---|---|---|---|"]
    for s in SCENARIOS:
        for n in WINDOWS:
            b = res[s][str(n)]
            h, a = b["hurst_rs"], b["dfa_alpha"]
            lines.append(f"| {s} | {n} | {h['lower']:.3f} | {h['median']:.3f} | {h['upper']:.3f} | "
                         f"{a['lower']:.3f} | {a['median']:.3f} | {a['upper']:.3f} |")
    lines += ["", "Nilai di dalam pita tidak dapat dibedakan dari pasar tanpa memori pada panjang jendela itu."]
    (OUT / "random_band.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

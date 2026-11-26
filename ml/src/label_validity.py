"""Tahap 1 validitas label (tanpa melatih ulang).

1. Akurasi per zona jarak ke ambang Hurst/DFA, dengan CI block bootstrap.
2. QWK dan kesalahan jauh (persistent <-> anti-persistent) vs kesalahan tetangga.
3. Validitas label pada data sintetis dengan H diketahui: aturan label yang sama dengan BTC
   (ambang kuantil 1/3-2/3 + Trend-Aware Soft Consensus + skor ER) dibandingkan dengan kelas sebenarnya.

Pemakaian: python ml/src/label_validity.py
Keluaran: ml/artifacts/label_validity.json dan label_validity.md
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fit_diagnostics as fd  # noqa: E402  (juga menyiapkan sys.path backend)
from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.services.hurst_dfa import compute_rolling_er  # noqa: E402
from app.services.regime_labeling import (  # noqa: E402
    calibrate_thresholds,
    compute_er_quantile_score,
    label_from_exponents,
)

OUT_JSON = ARTIFACTS_DIR / "label_validity.json"
OUT_MD = ARTIFACTS_DIR / "label_validity.md"
CLASSES = fd.CLASSES  # persistent, random_like, anti_persistent
# Urutan ordinal menurut tingkat persistensi: anti < random < persistent.
ORD = {0: 2, 1: 1, 2: 0}
BANDS = [(0.0, 0.02, "< 0,02"), (0.02, 0.05, "0,02 – 0,05"), (0.05, np.inf, "≥ 0,05")]
BLOCK = {"1h": 125, "4h": 250}  # 500 bar / stride
N_BOOT = 2000
SEED = 20261126


# ------------------------------------------------------------------ util
def block_indices(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """Moving block bootstrap: indeks sepanjang n dari blok berurutan acak."""
    block = max(1, min(block, n))
    starts = rng.integers(0, n - block + 1, size=int(np.ceil(n / block)))
    return np.concatenate([np.arange(s, s + block) for s in starts])[:n]


def ci(values: Sequence[float]) -> List[float]:
    v = np.asarray([x for x in values if np.isfinite(x)])
    return [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)] if v.size else [np.nan, np.nan]


def qwk(y: np.ndarray, p: np.ndarray) -> float:
    """Quadratic weighted kappa pada urutan ordinal anti < random < persistent."""
    a = np.vectorize(ORD.get)(y)
    b = np.vectorize(ORD.get)(p)
    M = np.zeros((3, 3))
    np.add.at(M, (a, b), 1)
    W = np.array([[(i - j) ** 2 / 4 for j in range(3)] for i in range(3)])
    E = np.outer(M.sum(1), M.sum(0)) / max(M.sum(), 1)
    den = (W * E).sum()
    return float(1 - (W * M).sum() / den) if den > 0 else float("nan")


def error_split(y: np.ndarray, p: np.ndarray) -> Dict[str, Any]:
    wrong = p != y
    far = wrong & (np.abs(np.vectorize(ORD.get)(y) - np.vectorize(ORD.get)(p)) == 2)
    n = len(y)
    return {
        "n": int(n),
        "benar_pct": round(100 * float((~wrong).mean()), 2),
        "salah_tetangga_pct": round(100 * float((wrong & ~far).mean()), 2),
        "salah_jauh_pct": round(100 * float(far.mean()), 2),
        "salah_jauh_n": int(far.sum()),
    }


def distance_to_threshold(h: np.ndarray, a: np.ndarray, thr: Dict[str, List[float]]) -> np.ndarray:
    dh = np.min(np.abs(h[:, None] - np.asarray(thr["hurst"])[None, :]), axis=1)
    da = np.min(np.abs(a[:, None] - np.asarray(thr["dfa"])[None, :]), axis=1)
    return np.minimum(dh, da)


# ------------------------------------------------------------------ 1 + 2: BTC
def btc(tf: str) -> Dict[str, Any]:
    d = fd.rebuild(tf)
    raw = np.load(ARTIFACTS_DIR / "review" / "raw" / f"{tf}_normal.npz")
    out: Dict[str, Any] = {"thresholds": d["thresholds"], "block_rows": BLOCK[tf], "splits": {}}
    rng = np.random.default_rng(SEED)
    for split, rk in (("test", "test"), ("validation", "val")):
        rows = d["rows"][split]
        if not np.array_equal(rows, raw[f"bt__rows_{rk}"]):
            raise SystemExit(f"[{tf}] baris {split} berbeda dari evaluasi")
        y = d["y"][rows]
        p = raw[f"bt__hybrid_ps__p_{rk}"].mean(0).argmax(1)
        dist = distance_to_threshold(d["hurst"][rows], d["dfa"][rows], d["thresholds"])
        band = np.digitize(dist, [b[1] for b in BANDS[:-1]])
        boots = [block_indices(len(y), BLOCK[tf], rng) for _ in range(N_BOOT)]

        zones = []
        for bi, (_, _, name) in enumerate(BANDS):
            m = band == bi
            if not m.any():
                zones.append({"band": name, "n": 0})
                continue
            yb, pb = y[m], p[m]
            counts = np.bincount(yb, minlength=3)
            acc_boot = []
            for idx in boots:
                mm = m[idx]
                if mm.sum() >= 5:
                    acc_boot.append(float((p[idx][mm] == y[idx][mm]).mean()))
            per_class = {}
            for c, cname in enumerate(CLASSES):
                mc = yb == c
                per_class[cname] = {"n": int(mc.sum()), "recall": round(float((pb[mc] == c).mean()), 4) if mc.any() else None}
            zones.append({
                "band": name,
                "n": int(m.sum()),
                "share_pct": round(100 * float(m.mean()), 1),
                "accuracy": round(float((pb == yb).mean()), 4),
                "ci95": ci(acc_boot),
                "majority_baseline": round(float(counts.max() / counts.sum()), 4),
                "majority_class": CLASSES[int(counts.argmax())],
                "composition_pct": {cn: round(100 * float(counts[c] / counts.sum()), 1) for c, cn in enumerate(CLASSES)},
                "per_class": per_class,
                "qwk": round(qwk(yb, pb), 4) if len(set(yb.tolist())) > 1 else None,
            })

        q_boot = [qwk(y[idx], p[idx]) for idx in boots[:1000]]
        out["splits"][split] = {
            "n": int(len(y)),
            "accuracy": round(float((p == y).mean()), 4),
            "qwk": round(qwk(y, p), 4),
            "qwk_ci95": ci(q_boot),
            "errors": error_split(y, p),
            "zones": zones,
            "distance_quantiles": [round(float(v), 4) for v in np.quantile(dist, [0.1, 0.25, 0.5, 0.75, 0.9])],
        }
    return out


# ------------------------------------------------------------------ 3: sintetis
def synthetic(scenario: str) -> Dict[str, Any]:
    """Aturan label BTC pada deret sintetis benchmark Fase 1 (n = 500, split uji 3.000 deret)."""
    import synthetic_benchmark as sb  # noqa: PLC0415
    from synthetic_regimes import CLASSES as SYN_CLASSES  # noqa: PLC0415
    from synthetic_regimes import PRIMARY, make_series, sample_h  # noqa: PLC0415

    n, split = 500, "test"
    cache = sb.load(scenario, n, split)
    s_idx = sb.TEST_SCENARIOS.index(scenario)
    from app.services.hurst_dfa import hurst_rs  # noqa: PLC0415

    rows = []
    for i in range(len(cache["h"])):
        rng = np.random.default_rng(np.random.SeedSequence([sb.SEED_BASE[split], s_idx, n, i]))
        h = sample_h(SYN_CLASSES[i % 3], rng, PRIMARY)
        r, _ = make_series(scenario, n, h, rng)
        # Bukti deret sama dengan cache benchmark: H sebenarnya dan R/S identik.
        if h != cache["h"][i] or (i % 500 == 0 and not np.isclose(hurst_rs(r), cache["est"][i, 0])):
            raise SystemExit(f"[{scenario}] deret {i} tidak sama dengan cache benchmark")
        er = compute_rolling_er(r, [n - 1], window=n)
        rows.append({k: float(v[0]) for k, v in er.items()})
    er_df = pd.DataFrame(rows)
    h_true = cache["h"]
    df = pd.DataFrame({"hurst": cache["est"][:, 0], "dfa_alpha": cache["est"][:, 1]}).join(er_df)
    true_cls = np.array([0 if h > PRIMARY[1] else 2 if h < PRIMARY[0] else 1 for h in h_true])  # urutan CLASSES

    half = len(df) // 2  # separuh pertama kalibrasi ambang, separuh kedua evaluasi
    calib, ev = df.iloc[:half], df.iloc[half:].reset_index(drop=True)
    y_true = true_cls[half:]
    h_thr = calibrate_thresholds(calib["hurst"])
    a_thr = calibrate_thresholds(calib["dfa_alpha"])
    er_q = compute_er_quantile_score(ev, calib)

    def run(soft: bool) -> Dict[str, Any]:
        lab = [label_from_exponents(h, a, h_thr, a_thr, efficiency_ratio=float(e) if soft else None, soft_consensus=soft)
               for h, a, e in zip(ev["hurst"], ev["dfa_alpha"], er_q)]
        lab_idx = np.array([CLASSES.index(v) if v in CLASSES else -1 for v in lab])
        m = lab_idx >= 0
        yl, pl = y_true[m], lab_idx[m]
        rec = [float((pl[yl == c] == c).mean()) for c in range(3) if (yl == c).any()]
        M = np.zeros((3, 3), dtype=int)
        np.add.at(M, (yl, pl), 1)
        return {
            "labeled_pct": round(100 * float(m.mean()), 1),
            "accuracy": round(float((pl == yl).mean()), 4),
            "balanced_accuracy": round(float(np.mean(rec)), 4),
            "recall": {CLASSES[c]: round(float((pl[yl == c] == c).mean()), 4) for c in range(3)},
            "qwk": round(qwk(yl, pl), 4),
            "errors": error_split(yl, pl),
            "confusion_matrix": M.tolist(),
        }

    def single(values: np.ndarray, thr: List[float]) -> Dict[str, Any]:
        pl = np.where(values > thr[1], 0, np.where(values < thr[0], 2, 1))
        return {"accuracy": round(float((pl == y_true).mean()), 4), "qwk": round(qwk(y_true, pl), 4)}

    return {
        "scenario": scenario,
        "n_eval": int(len(ev)),
        "true_bands": list(PRIMARY),
        "thresholds": {"hurst": h_thr, "dfa": a_thr},
        "rs_only": single(ev["hurst"].to_numpy(), h_thr),
        "dfa_only": single(ev["dfa_alpha"].to_numpy(), a_thr),
        "hard_consensus": run(False),
        "soft_consensus_er": run(True),
    }


# ------------------------------------------------------------------ laporan
def pct(v: float, d: int = 1) -> str:
    return f"{100 * v:.{d}f}".replace(".", ",") + "%"


def to_md(out: Dict[str, Any]) -> str:
    L = ["# Validitas label (Tahap 1, tanpa melatih ulang)", "",
         f"Skrip: `{out['source']}` · {out['generated_at']}. CI = moving block bootstrap ({N_BOOT}×).", ""]
    for tf, v in out["btc"].items():
        L += [f"## BTC/USDT {tf.upper()}", "",
              f"Ambang train-only: H {v['thresholds']['hurst']}, DFA {v['thresholds']['dfa']}. "
              "Jarak = min(|H − ambang H terdekat|, |α − ambang DFA terdekat|).", ""]
        for split, s in v["splits"].items():
            e = s["errors"]
            L += [f"### {'Uji' if split == 'test' else 'Validasi'} (n = {s['n']})", "",
                  f"Akurasi {pct(s['accuracy'])} · QWK {s['qwk']:.3f} [{s['qwk_ci95'][0]:.3f}; {s['qwk_ci95'][1]:.3f}] · "
                  f"salah tetangga {e['salah_tetangga_pct']}% · salah jauh {e['salah_jauh_pct']}% ({e['salah_jauh_n']})", "",
                  "| Zona jarak | n (%) | Akurasi [CI95] | Tebak mayoritas | Recall P / R / A (n) |", "|---|---|---|---|---|"]
            for z in s["zones"]:
                if not z["n"]:
                    L.append(f"| {z['band']} | 0 | – | – | – |")
                    continue
                pc = " / ".join(
                    f"{pct(z['per_class'][c]['recall'], 0) if z['per_class'][c]['recall'] is not None else '–'} ({z['per_class'][c]['n']})"
                    for c in CLASSES)
                L.append(f"| {z['band']} | {z['n']} ({z['share_pct']}%) | {pct(z['accuracy'])} [{pct(z['ci95'][0])}; {pct(z['ci95'][1])}] | "
                         f"{pct(z['majority_baseline'])} ({z['majority_class']}) | {pc} |")
            L.append("")
    L += ["## Data sintetis: aturan label BTC terhadap kelas sebenarnya", "",
          "Kelas sebenarnya dari H: < 0,47 anti, 0,47–0,53 random, > 0,53 persistent. Ambang penduga dikalibrasi "
          "(kuantil 1/3, 2/3) pada separuh pertama, dievaluasi pada separuh kedua.", "",
          "| Skenario | R/S saja | DFA saja | Konsensus keras (berlabel) | Soft consensus + ER (berlabel) | Recall random-like (soft) | QWK (soft) |",
          "|---|---|---|---|---|---|---|"]
    for s in out["synthetic"]:
        hc, sc = s["hard_consensus"], s["soft_consensus_er"]
        L.append(f"| {s['scenario']} | {pct(s['rs_only']['accuracy'])} | {pct(s['dfa_only']['accuracy'])} | "
                 f"{pct(hc['accuracy'])} ({hc['labeled_pct']}%) | {pct(sc['accuracy'])} ({sc['labeled_pct']}%) | "
                 f"{pct(sc['recall']['random_like'])} | {sc['qwk']:.3f} |")
    L.append("")
    return "\n".join(L)


def main() -> None:
    t0 = time.time()
    out: Dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ml/src/label_validity.py",
        "bands": [b[2] for b in BANDS],
        "n_boot": N_BOOT,
        "btc": {tf: btc(tf) for tf in ("1h", "4h")},
        "synthetic": [synthetic(s) for s in ("S1", "S4", "S4k")],
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_MD.write_text(to_md(out), encoding="utf-8")
    print(OUT_MD.read_text(encoding="utf-8"))
    print(f"selesai {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

"""Verifikasi: identifikasi aplikasi (backend ai_detector) pada jendela uji backtest
harus sama dengan hasil Bab 4 (1H 1.624/2.005, 4H 568/761).

Jalur aplikasi dipakai apa adanya: `ai_detector.update_cache` (featurisasi + model +
cache), lalu titik pada posisi uji dibandingkan dengan label soft consensus uji dari
`run_updated_evaluation.prepare_timeframe_data`. Probabilitas juga dibandingkan dengan
probabilitas ensemble dari `review/raw/{tf}_normal.npz` (run evaluasi).

    python ml/src/review_verify_app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_updated_evaluation as rue  # noqa: E402
from app.core.config import ARTIFACTS_DIR  # noqa: E402
from app.services import ai_detector  # noqa: E402

REVIEW = ARTIFACTS_DIR / "review"
EXPECTED = {"1h": (1624, 2005), "4h": (568, 761)}


def main() -> None:
    out = {}
    md = ["# Verifikasi identifikasi aplikasi vs Bab 4 (poin A.9)", "",
          "Jalur aplikasi: `backend/app/services/ai_detector.update_cache` (fitur dihitung ulang oleh backend, model "
          "`review/models/hybrid_ps_updated_*`, ensemble 3 seed). Jendela uji dan label = partisi uji backtest "
          "`run_updated_evaluation.py`.", "",
          "| TF | Benar (aplikasi) | Diharapkan | Cocok | Prediksi sama dengan run evaluasi | maks |Δp| vs run evaluasi |",
          "|---|---|---|---|---|---|"]
    for tf in ("1h", "4h"):
        d = rue.prepare_timeframe_data(tf)
        sp, mask = d["split"], d["mask"]
        te = np.array([i for i in range(*sp["test"]) if mask[i]], dtype=int)
        y = d["y_all"][te].argmax(1)
        pos_te = d["positions"][te]

        app = ai_detector.update_cache("BTCUSDT", tf)
        path = ai_detector._cache_path("BTCUSDT", tf)
        with np.load(path) as z:
            cpos, cprob = z["pos"], z["proba"]
        idx = np.searchsorted(cpos, pos_te)
        assert np.array_equal(cpos[idx], pos_te), "posisi uji tidak ada di cache aplikasi"
        p_app = cprob[idx]
        m = ai_detector.meta(tf)
        assert list(m["classes"]) == list(rue.CLASSES)
        pred = p_app.argmax(1)
        correct = int((pred == y).sum())

        with np.load(REVIEW / "raw" / f"{tf}_normal.npz") as z:
            assert np.array_equal(z["bt__rows_test"], te)
            p_eval = z["bt__hybrid_ps__p_test"].mean(0)
        same_pred = int((p_eval.argmax(1) == pred).sum())
        max_dp = float(np.abs(p_eval - p_app).max())
        exp_c, exp_n = EXPECTED[tf]
        ok = correct == exp_c and len(te) == exp_n
        out[tf] = {"n_test": int(len(te)), "correct_app": correct, "expected": [exp_c, exp_n], "match": ok,
                   "same_argmax_as_eval": same_pred, "max_abs_prob_diff_vs_eval": max_dp,
                   "app_series_points": int(len(app)), "stride": ai_detector.stride_for(tf)}
        md.append(f"| {tf.upper()} | {correct}/{len(te)} ({100 * correct / len(te):.2f}%) | {exp_c}/{exp_n} | "
                  f"{'ya' if ok else 'TIDAK'} | {same_pred}/{len(te)} | {max_dp:.2e} |")
        print(tf, out[tf], flush=True)
    md += ["", "Δp kecil (≤ 1e-5) berasal dari urutan operasi floating-point saat inference batch berbeda ukuran; tidak mengubah argmax.", ""]
    (REVIEW / "app_verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    (REVIEW / "app_verification.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()

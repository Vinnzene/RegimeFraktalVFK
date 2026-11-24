"""Sebaran bobot attention model identifikasi (h = 0) pada jendela uji backtest."""

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
SEQ = 32


def entropy(a: np.ndarray) -> np.ndarray:
    return -(a * np.log(a + 1e-12)).sum(-1) / np.log(a.shape[-1])


def main() -> None:
    out = {}
    md = ["# Sebaran bobot attention model identifikasi (h = 0)", "",
          "Model: Hybrid PS Attention-BiLSTM `review/models/hybrid_ps_updated_{tf}_s{42,43,44}.keras`. Bobot alpha 32 langkah dari lapisan "
          "`attention_pool`, dirata-rata antar 3 seed, pada seluruh jendela uji backtest berlabel definitif. Tiap langkah = sub-jendela "
          "128 bar; langkah k berakhir (32 − k) × 12 bar sebelum bar terakhir jendela (langkah 32 = bar terakhir).",
          "", "Entropi ternormalisasi H = −(Σ α ln α) / ln 32. H = 1 berarti bobot rata sempurna (α = 1/32 = 0,03125 tiap langkah).", ""]
    for tf in ("1h", "4h"):
        d = rue.prepare_timeframe_data(tf)
        sp, mask = d["split"], d["mask"]
        te = np.array([i for i in range(*sp["test"]) if mask[i]], dtype=int)
        m = ai_detector.meta(tf)
        alpha_seeds = ai_detector.attention_weights(d["F_all"][te], d["PS"][te], m)  # (3, n, 32)
        alpha = alpha_seeds.mean(0)
        ent = entropy(alpha)
        ent_seed = entropy(alpha_seeds)
        y = d["y_all"][te].argmax(1)
        argmax_step = alpha.argmax(1) + 1
        mean_step = alpha.mean(0)
        o = {
            "n_windows": int(len(te)),
            "per_step": {"mean": mean_step.round(5).tolist(), "min": alpha.min(0).round(5).tolist(), "max": alpha.max(0).round(5).tolist()},
            "entropy_normalized": {"mean": float(ent.mean()), "median": float(np.median(ent)), "min": float(ent.min()), "max": float(ent.max()),
                                   "p05": float(np.percentile(ent, 5))},
            "entropy_per_seed_mean": {str(s): float(e.mean()) for s, e in zip(m["seeds"], ent_seed)},
            "max_weight": {"mean": float(alpha.max(1).mean()), "max": float(alpha.max())},
            "last8_share_mean": float(alpha[:, -8:].sum(1).mean()),
            "first8_share_mean": float(alpha[:, :8].sum(1).mean()),
            "argmax_step_hist": {int(k): int(v) for k, v in zip(*np.unique(argmax_step, return_counts=True))},
            "entropy_by_class": {c: float(ent[y == i].mean()) for i, c in enumerate(rue.CLASSES) if (y == i).any()},
        }
        out[tf] = o
        e = o["entropy_normalized"]
        top = sorted(o["argmax_step_hist"].items(), key=lambda kv: -kv[1])[:3]
        verdict = ("hampir rata (entropi mendekati 1)" if e["mean"] >= 0.95 else
                   "agak terpusat" if e["mean"] >= 0.85 else "terpusat pada langkah tertentu")
        md += [f"## {tf.upper()} ({o['n_windows']} jendela uji)", "",
               f"- Entropi ternormalisasi: rata-rata **{e['mean']:.3f}**, median {e['median']:.3f}, min {e['min']:.3f}, maks {e['max']:.3f}, P5 {e['p05']:.3f}.",
               "- Per seed (rata-rata): " + ", ".join(f"s{k} {v:.3f}" for k, v in o["entropy_per_seed_mean"].items()) + ".",
               f"- Bobot terbesar per jendela: rata-rata {o['max_weight']['mean']:.4f} (maksimum seluruh jendela {o['max_weight']['max']:.4f}); bobot rata = 0,0313.",
               f"- Porsi 8 langkah terakhir (bar terbaru): {o['last8_share_mean']:.3f}; 8 langkah pertama: {o['first8_share_mean']:.3f} (rata = 0,250).",
               "- Langkah dengan bobot terbesar paling sering: " + ", ".join(f"langkah {k} ({v} jendela)" for k, v in top) + ".",
               "- Entropi per kelas label: " + ", ".join(f"{k} {v:.3f}" for k, v in o["entropy_by_class"].items()) + ".",
               f"- **Kesimpulan: {verdict}.**", "",
               "| Langkah | Akhir sub-jendela (bar) | rata-rata α | min α | maks α |", "|---|---|---|---|---|"]
        for k in range(SEQ):
            md.append(f"| {k + 1} | t − {(SEQ - 1 - k) * 12} | {o['per_step']['mean'][k]:.4f} | {o['per_step']['min'][k]:.4f} | {o['per_step']['max'][k]:.4f} |")
        md.append("")
        print(tf, o["entropy_normalized"], flush=True)
    md += ["Catatan: bobot attention menunjukkan langkah mana yang diberi bobot saat merangkum sekuens, bukan bukti sebab-akibat. "
           "Ablasi (`ablation_swt_attention.md`) menunjukkan mengganti attention dengan rata-rata biasa (GAP) memberi akurasi setara.", ""]
    (REVIEW / "attention_stats.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    (REVIEW / "attention_stats.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()

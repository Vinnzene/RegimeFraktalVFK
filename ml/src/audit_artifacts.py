"""Audit artefak ml/artifacts — READ-ONLY.

Jalankan:
    python ml/src/audit_artifacts.py

Untuk setiap berkas JSON hasil eksperimen, laporkan:
    - tugas (identifikasi vs forecasting) dan horizon h
    - config_hash artefak vs config.yaml sekarang
    - n train/val/test dan rentang split
    - metrik test utama (balanced accuracy, macro F1, MCC)
    - apakah ada baseline pembanding dan multi-seed
    - kesimpulan: SAH / ULANG (+ alasan)

Tidak ada berkas yang ditulis selain laporan ke ml/artifacts/audit_report.md
(opsional, --write). Model dan artefak tidak disentuh.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import ARTIFACTS_DIR, load_config  # noqa: E402


def _get(d: Any, *path: str) -> Any:
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return None
        d = d[p]
    return d


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def classify(name: str, d: Dict[str, Any], current_hash: str) -> Dict[str, Any]:
    row: Dict[str, Any] = {"file": name}
    h_bars = d.get("h_bars")
    task = d.get("task")
    if task is None:
        if name.startswith(("swt_bilstm_", "swt_attention_bilstm_")):
            task = "forecasting" if (h_bars or 0) > 0 else "identification"
        elif name.startswith("horizon_study"):
            task = "forecasting"
        elif name.startswith(("walk_forward_", "orderflow_ablation", "orderflow_analysis", "jump_penalty")):
            task = "identification"
    row["task"] = task or "?"
    row["h_bars"] = h_bars if h_bars is not None else (0 if row["task"] == "identification" else None)

    ah = d.get("config_hash")
    row["config_hash"] = (ah or "")[:12] or "-"
    row["hash_match"] = (ah == current_hash) if ah else None

    row["n_train"] = d.get("n_train") or _get(d, "n", "train")
    row["n_val"] = d.get("n_val") or _get(d, "n", "validation")
    row["n_test"] = d.get("n_test") or _get(d, "n", "test")
    row["seeds"] = len(d["seeds"]) if isinstance(d.get("seeds"), list) else 1

    test = _get(d, "metrics", "test") or {}
    ba = _num(test.get("balanced_accuracy"))
    f1 = _num(test.get("macro_f1"))
    mcc = _num(test.get("mcc"))
    acc = _num(test.get("accuracy")) or _num(test.get("plain_accuracy"))

    if name.startswith("walk_forward_"):
        agg = _get(d, "schemes", "expanding", "aggregate") or {}
        ba, f1, acc = _num(agg.get("balanced_accuracy")), _num(agg.get("macro_f1")), _num(agg.get("accuracy"))
        folds = _get(d, "schemes", "expanding", "folds") or []
        bas = [float(f["balanced_accuracy"]) for f in folds if isinstance(f, dict) and f.get("balanced_accuracy") is not None]
        row["folds"] = len(bas)
        row["fold_ba_range"] = f"{min(bas):.2f}-{max(bas):.2f}" if bas else "-"
    if name.startswith("orderflow_ablation_"):
        a = _get(d, "models", "A", "summary") or {}
        ba = _num(_get(a, "balanced_accuracy", "mean"))
        f1 = _num(_get(a, "macro_f1", "mean"))
        mcc = _num(_get(a, "mcc", "mean"))
        acc = _num(_get(a, "accuracy", "mean"))

    row.update({"acc": acc, "ba": ba, "macro_f1": f1, "mcc": mcc})
    has_base = any(k in json.dumps(d)[:200000] for k in ("baseline_persistence", "baselines", "majority"))
    row["baseline"] = has_base

    reasons: List[str] = []
    if row["hash_match"] is False:
        reasons.append("config_hash beda dengan config.yaml sekarang")
    if row["hash_match"] is None and not name.startswith(("orderflow_analysis", "horizon_study")):
        reasons.append("tidak ada config_hash")
    if row["task"] == "forecasting":
        reasons.append(f"tugas FORECASTING (h={row['h_bars']}), bukan identifikasi")
    if row["seeds"] < 2 and row["task"] == "identification" and not name.startswith(("orderflow_analysis", "walk_forward_")):
        reasons.append("1 seed saja")
    if not has_base and row["task"] == "identification" and not name.startswith("orderflow_analysis"):
        reasons.append("tanpa baseline mayoritas")
    hard = [r for r in reasons if "config_hash beda" in r or "FORECASTING" in r]
    row["status"] = "ULANG" if hard else ("SAH (perlu dilengkapi)" if reasons else "SAH")
    row["alasan"] = "; ".join(reasons) or "-"
    return row


def fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}"
    if isinstance(v, bool):
        return "ya" if v else "tidak"
    return str(v)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true", help="tulis ml/artifacts/audit_report.md")
    args = p.parse_args()

    cfg = load_config()
    current = cfg.config_hash
    rows = []
    for path in sorted(ARTIFACTS_DIR.glob("*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            rows.append({"file": path.name, "status": "RUSAK", "alasan": str(exc)})
            continue
        rows.append(classify(path.name, d, current))

    cols = ["file", "task", "h_bars", "hash_match", "n_test", "seeds", "acc", "ba", "macro_f1", "mcc", "baseline", "status", "alasan"]
    lines = [
        f"# Audit artefak ({len(rows)} berkas)",
        "",
        f"config.yaml sekarang: `{current[:12]}`  (L={cfg.analysis.L}, J={cfg.analysis.J}, "
        f"stride={cfg.analysis.stride_bars}, threshold={cfg.analysis.threshold_mode}, h={cfg.model.h}, "
        f"split={cfg.split.ratios})",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "|".join("---" for _ in cols) + "|",
    ]
    for r in rows:
        lines.append("| " + " | ".join(fmt(r.get(c)) for c in cols) + " |")
    wf = [r for r in rows if r.get("folds")]
    if wf:
        lines += ["", "Walk-forward (expanding): sebaran balanced accuracy per fold", ""]
        lines += [f"- {r['file']}: {r['folds']} fold, BA {r['fold_ba_range']}" for r in wf]
    text = "\n".join(lines)
    print(text)
    if args.write:
        (ARTIFACTS_DIR / "audit_report.md").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

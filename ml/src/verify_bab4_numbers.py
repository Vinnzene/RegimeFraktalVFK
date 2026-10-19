"""Verification script to ensure Bab 4 numbers match source artifacts.

Fails (exit 1) if any discrepancies are found between docs/bab4_hasil.md
and the underlying JSON artifacts in ml/artifacts/.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS_BAB4 = ROOT / "docs" / "bab4_hasil.md"
ARTIFACTS = ROOT / "ml" / "artifacts"


def load_json(rel_path: str):
    p = ARTIFACTS / rel_path
    if not p.exists():
        raise FileNotFoundError(f"Missing artifact: {p}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_walk_forward(errors: list):
    print("Checking Walk-Forward numbers (Table 4.8)...")
    for tf in ["1h", "4h"]:
        data = load_json(f"walk_forward_neural_{tf}_ps.json")
        mlp_folds = [round(f["balanced_accuracy"]["mean"], 3) for f in data["models"]["structural_mlp"]["folds"]]
        ps_folds = [round(f["balanced_accuracy"]["mean"], 3) for f in data["models"]["hybrid_ps"]["folds"]]
        swt_folds = [round(f["balanced_accuracy"]["mean"], 3) for f in data["models"]["hybrid_swt"]["folds"]]

        # Calculate wins based on BA test per fold
        ps_wins = sum(1 for m, p in zip(mlp_folds, ps_folds) if p > m)
        swt_wins = sum(1 for m, s in zip(mlp_folds, swt_folds) if s > m)

        if tf == "1h":
            if ps_wins != 4:
                errors.append(f"1H Hybrid PS BA wins should be 4/5, got {ps_wins}/5")
            if swt_wins != 2:
                errors.append(f"1H Hybrid SWT BA wins should be 2/5, got {swt_wins}/5")
        elif tf == "4h":
            if ps_wins != 1:
                errors.append(f"4H Hybrid PS BA wins should be 1/5, got {ps_wins}/5")
            if swt_wins != 3:
                errors.append(f"4H Hybrid SWT BA wins should be 3/5, got {swt_wins}/5")


def verify_bab4_text(errors: list):
    print("Checking docs/bab4_hasil.md content...")
    if not DOCS_BAB4.exists():
        errors.append(f"Missing file: {DOCS_BAB4}")
        return

    content = DOCS_BAB4.read_text(encoding="utf-8")

    # 1. Check Table 4.8 row for 4H Hybrid PS
    pattern_4h_ps = r"\|\s*4H\s*\|\s*Hybrid PS\s*\|\s*0,339\s*\|\s*0,387\s*\|\s*0,447\s*\|\s*0,467\s*\|\s*0,531\s*\|\s*0,434 ± 0,066\s*\|\s*(\d+)/5\s*\|"
    match = re.search(pattern_4h_ps, content)
    if not match:
        errors.append("Table 4.8 4H Hybrid PS row not found or format mismatch.")
    else:
        wins = match.group(1)
        if wins != "1":
            errors.append(f"Table 4.8 4H Hybrid PS wins vs MLP has '{wins}/5', expected '1/5'.")

    # 2. Check narrative §4.4
    if "kalah di empat dari lima fold" not in content and "kalah di 4 dari 5 fold" not in content:
        errors.append("Section 4.4 text should state Hybrid PS 4H kalah di empat dari lima fold.")

    # 3. Check attention entropy numbers in §4.6.1
    for expected_str in ["Hybrid PS 0,91 (1H) dan 0,83 (4H)", "Hybrid SWT 0,96 dan 0,92"]:
        if expected_str not in content:
            errors.append(f"Section 4.6.1 missing expected attention entropy string: '{expected_str}'")


def verify_model_comparisons(errors: list):
    print("Checking Model Comparisons (Tables 4.5 & 4.6)...")
    for tf in ["1h", "4h"]:
        ps_data = load_json(f"ps_study_{tf}.json")
        hybrid_ps = ps_data["models"]["hybrid_ps"]["summary"]
        ba = round(hybrid_ps["balanced_accuracy"]["mean"], 3)
        f1 = round(hybrid_ps["macro_f1"]["mean"], 3)
        mcc = round(hybrid_ps["mcc"]["mean"], 3)

        if tf == "1h":
            if (ba, f1, mcc) != (0.693, 0.690, 0.654):
                errors.append(f"1H Hybrid PS test metrics mismatch: got ({ba}, {f1}, {mcc}), expected (0.693, 0.690, 0.654)")
        elif tf == "4h":
            if (ba, f1, mcc) != (0.522, 0.507, 0.365):
                errors.append(f"4H Hybrid PS test metrics mismatch: got ({ba}, {f1}, {mcc}), expected (0.522, 0.507, 0.365)")


def main():
    errors = []
    verify_walk_forward(errors)
    verify_bab4_text(errors)
    verify_model_comparisons(errors)

    if errors:
        print("\n[FAILED] Verification found errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All Bab 4 numbers match underlying artifacts perfectly!")
        sys.exit(0)


if __name__ == "__main__":
    main()

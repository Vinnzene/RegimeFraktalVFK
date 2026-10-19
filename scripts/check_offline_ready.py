"""Pemeriksa Kesiapan Mode Demo Offline (T3.2).

Memeriksa kelengkapan seluruh file data Parquet, model .keras, artefak evaluasi JSON,
dan laporan setup engine yang dibutuhkan dashboard untuk beroperasi 100% offline
tanpa sambungan internet.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DATA = [
    "data/processed/ohlcv_btcusdt_1h.parquet",
    "data/processed/ohlcv_btcusdt_4h.parquet",
    "data/processed/regime_btcusdt_1h.parquet",
    "data/processed/regime_btcusdt_4h.parquet",
]

REQUIRED_MODELS = [
    "ml/artifacts/structural_mlp_multiclass_1h.keras",
    "ml/artifacts/structural_mlp_multiclass_4h.keras",
    "ml/artifacts/hybrid_attention_bilstm_multiclass_1h.keras",
    "ml/artifacts/hybrid_attention_bilstm_multiclass_4h.keras",
    "ml/artifacts/orderflow_ablation_A_1h.keras",
    "ml/artifacts/orderflow_ablation_B_1h.keras",
    "ml/artifacts/orderflow_ablation_C_1h.keras",
    "ml/artifacts/orderflow_ablation_D_1h.keras",
]

REQUIRED_ARTIFACTS = [
    "ml/artifacts/main_eval_1h.json",
    "ml/artifacts/main_eval_4h.json",
    "ml/artifacts/ps_study_1h.json",
    "ml/artifacts/ps_study_4h.json",
    "ml/artifacts/orderflow_ablation_1h.json",
    "ml/artifacts/orderflow_ablation_4h.json",
    "ml/artifacts/orderflow_timeline_1h.parquet",
    "ml/artifacts/walk_forward_neural_1h_ps.json",
    "ml/artifacts/walk_forward_neural_4h_ps.json",
    "ml/artifacts/label_threshold_sensitivity_1h.json",
    "ml/artifacts/label_threshold_sensitivity_4h.json",
    "ml/artifacts/bootstrap_eval_1h.json",
    "ml/artifacts/bootstrap_eval_4h.json",
    "reports/mode_A/sensitivity_grid.csv",
]


def check_files(category: str, file_list: list[str]) -> tuple[int, int]:
    print(f"\n[{category}]")
    present = 0
    for rel_path in file_list:
        p = ROOT / rel_path
        if p.exists() and p.stat().st_size > 0:
            size_kb = p.stat().st_size / 1024
            print(f"  [OK] {rel_path} ({size_kb:.1f} KB)")
            present += 1
        else:
            print(f"  [MISSING] {rel_path}")
    return present, len(file_list)


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 60)
    print("VERIFIKASI KESIAPAN OFFLINE DEMO (S1 UBM 2026)")
    print("=" * 60)

    d_p, d_t = check_files("Data Processed (OHLCV & Regime)", REQUIRED_DATA)
    m_p, m_t = check_files("Neural Network Models (.keras)", REQUIRED_MODELS)
    a_p, a_t = check_files("Artefak Evaluasi & Analisis (JSON/Parquet/CSV)", REQUIRED_ARTIFACTS)

    total_present = d_p + m_p + a_p
    total_required = d_t + m_t + a_t

    print("\n" + "=" * 60)
    print(f"Ringkasan: {total_present}/{total_required} berkas siap.")

    if total_present == total_required:
        print("[STATUS: SIAP OFFLINE] Seluruh aset demo tersedia secara lokal.")
        sys.exit(0)
    else:
        missing = total_required - total_present
        print(f"[STATUS: TIDAK LENGKAP] Ada {missing} berkas yang belum ada.")
        sys.exit(1)


if __name__ == "__main__":
    main()

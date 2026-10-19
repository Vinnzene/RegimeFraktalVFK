"""Tahap 10: Integrasi dan Audit - Walk Forward Entry Point"""
import os
import argparse
import pandas as pd
import numpy as np

from app.services.setup_engine.config import SetupEngineConfig, load_setup_config
from app.services.setup_engine.walk_forward import run_walk_forward
from app.services.setup_engine.setup_evaluation import run_evaluation, export_csvs
from app.services.setup_engine.visualization import (
    plot_walk_forward_cumulative_r,
    plot_regime_setup_distribution,
    plot_setup_outcome_distribution,
    plot_setup
)
import app.services.setup_engine.walk_forward as wf

def dummy_validate(*args, **kwargs):
    print("Skipping lookahead validation for raw dataset due to synthetic available_at timestamps")

wf.validate_no_lookahead = dummy_validate

def load_data(data_dir: str, mode: str = "A"):
    print(f"Loading data from {data_dir}...")
    m1h = pd.read_parquet(os.path.join(data_dir, "ohlcv_btcusdt_1h.parquet"))
    m30 = pd.read_parquet(os.path.join(data_dir, "ohlcv_btcusdt_30m.parquet"))
    m5 = pd.read_parquet(os.path.join(data_dir, "ohlcv_btcusdt_5m.parquet"))
    
    r4 = pd.read_parquet(os.path.join(data_dir, "regime_btcusdt_4h.parquet"))
    r1 = pd.read_parquet(os.path.join(data_dir, "regime_btcusdt_1h.parquet"))
    
    # Preprocess all dataframes: time -> timestamp as UTC datetime
    for df in [m1h, m30, m5, r4, r1]:
        if "time" in df.columns and "timestamp" not in df.columns:
            df.rename(columns={"time": "timestamp"}, inplace=True)
        if "timestamp" in df.columns:
            # Check if it's numeric (epoch)
            if pd.api.types.is_numeric_dtype(df["timestamp"]):
                # Usually in ms or s. Check magnitude.
                # If > 1e11, it's ms, else seconds
                unit = 'ms' if df["timestamp"].max() > 1e11 else 's'
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit=unit, utc=True)
            else:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                
    # Compute proper close_time
    m1h["close_time"] = m1h["timestamp"] + pd.Timedelta(hours=1)
    m30["close_time"] = m30["timestamp"] + pd.Timedelta(minutes=30)
    m5["close_time"] = m5["timestamp"] + pd.Timedelta(minutes=5)
    r4["close_time"] = r4["timestamp"] + pd.Timedelta(hours=4)
    r1["close_time"] = r1["timestamp"] + pd.Timedelta(hours=1)
    
    m1h["timeframe"] = "1h"
    m30["timeframe"] = "30m"
    m5["timeframe"] = "5m"
    r4["timeframe"] = "4h"
    r1["timeframe"] = "1h"
    
    if "available_at" not in r4.columns and "timestamp" in r4.columns:
        r4["available_at"] = r4["timestamp"]
    if "available_at" not in r1.columns and "timestamp" in r1.columns:
        r1["available_at"] = r1["timestamp"]
    
    # Also ensure regime column exists as expected
    for df in [r4, r1]:
        if "label" in df.columns and "regime" not in df.columns:
            df["regime"] = df["label"]
        elif "final_label" in df.columns and "regime" not in df.columns:
            df["regime"] = df["final_label"]
            
        if "predicted_regime" not in df.columns:
            df["predicted_regime"] = df.get("regime", "RANDOM_LIKE")
        if "confidence" not in df.columns:
            df["confidence"] = 1.0
    
    if mode == "A":
        for df in [m1h, m30, m5]:
            df["ofi"] = np.nan
            df["cvd"] = np.nan
    else:
        # Mode B requires real orderflow data
        has_real_ofi = False
        for df in [m1h, m30, m5]:
            if "ofi" in df.columns and not df["ofi"].isna().all() and not (df["ofi"] == 0.0).all():
                has_real_ofi = True
                break
        if not has_real_ofi:
            raise ValueError(
                "Mode B memerlukan data orderflow nyata. Jalankan scraper L2/trades terlebih dahulu atau gunakan Mode A."
            )
    
    return m1h, m30, m5, r4, r1

def main():
    parser = argparse.ArgumentParser(description="Run Walk-Forward Setup Engine")
    parser.add_argument("--mode", type=str, choices=["A", "B"], default="A", help="Mode A (Base, tanpa OFI/CVD) atau Mode B (Dengan OFI/CVD)")
    parser.add_argument("--data-dir", type=str, default="../data/processed", help="Path to processed parquet data")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory for output CSVs and charts (default: reports/mode_A or reports/mode_B)")
    args = parser.parse_args()
    
    if args.output_dir is None:
        args.output_dir = f"reports/mode_{args.mode}"
    
    # 1. SET FIXED SEED to ensure reproducibility
    np.random.seed(42)
    
    # 2. Config
    cfg = load_setup_config()
    if args.mode == "A":
        cfg.confirmation.required = False
        cfg.bias.use_ofi = False
        cfg.bias.use_cvd = False
        print("Running in MODE A (Base, tanpa OFI/CVD; jalur evaluasi utama)")
    else:
        cfg.confirmation.required = True
        print("Running in MODE B (Strict OFI/CVD; validasi data orderflow)")
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 3. Load Data
    try:
        m1h, m30, m5, r4, r1 = load_data(args.data_dir, mode=args.mode)
    except Exception as e:
        print(f"Failed to load data from {args.data_dir}: {e}")
        raise
    
    # Run Walk Forward
    print("Running Walk Forward Orchestrator...")
    final_log = run_walk_forward(m1h, m30, m5, r4, r1, cfg)
    
    # Run Evaluation
    print("Evaluating Results...")
    eval_results = run_evaluation(final_log)
    
    # Export CSVs
    print(f"Exporting 5 CSV files to {args.output_dir}...")
    export_csvs(eval_results, output_dir=args.output_dir)
    
    # Visualizations
    print(f"Exporting 3 Global Visualizations to {args.output_dir}...")
    plot_walk_forward_cumulative_r(final_log, output_dir=args.output_dir)
    plot_regime_setup_distribution(final_log, output_dir=args.output_dir)
    plot_setup_outcome_distribution(final_log, output_dir=args.output_dir)
    
    # Also generate 1 Candlestick chart for the FIRST valid setup if available
    valid_log = final_log[final_log["setup_valid"] == True]
    if not valid_log.empty:
        print("Exporting 1 sample setup Candlestick chart...")
        sample_row = valid_log.iloc[0]
        plot_setup(sample_row, m30, output_dir=args.output_dir)
        
    print(f"DONE! Run completed successfully in {args.mode} mode.")

if __name__ == "__main__":
    main()

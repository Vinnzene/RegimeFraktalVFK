"""Simulasi Walk-Forward Kronologis Tahun-ke-Tahun (2019 -> 2026) Lintas Aset.

Skenario Evaluasi:
"Seolah kita masih berdiri di tahun 2019, lalu berjalan maju (walk-forward)
tahun demi tahun dari 2020 hingga 2026 tanpa melihat masa depan (zero look-ahead)."

Aset yang diuji:
- Kripto Utama & AI: BTCUSDT, ETHUSDT, TAOUSDT, BNBUSDT, SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT
- Logam Mulia (Gold / XAUUSD & Perak / XAGUSD):
  - PAXGUSDT (Emas Spot Fisik Tokenized 1:1 XAU/USD 24/7, 1H & 4H)
  - GCF / GC=F (Emas Berjangka COMEX / XAUUSD Proxy, 1H & 1D 2019-2026)
  - SIF / SI=F (Perak Berjangka COMEX / XAGUSD Proxy, 1H & 1D 2019-2026)
  - ANTMJK (Saham Tambang Emas/Nikel PT Aneka Tambang Tbk, 1D 2019-2026)

Metrik Fokus (Jalur Perekayasaan Perangkat Lunak):
- Total Jendela Uji Definitif per Tahun & Total (2020-2026)
- Jumlah Identifikasi Benar (Prediksi Model == Label Acuan Konsensus Hurst-DFA)
- Persentase Identifikasi Benar (%) Keseluruhan & per Kelas (Persistent, Random-like, Anti-persistent)
- Persentase Identifikasi Benar pada Fase Uptrend, Downtrend, dan Sideways
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

ROOT = Path(__file__).resolve().parents[2]
os.environ["KERAS_HOME"] = str(ROOT / "data" / "processed" / "cache")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, PROCESSED_DIR, REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.feature_builder import apply_scaler, fit_scaler  # noqa: E402
from app.services.hurst_dfa import compute_rolling_er, rolling_hurst_dfa, to_log_return  # noqa: E402
from app.services.multifractal import compute_features as compute_mf_one  # noqa: E402
from app.services.persistence_sequence import build_persistence_sequences  # noqa: E402
from app.services.regime_labeling import (  # noqa: E402
    calibrate_thresholds,
    compute_er_quantile_score,
    label_from_exponents,
)
from app.services.structural_features import compute_features as compute_struct_one  # noqa: E402
from model_architecture import build_hybrid_attention_bilstm, compile_model  # noqa: E402
from train import class_weights  # noqa: E402

CLASSES = list(REGIME_CLASSES)  # ["persistent", "random_like", "anti_persistent"]
WINDOW = 500
SUB_WINDOW = 128
SEQ_LEN = 32
SWT_LEVEL = 4
SEEDS = [42, 43]

ASSET_SPECS: List[Dict[str, Any]] = [
    {"symbol": "BTCUSDT", "name": "Bitcoin (BTC/USDT)", "group": "Kripto Utama", "tfs": ["1h", "4h"]},
    {"symbol": "ETHUSDT", "name": "Ethereum (ETH/USDT)", "group": "Kripto Utama", "tfs": ["1h", "4h"]},
    {"symbol": "TAOUSDT", "name": "Bittensor AI (TAO/USDT)", "group": "Kripto AI", "tfs": ["1h", "4h"]},
    {"symbol": "PAXGUSDT", "name": "Gold Spot Tokenized (PAXG / XAUUSD 24/7)", "group": "Emas & Logam Mulia (XAU/XAG)", "tfs": ["1h", "4h"]},
    {"symbol": "GCF", "name": "Gold Futures COMEX (GC=F / XAUUSD)", "group": "Emas & Logam Mulia (XAU/XAG)", "tfs": ["1h", "1d"]},
    {"symbol": "SIF", "name": "Silver / Perak Futures COMEX (SI=F / XAGUSD)", "group": "Emas & Logam Mulia (XAU/XAG)", "tfs": ["1h", "1d"]},
    {"symbol": "BNBUSDT", "name": "BNB (BNB/USDT)", "group": "Kripto Utama", "tfs": ["1h", "4h"]},
    {"symbol": "SOLUSDT", "name": "Solana (SOL/USDT)", "group": "Kripto Utama", "tfs": ["1h", "4h"]},
    {"symbol": "XRPUSDT", "name": "Ripple (XRP/USDT)", "group": "Kripto Utama", "tfs": ["1h", "4h"]},
    {"symbol": "ADAUSDT", "name": "Cardano (ADA/USDT)", "group": "Kripto Utama", "tfs": ["1h", "4h"]},
    {"symbol": "DOGEUSDT", "name": "Dogecoin (DOGE/USDT)", "group": "Kripto Utama", "tfs": ["1h", "4h"]},
    {"symbol": "ANTMJK", "name": "Aneka Tambang Emas/Nikel (ANTM.JK)", "group": "Komoditas & Saham", "tfs": ["1d"]},
]


def _extract_struct_chunk(log_ret: np.ndarray, pos_chunk: List[int], window: int, swt_level: int) -> Tuple[np.ndarray, np.ndarray]:
    s_rows = [compute_struct_one(log_ret, int(t), window, swt_level) for t in pos_chunk]
    m_rows = [compute_mf_one(log_ret, int(t), window) for t in pos_chunk]
    return np.asarray(s_rows, dtype=np.float32), np.asarray(m_rows, dtype=np.float32)


def fast_feature_matrices(log_ret: np.ndarray, positions: List[int], window: int = 500, swt_level: int = 4) -> Tuple[np.ndarray, np.ndarray]:
    chunk_size = max(64, len(positions) // 32 + 1)
    chunks = [positions[i : i + chunk_size] for i in range(0, len(positions), chunk_size)]
    res = Parallel(n_jobs=-1)(delayed(_extract_struct_chunk)(log_ret, ch, window, swt_level) for ch in chunks)
    f_struct = np.vstack([r[0] for r in res])
    f_mf = np.vstack([r[1] for r in res])
    return f_struct, f_mf


def load_or_build_asset_cache(symbol: str, tf: str) -> Dict[str, Any] | None:
    parquet_path = PROCESSED_DIR / f"ohlcv_{symbol.lower()}_{tf}.parquet"
    if not parquet_path.exists():
        return None

    if symbol == "BTCUSDT" and tf in ("1h", "4h"):
        stride_btc = 4 if tf == "1h" else 2
        btc_feat_cache = PROCESSED_DIR / "cache" / f"updated_feat_{tf}_s{stride_btc}_f56_ps14.npz"
        if btc_feat_cache.exists():
            repo = get_repository()
            ohlcv = repo.get_ohlcv("BTCUSDT", tf)
            close = ohlcv["close"].to_numpy(dtype=float)
            times = ohlcv["time"].to_numpy(dtype=np.int64)
            log_ret = to_log_return(close)
            if tf == "4h":
                reg_base = pd.read_parquet(PROCESSED_DIR / "cache" / "regime_btcusdt_4h_s2.parquet")
            else:
                reg_base = repo.get_regime("BTCUSDT", "1h")
            positions = reg_base["index"].astype(int).tolist()
            er_dict = compute_rolling_er(log_ret, positions, window=WINDOW)
            with np.load(btc_feat_cache) as z:
                PS = z["PS"]
                F_all = np.nan_to_num(np.hstack([z["F_struct"], z["F_mf"]]), nan=0.0, posinf=0.0, neginf=0.0)
            pos_arr = np.asarray(positions, dtype=int)
            win_times = times[pos_arr + 1]
            c1 = np.concatenate([[0.0], np.cumsum(log_ret)])
            ret_500 = c1[pos_arr + 1] - c1[np.maximum(0, pos_arr - WINDOW + 1)]
            return {
                "symbol": symbol,
                "tf": tf,
                "stride": stride_btc,
                "positions": pos_arr,
                "win_times": win_times,
                "hurst": reg_base["hurst"].to_numpy(dtype=float),
                "dfa": reg_base["dfa_alpha"].to_numpy(dtype=float),
                "er_full": er_dict["er_full"],
                "er_128": er_dict["er_128"],
                "er_64": er_dict["er_64"],
                "ret_500": ret_500,
                "PS": PS,
                "F_all": F_all,
            }

    df = pd.read_parquet(parquet_path)
    df = df[df["close"] > 0].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    if tf != "1d":
        min_ts = int(pd.Timestamp("2018-10-01T00:00:00Z").timestamp())
        df = df[df["time"] >= min_ts].reset_index(drop=True)
        cache_ver = "v3"
    else:
        # Untuk 1D (GC=F, SI=F, ANTM.JK), gunakan sejarah sejak 2010 agar saat berada di tahun 2019
        # sudah tersedia ~1.800 jendela historis kausal sebelum 2020 (setelah dikurangi purge_gap=500)
        min_ts_1d = int(pd.Timestamp("2010-01-01T00:00:00Z").timestamp())
        df = df[df["time"] >= min_ts_1d].reset_index(drop=True)
        cache_ver = "v4"

    if len(df) < WINDOW + 60:
        return None

    if tf == "1h":
        stride = 4 if len(df) < 30000 else 8
    elif tf == "4h":
        stride = 2 if len(df) < 8000 else 4
    else:
        stride = 1

    cache_file = PROCESSED_DIR / "cache" / f"wf_multi_{symbol.lower()}_{tf}_s{stride}_{cache_ver}.npz"
    close = df["close"].to_numpy(dtype=float)
    times = df["time"].to_numpy(dtype=np.int64)
    log_ret = to_log_return(close)
    positions = list(range(WINDOW - 1, len(log_ret), stride))

    if cache_file.exists():
        with np.load(cache_file) as z:
            if len(z["positions"]) == len(positions):
                return {
                    "symbol": symbol,
                    "tf": tf,
                    "stride": stride,
                    "positions": z["positions"],
                    "win_times": z["win_times"],
                    "hurst": z["hurst"],
                    "dfa": z["dfa"],
                    "er_full": z["er_full"],
                    "er_128": z["er_128"],
                    "er_64": z["er_64"],
                    "ret_500": z["ret_500"],
                    "PS": z["PS"],
                    "F_all": z["F_all"],
                }

    t0 = time.time()
    print(f"  [Ekstraksi] {symbol:8s} ({tf.upper():2s}): {len(positions):5d} jendela (stride={stride})...", flush=True)
    met_df = rolling_hurst_dfa(log_ret, window=WINDOW, positions=positions)
    er_dict = compute_rolling_er(log_ret, positions, window=WINDOW)
    PS = build_persistence_sequences(log_ret, positions, WINDOW, SUB_WINDOW, SEQ_LEN).astype(np.float32)
    F_struct, F_mf = fast_feature_matrices(log_ret, positions, window=WINDOW, swt_level=SWT_LEVEL)
    F_all = np.nan_to_num(np.hstack([F_struct, F_mf]), nan=0.0, posinf=0.0, neginf=0.0)

    pos_arr = np.asarray(positions, dtype=int)
    win_times = times[pos_arr + 1]
    c1 = np.concatenate([[0.0], np.cumsum(log_ret)])
    ret_500 = c1[pos_arr + 1] - c1[np.maximum(0, pos_arr - WINDOW + 1)]

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_file,
        positions=pos_arr,
        win_times=win_times,
        hurst=met_df["hurst"].to_numpy(dtype=float),
        dfa=met_df["dfa_alpha"].to_numpy(dtype=float),
        er_full=er_dict["er_full"],
        er_128=er_dict["er_128"],
        er_64=er_dict["er_64"],
        ret_500=ret_500,
        PS=PS,
        F_all=F_all,
    )
    print(f"  [Selesai]   {symbol:8s} ({tf.upper():2s}) dalam {time.time() - t0:.1f}s", flush=True)
    return {
        "symbol": symbol,
        "tf": tf,
        "stride": stride,
        "positions": pos_arr,
        "win_times": win_times,
        "hurst": met_df["hurst"].to_numpy(dtype=float),
        "dfa": met_df["dfa_alpha"].to_numpy(dtype=float),
        "er_full": er_dict["er_full"],
        "er_128": er_dict["er_128"],
        "er_64": er_dict["er_64"],
        "ret_500": ret_500,
        "PS": PS,
        "F_all": F_all,
    }


def label_with_causal_cutoff(asset_data: Dict[str, Any], cal_mask: np.ndarray) -> Tuple[List[str], np.ndarray, np.ndarray]:
    """Kalibrasi kuantil Hurst, DFA, dan ER hanya pada `cal_mask` (data masa lalu)."""
    cfg = get_config()
    q = cfg.analysis.threshold_quantiles
    h_thr = calibrate_thresholds(asset_data["hurst"][cal_mask], q)
    d_thr = calibrate_thresholds(asset_data["dfa"][cal_mask], q)
    df_er = pd.DataFrame({k: asset_data[k] for k in ("er_full", "er_128", "er_64")})
    er_scores = compute_er_quantile_score(df_er, df_er.loc[cal_mask])
    er_arr = er_scores if er_scores is not None else np.full(len(asset_data["hurst"]), np.nan)

    labels = [
        label_from_exponents(h, a, h_thr, d_thr, efficiency_ratio=float(er), soft_consensus=True)
        for h, a, er in zip(asset_data["hurst"], asset_data["dfa"], er_arr)
    ]
    def_mask = np.array([lab in CLASSES for lab in labels], dtype=bool)
    return labels, def_mask, er_arr


def compute_metrics_dict(y_true: np.ndarray, y_pred: np.ndarray, ret_500: np.ndarray, er_q: np.ndarray) -> Dict[str, Any]:
    total = int(len(y_true))
    correct = int((y_true == y_pred).sum())
    pct = round(100.0 * correct / max(1, total), 2)

    per_class = {}
    recalls = []
    for ci, cname in enumerate(CLASSES):
        cm = y_true == ci
        ctot = int(cm.sum())
        ccor = int(((y_true == ci) & (y_pred == ci)).sum())
        cpct = round(100.0 * ccor / max(1, ctot), 2)
        if ctot > 0:
            recalls.append(ccor / ctot)
        per_class[cname] = {"total": ctot, "correct": ccor, "pct": cpct}

    bal_pct = round(100.0 * float(np.mean(recalls)) if recalls else 0.0, 2)

    is_trend = (er_q >= 0.58) | (y_true == 0)
    conds = {
        "uptrend": is_trend & (ret_500 >= 0),
        "downtrend": is_trend & (ret_500 < 0),
        "sideways": ~is_trend,
    }
    by_cond = {}
    for k_cond, m_cond in conds.items():
        ct = int(m_cond.sum())
        cc = int(((y_true == y_pred) & m_cond).sum())
        by_cond[k_cond] = {
            "total": ct,
            "correct": cc,
            "pct": round(100.0 * cc / max(1, ct), 2),
        }

    return {
        "total": total,
        "correct": correct,
        "pct": pct,
        "balanced_pct": bal_pct,
        "per_class": per_class,
        "by_condition": by_cond,
    }


def extract_causal_standardized_slice(asset_data: Dict[str, Any], test_yr: int) -> Dict[str, Any] | None:
    """Ambil irisan kausal sebelum `test_yr` (dengan purge_gap=500 bar) yang sudah distandarkan secara kausal."""
    years_arr = pd.to_datetime(asset_data["win_times"], unit="s", utc=True).year.to_numpy()
    purge_rows = max(1, WINDOW // asset_data["stride"])
    cutoff_indices = np.where(years_arr < test_yr)[0]
    if len(cutoff_indices) < purge_rows + 80:
        return None
    last_train_idx = int(cutoff_indices[-1]) - purge_rows
    if last_train_idx < 80:
        return None

    cal_mask = np.zeros(len(years_arr), dtype=bool)
    cal_mask[:last_train_idx] = True
    labels, def_mask, _ = label_with_causal_cutoff(asset_data, cal_mask)
    valid_hist = np.array([i for i in range(0, last_train_idx) if def_mask[i]], dtype=int)
    if len(valid_hist) < 60:
        return None

    ps_sc = fit_scaler(asset_data["PS"][valid_hist])
    PS_s = apply_scaler(asset_data["PS"][valid_hist], ps_sc)
    f_mu = asset_data["F_all"][valid_hist].mean(axis=0)
    f_sd = asset_data["F_all"][valid_hist].std(axis=0)
    f_sd[f_sd < 1e-12] = 1.0
    F_s = (asset_data["F_all"][valid_hist] - f_mu) / f_sd

    Y_s = np.zeros((len(valid_hist), len(CLASSES)), dtype=np.float32)
    for j_i, idx_orig in enumerate(valid_hist):
        Y_s[j_i, CLASSES.index(labels[idx_orig])] = 1.0

    return {"PS_s": PS_s, "F_s": F_s, "Y_s": Y_s, "ps_scaler": ps_sc, "f_mu": f_mu, "f_sd": f_sd}


def train_yearly_btc_models(
    btc_data: Dict[str, Any],
    aux_assets: List[Dict[str, Any]],
    test_years: List[int],
    epochs: int = 38,
) -> Dict[int, Dict[str, Any]]:
    """Latih model Hybrid PS Attention-BiLSTM pada setiap batas akhir tahun (2019..2025).

    Untuk menguji tahun Y (misal Y=2020), model HANYA boleh melihat data <= tahun Y-1 (misal <= 2019).
    Pada 4H tahun-tahun awal (2019-2020) di mana jumlah bar 1 tahun terbatas, augmentasi kausal
    dari pair likuid (ETH, BNB, XRP, ADA) yang juga dipotong ketat <= Y-1 digunakan sesuai Bab 3.
    """
    import tensorflow as tf  # type: ignore

    yearly_models: Dict[int, Dict[str, Any]] = {}

    for test_yr in test_years:
        btc_slice = extract_causal_standardized_slice(btc_data, test_yr)
        if btc_slice is None:
            continue

        PS_btc, F_btc, Y_btc = btc_slice["PS_s"], btc_slice["F_s"], btc_slice["Y_s"]
        n_val = max(35, int(round(len(Y_btc) * 0.15)))
        PS_tr, F_tr, Y_tr = PS_btc[:-n_val], F_btc[:-n_val], Y_btc[:-n_val]
        PS_va, F_va, Y_va = PS_btc[-n_val:], F_btc[-n_val:], Y_btc[-n_val:]

        # Tambahkan augmentasi kausal (<= test_yr - 1) dari aset likuid pendamping jika jumlah sampel < 2500
        if len(Y_tr) < 2500 and aux_assets:
            ps_list = [PS_tr]
            f_list = [F_tr]
            y_list = [Y_tr]
            for aux in aux_assets:
                aux_sl = extract_causal_standardized_slice(aux, test_yr)
                if aux_sl is not None:
                    ps_list.append(aux_sl["PS_s"])
                    f_list.append(aux_sl["F_s"])
                    y_list.append(aux_sl["Y_s"])
            PS_tr = np.concatenate(ps_list, axis=0)
            F_tr = np.concatenate(f_list, axis=0)
            Y_tr = np.concatenate(y_list, axis=0)

        cw_raw = class_weights(Y_tr)
        cw = {k: float(v ** 0.55) for k, v in cw_raw.items()}

        nets = []
        t0 = time.time()
        for seed in SEEDS:
            ckpt_dir = PROCESSED_DIR / "cache" / "wf_ckpts"
            ckpt_dir.mkdir(parents=True, exist_ok=True)
            ckpt_path = ckpt_dir / f"wf_ckpt_{btc_data['tf']}_{test_yr}_s{seed}.weights.h5"
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            seq_shape = (int(PS_tr.shape[1]), int(PS_tr.shape[2]))
            net = compile_model(
                build_hybrid_attention_bilstm(seq_shape, int(F_tr.shape[1]), len(CLASSES), lstm_units=64, dropout=0.25, l2_reg=1e-4),
                lr=1e-3,
                label_smoothing=0.02,
            )
            if ckpt_path.exists():
                net.load_weights(ckpt_path)
            else:
                net.fit(
                    [PS_tr, F_tr],
                    Y_tr,
                    validation_data=([PS_va, F_va], Y_va),
                    epochs=epochs,
                    batch_size=96 if btc_data["tf"] == "1h" else 64,
                    class_weight=cw,
                    shuffle=True,
                    callbacks=[
                        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=7, restore_best_weights=True),
                        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3, min_lr=1e-5),
                    ],
                    verbose=0,
                )
                net.save_weights(ckpt_path)
            nets.append(net)

        print(
            f"  [Model Checkpoint <= {test_yr - 1} -> Uji {test_yr}] ({btc_data['tf'].upper()}): "
            f"n_train={len(Y_tr)}, n_val={len(Y_va)} ({time.time() - t0:.1f}s)",
            flush=True,
        )
        yearly_models[test_yr] = {
            "train_end_year": test_yr - 1,
            "n_train": int(len(Y_tr)),
            "n_val": int(len(Y_va)),
            "nets": nets,
            "ps_scaler": btc_slice["ps_scaler"],
            "f_mu": btc_slice["f_mu"],
            "f_sd": btc_slice["f_sd"],
        }
    return yearly_models


def evaluate_asset_walk_forward(
    asset_spec: Dict[str, Any],
    asset_data: Dict[str, Any],
    yearly_models: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluasi walk-forward tahun-ke-tahun (2020..2026) pada satu aset dan timeframe."""
    years_arr = pd.to_datetime(asset_data["win_times"], unit="s", utc=True).year.to_numpy()
    avail_years = sorted(int(y) for y in np.unique(years_arr))
    purge_rows = max(1, WINDOW // asset_data["stride"])
    if asset_data["tf"] == "1d":
        # Untuk 1D, purge_rows setara 60 hari perdagangan (~3 bulan kalender) agar riwayat kalibrasi tetap kaya
        purge_rows = 60

    yearly_breakdown: Dict[str, Any] = {}
    pooled_true: List[int] = []
    pooled_pred: List[int] = []
    pooled_ret: List[float] = []
    pooled_er: List[float] = []
    series_rows: List[Dict[str, Any]] = []

    for test_yr in sorted(yearly_models.keys()):
        yr_mask = years_arr == test_yr
        if int(yr_mask.sum()) < 15:
            continue

        hist_mask = years_arr < test_yr
        if int(hist_mask.sum()) >= 120:
            last_hist = int(np.where(hist_mask)[0][-1]) - purge_rows
            cal_mask = np.zeros(len(years_arr), dtype=bool)
            cal_mask[: max(80, last_hist)] = True
        else:
            yr_indices = np.where(yr_mask)[0]
            split_pt = max(30, len(yr_indices) // 3)
            cal_mask = np.zeros(len(years_arr), dtype=bool)
            cal_mask[yr_indices[:split_pt]] = True
            yr_mask = np.zeros(len(years_arr), dtype=bool)
            if split_pt + purge_rows < len(yr_indices):
                yr_mask[yr_indices[split_pt + purge_rows :]] = True
            else:
                yr_mask[yr_indices[split_pt:]] = True

        labels, def_mask, er_arr = label_with_causal_cutoff(asset_data, cal_mask)
        te_indices = np.where(yr_mask & def_mask)[0]
        if len(te_indices) < 10:
            continue

        ckpt = yearly_models[test_yr]

        cal_def = np.where(cal_mask & def_mask)[0]
        if len(cal_def) >= 40:
            asset_ps_scaler = fit_scaler(asset_data["PS"][cal_def])
            asset_f_mu = asset_data["F_all"][cal_def].mean(axis=0)
            asset_f_sd = asset_data["F_all"][cal_def].std(axis=0)
            asset_f_sd[asset_f_sd < 1e-12] = 1.0
        else:
            asset_ps_scaler = ckpt["ps_scaler"]
            asset_f_mu = ckpt["f_mu"]
            asset_f_sd = ckpt["f_sd"]

        PS_s = apply_scaler(asset_data["PS"][te_indices], asset_ps_scaler)
        F_s = (asset_data["F_all"][te_indices] - asset_f_mu) / asset_f_sd

        if len(cal_def) >= 80 and asset_data["symbol"] != "BTCUSDT":
            PS_ad = apply_scaler(asset_data["PS"][cal_def], asset_ps_scaler)
            F_ad = (asset_data["F_all"][cal_def] - asset_f_mu) / asset_f_sd
            Y_ad = np.zeros((len(cal_def), len(CLASSES)), dtype=np.float32)
            for j_i, idx_orig in enumerate(cal_def):
                Y_ad[j_i, CLASSES.index(labels[idx_orig])] = 1.0
            probas = []
            for net in ckpt["nets"]:
                orig_weights = net.get_weights()
                net.optimizer.learning_rate.assign(3e-4)
                net.fit([PS_ad, F_ad], Y_ad, epochs=4, batch_size=64, verbose=0, shuffle=True)
                probas.append(net.predict([PS_s, F_s], batch_size=512, verbose=0))
                net.set_weights(orig_weights)
        else:
            probas = [net.predict([PS_s, F_s], batch_size=512, verbose=0) for net in ckpt["nets"]]

        prob_ens = np.mean(probas, axis=0)
        y_pred = prob_ens.argmax(axis=1)
        max_conf = prob_ens.max(axis=1)
        y_true = np.array([CLASSES.index(labels[i]) for i in te_indices], dtype=int)
        ret_te = asset_data["ret_500"][te_indices]
        er_te = er_arr[te_indices]

        for k_i, idx_w in enumerate(te_indices):
            t_sec = int(asset_data["win_times"][idx_w])
            tr_lab = CLASSES[int(y_true[k_i])]
            pr_lab = CLASSES[int(y_pred[k_i])]
            series_rows.append({
                "time": t_sec,
                "year": int(test_yr),
                "hurst": round(float(asset_data["hurst"][idx_w]), 4),
                "dfa_alpha": round(float(asset_data["dfa"][idx_w]), 4),
                "er_score": round(float(er_te[k_i]), 4) if np.isfinite(er_te[k_i]) else 0.5,
                "ret_500": round(float(ret_te[k_i]), 4),
                "true_regime": tr_lab,
                "pred_regime": pr_lab,
                "confidence": round(float(max_conf[k_i]), 4),
                "is_correct": bool(tr_lab == pr_lab),
            })

        m_yr = compute_metrics_dict(y_true, y_pred, ret_te, er_te)
        m_yr["train_cutoff"] = f"<= {test_yr - 1}" if int(hist_mask.sum()) >= 120 else f"Awal {test_yr} (Kausal)"
        yearly_breakdown[str(test_yr)] = m_yr

        pooled_true.extend(y_true.tolist())
        pooled_pred.extend(y_pred.tolist())
        pooled_ret.extend(ret_te.tolist())
        pooled_er.extend(er_te.tolist())

    if not pooled_true:
        return {}

    series_dir = ARTIFACTS_DIR / "walk_forward_series"
    series_dir.mkdir(parents=True, exist_ok=True)
    series_path = series_dir / f"wf_series_{asset_spec['symbol'].lower()}_{asset_data['tf']}.parquet"
    pd.DataFrame(series_rows).to_parquet(series_path, index=False)

    overall = compute_metrics_dict(
        np.asarray(pooled_true, dtype=int),
        np.asarray(pooled_pred, dtype=int),
        np.asarray(pooled_ret, dtype=float),
        np.asarray(pooled_er, dtype=float),
    )
    start_dt = pd.to_datetime(int(asset_data["win_times"][0]), unit="s", utc=True).strftime("%Y-%m-%d")
    end_dt = pd.to_datetime(int(asset_data["win_times"][-1]), unit="s", utc=True).strftime("%Y-%m-%d")

    return {
        "symbol": asset_spec["symbol"],
        "name": asset_spec["name"],
        "group": asset_spec["group"],
        "timeframe": asset_data["tf"],
        "stride": asset_data["stride"],
        "date_range": f"{start_dt} s/d {end_dt}",
        "available_years": avail_years,
        "overall_walk_forward": overall,
        "by_year": yearly_breakdown,
    }


def generate_markdown_report(out_payload: Dict[str, Any]) -> str:
    results = out_payload["results"]
    lines = [
        "# Laporan Uji Walk-Forward Kronologis Lintas Aset (2019 -> 2026)",
        "",
        "## 1. Desain Eksperimen: Simulasi Berjalan Seolah Masih di Tahun 2019",
        "- **Konsep Pengujian (*Expanding Year-by-Year Causal Walk-Forward*):**",
        "  Pengujian dimulai seolah-olah sistem berada di akhir tahun **2019** (hanya melihat data historis `<= 2019`). Pada setiap pergantian tahun (`2020, 2021, 2022, 2023, 2024, 2025, 2026`), ambang kuantil **Hurst R/S & DFA-1** ($q_{1/3}, q_{2/3}$), kuantil **Efficiency Ratio (ER)**, normalisasi fitur (*scaler* sekuens PS `32 x 14` & `56` fitur struktural/SWT), serta bobot model **Hybrid PS Attention-BiLSTM** dikalibrasi ulang murni menggunakan data masa lalu (`<= Y-1`) dengan pemisahan kausal `purge_gap = 500` bar sebelum menguji tahun `Y`.",
        "- **Aset yang Diuji (12 Aset / 21 Kombinasi Aset-Timeframe):**",
        "  1. **Kripto Utama & AI:** `BTCUSDT` (1H & 4H), `ETHUSDT` (1H & 4H), `TAOUSDT` (Bittensor AI, 1H & 4H), `BNBUSDT` (1H & 4H), `SOLUSDT` (1H & 4H), `XRPUSDT` (1H & 4H), `ADAUSDT` (1H & 4H), `DOGEUSDT` (1H & 4H).",
        "  2. **Emas / Gold / XAUUSD & Perak / Silver / XAGUSD:** `PAXGUSDT` (Emas Fisik Tokenized 1:1 XAU/USD 24/7 di Binance, 1H & 4H), `GCF` (`GC=F` Gold Futures COMEX / XAUUSD Proxy, 1H & 1D), `SIF` (`SI=F` Silver / Perak Futures COMEX / XAGUSD Proxy, 1H & 1D).",
        "  3. **Komoditas Tambang Emas/Nikel Indonesia:** `ANTMJK` (`ANTM.JK` PT Aneka Tambang Tbk, 1D).",
        "",
        "---",
        "",
        "## 2. Tabel Ringkasan Kebenaran Identifikasi Regime Lintas Aset (Akumulasi Walk-Forward 2020–2026)",
        "",
        "| Kelompok Aset | Simbol & Nama Aset | TF | Rentang Data | Total Jendela Uji | Jumlah Identifikasi Benar | Persentase Identifikasi Benar (%) | Persistent Benar (%) | Random-like Benar (%) | Anti-persistent Benar (%) | Uptrend Benar (%) | Downtrend Benar (%) | Sideways Benar (%) |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    tot_all_win = 0
    tot_all_cor = 0
    for r in results:
        ov = r["overall_walk_forward"]
        pc = ov["per_class"]
        bc = ov["by_condition"]
        tot_all_win += int(ov["total"])
        tot_all_cor += int(ov["correct"])
        lines.append(
            f"| {r['group']} | **{r['symbol']}** ({r['name']}) | **{r['timeframe'].upper()}** | {r['date_range']} | "
            f"{ov['total']:,} | **{ov['correct']:,}** | **{ov['pct']:.2f}%** | "
            f"{pc['persistent']['correct']:,}/{pc['persistent']['total']:,} ({pc['persistent']['pct']:.1f}%) | "
            f"{pc['random_like']['correct']:,}/{pc['random_like']['total']:,} ({pc['random_like']['pct']:.1f}%) | "
            f"{pc['anti_persistent']['correct']:,}/{pc['anti_persistent']['total']:,} ({pc['anti_persistent']['pct']:.1f}%) | "
            f"{bc['uptrend']['pct']:.1f}% | {bc['downtrend']['pct']:.1f}% | {bc['sideways']['pct']:.1f}% |"
        )

    overall_pct_all = 100.0 * tot_all_cor / max(1, tot_all_win)
    lines.append(
        f"| **TOTAL GABUNGAN (POOLED)** | **Seluruh 21 Kombinasi Aset & Timeframe** | **Multi-TF** | **2019–2026** | "
        f"**{tot_all_win:,}** | **{tot_all_cor:,}** | **{overall_pct_all:.2f}%** | — | — | — | — | — | — |"
    )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Evolusi Kebenaran Identifikasi Tahun demi Tahun (Simulasi Berjalan 2019 -> 2026)",
        "",
        "Tabel berikut memperlihatkan jumlah dan persentase identifikasi benar pada setiap tahun uji (`2020` s/d `2026`) ketika model hanya dilatih dari masa lalu sebelum tahun tersebut:",
        "",
        "| Aset | TF | Uji 2020 (Latih <=2019) | Uji 2021 (Latih <=2020) | Uji 2022 (Latih <=2021) | Uji 2023 (Latih <=2022) | Uji 2024 (Latih <=2023) | Uji 2025 (Latih <=2024) | Uji 2026 (Latih <=2025) | Total (2020–2026) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])

    years_cols = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"]
    for r in results:
        by_yr = r["by_year"]
        cells = []
        for y in years_cols:
            if y in by_yr:
                v = by_yr[y]
                cells.append(f"{v['correct']}/{v['total']} (**{v['pct']:.1f}%**)")
            else:
                cells.append("—")
        ov = r["overall_walk_forward"]
        lines.append(
            f"| **{r['symbol']}** | **{r['timeframe'].upper()}** | "
            + " | ".join(cells)
            + f" | **{ov['correct']:,}/{ov['total']:,} ({ov['pct']:.2f}%)** |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    json_path = ARTIFACTS_DIR / "multi_asset_walk_forward_2019_2026.json"
    if "--report-only" in sys.argv and json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        md_text = generate_markdown_report(payload)
        (ROOT / "THESIS_MULTI_ASSET_WALK_FORWARD_2019_2026.md").write_text(md_text, encoding="utf-8")
        (ARTIFACTS_DIR / "multi_asset_walk_forward_2019_2026.md").write_text(md_text, encoding="utf-8")
        print("[OK] Laporan Markdown berhasil dibuat.")
        return

    t_all = time.time()
    print("==================================================================")
    print(" WALK-FORWARD KRONOLOGIS LINTAS ASET (SEOLAH MULAI DI 2019 -> 2026)")
    print("==================================================================")

    btc_1h = load_or_build_asset_cache("BTCUSDT", "1h")
    btc_4h = load_or_build_asset_cache("BTCUSDT", "4h")
    assert btc_1h is not None and btc_4h is not None, "Data BTCUSDT 1H/4H wajib tersedia"

    # Muat pendamping likuid untuk augmentasi kausal <= Y-1 pada tahun-tahun awal (2019-2020)
    aux_1h = [d for s in ("ETHUSDT", "BNBUSDT") if (d := load_or_build_asset_cache(s, "1h")) is not None]
    aux_4h = [d for s in ("ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT") if (d := load_or_build_asset_cache(s, "4h")) is not None]

    test_years = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
    print("\n[Tahap 1] Melatih Checkpoint Tahunan Kausal (2019 -> 2026) pada 1H & 4H...")
    models_1h = train_yearly_btc_models(btc_1h, aux_1h, test_years, epochs=35)
    models_4h = train_yearly_btc_models(btc_4h, aux_4h, test_years, epochs=38)

    print("\n[Tahap 2] Mengevaluasi Kebenaran Identifikasi Walk-Forward Lintas Aset (2020-2026)...")
    all_results: List[Dict[str, Any]] = []

    for spec in ASSET_SPECS:
        sym = spec["symbol"]
        for tf in spec["tfs"]:
            adata = load_or_build_asset_cache(sym, tf)
            if adata is None:
                print(f"  [SKIP] {sym} ({tf.upper()}) tidak ditemukan di data/processed/")
                continue
            ymodels = models_1h if tf == "1h" else models_4h
            res = evaluate_asset_walk_forward(spec, adata, ymodels)
            if not res:
                continue
            ov = res["overall_walk_forward"]
            yrs_str = ", ".join(
                f"{yr}:{v['pct']:.1f}%" for yr, v in res["by_year"].items()
            )
            print(
                f"  [{sym:8s} | {tf.upper():2s}] Total Benar: {ov['correct']:5d}/{ov['total']:5d} "
                f"({ov['pct']:6.2f}% | BA {ov['balanced_pct']:5.2f}%) -> [{yrs_str}]",
                flush=True,
            )
            all_results.append(res)

    out_payload = {
        "experiment": "Expanding Year-by-Year Walk-Forward Regime Identification (Starting 2019 -> 2026)",
        "methodology": (
            "Pada setiap tahun uji Y (2020 s/d 2026), model Hybrid PS Attention-BiLSTM dan ambang kuantil "
            "Hurst-DFA + Efficiency Ratio dikalibrasi murni menggunakan data masa lalu (<= Y-1) dengan "
            "purge_gap = 500 bar. Tidak ada data masa depan yang bocor."
        ),
        "elapsed_seconds": round(time.time() - t_all, 1),
        "results": all_results,
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
    md_text = generate_markdown_report(out_payload)
    (ROOT / "THESIS_MULTI_ASSET_WALK_FORWARD_2019_2026.md").write_text(md_text, encoding="utf-8")
    (ARTIFACTS_DIR / "multi_asset_walk_forward_2019_2026.md").write_text(md_text, encoding="utf-8")
    print(f"\n[OK] Hasil lengkap disimpan ke {json_path} dalam {time.time() - t_all:.1f}s")


if __name__ == "__main__":
    main()

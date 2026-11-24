"""Eksekusi terpadu upgrade pipeline: 1."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

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
from app.services.feature_builder import apply_scaler, build_sequence_features, fit_scaler  # noqa: E402
from app.services.hurst_dfa import compute_rolling_er, rolling_hurst_dfa, to_log_return  # noqa: E402
from app.services.multifractal import compute_features as compute_mf_one  # noqa: E402
from app.services.persistence_sequence import build_persistence_sequences  # noqa: E402
from app.services.regime_labeling import (  # noqa: E402
    calibrate_thresholds,
    compute_er_quantile_score,
    label_from_exponents,
    label_series,
)
from app.services.splitting import bars_to_rows, split_indices  # noqa: E402
from app.services.structural_features import compute_features as compute_struct_one  # noqa: E402
from app.services.walk_forward import generate_folds  # noqa: E402
from model_architecture import (  # noqa: E402
    build_hybrid_attention_bilstm,
    build_structural_mlp,
    build_swt_attention_bilstm,
    build_swt_bilstm,
    compile_model,
)
from train import class_weights  # noqa: E402

SEEDS = [42, 43, 44]
SEQ_LEN = 32
SUB_WINDOW = 128
CLASSES = list(REGIME_CLASSES)  # ["persistent", "random_like", "anti_persistent"]

MODELS = [
    "swt_bilstm",
    "swt_attention_bilstm",
    "structural_mlp",
    "hybrid_swt",
    "hybrid_ps",
]

MODEL_LABELS = {
    "swt_bilstm": "SWT + BiLSTM",
    "swt_attention_bilstm": "SWT + Attention-BiLSTM",
    "structural_mlp": "Structural MLP",
    "hybrid_swt": "Hybrid SWT Attention-BiLSTM",
    "hybrid_ps": "Hybrid PS Attention-BiLSTM (Usulan)",
}


def _extract_chunk(log_ret: np.ndarray, pos_chunk: List[int], window: int, swt_level: int) -> Tuple[np.ndarray, np.ndarray]:
    s_rows = [compute_struct_one(log_ret, int(t), window, swt_level) for t in pos_chunk]
    m_rows = [compute_mf_one(log_ret, int(t), window) for t in pos_chunk]
    return np.asarray(s_rows, dtype=np.float32), np.asarray(m_rows, dtype=np.float32)


def fast_feature_matrices(log_ret: np.ndarray, positions: List[int], window: int = 500, swt_level: int = 4) -> Tuple[np.ndarray, np.ndarray]:
    chunk_size = max(64, len(positions) // 32 + 1)
    chunks = [positions[i : i + chunk_size] for i in range(0, len(positions), chunk_size)]
    res = Parallel(n_jobs=-1)(delayed(_extract_chunk)(log_ret, ch, window, swt_level) for ch in chunks)
    f_struct = np.vstack([r[0] for r in res])
    f_mf = np.vstack([r[1] for r in res])
    return f_struct, f_mf


def prepare_timeframe_data(tf: str) -> Dict[str, Any]:
    cfg = get_config()
    repo = get_repository()
    ohlcv = repo.get_ohlcv("BTCUSDT", tf)
    close = ohlcv["close"].to_numpy(dtype=float)
    log_ret = to_log_return(close)
    window = cfg.analysis.L
    stride = 2 if tf == "4h" else 4

    reg_base = repo.get_regime("BTCUSDT", tf).copy()
    if tf == "4h" and stride == 2:
        cache_s2 = PROCESSED_DIR / "cache" / "regime_btcusdt_4h_s2.parquet"
        all_pos = list(range(window - 1, len(log_ret), stride))
        if cache_s2.exists():
            c_df = pd.read_parquet(cache_s2)
            if len(c_df) == len(all_pos):
                reg_base = c_df
        if len(reg_base) != len(all_pos):
            existing_pos = set(reg_base["index"].astype(int).tolist())
            missing_pos = [p for p in all_pos if p not in existing_pos]
            fresh = rolling_hurst_dfa(log_ret, window=window, positions=missing_pos)
            reused = reg_base[["index", "hurst", "dfa_alpha"]].copy()
            reg_base = pd.concat([reused, fresh[["index", "hurst", "dfa_alpha"]]], ignore_index=True)
            reg_base = reg_base.sort_values("index").reset_index(drop=True)
            cache_s2.parent.mkdir(parents=True, exist_ok=True)
            reg_base.to_parquet(cache_s2, index=False)

    positions = reg_base["index"].astype(int).tolist()
    er_dict = compute_rolling_er(log_ret, positions, window=window)
    for k_er, v_er in er_dict.items():
        reg_base[k_er] = v_er

    purge_rows = bars_to_rows(window, stride)
    sp = split_indices(len(positions), cfg.split.ratios, purge_rows)
    train_mask = np.zeros(len(positions), dtype=bool)
    train_mask[: sp["train"][1]] = True

    # 1. Label Konsensus Lama (soft_consensus=False) pada grid yang sama
    lab_old_same = label_series(
        reg_base,
        cfg.analysis.hurst_threshold,
        cfg.analysis.dfa_threshold,
        mode="quantile",
        quantiles=(1 / 3, 2 / 3),
        threshold_source="train_only",
        train_mask=train_mask,
        soft_consensus=False,
    )
    # Jika 4H, juga ambil distribusi lama pada stride=4 (4.151 jendela) untuk perbandingan historis
    reg_orig_s4 = repo.get_regime("BTCUSDT", tf).copy()
    sp_orig = split_indices(len(reg_orig_s4), cfg.split.ratios, bars_to_rows(window, int(reg_orig_s4["stride_bars"].iloc[0])))
    tm_orig = np.zeros(len(reg_orig_s4), dtype=bool)
    tm_orig[: sp_orig["train"][1]] = True
    lab_old_orig = label_series(
        reg_orig_s4,
        cfg.analysis.hurst_threshold,
        cfg.analysis.dfa_threshold,
        mode="quantile",
        quantiles=(1 / 3, 2 / 3),
        threshold_source="train_only",
        train_mask=tm_orig,
        soft_consensus=False,
    )

    # 2. Label Konsensus Baru Trend-Aware Soft Consensus (soft_consensus=True)
    lab_new = label_series(
        reg_base,
        cfg.analysis.hurst_threshold,
        cfg.analysis.dfa_threshold,
        mode="quantile",
        quantiles=(1 / 3, 2 / 3),
        threshold_source="train_only",
        train_mask=train_mask,
        soft_consensus=True,
    )

    feat_cache = PROCESSED_DIR / "cache" / f"updated_feat_{tf}_s{stride}_f56_ps14.npz"
    loaded_tensors: Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None
    if feat_cache.exists():
        with np.load(feat_cache) as z:
            if len(z["positions"]) == len(positions):
                loaded_tensors = (z["X_swt"], z["PS"], z["F_struct"], z["F_mf"])
    if loaded_tensors is not None:
        X_swt, PS, F_struct, F_mf = loaded_tensors
    else:
        t0 = time.time()
        print(f"[{tf}] Mengekstraksi fitur SWT, PS (14 kanal), dan Struktural (56 fitur) untuk {len(positions)} jendela...")
        X_swt = build_sequence_features(log_ret, positions, level=cfg.analysis.J, seq_len=SEQ_LEN, swt_window=window).astype(np.float32)
        PS = build_persistence_sequences(log_ret, positions, window, SUB_WINDOW, SEQ_LEN).astype(np.float32)
        F_struct, F_mf = fast_feature_matrices(log_ret, positions, window=window, swt_level=cfg.analysis.J)
        feat_cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(feat_cache, positions=np.asarray(positions), X_swt=X_swt, PS=PS, F_struct=F_struct, F_mf=F_mf)
        print(f"[{tf}] Ekstraksi fitur selesai dalam {time.time() - t0:.1f}s")

    F_all = np.hstack([F_struct, F_mf])
    labels = lab_new["regime"].tolist()
    y_all = np.zeros((len(labels), len(CLASSES)), dtype=np.float32)
    for i, lab in enumerate(labels):
        if lab in CLASSES:
            y_all[i, CLASSES.index(lab)] = 1.0
    mask = np.array([lab in CLASSES for lab in labels], dtype=bool)

    # Hitung return kumulatif jendela L=500 dan W=128 untuk analisis kondisi pasar.
    c1 = np.concatenate([[0.0], np.cumsum(log_ret)])
    pos_arr = np.asarray(positions, dtype=int)
    ret_500 = c1[pos_arr + 1] - c1[np.maximum(0, pos_arr - window + 1)]
    ret_128 = c1[pos_arr + 1] - c1[np.maximum(0, pos_arr - 128 + 1)]
    er_q = lab_new["efficiency_ratio"].to_numpy(dtype=float)

    # Extra train-only augmentation for 4H from ETHUSDT and BNBUSDT.
    extra_train = None
    if tf == "4h":
        extra_cache = PROCESSED_DIR / "cache" / "updated_extra_4h_eth_bnb_train.npz"
        max_train_bar = int(positions[sp["train"][1] - 1]) + 1
        if extra_cache.exists():
            with np.load(extra_cache) as z:
                extra_train = {k: z[k] for k in ("X_swt", "PS", "F_all", "y")}
        else:
            x_swt_l, ps_l, f_l, y_l = [], [], [], []
            for sym in ("ETHUSDT", "BNBUSDT"):
                ex_df = repo.get_ohlcv(sym, "4h")
                ex_close = ex_df["close"].to_numpy(dtype=float)[:max_train_bar]
                ex_lr = to_log_return(ex_close)
                ex_met = rolling_hurst_dfa(ex_lr, window=window, step=stride)
                ex_lab = label_series(
                    ex_met,
                    cfg.analysis.hurst_threshold,
                    cfg.analysis.dfa_threshold,
                    mode="quantile",
                    quantiles=(1 / 3, 2 / 3),
                    threshold_source="full_history",
                    soft_consensus=True,
                )
                ex_pos = ex_lab["index"].astype(int).tolist()
                ex_reg = ex_lab["regime"].tolist()
                ex_sel = [idx_i for idx_i, r_val in enumerate(ex_reg) if r_val in CLASSES]
                ex_pos_sel = [ex_pos[idx_i] for idx_i in ex_sel]
                ex_x = build_sequence_features(ex_lr, ex_pos_sel, level=cfg.analysis.J, seq_len=SEQ_LEN, swt_window=window).astype(np.float32)
                ex_ps = build_persistence_sequences(ex_lr, ex_pos_sel, window, SUB_WINDOW, SEQ_LEN).astype(np.float32)
                ex_fs, ex_fm = fast_feature_matrices(ex_lr, ex_pos_sel, window=window, swt_level=cfg.analysis.J)
                ex_f = np.hstack([ex_fs, ex_fm])
                ex_y = np.zeros((len(ex_sel), len(CLASSES)), dtype=np.float32)
                for j_i, idx_i in enumerate(ex_sel):
                    ex_y[j_i, CLASSES.index(ex_reg[idx_i])] = 1.0
                x_swt_l.append(ex_x)
                ps_l.append(ex_ps)
                f_l.append(ex_f)
                y_l.append(ex_y)
            extra_train = {
                "X_swt": np.concatenate(x_swt_l, axis=0),
                "PS": np.concatenate(ps_l, axis=0),
                "F_all": np.concatenate(f_l, axis=0),
                "y": np.concatenate(y_l, axis=0),
            }
            np.savez_compressed(extra_cache, **extra_train)

    return {
        "tf": tf,
        "window": window,
        "stride": stride,
        "purge_rows": purge_rows,
        "split": sp,
        "positions": pos_arr,
        "hurst": reg_base["hurst"].to_numpy(dtype=float),
        "dfa": reg_base["dfa_alpha"].to_numpy(dtype=float),
        "er_full": reg_base["er_full"].to_numpy(dtype=float),
        "er_128": reg_base["er_128"].to_numpy(dtype=float),
        "er_64": reg_base["er_64"].to_numpy(dtype=float),
        "er_q": er_q,
        "ret_500": ret_500,
        "ret_128": ret_128,
        "lab_old_orig": lab_old_orig["regime"].tolist(),
        "lab_old_same": lab_old_same["regime"].tolist(),
        "lab_new": labels,
        "thresholds": {
            "hurst": [float(lab_new["hurst_lower"].iloc[0]), float(lab_new["hurst_upper"].iloc[0])],
            "dfa": [float(lab_new["dfa_lower"].iloc[0]), float(lab_new["dfa_upper"].iloc[0])],
        },
        "X_swt": X_swt,
        "PS": PS,
        "F_all": F_all,
        "y_all": y_all,
        "mask": mask,
        "extra_train": extra_train,
    }


def build_net(key: str, seq_shape: Tuple[int, int], n_feat: int, n_classes: int = 3):
    if key == "structural_mlp":
        return compile_model(build_structural_mlp(n_feat, n_classes, dropout=0.25), lr=1e-3, label_smoothing=0.02)
    if key == "swt_bilstm":
        return compile_model(build_swt_bilstm(seq_shape, n_classes, lstm_units=64, dropout=0.20), lr=1e-3)
    if key == "swt_attention_bilstm":
        return compile_model(build_swt_attention_bilstm(seq_shape, n_classes, lstm_units=64, dropout=0.20), lr=1e-3)
    if key in ("hybrid_swt", "hybrid_ps"):
        return compile_model(
            build_hybrid_attention_bilstm(seq_shape, n_feat, n_classes, lstm_units=64, dropout=0.25, l2_reg=1e-4),
            lr=1e-3,
            label_smoothing=0.02,
        )
    raise ValueError(key)


def get_inputs(key: str, S: np.ndarray, F: np.ndarray):
    if key == "structural_mlp":
        return F
    if key in ("swt_bilstm", "swt_attention_bilstm"):
        return S
    return [S, F]


def compute_identification_breakdown(y_true_idx: np.ndarray, y_pred_idx: np.ndarray) -> Dict[str, Any]:
    total = int(len(y_true_idx))
    correct = int((y_true_idx == y_pred_idx).sum())
    pct = round(100.0 * correct / max(1, total), 2)
    per_class = {}
    recalls = []
    for c_i, c_name in enumerate(CLASSES):
        c_mask = y_true_idx == c_i
        c_tot = int(c_mask.sum())
        c_cor = int(((y_true_idx == c_i) & (y_pred_idx == c_i)).sum())
        c_pct = round(100.0 * c_cor / max(1, c_tot), 2)
        recalls.append(c_cor / max(1, c_tot))
        per_class[c_name] = {
            "total": c_tot,
            "correct": c_cor,
            "pct": c_pct,
        }
    bal_pct = round(100.0 * float(np.mean(recalls)), 2)
    return {
        "total": total,
        "correct": correct,
        "pct": pct,
        "balanced_pct": bal_pct,
        "per_class": per_class,
    }


def run_historical_backtest(data: Dict[str, Any], epochs: int = 60, batch_size: int = 64) -> Dict[str, Any]:
    import tensorflow as tf  # type: ignore

    sp = data["split"]
    mask = data["mask"]
    rows = {k: np.array([i for i in range(*sp[k]) if mask[i]], dtype=int) for k in ("train", "validation", "test")}

    tr, va, te = rows["train"], rows["validation"], rows["test"]
    swt_scaler = fit_scaler(data["X_swt"][tr])
    ps_scaler = fit_scaler(data["PS"][tr])
    X_swt_s = apply_scaler(data["X_swt"], swt_scaler)
    PS_s = apply_scaler(data["PS"], ps_scaler)

    f_mu = data["F_all"][tr].mean(axis=0)
    f_sd = data["F_all"][tr].std(axis=0)
    f_sd[f_sd < 1e-12] = 1.0
    F_s = (data["F_all"] - f_mu) / f_sd
    Y = data["y_all"]

    # Augmentasi kausal Train-Only pada 4H
    aug_count = 0
    if data["tf"] == "4h" and data["extra_train"] is not None:
        ex = data["extra_train"]
        aug_count = len(ex["y"])

    y_true_te = Y[te].argmax(axis=1)
    model_results: Dict[str, Any] = {}
    proba_test_by_model: Dict[str, List[np.ndarray]] = {}

    for mkey in MODELS:
        t_m = time.time()
        S_all = PS_s if mkey == "hybrid_ps" else X_swt_s
        X_tr_seq, F_tr_mat, Y_tr_mat = S_all[tr], F_s[tr], Y[tr]

        if data["tf"] == "4h" and data["extra_train"] is not None and mkey in ("hybrid_ps", "hybrid_swt", "structural_mlp"):
            ex = data["extra_train"]
            ex_seq_raw = ex["PS"] if mkey == "hybrid_ps" else ex["X_swt"]
            ex_seq = apply_scaler(ex_seq_raw, ps_scaler if mkey == "hybrid_ps" else swt_scaler)
            ex_f = (ex["F_all"] - f_mu) / f_sd
            X_tr_seq = np.concatenate([X_tr_seq, ex_seq], axis=0)
            F_tr_mat = np.concatenate([F_tr_mat, ex_f], axis=0)
            Y_tr_mat = np.concatenate([Y_tr_mat, ex["y"]], axis=0)

        # Untuk model murni harus belajar mengenali sinyal arah secara proporsional.
        cw_raw = class_weights(Y_tr_mat)
        if mkey in ("hybrid_ps", "hybrid_swt", "structural_mlp"):
            cw = {k: float(v ** 0.60) for k, v in cw_raw.items()}
        else:
            cw = cw_raw

        per_seed = []
        probas = []
        ep_m = 30 if mkey in ("swt_bilstm", "swt_attention_bilstm") else epochs
        bs_m = batch_size * 2 if mkey in ("swt_bilstm", "swt_attention_bilstm") else batch_size
        pat_m = 6 if mkey in ("swt_bilstm", "swt_attention_bilstm") else 10
        for seed in SEEDS:
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            seq_shape_m = (int(X_tr_seq.shape[1]), int(X_tr_seq.shape[2]))
            net = build_net(mkey, seq_shape_m, int(F_tr_mat.shape[1]), len(CLASSES))
            hist = net.fit(
                get_inputs(mkey, X_tr_seq, F_tr_mat),
                Y_tr_mat,
                validation_data=(get_inputs(mkey, S_all[va], F_s[va]), Y[va]),
                epochs=ep_m,
                batch_size=bs_m,
                class_weight=cw,
                shuffle=True,
                callbacks=[
                    tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=pat_m, restore_best_weights=True),
                    tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=max(3, pat_m // 2), min_lr=1e-5),
                ],
                verbose=0,
            )
            prob_te = net.predict(get_inputs(mkey, S_all[te], F_s[te]), batch_size=512, verbose=0)
            probas.append(prob_te)
            pred_idx = prob_te.argmax(axis=1)
            bd = compute_identification_breakdown(y_true_te, pred_idx)
            bd["seed"] = seed
            bd["epochs"] = len(hist.history["loss"])
            per_seed.append(bd)

        proba_test_by_model[mkey] = probas
        # Ensemble / rata-rata probabilitas 3 seed serta rata-rata metrik per seed
        prob_ens = np.mean(probas, axis=0)
        pred_ens = prob_ens.argmax(axis=1)
        ens_bd = compute_identification_breakdown(y_true_te, pred_ens)

        mean_cor = int(round(float(np.mean([s["correct"] for s in per_seed]))))
        mean_pct = round(100.0 * mean_cor / max(1, len(y_true_te)), 2)
        std_pct = round(float(np.std([s["pct"] for s in per_seed])), 2)
        mean_bal = round(float(np.mean([s["balanced_pct"] for s in per_seed])), 2)

        per_class_mean = {}
        for c_name in CLASSES:
            c_tot = per_seed[0]["per_class"][c_name]["total"]
            c_cor = int(round(float(np.mean([s["per_class"][c_name]["correct"] for s in per_seed]))))
            c_pct = round(100.0 * c_cor / max(1, c_tot), 2)
            per_class_mean[c_name] = {"total": c_tot, "correct": c_cor, "pct": c_pct}

        model_results[mkey] = {
            "label": MODEL_LABELS[mkey],
            "total_test": int(len(y_true_te)),
            "mean_correct": mean_cor,
            "mean_pct": mean_pct,
            "std_pct": std_pct,
            "mean_balanced_pct": mean_bal,
            "per_class_mean": per_class_mean,
            "ensemble": ens_bd,
            "per_seed": per_seed,
        }
        print(
            f"  [{data['tf'].upper()}] {MODEL_LABELS[mkey]:36s} ({time.time() - t_m:4.0f}s): "
            f"Benar={mean_cor}/{len(y_true_te)} ({mean_pct:.2f}% ± {std_pct:.2f}%) | "
            f"Ens={ens_bd['correct']}/{len(y_true_te)} ({ens_bd['pct']:.2f}%) | BA={mean_bal:.2f}%"
        )

    # Analisis Kondisi Pasar Spesifik (Uptrend / Downtrend / Sideways) pada Partisi Test
    te_ret_500 = data["ret_500"][te]
    te_er_q = data["er_q"][te]
    te_old_lab = [data["lab_old_same"][i] for i in te]
    te_new_lab = [CLASSES[i] for i in y_true_te]
    prob_hps = np.mean(proba_test_by_model["hybrid_ps"], axis=0)
    pred_hps = [CLASSES[i] for i in prob_hps.argmax(axis=1)]

    # Definisi objektif kondisi pasar pada jendela uji: 1.
    is_trend = (te_er_q >= 0.58) | (y_true_te == 0)
    cond_masks = {
        "uptrend": is_trend & (te_ret_500 >= 0),
        "downtrend": is_trend & (te_ret_500 < 0),
        "sideways": ~is_trend,
    }
    market_pivot = {}
    for cname, cmask in cond_masks.items():
        idxs = np.where(cmask)[0]
        old_counts = pd.Series([te_old_lab[i] for i in idxs]).value_counts().to_dict()
        new_counts = pd.Series([te_new_lab[i] for i in idxs]).value_counts().to_dict()
        pred_counts = pd.Series([pred_hps[i] for i in idxs]).value_counts().to_dict()
        cor_cnt = int(sum(1 for i in idxs if pred_hps[i] == te_new_lab[i]))
        tot_cnt = int(len(idxs))
        market_pivot[cname] = {
            "total": tot_cnt,
            "correct": cor_cnt,
            "pct": round(100.0 * cor_cnt / max(1, tot_cnt), 2),
            "old_label_dist": {k: int(old_counts.get(k, 0)) for k in CLASSES + ["uncertain_rule"]},
            "new_label_dist": {k: int(new_counts.get(k, 0)) for k in CLASSES},
            "pred_label_dist": {k: int(pred_counts.get(k, 0)) for k in CLASSES},
        }

    part_counts: Dict[str, Dict[str, Any]] = {}
    for p_key in ("train", "purge_1", "validation", "purge_2", "test"):
        s_i, e_i = sp[p_key]
        sub_labs = data["lab_new"][s_i:e_i]
        vc = pd.Series(sub_labs).value_counts().to_dict()
        def_cnt = int(sum(vc.get(c, 0) for c in CLASSES))
        part_counts[p_key] = {
            "range": [int(s_i), int(e_i)],
            "total_windows": int(e_i - s_i),
            "definitive_windows": def_cnt,
            "uncertain_windows": int(vc.get("uncertain_rule", 0)),
            "per_class": {c: int(vc.get(c, 0)) for c in CLASSES},
        }
    if aug_count > 0:
        base_def = int(part_counts["train"]["definitive_windows"])
        part_counts["train"]["augmented_extra_windows"] = int(aug_count)
        part_counts["train"]["total_definitive_with_aug"] = base_def + int(aug_count)

    return {
        "partitions": part_counts,
        "models": model_results,
        "market_pivot": market_pivot,
    }


def run_walk_forward_5fold(data: Dict[str, Any], epochs: int = 45, batch_size: int = 96) -> Dict[str, Any]:
    import tensorflow as tf  # type: ignore

    cfg = get_config()
    purge = data["purge_rows"]
    folds = generate_folds(len(data["mask"]), n_splits=5, purge=purge, scheme="expanding")
    wf_models = ["swt_bilstm", "swt_attention_bilstm", "structural_mlp", "hybrid_swt", "hybrid_ps"]

    fold_records: List[Dict[str, Any]] = []
    df_er_all = pd.DataFrame({k: data[k] for k in ("er_full", "er_128", "er_64")})

    for raw_fold in folds:
        fold = cast(Dict[str, Any], raw_fold)
        f_num = int(fold["fold"])
        tr0, tr1 = fold["train"]
        n_val = int(round((tr1 - tr0) * 0.15))
        va0 = tr1 - n_val
        fit_end = va0 - purge
        te0, te1 = fold["test"]

        # Kalibrasi ambang kuantil & ER hanya dari train_fit fold ini (bebas leakage)
        q = cfg.analysis.threshold_quantiles
        h_thr = calibrate_thresholds(data["hurst"][tr0:fit_end], q)
        d_thr = calibrate_thresholds(data["dfa"][tr0:fit_end], q)
        er_scores = compute_er_quantile_score(df_er_all, df_er_all.iloc[tr0:fit_end])
        er_iter = er_scores if er_scores is not None else np.full(len(data["hurst"]), np.nan)

        f_labels = [
            label_from_exponents(h, a, h_thr, d_thr, efficiency_ratio=float(er), soft_consensus=True)
            for h, a, er in zip(data["hurst"], data["dfa"], er_iter)
        ]
        f_mask = np.array([lab in CLASSES for lab in f_labels], dtype=bool)
        Y_f = np.zeros((len(f_labels), len(CLASSES)), dtype=np.float32)
        for i, lab in enumerate(f_labels):
            if lab in CLASSES:
                Y_f[i, CLASSES.index(lab)] = 1.0

        pick = lambda a, b: np.array([i for i in range(a, b) if f_mask[i]], dtype=int)  # noqa: E731
        r_tr = pick(tr0, fit_end)
        r_va = pick(va0, tr1)
        r_te = pick(te0, te1)

        swt_sc = fit_scaler(data["X_swt"][r_tr])
        ps_sc = fit_scaler(data["PS"][r_tr])
        X_swt_s = apply_scaler(data["X_swt"], swt_sc)
        PS_s = apply_scaler(data["PS"], ps_sc)

        f_mu = data["F_all"][r_tr].mean(axis=0)
        f_sd = data["F_all"][r_tr].std(axis=0)
        f_sd[f_sd < 1e-12] = 1.0
        F_s = (data["F_all"] - f_mu) / f_sd

        y_true_te = Y_f[r_te].argmax(axis=1)
        dist_te = {c: int((y_true_te == idx_c).sum()) for idx_c, c in enumerate(CLASSES)}

        m_out: Dict[str, Any] = {}
        t_f = time.time()
        for mkey in wf_models:
            S_all = PS_s if mkey == "hybrid_ps" else X_swt_s
            X_tr_seq, F_tr_mat, Y_tr_mat = S_all[r_tr], F_s[r_tr], Y_f[r_tr]

            cw_raw = class_weights(Y_tr_mat)
            cw = {k: float(v ** 0.55) for k, v in cw_raw.items()} if mkey in ("hybrid_ps", "hybrid_swt", "structural_mlp") else cw_raw

            per_seed = []
            probas = []
            ep_w = 24 if mkey in ("swt_bilstm", "swt_attention_bilstm") else epochs
            bs_w = batch_size * 2 if mkey in ("swt_bilstm", "swt_attention_bilstm") else batch_size
            pat_w = 5 if mkey in ("swt_bilstm", "swt_attention_bilstm") else 8
            for seed in SEEDS:
                tf.keras.backend.clear_session()
                tf.keras.utils.set_random_seed(seed)
                seq_shape_w = (int(X_tr_seq.shape[1]), int(X_tr_seq.shape[2]))
                net = build_net(mkey, seq_shape_w, int(F_tr_mat.shape[1]), len(CLASSES))
                net.fit(
                    get_inputs(mkey, X_tr_seq, F_tr_mat),
                    Y_tr_mat,
                    validation_data=(get_inputs(mkey, S_all[r_va], F_s[r_va]), Y_f[r_va]),
                    epochs=ep_w,
                    batch_size=bs_w,
                    class_weight=cw,
                    shuffle=True,
                    callbacks=[
                        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=pat_w, restore_best_weights=True),
                        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=max(3, pat_w // 2), min_lr=1e-5),
                    ],
                    verbose=0,
                )
                prob_te = net.predict(get_inputs(mkey, S_all[r_te], F_s[r_te]), batch_size=512, verbose=0)
                probas.append(prob_te)
                bd = compute_identification_breakdown(y_true_te, prob_te.argmax(axis=1))
                bd["seed"] = seed
                per_seed.append(bd)

            prob_ens = np.mean(probas, axis=0)
            ens_bd = compute_identification_breakdown(y_true_te, prob_ens.argmax(axis=1))
            mean_cor = int(round(float(np.mean([s["correct"] for s in per_seed]))))
            mean_pct = round(100.0 * mean_cor / max(1, len(y_true_te)), 2)
            std_pct = round(float(np.std([s["pct"] for s in per_seed])), 2)
            mean_bal = round(float(np.mean([s["balanced_pct"] for s in per_seed])), 2)
            m_out[mkey] = {
                "mean_correct": mean_cor,
                "mean_pct": mean_pct,
                "std_pct": std_pct,
                "mean_balanced_pct": mean_bal,
                "ensemble": ens_bd,
                "per_seed": per_seed,
            }

        print(
            f"  [{data['tf'].upper()}] Fold {f_num} (n_test={len(y_true_te)}, {time.time() - t_f:.0f}s): "
            f"Hybrid PS = {m_out['hybrid_ps']['mean_correct']}/{len(y_true_te)} ({m_out['hybrid_ps']['mean_pct']:.2f}%) | "
            f"MLP = {m_out['structural_mlp']['mean_correct']}/{len(y_true_te)} ({m_out['structural_mlp']['mean_pct']:.2f}%)"
        )
        fold_records.append({
            "fold": f_num,
            "n_train": int(len(r_tr)),
            "n_val": int(len(r_va)),
            "n_test": int(len(r_te)),
            "test_distribution": dist_te,
            "models": m_out,
        })

    # Agregat sepanjang 5 fold
    summary_by_model = {}
    for mkey in wf_models:
        tot_te = sum(f["n_test"] for f in fold_records)
        tot_cor_mean = sum(f["models"][mkey]["mean_correct"] for f in fold_records)
        tot_cor_ens = sum(f["models"][mkey]["ensemble"]["correct"] for f in fold_records)
        avg_pct = round(float(np.mean([f["models"][mkey]["mean_pct"] for f in fold_records])), 2)
        std_pct = round(float(np.std([f["models"][mkey]["mean_pct"] for f in fold_records])), 2)
        summary_by_model[mkey] = {
            "label": MODEL_LABELS[mkey],
            "total_test_pooled": int(tot_te),
            "total_correct_mean": int(tot_cor_mean),
            "pooled_pct_mean": round(100.0 * tot_cor_mean / max(1, tot_te), 2),
            "total_correct_ensemble": int(tot_cor_ens),
            "pooled_pct_ensemble": round(100.0 * tot_cor_ens / max(1, tot_te), 2),
            "fold_avg_pct": avg_pct,
            "fold_std_pct": std_pct,
        }

    return {"folds": fold_records, "summary": summary_by_model}


def summarize_label_dist(labels: List[str]) -> Dict[str, Any]:
    total = len(labels)
    vc = pd.Series(labels).value_counts().to_dict()
    def_cnt = sum(int(vc.get(c, 0)) for c in CLASSES)
    out = {
        "total_windows": total,
        "definitive_windows": def_cnt,
        "definitive_pct": round(100.0 * def_cnt / max(1, total), 2),
        "counts": {k: int(vc.get(k, 0)) for k in CLASSES + ["uncertain_rule"]},
        "pcts": {k: round(100.0 * int(vc.get(k, 0)) / max(1, total), 2) for k in CLASSES + ["uncertain_rule"]},
    }
    return out


def main() -> None:
    t_start = time.time()
    all_out: Dict[str, Any] = {}
    for tf in ("1h", "4h"):
        print("\n==========================================")
        print(f"MEMPROSES TIMEFRAME: {tf.upper()}")
        print("==========================================")
        data = prepare_timeframe_data(tf)
        label_comp = {
            "old_original_stride": summarize_label_dist(data["lab_old_orig"]),
            "old_same_stride": summarize_label_dist(data["lab_old_same"]),
            "new_soft_consensus": summarize_label_dist(data["lab_new"]),
        }
        print(
            f"[{tf.upper()}] Definitif Lama: {label_comp['old_original_stride']['definitive_pct']:.2f}% "
            f"-> Definitif Baru (Soft Consensus): {label_comp['new_soft_consensus']['definitive_pct']:.2f}%"
        )
        hb = run_historical_backtest(data, epochs=60, batch_size=96 if tf == "1h" else 64)
        wf = run_walk_forward_5fold(data, epochs=45, batch_size=128 if tf == "1h" else 64)
        all_out[tf] = {
            "timeframe": tf,
            "window": data["window"],
            "stride": data["stride"],
            "purge_rows": data["purge_rows"],
            "thresholds": data["thresholds"],
            "label_comparison": label_comp,
            "historical_backtest": hb,
            "walk_forward_5fold": wf,
        }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "updated_eval_summary.json"
    out_path.write_text(json.dumps(all_out, indent=2), encoding="utf-8")
    print(f"\nSeluruh evaluasi selesai dalam {time.time() - t_start:.1f}s -> {out_path}")


if __name__ == "__main__":
    main()

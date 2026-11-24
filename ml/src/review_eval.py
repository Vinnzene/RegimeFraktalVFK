"""Evaluasi ulang untuk review naskah Bab 4 (ml/artifacts/review/).

Mereplikasi persis prosedur `run_updated_evaluation.py` (seed 42/43/44, split
70/15/15 + purge, ambang kuantil train-only, label Trend-Aware Soft Consensus,
augmentasi ETH/BNB 4H hanya pada backtest, eksponen class weight 0,60/0,55,
epoch/batch/patience yang sama), tetapi:

- menyimpan probabilitas per seed pada set VALIDASI dan UJI (backtest dan tiap
  fold walk-forward) agar metrik lengkap dapat dihitung tanpa melatih ulang;
- mendukung varian ablasi (fitur dihapus / arsitektur tanpa attention);
- opsional menyimpan model .keras + scaler (varian normal, Hybrid PS).

Tidak menulis ke ml/artifacts/updated_eval_summary.json.

Pemakaian:
    python ml/src/review_eval.py --tf 1h --variant normal --save-models
    python ml/src/review_eval.py --tf 4h --variant no_er
    python ml/src/review_eval.py --tf 1h --variant cw_sweep   # sweep eksponen (validasi saja)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_updated_evaluation as rue  # noqa: E402  (menyiapkan sys.path & KERAS_HOME)
from app.core.config import ARTIFACTS_DIR, get_config  # noqa: E402
from app.services.feature_builder import apply_scaler, fit_scaler  # noqa: E402
from app.services.persistence_sequence import PS_CHANNELS  # noqa: E402
from app.services.regime_labeling import calibrate_thresholds, compute_er_quantile_score, label_from_exponents  # noqa: E402
from app.services.structural_features import feature_names as struct_names  # noqa: E402
from app.services.multifractal import feature_names as mf_names  # noqa: E402
from app.services.walk_forward import generate_folds  # noqa: E402
from train import class_weights  # noqa: E402

REVIEW_DIR = ARTIFACTS_DIR / "review"
RAW_DIR = REVIEW_DIR / "raw"
MODEL_DIR = REVIEW_DIR / "models"

F_NAMES: List[str] = list(struct_names()) + list(mf_names())  # 50 + 6 = 56
ER_F = ["er_full", "er_128", "er_64", "trend_tstat_full", "trend_tstat_128", "signed_trend_slope"]
ER_PS = ["er_w", "er_fast", "trend_tstat"]
SWT_F = [n for n in F_NAMES if n.startswith("swt_energy")]

VARIANTS: Dict[str, Dict[str, Any]] = {
    "normal": {"models": list(rue.MODELS), "drop_f": [], "drop_ps": [], "arch": "standard"},
    "no_er": {"models": ["structural_mlp", "hybrid_swt", "hybrid_ps"], "drop_f": ER_F, "drop_ps": ER_PS, "arch": "standard"},
    "no_swt_energy": {"models": ["hybrid_ps"], "drop_f": SWT_F, "drop_ps": [], "arch": "standard"},
    "no_attention": {"models": ["hybrid_ps"], "drop_f": [], "drop_ps": [], "arch": "gap"},
}
CW_SWEEP = [0.40, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 1.00]


def build_hybrid_gap(seq_shape, n_feat, n_classes=3, lstm_units=64, dropout=0.25, l2_reg=1e-4):
    """Hybrid identik dengan build_hybrid_attention_bilstm, attention -> GlobalAveragePooling1D."""
    import tensorflow as tf  # type: ignore
    from tensorflow.keras import layers, models  # type: ignore

    reg = tf.keras.regularizers.l2(l2_reg) if l2_reg > 0 else None
    seq_in = layers.Input(shape=seq_shape, name="swt_features")
    feat_in = layers.Input(shape=(n_feat,), name="structural_features")
    seq = layers.Bidirectional(layers.LSTM(lstm_units, return_sequences=True, kernel_regularizer=reg, recurrent_regularizer=reg))(seq_in)
    seq = layers.Dropout(dropout)(seq)
    context = layers.GlobalAveragePooling1D(name="gap_pool")(seq)
    feat = layers.Dense(64, activation="relu", kernel_regularizer=reg)(feat_in)
    feat = layers.Dropout(dropout)(feat)
    feat = layers.Dense(32, activation="relu", kernel_regularizer=reg)(feat)
    merged = layers.Concatenate()([context, feat])
    merged = layers.Dropout(dropout)(merged)
    merged = layers.Dense(64, activation="relu", kernel_regularizer=reg)(merged)
    out = layers.Dense(n_classes, activation="softmax", name="regime")(merged)
    return models.Model([seq_in, feat_in], out, name="hybrid_gap_bilstm")


def make_net(mkey: str, arch: str, seq_shape, n_feat):
    if arch == "gap":
        from model_architecture import compile_model  # noqa: PLC0415

        return compile_model(build_hybrid_gap(seq_shape, n_feat), lr=1e-3, label_smoothing=0.02)
    return rue.build_net(mkey, seq_shape, n_feat, len(rue.CLASSES))


def slice_data(data: Dict[str, Any], drop_f: List[str], drop_ps: List[str]) -> Dict[str, Any]:
    keep_f = [i for i, n in enumerate(F_NAMES) if n not in drop_f]
    keep_ps = [i for i, n in enumerate(PS_CHANNELS) if n not in drop_ps]
    assert data["F_all"].shape[1] == len(F_NAMES) and data["PS"].shape[2] == len(PS_CHANNELS)
    out = dict(data)
    out["F_all"] = data["F_all"][:, keep_f]
    out["PS"] = data["PS"][:, :, keep_ps]
    if data.get("extra_train") is not None:
        ex = dict(data["extra_train"])
        ex["F_all"] = ex["F_all"][:, keep_f]
        ex["PS"] = ex["PS"][:, :, keep_ps]
        out["extra_train"] = ex
    out["f_names"] = [F_NAMES[i] for i in keep_f]
    out["ps_names"] = [PS_CHANNELS[i] for i in keep_ps]
    return out


def _cw(mkey: str, Y: np.ndarray, power: float) -> Dict[int, float]:
    raw = class_weights(Y)
    if mkey in ("hybrid_ps", "hybrid_swt", "structural_mlp"):
        return {k: float(v ** power) for k, v in raw.items()}
    return raw


def _fit_predict(mkey, arch, X_tr, F_tr, Y_tr, X_va, F_va, Y_va, evals, cw, ep, bs, pat, seed, save_path=None):
    import tensorflow as tf  # type: ignore

    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(seed)
    net = make_net(mkey, arch, (int(X_tr.shape[1]), int(X_tr.shape[2])), int(F_tr.shape[1]))
    hist = net.fit(
        rue.get_inputs(mkey, X_tr, F_tr), Y_tr,
        validation_data=(rue.get_inputs(mkey, X_va, F_va), Y_va),
        epochs=ep, batch_size=bs, class_weight=cw, shuffle=True,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=pat, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=max(3, pat // 2), min_lr=1e-5),
        ],
        verbose=0,
    )
    outs = [net.predict(rue.get_inputs(mkey, S, F), batch_size=512, verbose=0) for S, F in evals]
    if save_path is not None:
        net.save(save_path)
    return outs, len(hist.history["loss"])


def run_backtest(data, models, arch, cw_power=0.60, save_models=False, tag="normal", epochs=60, batch_size=64):
    sp, mask = data["split"], data["mask"]
    rows = {k: np.array([i for i in range(*sp[k]) if mask[i]], dtype=int) for k in ("train", "validation", "test")}
    tr, va, te = rows["train"], rows["validation"], rows["test"]
    swt_sc, ps_sc = fit_scaler(data["X_swt"][tr]), fit_scaler(data["PS"][tr])
    X_swt_s, PS_s = apply_scaler(data["X_swt"], swt_sc), apply_scaler(data["PS"], ps_sc)
    f_mu = data["F_all"][tr].mean(axis=0)
    f_sd = data["F_all"][tr].std(axis=0)
    f_sd[f_sd < 1e-12] = 1.0
    F_s = (data["F_all"] - f_mu) / f_sd
    Y = data["y_all"]
    out: Dict[str, Any] = {"rows_val": va, "rows_test": te, "y_val": Y[va].argmax(1), "y_test": Y[te].argmax(1), "models": {}}
    for mkey in models:
        t0 = time.time()
        S_all = PS_s if mkey == "hybrid_ps" else X_swt_s
        X_tr, F_tr, Y_tr = S_all[tr], F_s[tr], Y[tr]
        if data["tf"] == "4h" and data["extra_train"] is not None and mkey in ("hybrid_ps", "hybrid_swt", "structural_mlp"):
            ex = data["extra_train"]
            ex_seq = apply_scaler(ex["PS"] if mkey == "hybrid_ps" else ex["X_swt"], ps_sc if mkey == "hybrid_ps" else swt_sc)
            X_tr = np.concatenate([X_tr, ex_seq], axis=0)
            F_tr = np.concatenate([F_tr, (ex["F_all"] - f_mu) / f_sd], axis=0)
            Y_tr = np.concatenate([Y_tr, ex["y"]], axis=0)
        cw = _cw(mkey, Y_tr, cw_power)
        fast = mkey in ("swt_bilstm", "swt_attention_bilstm")
        ep, bs, pat = (30, batch_size * 2, 6) if fast else (epochs, batch_size, 10)
        pv, pt, eps = [], [], []
        for seed in rue.SEEDS:
            sv = None
            if save_models and mkey == "hybrid_ps":
                MODEL_DIR.mkdir(parents=True, exist_ok=True)
                sv = MODEL_DIR / f"hybrid_ps_updated_{data['tf']}_s{seed}.keras"
            (p_va, p_te), n_ep = _fit_predict(mkey, arch, X_tr, F_tr, Y_tr, S_all[va], F_s[va], Y[va],
                                               [(S_all[va], F_s[va]), (S_all[te], F_s[te])], cw, ep, bs, pat, seed, sv)
            pv.append(p_va)
            pt.append(p_te)
            eps.append(n_ep)
        out["models"][mkey] = {"p_val": np.stack(pv), "p_test": np.stack(pt), "epochs": eps, "class_weight": cw,
                               "n_train": int(len(Y_tr))}
        acc = float((np.mean(pt, axis=0).argmax(1) == out["y_test"]).mean())
        print(f"[{data['tf']}|{tag}|BT] {mkey:22s} ens acc={acc:.4f} ({time.time() - t0:.0f}s)", flush=True)
        if save_models and mkey == "hybrid_ps":
            scaler = {
                "timeframe": data["tf"], "seeds": rue.SEEDS, "classes": rue.CLASSES,
                "files": [f"hybrid_ps_updated_{data['tf']}_s{s}.keras" for s in rue.SEEDS],
                "ensemble": "mean softmax of the 3 seeds",
                "ps_channels": data.get("ps_names", list(PS_CHANNELS)), "ps_scaler": ps_sc,
                "f_names": data.get("f_names", F_NAMES), "f_mean": f_mu.tolist(), "f_std": f_sd.tolist(),
                "window": data["window"], "stride": data["stride"], "sub_window": rue.SUB_WINDOW, "seq_len": rue.SEQ_LEN,
                "label_thresholds_train_only": data["thresholds"],
                "inputs": "[PS (N,32,14) standardized with ps_scaler, F (N,56) standardized with f_mean/f_std]",
                "test_acc_ensemble_reproduced": round(acc, 4),
                "custom_objects": "AttentionPooling from backend/ml_layers.py or ml/src/model_architecture.py",
            }
            (MODEL_DIR / f"hybrid_ps_updated_{data['tf']}_scaler.json").write_text(json.dumps(scaler, indent=2), encoding="utf-8")
    return out


def run_wf(data, models, arch, cw_power=0.55, tag="normal", epochs=45, batch_size=96):
    cfg = get_config()
    purge = data["purge_rows"]
    folds = generate_folds(len(data["mask"]), n_splits=5, purge=purge, scheme="expanding")
    import pandas as pd  # noqa: PLC0415

    df_er = pd.DataFrame({k: data[k] for k in ("er_full", "er_128", "er_64")})
    out_folds = []
    for fold in folds:
        tr0, tr1 = fold["train"]
        n_val = int(round((tr1 - tr0) * 0.15))
        va0 = tr1 - n_val
        fit_end = va0 - purge
        te0, te1 = fold["test"]
        q = cfg.analysis.threshold_quantiles
        h_thr = calibrate_thresholds(data["hurst"][tr0:fit_end], q)
        d_thr = calibrate_thresholds(data["dfa"][tr0:fit_end], q)
        er_s = compute_er_quantile_score(df_er, df_er.iloc[tr0:fit_end])
        labs = [label_from_exponents(h, a, h_thr, d_thr, efficiency_ratio=float(e), soft_consensus=True)
                for h, a, e in zip(data["hurst"], data["dfa"], er_s)]
        fm = np.array([lab in rue.CLASSES for lab in labs])
        Yf = np.zeros((len(labs), 3), dtype=np.float32)
        for i, lab in enumerate(labs):
            if lab in rue.CLASSES:
                Yf[i, rue.CLASSES.index(lab)] = 1.0
        pick = lambda a, b: np.array([i for i in range(a, b) if fm[i]], dtype=int)  # noqa: E731
        r_tr, r_va, r_te = pick(tr0, fit_end), pick(va0, tr1), pick(te0, te1)
        swt_sc, ps_sc = fit_scaler(data["X_swt"][r_tr]), fit_scaler(data["PS"][r_tr])
        X_swt_s, PS_s = apply_scaler(data["X_swt"], swt_sc), apply_scaler(data["PS"], ps_sc)
        f_mu = data["F_all"][r_tr].mean(axis=0)
        f_sd = data["F_all"][r_tr].std(axis=0)
        f_sd[f_sd < 1e-12] = 1.0
        F_s = (data["F_all"] - f_mu) / f_sd
        rec: Dict[str, Any] = {"fold": int(fold["fold"]), "rows_val": r_va, "rows_test": r_te,
                               "y_val": Yf[r_va].argmax(1), "y_test": Yf[r_te].argmax(1),
                               "labels_all": np.array(labs, dtype=object), "h_thr": h_thr, "d_thr": d_thr, "models": {}}
        for mkey in models:
            S_all = PS_s if mkey == "hybrid_ps" else X_swt_s
            cw = _cw(mkey, Yf[r_tr], cw_power)
            fast = mkey in ("swt_bilstm", "swt_attention_bilstm")
            ep, bs, pat = (24, batch_size * 2, 5) if fast else (epochs, batch_size, 8)
            pv, pt = [], []
            for seed in rue.SEEDS:
                (p_va, p_te), _ = _fit_predict(mkey, arch, S_all[r_tr], F_s[r_tr], Yf[r_tr], S_all[r_va], F_s[r_va], Yf[r_va],
                                               [(S_all[r_va], F_s[r_va]), (S_all[r_te], F_s[r_te])], cw, ep, bs, pat, seed)
                pv.append(p_va)
                pt.append(p_te)
            rec["models"][mkey] = {"p_val": np.stack(pv), "p_test": np.stack(pt)}
        accs = {m: round(float((rec["models"][m]["p_test"].mean(0).argmax(1) == rec["y_test"]).mean()), 4) for m in models}
        print(f"[{data['tf']}|{tag}|WF] fold {rec['fold']} n_test={len(r_te)} ens acc={accs}", flush=True)
        out_folds.append(rec)
    return out_folds


def save_raw(tf: str, tag: str, bt: Optional[Dict[str, Any]], wf: Optional[List[Dict[str, Any]]], extra: Dict[str, Any]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    arrs: Dict[str, np.ndarray] = {}
    if bt is not None:
        for k in ("rows_val", "rows_test", "y_val", "y_test"):
            arrs[f"bt__{k}"] = bt[k]
        for m, v in bt["models"].items():
            arrs[f"bt__{m}__p_val"] = v["p_val"]
            arrs[f"bt__{m}__p_test"] = v["p_test"]
    if wf is not None:
        for f in wf:
            fi = f["fold"]
            for k in ("rows_val", "rows_test", "y_val", "y_test"):
                arrs[f"wf{fi}__{k}"] = f[k]
            for m, v in f["models"].items():
                arrs[f"wf{fi}__{m}__p_val"] = v["p_val"]
                arrs[f"wf{fi}__{m}__p_test"] = v["p_test"]
    path = RAW_DIR / f"{tf}_{tag}.npz"
    np.savez_compressed(path, **arrs)
    meta = dict(extra)
    if bt is not None:
        meta["bt"] = {m: {"epochs": v["epochs"], "class_weight": v["class_weight"], "n_train": v["n_train"]} for m, v in bt["models"].items()}
    if wf is not None:
        meta["wf_thresholds"] = {f["fold"]: {"hurst": f["h_thr"], "dfa": f["d_thr"]} for f in wf}
    (RAW_DIR / f"{tf}_{tag}.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", required=True, choices=["1h", "4h"])
    ap.add_argument("--variant", required=True, choices=list(VARIANTS) + ["cw_sweep"])
    ap.add_argument("--save-models", action="store_true")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--skip-wf", action="store_true")
    ap.add_argument("--wf-only", action="store_true", help="lanjutkan: pakai hasil backtest tersimpan di raw/, jalankan walk-forward saja")
    ap.add_argument("--powers", default="", help="cw_sweep: daftar eksponen dipisah koma (default semua)")
    args = ap.parse_args()

    import tensorflow as tf  # type: ignore

    tf.config.threading.set_intra_op_parallelism_threads(args.threads)
    tf.config.threading.set_inter_op_parallelism_threads(2)

    t0 = time.time()
    data = rue.prepare_timeframe_data(args.tf)
    bs_bt = 96 if args.tf == "1h" else 64
    bs_wf = 128 if args.tf == "1h" else 64

    if args.variant == "cw_sweep":
        # Sweep eksponen class weight Hybrid PS; dilaporkan pada VALIDASI (uji ikut disimpan untuk transparansi).
        d = slice_data(data, [], [])
        powers = [float(x) for x in args.powers.split(",")] if args.powers else CW_SWEEP
        for p in powers:
            tag = f"cw_sweep_p{int(round(p * 100)):03d}"
            bt = run_backtest(d, ["hybrid_ps"], "standard", cw_power=p, tag=tag, batch_size=bs_bt)
            save_raw(args.tf, tag, bt, None, {"variant": "cw_sweep", "power": p, "f_names": d["f_names"], "ps_names": d["ps_names"]})
        print(f"selesai {time.time() - t0:.0f}s")
        return

    v = VARIANTS[args.variant]
    d = slice_data(data, v["drop_f"], v["drop_ps"])
    if args.wf_only:
        prev_npz = RAW_DIR / f"{args.tf}_{args.variant}.npz"
        prev_meta = json.loads((RAW_DIR / f"{args.tf}_{args.variant}.json").read_text(encoding="utf-8"))
        with np.load(prev_npz, allow_pickle=True) as z:
            arrs = {k: z[k] for k in z.files if k.startswith("bt__")}
        wf = run_wf(d, v["models"], v["arch"], tag=args.variant, batch_size=bs_wf)
        for f in wf:
            fi = f["fold"]
            for k in ("rows_val", "rows_test", "y_val", "y_test"):
                arrs[f"wf{fi}__{k}"] = f[k]
            for m, mv in f["models"].items():
                arrs[f"wf{fi}__{m}__p_val"] = mv["p_val"]
                arrs[f"wf{fi}__{m}__p_test"] = mv["p_test"]
        np.savez_compressed(prev_npz, **arrs)
        prev_meta.pop("partial", None)
        prev_meta["wf_thresholds"] = {f["fold"]: {"hurst": f["h_thr"], "dfa": f["d_thr"]} for f in wf}
        prev_meta["wf_resumed"] = True
        (RAW_DIR / f"{args.tf}_{args.variant}.json").write_text(json.dumps(prev_meta, indent=2, default=str), encoding="utf-8")
        print(f"selesai {args.tf}/{args.variant} (wf-only) dalam {time.time() - t0:.0f}s", flush=True)
        return
    bt = run_backtest(d, v["models"], v["arch"], save_models=args.save_models and args.variant == "normal",
                      tag=args.variant, batch_size=bs_bt)
    save_raw(args.tf, args.variant, bt, None, {"variant": args.variant, **{k: v[k] for k in ("models", "drop_f", "drop_ps", "arch")},
                                               "f_names": d["f_names"], "ps_names": d["ps_names"], "partial": "bt_only"})
    wf = None if args.skip_wf else run_wf(d, v["models"], v["arch"], tag=args.variant, batch_size=bs_wf)
    save_raw(args.tf, args.variant, bt, wf, {"variant": args.variant, **{k: v[k] for k in ("models", "drop_f", "drop_ps", "arch")},
                                             "f_names": d["f_names"], "ps_names": d["ps_names"],
                                             "seconds": round(time.time() - t0, 1)})
    print(f"selesai {args.tf}/{args.variant} dalam {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()

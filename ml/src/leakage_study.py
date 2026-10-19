"""Eksperimen kebocoran data: protokol bersih vs protokol bocor yang umum.

Jalankan:
    python ml/src/leakage_study.py --timeframe 1h
    python ml/src/leakage_study.py --timeframe 4h --seeds 42 43 44
    python ml/src/leakage_study.py --timeframe 1h --variants clean no_purge --models hybrid_attention_bilstm

Tujuan: mengukur seberapa besar angka evaluasi MENGGELEMBUNG bila protokol
evaluasi bocor. Selisih "bocor − bersih" adalah bukti kuantitatif kontribusi
metodologi skripsi (evaluasi tanpa kebocoran), bukan klaim tanpa data.

Varian (arsitektur, hyperparameter, seed, epoch, callback IDENTIK; yang beda
hanya protokol data):

    clean            protokol skripsi: SWT kausal, split kronologis, purge L
                     bar, scaler dari train saja
    shuffle_split    split ACAK antar window (window bertetangga berbagi
                     ~L bar, jadi test "mirip" train)
    no_purge         kronologis tetapi TANPA purge gap di batas split
    global_scaler    scaler dihitung dari SELURUH data (statistik test bocor)
    noncausal_swt    SWT atas seluruh deret sekaligus (filter wavelet memakai
                     sampel SESUDAH t)
    all_leaks        noncausal_swt + shuffle_split + global_scaler

    ABLATION FITUR (bukan varian bocor; protokol bersih, fitur dikurangi):
    no_multifractal  tanpa 6 fitur H(q). H(2) adalah estimator persistensi
                     lain (fungsi struktur), berbeda dari R/S dan DFA.
    no_vr            tanpa variance ratio (vr_*)
    no_vr_ac         tanpa variance ratio dan autokorelasi (vr_*, ac_*)
    no_persistence_proxies  tanpa vr_*, ac_*, DAN H(q)
                     Semua kelompok ini secara matematis berkaitan dengan
                     eksponen Hurst. Bila hasil turun mendekati model SWT
                     murni tanpa mereka, model sebagian besar "membaca ulang"
                     label lewat proksi persistensi — temuan yang wajib
                     dilaporkan (uji sirkularitas).

Hurst dan DFA tidak pernah menjadi input di varian mana pun.

Keluaran (tidak menimpa artefak lain):
    ml/artifacts/leakage_study_{tf}.json
    ml/artifacts/leakage_study_{tf}.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.feature_builder import apply_scaler, build_sequence_features, fit_scaler  # noqa: E402
from app.services.hurst_dfa import to_log_return  # noqa: E402
from app.services.multifractal import build_feature_matrix as build_multifractal_matrix  # noqa: E402
from app.services.regime_labeling import label_series  # noqa: E402
from app.services.splitting import bars_to_rows, split_indices  # noqa: E402
from app.services.structural_features import build_feature_matrix  # noqa: E402
from app.services.structural_features import feature_names as structural_names  # noqa: E402
from app.services.swt import swt_decompose  # noqa: E402
from main_evaluation import LABELS, build_model, inputs_for  # noqa: E402
from train import class_weights  # noqa: E402
from train_orderflow_ablation import classification_metrics  # noqa: E402

VARIANTS: Dict[str, Dict[str, object]] = {
    "clean": {"swt": "causal", "split": "chrono", "purge": True, "scaler": "train", "mf": True,
              "desc": "Protokol skripsi (bersih)"},
    "shuffle_split": {"swt": "causal", "split": "shuffle", "purge": False, "scaler": "train", "mf": True,
                      "desc": "Split acak antar window"},
    "no_purge": {"swt": "causal", "split": "chrono", "purge": False, "scaler": "train", "mf": True,
                 "desc": "Kronologis tanpa purge gap"},
    "global_scaler": {"swt": "causal", "split": "chrono", "purge": True, "scaler": "global", "mf": True,
                      "desc": "Scaler dari seluruh data"},
    "noncausal_swt": {"swt": "noncausal", "split": "chrono", "purge": True, "scaler": "train", "mf": True,
                      "desc": "SWT non-kausal (seluruh deret)"},
    "all_leaks": {"swt": "noncausal", "split": "shuffle", "purge": False, "scaler": "global", "mf": True,
                  "desc": "Semua kebocoran sekaligus"},
    "no_multifractal": {"swt": "causal", "split": "chrono", "purge": True, "scaler": "train", "mf": False,
                        "desc": "Bersih, tanpa fitur H(q) (uji sirkularitas)"},
    "no_vr": {"swt": "causal", "split": "chrono", "purge": True, "scaler": "train", "mf": True,
              "drop": ("vr_",), "desc": "Bersih, tanpa variance ratio"},
    "no_vr_ac": {"swt": "causal", "split": "chrono", "purge": True, "scaler": "train", "mf": True,
                 "drop": ("vr_", "ac_ret_", "ac_abs_"), "desc": "Bersih, tanpa variance ratio & autokorelasi"},
    "no_persistence_proxies": {"swt": "causal", "split": "chrono", "purge": True, "scaler": "train", "mf": False,
                               "drop": ("vr_", "ac_ret_", "ac_abs_"),
                               "desc": "Bersih, tanpa VR, autokorelasi, dan H(q)"},
    # Hanya bermakna untuk model PS: kanal VR/AC juga dibuang dari SEKUENS PS,
    # menyisakan sign_flip dan log_vol per langkah.
    "no_persistence_proxies_all": {"swt": "causal", "split": "chrono", "purge": True, "scaler": "train", "mf": False,
                                   "drop": ("vr_", "ac_ret_", "ac_abs_"), "ps_drop": ("vr_", "ac_", "acabs_"),
                                   "desc": "Tanpa VR, AC, H(q) di fitur DAN di sekuens PS"},
}
LEAKY = ["shuffle_split", "no_purge", "global_scaler", "noncausal_swt", "all_leaks"]


def noncausal_sequences(log_ret: np.ndarray, positions: np.ndarray, level: int, seq_len: int) -> np.ndarray:
    """SWT atas SELURUH deret, lalu dipotong per sampel. Sengaja bocor."""
    dec = swt_decompose(log_ret, level=level)
    keys = sorted(dec)
    mat = np.stack([dec[k] for k in keys], axis=1)
    idx = positions[:, None] + (np.arange(seq_len) - (seq_len - 1))[None, :]
    out = mat[np.clip(idx, 0, None)]
    out[idx < 8] = 0.0
    return out


def build_base(
    timeframe: str,
    seq_len: int,
    classes: List[str],
    threshold_source: str = "full_history",
) -> Dict[str, Any]:
    cfg = get_config()
    repo = get_repository()
    close = repo.get_ohlcv("BTCUSDT", timeframe)["close"].to_numpy()
    log_ret = to_log_return(close)
    regime = repo.get_regime("BTCUSDT", timeframe)
    window = int(regime["effective_window"].iloc[0])
    stride = int(regime["stride_bars"].iloc[0])
    expected = min(cfg.analysis.L, max(64, len(log_ret) // 4))
    if window != expected or stride != max(1, cfg.analysis.stride_bars):
        raise SystemExit("tabel regime tidak cocok dengan config; jalankan ulang compute_regime")
    positions = regime["index"].to_numpy(dtype=int)

    if threshold_source == "train_only":
        purge_rows = bars_to_rows(cfg.analysis.L, stride)
        pre_split = split_indices(len(positions), cfg.split.ratios, purge_rows)
        train_end = pre_split["train"][1]
        train_mask = np.zeros(len(positions), dtype=bool)
        train_mask[:train_end] = True
        labeled = label_series(
            regime,
            cfg.analysis.hurst_threshold,
            cfg.analysis.dfa_threshold,
            mode=cfg.analysis.threshold_mode,
            quantiles=cfg.analysis.threshold_quantiles,
            threshold_source="train_only",
            train_mask=train_mask,
        )
        labels = labeled["regime"].tolist()
        resolved_thresholds = {
            "hurst": [float(labeled["hurst_lower"].iloc[0]), float(labeled["hurst_upper"].iloc[0])],
            "dfa": [float(labeled["dfa_lower"].iloc[0]), float(labeled["dfa_upper"].iloc[0])],
        }
    else:
        labels = regime["regime"].tolist()
        resolved_thresholds = {
            "hurst": [float(regime["hurst_lower"].iloc[0]), float(regime["hurst_upper"].iloc[0])],
            "dfa": [float(regime["dfa_lower"].iloc[0]), float(regime["dfa_upper"].iloc[0])],
        }

    mask = np.array([l in classes for l in labels])

    t = time.time()
    X_causal = build_sequence_features(log_ret, positions.tolist(), level=cfg.analysis.J, seq_len=seq_len, swt_window=window)
    X_noncausal = noncausal_sequences(log_ret, positions, cfg.analysis.J, seq_len)
    if X_noncausal.shape != X_causal.shape:
        raise SystemExit(f"bentuk SWT non-kausal {X_noncausal.shape} != kausal {X_causal.shape}")
    F_struct = build_feature_matrix(log_ret, positions.tolist(), window=window, swt_level=cfg.analysis.J)
    F_mf = build_multifractal_matrix(log_ret, positions.tolist(), window=window)
    print(f"  fitur {time.time() - t:.0f}s | seq {X_causal.shape[1:]} | struktural {F_struct.shape[1]} | H(q) {F_mf.shape[1]}")

    y = np.zeros((len(labels), len(classes)))
    for i, l in enumerate(labels):
        if l in classes:
            y[i, classes.index(l)] = 1.0
    return {
        "labels": labels, "positions": positions, "mask": mask, "y": y,
        "X_causal": X_causal, "X_noncausal": X_noncausal, "F_struct": F_struct, "F_mf": F_mf,
        "window": window, "stride": stride,
        "threshold_source": threshold_source,
        "thresholds": resolved_thresholds,
    }


def make_split(base: Dict[str, Any], spec: Dict[str, Any], ref_sizes: Dict[str, int] | None, seed: int) -> Dict[str, np.ndarray]:
    cfg = get_config()
    mask = base["mask"]
    n = len(mask)
    if spec["split"] == "chrono":
        purge_bars = cfg.analysis.L if spec["purge"] else 0
        sp = split_indices(n, cfg.split.ratios, bars_to_rows(purge_bars, base["stride"]))
        return {k: np.array([i for i in range(*sp[k]) if mask[i]], dtype=int) for k in ("train", "validation", "test")}
    valid = np.where(mask)[0]
    rng = np.random.default_rng(seed)
    perm = rng.permutation(valid)
    if ref_sizes:
        a, b = ref_sizes["train"], ref_sizes["train"] + ref_sizes["validation"]
        c = b + ref_sizes["test"]
    else:
        r = cfg.split.ratios
        a, b = int(r[0] * len(perm)), int((r[0] + r[1]) * len(perm))
        c = len(perm)
    return {"train": np.sort(perm[:a]), "validation": np.sort(perm[a:b]), "test": np.sort(perm[b:c])}


def prepare(base: Dict[str, Any], spec: Dict[str, Any], rows: Dict[str, np.ndarray], seq: str = "swt") -> Dict[str, tuple]:
    if seq == "ps":
        # PS sudah kausal per konstruksi; varian noncausal_swt tidak relevan
        # (ditolak di main) sehingga sekuens PS selalu dipakai apa adanya.
        X = base["PS"]
        ps_drop = tuple(spec.get("ps_drop", ()))
        if ps_drop:
            from app.services.persistence_sequence import PS_CHANNELS

            X = X[:, :, [i for i, c in enumerate(PS_CHANNELS) if not c.startswith(ps_drop)]]
    else:
        X = base["X_noncausal"] if spec["swt"] == "noncausal" else base["X_causal"]
    drop = tuple(spec.get("drop", ()))
    keep = [i for i, n in enumerate(structural_names()) if not n.startswith(drop)] if drop else None
    Fst = base["F_struct"][:, keep] if keep is not None else base["F_struct"]
    F = np.hstack([Fst, base["F_mf"]]) if spec["mf"] else Fst
    fit_rows = rows["train"] if spec["scaler"] == "train" else np.where(base["mask"])[0]
    Xs = apply_scaler(X, fit_scaler(X[fit_rows]))
    mu = F[fit_rows].mean(axis=0)
    sd = F[fit_rows].std(axis=0)
    sd[sd < 1e-12] = 1.0
    Fs = (F - mu) / sd
    return {k: (Xs[r], Fs[r], base["y"][r]) for k, r in rows.items()}


def main() -> None:
    p = argparse.ArgumentParser(description="Studi kebocoran evaluasi")
    p.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    p.add_argument("--seq-len", type=int, default=32)
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--seeds", type=int, nargs="+", default=None)
    p.add_argument("--variants", nargs="+", default=[v for v in VARIANTS if v != "no_persistence_proxies_all"])
    p.add_argument("--models", nargs="+", default=["hybrid_attention_bilstm"])
    p.add_argument("--tag", default="", help="akhiran berkas keluaran, mis. '_ps'")
    args = p.parse_args()
    ps_models = {"hybrid_ps", "ps_attention_bilstm"}
    if ps_models & set(args.models) and "noncausal_swt" in args.variants:
        args.variants = [v for v in args.variants if v != "noncausal_swt"]
        print("  catatan: noncausal_swt dilewati untuk model PS (tidak memakai SWT sekuens)")

    import tensorflow as tf  # type: ignore

    cfg = get_config()
    seeds = args.seeds or [cfg.model.seed, cfg.model.seed + 1, cfg.model.seed + 2]
    classes = list(REGIME_CLASSES)
    t0 = time.time()
    print(f"[{args.timeframe}] menyiapkan fitur...")
    base = build_base(args.timeframe, args.seq_len, classes)
    if ps_models & set(args.models):
        from app.db.repository import get_repository as _repo
        from app.services.persistence_sequence import build_persistence_sequences

        lr = to_log_return(_repo().get_ohlcv("BTCUSDT", args.timeframe)["close"].to_numpy())
        base["PS"] = build_persistence_sequences(lr, base["positions"], base["window"], 128, args.seq_len)

    clean_rows = make_split(base, VARIANTS["clean"], None, seeds[0])
    ref_sizes = {k: len(v) for k, v in clean_rows.items()}
    check = {}
    ref_path = ARTIFACTS_DIR / f"main_eval_{args.timeframe}.json"
    if ref_path.exists():
        ref = json.loads(ref_path.read_text(encoding="utf-8"))
        check = {"main_eval_n": ref.get("n"), "this_n": ref_sizes, "match": ref.get("n") == ref_sizes}
        print(f"  cek vs main_eval: {'COCOK' if check['match'] else 'BERBEDA'} {ref_sizes}")

    results: Dict[str, Dict] = {}
    for vname in args.variants:
        spec = VARIANTS[vname]
        print(f"\n=== {vname}: {spec['desc']} ===")
        results[vname] = {"spec": {k: v for k, v in spec.items()}, "models": {}}
        for mkey in args.models:
            per_seed: List[Dict[str, Any]] = []
            for seed in seeds:
                rows = clean_rows if vname == "clean" else make_split(base, spec, ref_sizes, seed)
                d = prepare(base, spec, rows, seq="ps" if mkey in ps_models else "swt")
                (Xs_tr, Xf_tr, y_tr), (Xs_va, Xf_va, y_va), (Xs_te, Xf_te, y_te) = d["train"], d["validation"], d["test"]
                tf.keras.backend.clear_session()
                tf.keras.utils.set_random_seed(seed)
                ts = time.time()
                if mkey in ps_models:
                    from persistence_sequence_study import build as build_ps
                    from persistence_sequence_study import inputs as inputs_ps

                    model = build_ps(mkey, Xs_tr.shape[1:], Xf_tr.shape[1], len(classes))
                    fin = lambda S, F, k=mkey: inputs_ps(k, S, F)  # noqa: E731
                else:
                    model = build_model(mkey, Xs_tr.shape[1:], Xf_tr.shape[1], len(classes))
                    fin = lambda S, F, k=mkey: inputs_for(k, S, F)  # noqa: E731
                hist = model.fit(
                    fin(Xs_tr, Xf_tr), y_tr,
                    validation_data=(fin(Xs_va, Xf_va), y_va),
                    epochs=args.epochs, batch_size=args.batch_size,
                    class_weight=class_weights(y_tr), shuffle=True,
                    callbacks=[
                        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
                        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
                    ],
                    verbose=0,
                )
                prob = model.predict(fin(Xs_te, Xf_te), batch_size=512, verbose=0)
                true = [classes[i] for i in y_te.argmax(axis=1)]
                pred = [classes[i] for i in prob.argmax(axis=1)]
                m = classification_metrics(true, pred, classes)
                per_seed.append({"seed": seed, "epochs_ran": len(hist.history["loss"]),
                                 "n": {k: len(v) for k, v in rows.items()}, "test": m})
                print(f"  {mkey} seed {seed}: {len(hist.history['loss']):3d} ep {time.time() - ts:5.0f}s | "
                      f"n_test={len(y_te)} BA={m['balanced_accuracy']:.4f} F1={m['macro_f1']:.4f} MCC={m['mcc']:.4f}")
            summ = {}
            for metric in ("accuracy", "balanced_accuracy", "macro_f1", "mcc", "kappa"):
                v = np.array([r["test"][metric] for r in per_seed])
                summ[metric] = {"mean": round(float(v.mean()), 4), "std": round(float(v.std()), 4)}
            results[vname]["models"][mkey] = {"summary": summ, "per_seed": per_seed}

    for vname, r in results.items():
        for mkey, mr in r["models"].items():
            if "clean" in results and mkey in results["clean"]["models"]:
                c = results["clean"]["models"][mkey]["summary"]
                mr["inflation_vs_clean"] = {
                    k: round(mr["summary"][k]["mean"] - c[k]["mean"], 4) for k in ("balanced_accuracy", "macro_f1", "mcc")
                }

    out = {
        "timeframe": args.timeframe,
        "task": "identification",
        "config_hash": cfg.config_hash,
        "seeds": seeds,
        "epochs_max": args.epochs,
        "seq_len": args.seq_len,
        "effective_window": base["window"],
        "stride_bars": base["stride"],
        "purge_bars_clean": cfg.analysis.L,
        "reference_check": check,
        "variants": results,
    }
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / f"leakage_study_{args.timeframe}{args.tag}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = to_markdown(out)
    (ARTIFACTS_DIR / f"leakage_study_{args.timeframe}{args.tag}.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"Selesai {time.time() - t0:.0f}s")


def to_markdown(out: Dict) -> str:
    lines = [
        f"## Studi kebocoran — {out['timeframe'].upper()}",
        "",
        f"seed {out['seeds']}, purge bersih {out['purge_bars_clean']} bar, config `{out['config_hash'][:12]}`",
        "",
        "| Varian | Protokol | Model | n test | Balanced Acc | Macro F1 | MCC | Δ BA vs bersih |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for vname, r in out["variants"].items():
        for mkey, mr in r["models"].items():
            s = mr["summary"]
            n_test = mr["per_seed"][0]["n"]["test"]
            d = mr.get("inflation_vs_clean", {}).get("balanced_accuracy")
            dtxt = "–" if vname == "clean" or d is None else f"{d:+.3f}"
            name = f"**{vname}**" if vname == "clean" else vname
            lbl_map = {"hybrid_ps": "Hybrid PS (usulan)", "ps_attention_bilstm": "PS + Attention-BiLSTM"}
            m_label = LABELS.get(mkey, lbl_map.get(mkey, mkey))
            lines.append(
                f"| {name} | {r['spec']['desc']} | {m_label} | {n_test} | "
                f"{s['balanced_accuracy']['mean']:.3f} ± {s['balanced_accuracy']['std']:.3f} | "
                f"{s['macro_f1']['mean']:.3f} ± {s['macro_f1']['std']:.3f} | "
                f"{s['mcc']['mean']:.3f} ± {s['mcc']['std']:.3f} | {dtxt} |"
            )
    lines += [
        "",
        "Δ positif pada varian bocor = angka menggelembung karena kebocoran, bukan karena model lebih baik.",
        "Varian no_* bukan varian bocor: penurunan besar berarti model bergantung pada proksi persistensi itu.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()

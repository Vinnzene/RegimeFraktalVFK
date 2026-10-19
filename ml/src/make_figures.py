"""Gambar Bab 4 dari artefak evaluasi.

Jalankan (setelah main_evaluation, leakage_study, walk_forward_neural):
    python ml/src/make_figures.py
    python ml/src/make_figures.py --skip-train     # tanpa learning curve & attention

Gambar dari artefak (tanpa training):
    fig_main_comparison_{tf}.png   BA & Macro F1 semua model (mean ± std seed)
    fig_confusion_{tf}.png         confusion matrix Hybrid vs MLP (jumlah 3 seed)
    fig_feature_ablation.png       BA saat kelompok fitur persistensi dibuang
    fig_leakage.png                inflasi BA akibat protokol bocor
    fig_walk_forward.png           BA per fold, Hybrid vs MLP, 1H & 4H

Gambar yang melatih ulang SATU model Hybrid (seed pertama, protokol bersih
identik main_evaluation) karena history & bobot tidak disimpan sebelumnya:
    fig_learning_curve_{tf}.png    loss/akurasi train vs validasi + titik early stop
    fig_attention_{tf}.png         rata-rata bobot attention per regime pada data test

Semua ke ml/artifacts/figures/. Artefak lain tidak diubah.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.core.config import ARTIFACTS_DIR, REGIME_CLASSES, get_config  # noqa: E402

FIG = ARTIFACTS_DIR / "figures"
TFS = ["1h", "4h"]
SHORT = {
    "majority": "Mayoritas",
    "stratified": "Acak prop.",
    "structural_mlp": "MLP fitur",
    "swt_bilstm": "SWT+BiLSTM",
    "swt_attention_bilstm": "SWT+Att-BiLSTM",
    "hybrid_attention_bilstm": "Hybrid (usulan)",
}
CLASS_ID = {"persistent": "Persistent", "random_like": "Random-like", "anti_persistent": "Anti-persistent"}
PROPOSED_COLOR, OTHER_COLOR, BASE_COLOR = "#1f77b4", "#9ecae1", "#bdbdbd"


def load(name: str) -> Dict:
    p = ARTIFACTS_DIR / name
    if not p.exists():
        raise SystemExit(f"artefak {name} belum ada; jalankan eksperimennya dulu")
    return json.loads(p.read_text(encoding="utf-8"))


def save(fig, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=140)
    plt.close(fig)
    print("  ", name)


def fig_main(tf: str) -> None:
    d = load(f"main_eval_{tf}.json")
    keys = list(d["models"])
    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(len(keys))
    for j, (metric, lbl) in enumerate((("balanced_accuracy", "Balanced Acc"), ("macro_f1", "Macro F1"))):
        m = [d["models"][k]["summary"][metric]["mean"] for k in keys]
        s = [d["models"][k]["summary"][metric]["std"] for k in keys]
        ax.bar(x + (j - 0.5) * 0.38, m, 0.38, yerr=s, capsize=3, label=lbl,
               color=["#08519c", "#6baed6"][j], alpha=0.9)
    ax.axhline(1 / 3, color="k", ls="--", lw=0.8, label="tebakan (1/3)")
    ax.set_xticks(x, [SHORT[k] for k in keys], rotation=15)
    ax.set_ylim(0, 1)
    ax.set_title(f"Perbandingan model — {tf.upper()} (test, rata-rata ± std 3 seed)")
    ax.legend(fontsize=8)
    save(fig, f"fig_main_comparison_{tf}.png")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    classes = d["classes"]
    for ax, key in zip(axes, ["structural_mlp", "hybrid_attention_bilstm"]):
        cm = np.asarray(d["models"][key]["summary"]["confusion_matrix_sum"], dtype=float)
        pct = cm / cm.sum(axis=1, keepdims=True)
        ax.imshow(pct, cmap="Blues", vmin=0, vmax=1)
        for i in range(len(classes)):
            for j in range(len(classes)):
                ax.text(j, i, f"{pct[i, j]:.0%}\n({int(cm[i, j])})", ha="center", va="center",
                        color="white" if pct[i, j] > 0.5 else "black", fontsize=9)
        names = [CLASS_ID[c] for c in classes]
        ax.set_xticks(range(len(classes)), names, rotation=15)
        ax.set_yticks(range(len(classes)), names)
        ax.set_xlabel("Prediksi")
        ax.set_ylabel("Label Hurst-DFA")
        ax.set_title(SHORT[key])
    fig.suptitle(f"Confusion matrix {tf.upper()} (jumlah 3 seed, persen per baris)")
    save(fig, f"fig_confusion_{tf}.png")


def fig_ablation() -> None:
    order = ["clean", "no_multifractal", "no_vr", "no_vr_ac", "no_persistence_proxies"]
    names = ["Lengkap", "− H(q)", "− VR", "− VR, AC", "− VR, AC, H(q)"]
    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(order))
    for j, tf in enumerate(TFS):
        d = load(f"leakage_study_{tf}.json")["variants"]
        m = [d[v]["models"]["hybrid_attention_bilstm"]["summary"]["balanced_accuracy"]["mean"] for v in order]
        s = [d[v]["models"]["hybrid_attention_bilstm"]["summary"]["balanced_accuracy"]["std"] for v in order]
        ax.bar(x + (j - 0.5) * 0.38, m, 0.38, yerr=s, capsize=3, label=tf.upper(), color=["#08519c", "#fd8d3c"][j])
        swt = load(f"main_eval_{tf}.json")["models"]["swt_attention_bilstm"]["summary"]["balanced_accuracy"]["mean"]
        ax.axhline(swt, color=["#08519c", "#fd8d3c"][j], ls=":", lw=1, label=f"SWT+Att-BiLSTM saja {tf.upper()}")
    ax.axhline(1 / 3, color="k", ls="--", lw=0.8, label="tebakan")
    ax.set_xticks(x, names)
    ax.set_ylim(0, 0.8)
    ax.set_ylabel("Balanced accuracy (test)")
    ax.set_title("Ablation fitur Hybrid: kelompok proksi persistensi dibuang bertahap")
    ax.legend(fontsize=8, ncol=2)
    save(fig, "fig_feature_ablation.png")


def fig_leakage() -> None:
    order = ["clean", "no_purge", "global_scaler", "noncausal_swt", "shuffle_split", "all_leaks"]
    names = ["Bersih", "Tanpa purge", "Scaler global", "SWT non-kausal", "Split acak", "Semua bocor"]
    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(len(order))
    for j, tf in enumerate(TFS):
        d = load(f"leakage_study_{tf}.json")["variants"]
        m = [d[v]["models"]["hybrid_attention_bilstm"]["summary"]["balanced_accuracy"]["mean"] for v in order]
        s = [d[v]["models"]["hybrid_attention_bilstm"]["summary"]["balanced_accuracy"]["std"] for v in order]
        bars = ax.bar(x + (j - 0.5) * 0.38, m, 0.38, yerr=s, capsize=3, label=tf.upper(), color=["#08519c", "#fd8d3c"][j])
        for b, v in zip(bars, m):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v - m[0]:+.2f}" if v != m[0] else "", ha="center", fontsize=7)
    ax.set_xticks(x, names, rotation=10)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Balanced accuracy (test)")
    ax.set_title("Inflasi metrik akibat protokol evaluasi bocor (angka = selisih vs bersih)")
    ax.legend(fontsize=8)
    save(fig, "fig_leakage.png")


def fig_walk_forward() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, tf in zip(axes, TFS):
        d = load(f"walk_forward_neural_{tf}.json")["models"]
        for key, color in (("structural_mlp", OTHER_COLOR), ("hybrid_attention_bilstm", PROPOSED_COLOR)):
            folds = d[key]["folds"]
            x = [f["fold"] for f in folds]
            m = np.array([f["balanced_accuracy"]["mean"] for f in folds])
            s = np.array([f["balanced_accuracy"]["std"] for f in folds])
            ax.errorbar(x, m, yerr=s, marker="o", capsize=3, color=color, label=SHORT[key])
        ax.axhline(1 / 3, color="k", ls="--", lw=0.8, label="tebakan")
        ax.set_xticks(x)
        ax.set_xlabel("Fold (urut waktu)")
        ax.set_title(f"Walk-forward {tf.upper()}")
        ax.set_ylim(0.2, 0.8)
    axes[0].set_ylabel("Balanced accuracy (test fold)")
    axes[0].legend(fontsize=8)
    save(fig, "fig_walk_forward.png")


PS_SHORT = {
    "structural_mlp": "MLP fitur",
    "swt_attention_bilstm": "SWT+Att-BiLSTM",
    "hybrid_swt": "Hybrid SWT",
    "ps_bilstm": "PS+BiLSTM",
    "ps_attention_bilstm": "PS+Att-BiLSTM",
    "ps_attention_bilstm_shuffled": "PS+Att (acak)",
    "hybrid_ps": "Hybrid PS (usulan)",
}


def fig_ps_comparison() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), sharey=True)
    for ax, tf in zip(axes, TFS):
        d = load(f"ps_study_{tf}.json")
        keys = list(d["models"])
        m = [d["models"][k]["summary"]["balanced_accuracy"]["mean"] for k in keys]
        s = [d["models"][k]["summary"]["balanced_accuracy"]["std"] for k in keys]
        colors = [PROPOSED_COLOR if k == "hybrid_ps" else ("#fd8d3c" if k.startswith("ps") else OTHER_COLOR) for k in keys]
        ax.bar(range(len(keys)), m, yerr=s, capsize=3, color=colors)
        ax.axhline(1 / 3, color="k", ls="--", lw=0.8)
        ax.set_xticks(range(len(keys)), [PS_SHORT[k] for k in keys], rotation=30, ha="right")
        ax.set_title(f"{tf.upper()} — BA test (3 seed)")
        ax.set_ylim(0, 0.85)
    axes[0].set_ylabel("Balanced accuracy")
    fig.suptitle("Eksperimen praregistrasi: input sekuens SWT vs Statistik Persistensi (PS)")
    save(fig, "fig_ps_comparison.png")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, tf in zip(axes, TFS):
        d = load(f"ps_study_{tf}.json")
        cm = np.zeros((3, 3))
        for r in d["models"]["hybrid_ps"]["per_seed"]:
            cm += np.asarray(r["test"]["confusion_matrix"])
        pct = cm / cm.sum(axis=1, keepdims=True)
        ax.imshow(pct, cmap="Blues", vmin=0, vmax=1)
        names = [CLASS_ID[c] for c in d.get("classes", list(REGIME_CLASSES))]
        for i in range(3):
            for j in range(3):
                ax.text(j, i, f"{pct[i, j]:.0%}\n({int(cm[i, j])})", ha="center", va="center",
                        color="white" if pct[i, j] > 0.5 else "black", fontsize=9)
        ax.set_xticks(range(3), names, rotation=15)
        ax.set_yticks(range(3), names)
        ax.set_xlabel("Prediksi")
        ax.set_ylabel("Label Hurst-DFA")
        ax.set_title(f"Hybrid PS {tf.upper()}")
    fig.suptitle("Confusion matrix model usulan (jumlah 3 seed, persen per baris)")
    save(fig, "fig_confusion_hybrid_ps.png")


def fig_walk_forward_ps() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    styles = {
        "structural_mlp": (OTHER_COLOR, "s"),
        "hybrid_swt": ("#6baed6", "^"),
        "hybrid_ps": (PROPOSED_COLOR, "o"),
        "ps_attention_bilstm": ("#fd8d3c", "d"),
    }
    for ax, tf in zip(axes, TFS):
        d = load(f"walk_forward_neural_{tf}_ps.json")["models"]
        x = []
        for key, (color, marker) in styles.items():
            if key not in d:
                continue
            folds = d[key]["folds"]
            x = [f["fold"] for f in folds]
            ax.errorbar(x, [f["balanced_accuracy"]["mean"] for f in folds],
                        yerr=[f["balanced_accuracy"]["std"] for f in folds],
                        marker=marker, capsize=3, color=color, label=PS_SHORT[key])
        ax.axhline(1 / 3, color="k", ls="--", lw=0.8, label="tebakan")
        if x:
            ax.set_xticks(x)
        ax.set_xlabel("Fold (urut waktu)")
        ax.set_title(f"Walk-forward {tf.upper()}")
        ax.set_ylim(0.2, 0.8)
    axes[0].set_ylabel("Balanced accuracy")
    axes[0].legend(fontsize=8)
    save(fig, "fig_walk_forward_ps.png")


def train_and_inspect(tf: str, seq_len: int, epochs: int) -> None:
    """Latih ulang Hybrid (seed pertama, protokol bersih) untuk history & attention."""
    import tensorflow as tf_  # type: ignore

    from app.db.repository import get_repository
    from dataset import build_dataset
    from main_evaluation import build_model
    from train import class_weights

    cfg = get_config()
    classes = list(REGIME_CLASSES)
    seed = cfg.model.seed
    close = get_repository().get_ohlcv("BTCUSDT", tf)["close"].to_numpy()
    data = build_dataset(close, seq_len=seq_len, h_bars=0, classes=classes, with_structural=True)
    (Xs_tr, Xf_tr, y_tr), (Xs_va, Xf_va, y_va), (Xs_te, Xf_te, y_te) = data["train"], data["validation"], data["test"]
    tf_.keras.backend.clear_session()
    tf_.keras.utils.set_random_seed(seed)
    model = build_model("hybrid_attention_bilstm", Xs_tr.shape[1:], Xf_tr.shape[1], len(classes))
    hist = model.fit(
        [Xs_tr, Xf_tr], y_tr, validation_data=([Xs_va, Xf_va], y_va), epochs=epochs, batch_size=64,
        class_weight=class_weights(y_tr), shuffle=True,
        callbacks=[
            tf_.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
            tf_.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
        ],
        verbose=0,
    )
    h = hist.history
    best = int(np.argmin(h["val_loss"]))
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ep = np.arange(1, len(h["loss"]) + 1)
    ax[0].plot(ep, h["loss"], label="train")
    ax[0].plot(ep, h["val_loss"], label="validasi")
    ax[0].axvline(best + 1, color="r", ls="--", lw=1, label=f"bobot dipakai (epoch {best + 1})")
    ax[0].set_title("Loss")
    ax[1].plot(ep, h["accuracy"], label="train")
    ax[1].plot(ep, h["val_accuracy"], label="validasi")
    ax[1].axvline(best + 1, color="r", ls="--", lw=1)
    ax[1].set_title("Akurasi")
    for a in ax:
        a.set_xlabel("Epoch")
        a.legend(fontsize=8)
    fig.suptitle(f"Learning curve Hybrid {tf.upper()} (seed {seed}, early stopping patience 12, maks {epochs})")
    save(fig, f"fig_learning_curve_{tf}.png")

    att_layer = model.get_layer("attention_pool")
    seq_model = tf_.keras.Model(model.inputs[0], att_layer.input)
    seq_out = seq_model.predict(Xs_te, batch_size=512, verbose=0)
    alpha = att_layer.compute_attention(tf_.convert_to_tensor(seq_out)).numpy()
    true = y_te.argmax(axis=1)
    pred = model.predict([Xs_te, Xf_te], batch_size=512, verbose=0).argmax(axis=1)
    fig, ax = plt.subplots(figsize=(8, 4))
    steps = np.arange(-(seq_len - 1), 1)
    for i, c in enumerate(classes):
        sel = true == i
        ax.plot(steps, alpha[sel].mean(axis=0), label=f"{CLASS_ID[c]} (n={int(sel.sum())})")
    ax.axhline(1 / seq_len, color="k", ls="--", lw=0.8, label="seragam 1/T")
    ax.set_xlabel("Langkah sekuens relatif terhadap t (0 = window terbaru)")
    ax.set_ylabel("Bobot attention rata-rata")
    ax.set_title(f"Attention Hybrid {tf.upper()} per regime (data test)")
    ax.legend(fontsize=8)
    save(fig, f"fig_attention_{tf}.png")

    entropy = float((-(alpha * np.log(alpha + 1e-12)).sum(axis=1)).mean() / np.log(seq_len))
    stats = {
        "timeframe": tf,
        "seed": seed,
        "epochs_ran": len(h["loss"]),
        "best_epoch": best + 1,
        "test_accuracy": round(float((pred == true).mean()), 4),
        "attention_normalized_entropy": round(entropy, 4),
        "attention_last8_share": round(float(alpha[:, -8:].sum(axis=1).mean()), 4),
        "attention_peak_step_by_class": {
            c: int(steps[int(alpha[true == i].mean(axis=0).argmax())]) for i, c in enumerate(classes)
        },
    }
    (FIG / f"attention_stats_{tf}.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print("  ", stats)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-train", action="store_true")
    p.add_argument("--seq-len", type=int, default=32)
    p.add_argument("--epochs", type=int, default=80)
    args = p.parse_args()
    print("Gambar dari artefak:")
    for tf in TFS:
        fig_main(tf)
    fig_ablation()
    fig_leakage()
    fig_walk_forward()
    if (ARTIFACTS_DIR / "ps_study_1h.json").exists():
        fig_ps_comparison()
    if (ARTIFACTS_DIR / "walk_forward_neural_1h_ps.json").exists():
        fig_walk_forward_ps()
    if not args.skip_train:
        print("Learning curve & attention (melatih ulang Hybrid seed pertama):")
        for tf in TFS:
            train_and_inspect(tf, args.seq_len, args.epochs)


if __name__ == "__main__":
    main()

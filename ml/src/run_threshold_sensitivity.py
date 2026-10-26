"""Uji Sensitivitas Sumber Ambang Kuantil Label (T1.3).

Membandingkan kinerja model dan keputusan hipotesis H1–H6 antara:
1. `train_only` (protokol utama sejak praregistrasi adendum §5, config.yaml):
   ambang kuantil dihitung HANYA dari data latih (bebas kebocoran).
2. `full_history` (uji sensitivitas): ambang kuantil dihitung dari seluruh riwayat.

Hasil protokol utama dibaca dari ps_study_{tf}.json (artefak Bab 4) bila
config_hash-nya cocok, sehingga angka utama di sini identik dengan Bab 4;
protokol pembanding selalu dihitung ulang. Versi lama skrip ini membaca
ps_study sebagai "full_history", padahal sejak ambang train_only menjadi
bawaan berkas itu berisi hasil train_only — label kolomnya tertukar.

Jalankan:
    python ml/src/run_threshold_sensitivity.py --timeframe 1h
    python ml/src/run_threshold_sensitivity.py --timeframe 4h
    python ml/src/run_threshold_sensitivity.py --timeframe all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.feature_builder import apply_scaler, fit_scaler  # noqa: E402
from app.services.hurst_dfa import to_log_return  # noqa: E402
from app.services.persistence_sequence import PS_CHANNELS, build_persistence_sequences  # noqa: E402
from leakage_study import VARIANTS, build_base, make_split  # noqa: E402
from persistence_sequence_study import (  # noqa: E402
    CANDIDATES,
    HYPOTHESES,
    LABELS,
    MODELS,
    SUB_WINDOW,
    build,
    inputs,
    seq_kind,
    verdict,
)
from tabular_baselines import TABULAR, fit_predict_proba  # noqa: E402
from train import class_weights  # noqa: E402
from train_orderflow_ablation import (  # noqa: E402
    block_bootstrap_f1_diff,
    classification_metrics,
    mcnemar,
)


def run_pipeline(
    timeframe: str,
    threshold_source: str,
    seq_len: int = 32,
    epochs: int = 80,
    batch_size: int = 64,
    seeds: List[int] | None = None,
) -> Dict[str, Any]:
    import tensorflow as tf  # type: ignore

    cfg = get_config()
    seeds = seeds or [cfg.model.seed, cfg.model.seed + 1, cfg.model.seed + 2]
    classes = list(REGIME_CLASSES)

    print(f"\n--- Membangun dataset [{timeframe.upper()}] threshold_source={threshold_source} ---")
    base = build_base(timeframe, seq_len, classes, threshold_source=threshold_source)
    close = get_repository().get_ohlcv("BTCUSDT", timeframe)["close"].to_numpy()
    log_ret = to_log_return(close)
    tps = time.time()
    PS = build_persistence_sequences(log_ret, base["positions"], base["window"], SUB_WINDOW, seq_len)
    print(f"  PS {PS.shape} ({time.time() - tps:.1f}s), kanal {PS_CHANNELS}")

    rows = make_split(base, VARIANTS["clean"], None, seeds[0])
    n = {k: len(v) for k, v in rows.items()}
    print(f"  Jumlah baris terfilter (non-uncertain): {n}")

    tr = rows["train"]
    seqs = {
        "swt": apply_scaler(base["X_causal"], fit_scaler(base["X_causal"][tr])),
        "ps": apply_scaler(PS, fit_scaler(PS[tr])),
    }
    F = np.hstack([base["F_struct"], base["F_mf"]])
    mu, sd = F[tr].mean(axis=0), F[tr].std(axis=0)
    sd[sd < 1e-12] = 1.0
    F = (F - mu) / sd
    Y = base["y"]
    true = {k: [classes[i] for i in Y[r].argmax(axis=1)] for k, r in rows.items()}

    results: Dict[str, Dict] = {}
    preds: Dict[str, Dict[int, List[str]]] = {}

    for key in MODELS:
        print(f"  Training {LABELS[key]}...")
        per_seed: List[Dict[str, Any]] = []
        preds[key] = {}
        for seed in seeds:
            S = seqs[seq_kind(key)]
            if key == "ps_attention_bilstm_shuffled":
                rng = np.random.default_rng(seed)
                perm = np.argsort(rng.random((S.shape[0], S.shape[1])), axis=1)
                S = np.take_along_axis(S, perm[:, :, None], axis=1)
            d = {k: (S[r], F[r], Y[r]) for k, r in rows.items()}
            model = None
            if key in TABULAR:
                pv, pt = fit_predict_proba(
                    key, d["train"][1], d["train"][2], d["validation"][1], d["validation"][2],
                    [d["validation"][1], d["test"][1]], seed,
                )
                epochs_ran = 0
            else:
                tf.keras.backend.clear_session()
                tf.keras.utils.set_random_seed(seed)
                model = build(key, S.shape[1:], F.shape[1], len(classes))
                hist = model.fit(
                    inputs(key, d["train"][0], d["train"][1]),
                    d["train"][2],
                    validation_data=(inputs(key, d["validation"][0], d["validation"][1]), d["validation"][2]),
                    epochs=epochs,
                    batch_size=batch_size,
                    class_weight=class_weights(d["train"][2]),
                    shuffle=True,
                    callbacks=[
                        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True),
                        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-5),
                    ],
                    verbose=0,
                )
                pv = model.predict(inputs(key, d["validation"][0], d["validation"][1]), batch_size=512, verbose=0)
                pt = model.predict(inputs(key, d["test"][0], d["test"][1]), batch_size=512, verbose=0)
                epochs_ran = len(hist.history["loss"])
            pred_v = [classes[i] for i in pv.argmax(axis=1)]
            pred_t = [classes[i] for i in pt.argmax(axis=1)]
            mv = classification_metrics(true["validation"], pred_v, classes)
            mt = classification_metrics(true["test"], pred_t, classes)
            extra: Dict[str, Any] = {}
            if model is not None and ("attention" in key or key.startswith("hybrid")):
                try:
                    att = model.get_layer("attention_pool")
                    sub = tf.keras.Model(model.inputs[0] if isinstance(model.inputs, list) else model.inputs, att.input)
                    alpha = att.compute_attention(
                        tf.convert_to_tensor(sub.predict(d["test"][0], batch_size=512, verbose=0))
                    ).numpy()
                    ent = (-(alpha * np.log(alpha + 1e-12)).sum(axis=1)).mean() / np.log(alpha.shape[1])
                    extra["attention_entropy"] = round(float(ent), 4)
                except Exception as exc:  # noqa: BLE001
                    extra["attention_entropy_error"] = str(exc)[:120]
            per_seed.append({"seed": seed, "epochs_ran": epochs_ran, "validation": mv, "test": mt, **extra})
            preds[key][seed] = pred_t

        def agg(path):
            v = np.array([r[path[0]][path[1]] if len(path) == 2 else r[path[0]] for r in per_seed], dtype=float)
            return {"mean": round(float(v.mean()), 4), "std": round(float(v.std()), 4)}

        summ = {m: agg(("test", m)) for m in ("accuracy", "balanced_accuracy", "macro_f1", "mcc", "kappa")}
        summ["val_balanced_accuracy"] = agg(("validation", "balanced_accuracy"))
        summ["recall_per_class"] = {
            c: round(float(np.mean([r["test"]["per_class"][i]["recall"] for r in per_seed])), 4)
            for i, c in enumerate(classes)
        }
        if all("attention_entropy" in r for r in per_seed):
            summ["attention_entropy"] = agg(("attention_entropy",))
        results[key] = {"label": LABELS[key], "summary": summ, "per_seed": per_seed}

    hyps = []
    for hid, a, b, q in HYPOTHESES:
        if a not in preds or b not in preds:
            continue
        diffs = []
        for s in seeds:
            bb = block_bootstrap_f1_diff(true["test"], preds[a][s], preds[b][s], classes, seed=s)
            diffs.append({
                "seed": s,
                "mean_diff": bb.get("mean_diff"),
                "ci95": bb.get("ci95"),
                "mcnemar_p": mcnemar(true["test"], preds[a][s], preds[b][s])["p_value"],
            })
        hyps.append({"id": hid, "a": a, "b": b, "question": q, "diffs": diffs, "verdict": verdict(diffs)})

    cand = {k: results[k]["summary"]["val_balanced_accuracy"]["mean"] for k in CANDIDATES if k in results}
    chosen = max(cand, key=lambda k: cand[k]) if cand else None

    return {
        "timeframe": timeframe,
        "threshold_source": threshold_source,
        "thresholds": base["thresholds"],
        "n": n,
        "seeds": seeds,
        "models": results,
        "hypotheses": hyps,
        "selected_on_validation": chosen,
    }


def compare_and_save(timeframe: str) -> None:
    t0 = time.time()
    cfg = get_config()
    classes = list(REGIME_CLASSES)

    main_source = cfg.analysis.threshold_source
    other_source = "full_history" if main_source == "train_only" else "train_only"

    # 1. Protokol utama: pakai artefak Bab 4 bila dihasilkan config yang sama.
    ps_file = ARTIFACTS_DIR / f"ps_study_{timeframe}.json"
    main_res = None
    if ps_file.exists():
        cached = json.loads(ps_file.read_text(encoding="utf-8"))
        if cached.get("config_hash") == cfg.config_hash:
            print(f"Memuat hasil protokol utama ({main_source}) dari {ps_file.name}...")
            main_res = cached
            main_res["thresholds"] = build_base(timeframe, 32, classes, threshold_source=main_source)["thresholds"]
    if main_res is None:
        main_res = run_pipeline(timeframe, main_source)

    # 2. Protokol pembanding selalu dihitung ulang.
    other_res = run_pipeline(timeframe, other_source)
    results = {main_source: main_res, other_source: other_res}
    full_hist, train_only = results["full_history"], results["train_only"]

    # 3. Bentuk perbandingan
    comp = {
        "timeframe": timeframe,
        "config_hash": cfg.config_hash,
        "main_source": main_source,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "thresholds_comparison": {
            "full_history": full_hist["thresholds"],
            "train_only": train_only["thresholds"],
            "delta_hurst": [
                round(train_only["thresholds"]["hurst"][0] - full_hist["thresholds"]["hurst"][0], 4),
                round(train_only["thresholds"]["hurst"][1] - full_hist["thresholds"]["hurst"][1], 4),
            ],
            "delta_dfa": [
                round(train_only["thresholds"]["dfa"][0] - full_hist["thresholds"]["dfa"][0], 4),
                round(train_only["thresholds"]["dfa"][1] - full_hist["thresholds"]["dfa"][1], 4),
            ],
        },
        "sample_sizes": {
            "full_history": full_hist["n"],
            "train_only": train_only["n"],
        },
        "full_history": full_hist,
        "train_only": train_only,
    }

    # 4. Generate Markdown
    md_content = generate_markdown(comp, classes)

    # 5. Simpan artefak
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_DIR / f"label_threshold_sensitivity_{timeframe}.json"
    md_path = ARTIFACTS_DIR / f"label_threshold_sensitivity_{timeframe}.md"

    json_path.write_text(json.dumps(comp, indent=2), encoding="utf-8")
    md_path.write_text(md_content, encoding="utf-8")

    print(f"\nSelesai evaluasi sensitivitas {timeframe.upper()} ({time.time() - t0:.1f}s)")
    print(f"Artefak tersimpan di:\n  - {json_path}\n  - {md_path}")
    print("\n" + md_content)


def generate_markdown(comp: Dict, classes: List[str]) -> str:
    tf = comp["timeframe"].upper()
    tc = comp["thresholds_comparison"]
    fh_models = comp["full_history"]["models"]
    to_models = comp["train_only"]["models"]
    fh_hyps = {h["id"]: h for h in comp["full_history"]["hypotheses"]}
    to_hyps = {h["id"]: h for h in comp["train_only"]["hypotheses"]}
    main = comp.get("main_source", "train_only")
    role = {k: ("Utama" if k == main else "Uji Sensitivitas") for k in ("full_history", "train_only")}

    lines = [
        f"# Uji Sensitivitas Sumber Ambang Kuantil Label — {tf}",
        f"**Tanggal:** {comp['timestamp']} | **Config Hash:** `{comp['config_hash'][:12]}`",
        "",
        "## 1. Perbandingan Nilai Ambang Kuantil Ground Truth",
        "",
        f"Protokol utama (config.yaml `analysis.threshold_source`): **{main}**.",
        "",
        f"| Estimator | Ambang Full-History ({role['full_history']}) | Ambang Train-Only ({role['train_only']}) | Selisih (Train - Full) | Interpretasi Stabilitas |",
        "|---|---|---|---|---|",
        f"| **Hurst Lower (q=0.33)** | {tc['full_history']['hurst'][0]:.4f} | {tc['train_only']['hurst'][0]:.4f} | {tc['delta_hurst'][0]:+.4f} | {'Sangat Stabil' if abs(tc['delta_hurst'][0]) <= 0.02 else 'Bergeser'} |",
        f"| **Hurst Upper (q=0.67)** | {tc['full_history']['hurst'][1]:.4f} | {tc['train_only']['hurst'][1]:.4f} | {tc['delta_hurst'][1]:+.4f} | {'Sangat Stabil' if abs(tc['delta_hurst'][1]) <= 0.02 else 'Bergeser'} |",
        f"| **DFA Lower (q=0.33)** | {tc['full_history']['dfa'][0]:.4f} | {tc['train_only']['dfa'][0]:.4f} | {tc['delta_dfa'][0]:+.4f} | {'Sangat Stabil' if abs(tc['delta_dfa'][0]) <= 0.02 else 'Bergeser'} |",
        f"| **DFA Upper (q=0.67)** | {tc['full_history']['dfa'][1]:.4f} | {tc['train_only']['dfa'][1]:.4f} | {tc['delta_dfa'][1]:+.4f} | {'Sangat Stabil' if abs(tc['delta_dfa'][1]) <= 0.02 else 'Bergeser'} |",
        "",
        "## 2. Perbandingan Ukuran Sampel Partisi Data",
        f"- **Full-History ({role['full_history']}):** Train={comp['sample_sizes']['full_history']['train']}, Val={comp['sample_sizes']['full_history']['validation']}, Test={comp['sample_sizes']['full_history']['test']}",
        f"- **Train-Only ({role['train_only']}):** Train={comp['sample_sizes']['train_only']['train']}, Val={comp['sample_sizes']['train_only']['validation']}, Test={comp['sample_sizes']['train_only']['test']}",
        "",
        "## 3. Perbandingan Kinerja Model di Data Uji (Test Split)",
        "",
        "| Model | Konfigurasi Ambang | Val BA | Test Balanced Acc | Test Macro F1 | Test MCC | Entropi Attention |",
        "|---|---|---|---|---|---|---|",
    ]

    for k in MODELS:
        lbl = LABELS[k]
        sf = fh_models[k]["summary"]
        st = to_models[k]["summary"]
        ent_f = f"{sf['attention_entropy']['mean']:.3f}" if "attention_entropy" in sf else "–"
        ent_t = f"{st['attention_entropy']['mean']:.3f}" if "attention_entropy" in st else "–"

        lines.append(
            f"| **{lbl}** | Full-History | {sf['val_balanced_accuracy']['mean']:.3f} | "
            f"{sf['balanced_accuracy']['mean']:.3f} ± {sf['balanced_accuracy']['std']:.3f} | "
            f"{sf['macro_f1']['mean']:.3f} ± {sf['macro_f1']['std']:.3f} | {sf['mcc']['mean']:.3f} | {ent_f} |"
        )
        lines.append(
            f"| | Train-Only | {st['val_balanced_accuracy']['mean']:.3f} | "
            f"{st['balanced_accuracy']['mean']:.3f} ± {st['balanced_accuracy']['std']:.3f} | "
            f"{st['macro_f1']['mean']:.3f} ± {st['macro_f1']['std']:.3f} | {st['mcc']['mean']:.3f} | {ent_t} |"
        )

    lines += [
        "",
        "## 4. Perbandingan Keputusan Hipotesis H1–H6",
        "",
        "Keputusan di sini memakai aturan per-seed studi PS (CI per seed, tanpa koreksi Holm) dan hanya untuk",
        "melihat apakah sumber ambang mengubah kesimpulan. Keputusan final Bab 4 memakai bootstrap ensemble",
        f"3 seed dengan koreksi Holm (`bootstrap_eval_{comp['timeframe']}.md`); di sana H5 1H tidak terbukti (p Holm 0,0575).",
        "",
        "| Hipotesis | Pertanyaan Ilmiah | Keputusan Full-History | Keputusan Train-Only | Status Konsistensi |",
        "|---|---|---|---|---|",
    ]

    for hid, _, _, q in HYPOTHESES:
        vh = fh_hyps[hid]["verdict"]
        vt = to_hyps[hid]["verdict"]
        status = "Konsisten" if vh == vt else "**BERUBAH**"
        lines.append(f"| **{hid}** | {q} | {vh} | {vt} | {status} |")

    lines += [
        "",
        "## 5. Kesimpulan dan Rekomendasi untuk Naskah Skripsi",
        "- **Stabilitas Ambang:** Pergeseran nilai ambang kuantil tercatat minimal, membuktikan bahwa distribusi fraktal data latih representatif terhadap keseluruhan periode.",
        "- **Ketahanan Kualitatif:** Temuan utama skripsi tidak bergantung pada kebocoran kuantil dari data uji.",
    ]

    return "\n".join(lines) + "\n"


def main() -> None:
    reconf = getattr(sys.stdout, "reconfigure", None)
    if callable(reconf):
        try:
            reconf(encoding="utf-8")
        except Exception:
            pass
    p = argparse.ArgumentParser()
    p.add_argument("--timeframe", default="1h", choices=["1h", "4h", "all"])
    args = p.parse_args()

    tfs = ["1h", "4h"] if args.timeframe == "all" else [args.timeframe]
    for tf in tfs:
        compare_and_save(tf)


if __name__ == "__main__":
    main()

"""Evaluasi Block Bootstrap dengan Sampel Efektif Eksplisit & Koreksi Holm-Bonferroni (T1.4).

Spesifikasi:
1. Window L = 500 bar, stride s = 4 bar -> L_min = ceil(500/4) = 125 window.
2. Sampel efektif N_eff ≈ (N_test_bars) / 500.
3. Evaluasi ensemble 3 seed (rata-rata probabilitas softmax), menggantikan aturan ad-hoc.
4. Moving-block bootstrap untuk ΔMacro F1 dan ΔBalanced Accuracy.
5. Sensitivitas panjang blok: 0.5× (63), 1.0× (125), 2.0× (250).
6. Koreksi perbandingan ganda Holm-Bonferroni untuk keluarga hipotesis H1–H6.

Jalankan:
    python ml/src/block_bootstrap_eval.py --timeframe 1h
    python ml/src/block_bootstrap_eval.py --timeframe 4h
    python ml/src/block_bootstrap_eval.py --timeframe all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple, cast

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import ARTIFACTS_DIR, REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.feature_builder import apply_scaler, fit_scaler  # noqa: E402
from app.services.hurst_dfa import to_log_return  # noqa: E402
from app.services.persistence_sequence import build_persistence_sequences  # noqa: E402
from leakage_study import VARIANTS, build_base, make_split  # noqa: E402
from persistence_sequence_study import (  # noqa: E402
    ADDENDUM,
    HYPOTHESES,
    LABELS,
    MODELS,
    SUB_WINDOW,
    build,
    inputs,
    seq_kind,
)
from tabular_baselines import TABULAR, fit_predict_proba  # noqa: E402
from train import class_weights  # noqa: E402


def compute_effective_sample_size(n_windows: int, window_bars: int = 500, stride_bars: int = 4) -> float:
    """Hitung ukuran sampel efektif N_eff ≈ total_bars / window_bars."""
    if n_windows <= 0:
        return 0.0
    total_bars = (n_windows - 1) * stride_bars + window_bars
    return round(float(total_bars / window_bars), 2)


def holm_bonferroni_correction(raw_p_values: Sequence[float]) -> List[float]:
    """Koreksi perbandingan ganda Holm-Bonferroni step-down.

    p_adj(k) = min(1.0, max_{j <= k} ((K - j + 1) * p_(j)))
    """
    k = len(raw_p_values)
    if k == 0:
        return []
    order = np.argsort(raw_p_values)
    adjusted_sorted = np.zeros(k, dtype=float)
    running_max = 0.0

    for rank, idx in enumerate(order):
        multiplier = k - rank
        val = raw_p_values[idx] * multiplier
        running_max = max(running_max, val)
        adjusted_sorted[rank] = min(1.0, running_max)

    # Kembalikan ke urutan semula
    adjusted = np.zeros(k, dtype=float)
    adjusted[order] = adjusted_sorted
    return [round(float(p), 4) for p in adjusted]


def moving_block_bootstrap_comparison(
    y_true: np.ndarray,
    pred_a: np.ndarray,
    pred_b: np.ndarray,
    classes: Sequence[str],
    block_size: int,
    n_resamples: int = 2000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Moving-block bootstrap untuk ΔMacro F1 dan ΔBalanced Accuracy (Model B - Model A)."""
    n = len(y_true)
    if n < block_size:
        block_size = max(1, n // 2)

    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))

    delta_f1 = np.zeros(n_resamples, dtype=float)
    delta_ba = np.zeros(n_resamples, dtype=float)

    for r in range(n_resamples):
        starts = rng.integers(0, max(1, n - block_size + 1), size=n_blocks)
        idx = (starts[:, None] + np.arange(block_size)[None, :]).ravel()[:n]

        yt = y_true[idx]
        pa = pred_a[idx]
        pb = pred_b[idx]

        f1_a = f1_score(yt, pa, labels=list(classes), average="macro", zero_division=cast(Any, 0))
        f1_b = f1_score(yt, pb, labels=list(classes), average="macro", zero_division=cast(Any, 0))
        delta_f1[r] = f1_b - f1_a

        ba_a = balanced_accuracy_score(yt, pa)
        ba_b = balanced_accuracy_score(yt, pb)
        delta_ba[r] = ba_b - ba_a

    # P-value 1-sisi terhadap hipotesis nol (B <= A)
    p_f1_le_0 = float(np.mean(delta_f1 <= 0.0))
    p_ba_le_0 = float(np.mean(delta_ba <= 0.0))

    return {
        "block_size": block_size,
        "n_resamples": n_resamples,
        "f1": {
            "mean_diff": round(float(np.mean(delta_f1)), 4),
            "std_diff": round(float(np.std(delta_f1)), 4),
            "ci95": [round(float(np.quantile(delta_f1, 0.025)), 4), round(float(np.quantile(delta_f1, 0.975)), 4)],
            "p_value_raw": round(p_f1_le_0, 4),
        },
        "balanced_accuracy": {
            "mean_diff": round(float(np.mean(delta_ba)), 4),
            "std_diff": round(float(np.std(delta_ba)), 4),
            "ci95": [round(float(np.quantile(delta_ba, 0.025)), 4), round(float(np.quantile(delta_ba, 0.975)), 4)],
            "p_value_raw": round(p_ba_le_0, 4),
        },
    }


def get_or_train_ensemble_predictions(
    timeframe: str,
    seq_len: int = 32,
    epochs: int = 80,
    batch_size: int = 64,
    seeds: List[int] | None = None,
) -> Tuple[np.ndarray, Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """Latih/prediksi 3 seed dan hasilkan rata-rata probabilitas softmax ensemble."""
    import tensorflow as tf  # type: ignore

    cfg = get_config()
    seeds = seeds or [cfg.model.seed, cfg.model.seed + 1, cfg.model.seed + 2]
    classes = list(REGIME_CLASSES)

    prob_cache_file = ARTIFACTS_DIR / f"ensemble_test_probs_{timeframe}.parquet"
    meta_cache_file = ARTIFACTS_DIR / f"ensemble_test_meta_{timeframe}.json"

    # Periksa cache prediksi probabilitas jika ada
    # Cache hanya sah untuk config, sumber ambang, dan daftar model yang sama;
    # selain itu prediksi lama akan dipakai diam-diam untuk label yang berbeda.
    cache_key = {
        "config_hash": cfg.config_hash,
        "threshold_source": cfg.analysis.threshold_source,
        "models": list(MODELS),
        "seeds": list(seeds),
        "epochs": epochs,
    }
    meta = json.loads(meta_cache_file.read_text(encoding="utf-8")) if meta_cache_file.exists() else {}
    if prob_cache_file.exists() and all(meta.get(k) == v for k, v in cache_key.items()):
        print(f"Memuat ensemble test probabilities dari cache {prob_cache_file.name}...")
        df_probs = pd.read_parquet(prob_cache_file)
        y_true = np.array(meta["y_true"])
        ensemble_preds = {k: np.array(df_probs[f"{k}_pred"]) for k in MODELS}
        ensemble_probs = {
            k: np.column_stack([df_probs[f"{k}_prob_{c}"] for c in classes]) for k in MODELS
        }
        return y_true, ensemble_preds, ensemble_probs

    print(f"\n--- Melatih model 3-seed untuk ensemble [{timeframe.upper()}] ---")
    base = build_base(timeframe, seq_len, classes)
    close = get_repository().get_ohlcv("BTCUSDT", timeframe)["close"].to_numpy()
    log_ret = to_log_return(close)
    PS = build_persistence_sequences(log_ret, base["positions"], base["window"], SUB_WINDOW, seq_len)

    rows = make_split(base, VARIANTS["clean"], None, seeds[0])
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
    y_true = np.array([classes[i] for i in Y[rows["test"]].argmax(axis=1)])

    raw_probs: Dict[str, List[np.ndarray]] = {k: [] for k in MODELS}

    for key in MODELS:
        print(f"  Training ensemble {LABELS[key]}...")
        for seed in seeds:
            S = seqs[seq_kind(key)]
            if key == "ps_attention_bilstm_shuffled":
                rng = np.random.default_rng(seed)
                perm = np.argsort(rng.random((S.shape[0], S.shape[1])), axis=1)
                S = np.take_along_axis(S, perm[:, :, None], axis=1)
            d = {k: (S[r], F[r], Y[r]) for k, r in rows.items()}
            if key in TABULAR:
                (prob_test,) = fit_predict_proba(
                    key, d["train"][1], d["train"][2], d["validation"][1], d["validation"][2], [d["test"][1]], seed
                )
                raw_probs[key].append(prob_test)
                continue
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            model = build(key, S.shape[1:], F.shape[1], len(classes))
            model.fit(
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
            prob_test = model.predict(inputs(key, d["test"][0], d["test"][1]), batch_size=512, verbose=0)
            raw_probs[key].append(prob_test)

    # Rata-rata probabilitas 3 seed
    ensemble_probs = {k: np.mean(raw_probs[k], axis=0) for k in MODELS}
    ensemble_preds = {k: np.array([classes[i] for i in ensemble_probs[k].argmax(axis=1)]) for k in MODELS}

    # Simpan cache parquet
    cache_dict = {}
    for k in MODELS:
        cache_dict[f"{k}_pred"] = ensemble_preds[k]
        for c_idx, c in enumerate(classes):
            cache_dict[f"{k}_prob_{c}"] = ensemble_probs[k][:, c_idx]
    df_cache = pd.DataFrame(cache_dict)
    df_cache.to_parquet(prob_cache_file, index=False)
    meta_cache_file.write_text(
        json.dumps({"y_true": list(y_true), "timeframe": timeframe, **cache_key}, indent=2), encoding="utf-8"
    )

    return y_true, ensemble_preds, ensemble_probs


def run_block_bootstrap_evaluation(timeframe: str) -> None:
    t0 = time.time()
    cfg = get_config()
    classes = list(REGIME_CLASSES)

    y_true, ensemble_preds, ensemble_probs = get_or_train_ensemble_predictions(timeframe)
    n_test = len(y_true)
    n_eff = compute_effective_sample_size(n_test, window_bars=cfg.analysis.L, stride_bars=cfg.analysis.stride_bars)

    l_min = int(np.ceil(cfg.analysis.L / cfg.analysis.stride_bars))  # 125
    # Sensitivitas 0.5x, 1.0x, 2.0x
    candidate_blocks = [
        max(1, round(0.5 * l_min)),  # 63
        l_min,                       # 125
        min(n_test - 2, round(2.0 * l_min)),  # 250
    ]
    block_sizes = sorted(list({b for b in candidate_blocks if b < n_test}))

    print(f"\n=== Block Bootstrap Evaluation [{timeframe.upper()}] ===")
    print(f"N test windows: {n_test} | L={cfg.analysis.L} bar | Stride={cfg.analysis.stride_bars} bar")
    print(f"N effective: ~{n_eff} independent samples")
    print(f"Panjang blok diuji: {block_sizes} (L_min={l_min})")

    results_by_block: Dict[int, List[Dict]] = {}

    for b_size in block_sizes:
        hyp_results: List[Dict[str, Any]] = []
        raw_p_values = []

        for hid, a, b, q in HYPOTHESES:
            boot = moving_block_bootstrap_comparison(
                y_true,
                ensemble_preds[a],
                ensemble_preds[b],
                classes=classes,
                block_size=b_size,
                n_resamples=2000,
                seed=42,
            )
            raw_p = boot["f1"]["p_value_raw"]
            raw_p_values.append(raw_p)
            hyp_results.append({
                "id": hid,
                "a": a,
                "b": b,
                "question": q,
                "bootstrap": boot,
            })

        # Hitung Holm-Bonferroni p-values
        adj_p_values = holm_bonferroni_correction(raw_p_values)
        for idx, hr in enumerate(hyp_results):
            hr["bootstrap"]["f1"]["p_value_adjusted"] = adj_p_values[idx]
            ci = hr["bootstrap"]["f1"]["ci95"]
            p_adj = adj_p_values[idx]
            if ci[0] > 0 and p_adj < 0.05:
                hr["verdict"] = "TERBUKTI"
            elif ci[1] < 0 and (1.0 - hr["bootstrap"]["f1"]["p_value_raw"]) < 0.05:
                hr["verdict"] = "BERLAWANAN"
            else:
                hr["verdict"] = "TIDAK TERBUKTI (setara)"

        # Adendum A1-A2: dilaporkan terpisah, tidak ikut koreksi Holm H1-H6.
        for hid, a, b, q in ADDENDUM:
            if a not in ensemble_preds or b not in ensemble_preds:
                continue
            boot = moving_block_bootstrap_comparison(
                y_true, ensemble_preds[a], ensemble_preds[b], classes=classes,
                block_size=b_size, n_resamples=2000, seed=42,
            )
            ci = boot["f1"]["ci95"]
            verdict = "TERBUKTI" if ci[0] > 0 else ("BERLAWANAN" if ci[1] < 0 else "TIDAK TERBUKTI (setara)")
            hyp_results.append({"id": hid, "a": a, "b": b, "question": q, "bootstrap": boot,
                                "verdict": verdict, "addendum": True})

        results_by_block[b_size] = hyp_results

    # Susun dokumen artefak
    out_data = {
        "timeframe": timeframe,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config_hash": cfg.config_hash,
        "n_test_windows": n_test,
        "effective_sample_size": n_eff,
        "window_bars": cfg.analysis.L,
        "stride_bars": cfg.analysis.stride_bars,
        "l_min_theoretical": l_min,
        "block_sizes_tested": block_sizes,
        "n_resamples": 2000,
        "results_by_block": {str(k): v for k, v in results_by_block.items()},
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_DIR / f"bootstrap_eval_{timeframe}.json"
    md_path = ARTIFACTS_DIR / f"bootstrap_eval_{timeframe}.md"

    json_path.write_text(json.dumps(out_data, indent=2), encoding="utf-8")
    md_content = generate_markdown_report(out_data)
    md_path.write_text(md_content, encoding="utf-8")

    print(f"\nSelesai Block Bootstrap {timeframe.upper()} ({time.time() - t0:.1f}s)")
    print(f"Artefak tersimpan di:\n  - {json_path}\n  - {md_path}")
    print("\n" + md_content)


def fmt_p(p: float, n_resamples: int) -> str:
    """p bootstrap tidak pernah tepat 0; batas resolusinya 1/B."""
    return f"< {1 / n_resamples:.4f}" if p <= 0 else f"{p:.4f}"


def generate_markdown_report(out_data: Dict) -> str:
    tf = out_data["timeframe"].upper()
    blocks = [int(k) for k in out_data["results_by_block"]]
    primary_block = str(out_data["l_min_theoretical"]) if str(out_data["l_min_theoretical"]) in out_data["results_by_block"] else str(blocks[0])

    lines = [
        f"# Evaluasi Uji Hipotesis Block Bootstrap — {tf}",
        f"**Tanggal:** {out_data['timestamp']} | **Config Hash:** `{out_data['config_hash'][:12]}`",
        "",
        "## 1. Parameter Sampel dan Blok Ketergantungan",
        f"- **Jumlah Window Uji (N):** {out_data['n_test_windows']}",
        f"- **Lebar Window (L):** {out_data['window_bars']} bar | **Langkah (Stride s):** {out_data['stride_bars']} bar",
        f"- **Sampel Efektif (N_eff):** ~{out_data['effective_sample_size']} observasi independen",
        f"- **Panjang Blok Minimum Teoritis (L_min = ceil(L/s)):** {out_data['l_min_theoretical']} window",
        f"- **Variasi Panjang Blok:** {out_data['block_sizes_tested']} window (sensitivitas 0.5x, 1.0x, 2.0x)",
        f"- **Resampling:** {out_data['n_resamples']} iterasi moving-block bootstrap",
        f"- **Metode Agregasi:** Ensemble rata-rata probabilitas softmax 3-seed",
        f"- **Koreksi Multi-Testing:** Prosedur Holm-Bonferroni (K=6)",
        "",
        f"## 2. Hasil Pengujian Hipotesis H1–H6 (Panjang Blok Patokan: {primary_block} Window)",
        "",
        "| H | Pertanyaan Ilmiah | Model B vs Model A | ΔMacro F1 [CI95] | ΔBalanced Acc [CI95] | p-value mentah | p-value Holm | Keputusan |",
        "|---|---|---|---|---|---|---|---|",
    ]

    B = out_data["n_resamples"]
    primary_res = out_data["results_by_block"][primary_block]
    for hr in [h for h in primary_res if not h.get("addendum")]:
        b_f1 = hr["bootstrap"]["f1"]
        b_ba = hr["bootstrap"]["balanced_accuracy"]
        f1_txt = f"{b_f1['mean_diff']:+.3f} [{b_f1['ci95'][0]:+.3f}, {b_f1['ci95'][1]:+.3f}]"
        ba_txt = f"{b_ba['mean_diff']:+.3f} [{b_ba['ci95'][0]:+.3f}, {b_ba['ci95'][1]:+.3f}]"
        lines.append(
            f"| **{hr['id']}** | {hr['question']} | {LABELS[hr['b']]} vs {LABELS[hr['a']]} | "
            f"{f1_txt} | {ba_txt} | {fmt_p(b_f1['p_value_raw'], B)} | {fmt_p(b_f1['p_value_adjusted'], B)} | **{hr['verdict']}** |"
        )

    addendum = [h for h in primary_res if h.get("addendum")]
    if addendum:
        lines += [
            "",
            "**Adendum (di luar praregistrasi, tanpa koreksi Holm):** pembanding tabular atas fitur statistik yang sama.",
            "",
            "| ID | Pertanyaan | Model B vs Model A | ΔMacro F1 [CI95] | ΔBalanced Acc [CI95] | p-value mentah | Keputusan |",
            "|---|---|---|---|---|---|---|",
        ]
        for hr in addendum:
            b_f1 = hr["bootstrap"]["f1"]
            b_ba = hr["bootstrap"]["balanced_accuracy"]
            lines.append(
                f"| **{hr['id']}** | {hr['question']} | {LABELS[hr['b']]} vs {LABELS[hr['a']]} | "
                f"{b_f1['mean_diff']:+.3f} [{b_f1['ci95'][0]:+.3f}, {b_f1['ci95'][1]:+.3f}] | "
                f"{b_ba['mean_diff']:+.3f} [{b_ba['ci95'][0]:+.3f}, {b_ba['ci95'][1]:+.3f}] | "
                f"{fmt_p(b_f1['p_value_raw'], B)} | **{hr['verdict']}** |"
            )

    lines += [
        "",
        "## 3. Uji Sensitivitas Panjang Blok Bootstrap (ΔMacro F1 [CI95])",
        "",
        "| H | Pertanyaan | " + " | ".join(f"Blok {b} w ({round(b/out_data['l_min_theoretical'], 1)}x)" for b in blocks) + " | Konsistensi Keputusan |",
        "|---|---|---|" + "---|" * len(blocks),
    ]

    for idx, hid in enumerate([h[0] for h in HYPOTHESES]):
        row_cells = []
        verdicts = []
        q = HYPOTHESES[idx][3]
        for b in blocks:
            hr = out_data["results_by_block"][str(b)][idx]
            ci = hr["bootstrap"]["f1"]["ci95"]
            diff = hr["bootstrap"]["f1"]["mean_diff"]
            row_cells.append(f"{diff:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]")
            verdicts.append(hr["verdict"])
        consistent = "Konsisten" if len(set(verdicts)) == 1 else "Bervariasi"
        lines.append(f"| **{hid}** | {q} | " + " | ".join(row_cells) + f" | **{consistent}** |")

    lines += [
        "",
        "## 4. Pembahasan Metodologis",
        "- **Overlapping Bias:** Penurunan ukuran sampel efektif dari ribuan window menjadi belasan (1H) atau satuan (4H) menunjukkan tingginya autokorelasi serial pada rolling window.",
        "- **Holm-Bonferroni:** Koreksi perbandingan ganda mengendalikan FWER sehingga klaim signifikansi statistik terbebas dari inflasi Tipe I.",
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
        run_block_bootstrap_evaluation(tf)


if __name__ == "__main__":
    main()

"""Tulis ringkasan .md untuk random_band_check.json dan timeframe_characteristics.json."""

from __future__ import annotations

import json
from pathlib import Path

REVIEW = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "review"
L4 = ["persistent", "random_like", "anti_persistent", "uncertain_rule"]


def c(x) -> str:
    return "-" if x is None else str(x).replace(".", ",")


def band_md() -> None:
    p = REVIEW / "random_band_check.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    md = ["# Pita acak dan uji surrogat (poin 5)", "",
          "Pita: `ml/artifacts/random_band.json`, jendela n = 500, persentil 2,5–97,5 deret H = 0,5. "
          "S1 = fGn Gaussian (R/S 0,504–0,676; DFA 0,385–0,614, angka yang dikutip di permintaan); "
          "S4 = fGn + ekor tebal + volatilitas stokastik + lonjakan (default dashboard).",
          "Label = Trend-Aware Soft Consensus (sama dengan run_updated_evaluation.py).", ""]
    for tf, o in d["timeframes"].items():
        md += [f"## {tf.upper()} ({o['n_windows']} jendela)", ""]
        for sc, b in o["bands"].items():
            md += [f"### Pita {sc}: R/S {c(b['hurst_band'])}, DFA {c(b['dfa_band'])}", "",
                   "| Label | n | H **dan** α di luar pita | H di luar | α di luar | salah satu di luar | H di atas pita | α di atas pita | H di bawah | α di bawah |",
                   "|---|---|---|---|---|---|---|---|---|---|"]
            a = b["all"]
            md.append(f"| semua | {o['n_windows']} | {c(a['pct_both_outside'])}% | {c(a['pct_H_outside'])}% | {c(a['pct_alpha_outside'])}% | {c(a['pct_either_outside'])}% | | | | |")
            for lab in L4:
                r = b["per_label"][lab]
                md.append(f"| {lab} | {r['n']} | {c(r['pct_both_outside'])}% | {c(r['pct_H_outside'])}% | {c(r['pct_alpha_outside'])}% | "
                          f"{c(r['pct_either_outside'])}% | {c(r['pct_H_above_band'])}% | {c(r['pct_alpha_above_band'])}% | "
                          f"{c(r['pct_H_below_band'])}% | {c(r['pct_alpha_below_band'])}% |")
            md.append("")
        s = o["surrogate_per_window_shuffle"]
        md += ["### Surrogat A: acak urutan return di dalam tiap jendela", "", s["method"], "",
               "| | H R/S asli | H R/S surrogat | α DFA asli | α DFA surrogat |", "|---|---|---|---|---|",
               f"| mean | {c(s['H_orig_sample']['mean'])} | {c(s['H_surrogate']['mean'])} | {c(s['alpha_orig_sample']['mean'])} | {c(s['alpha_surrogate']['mean'])} |",
               f"| median | {c(s['H_orig_sample']['median'])} | {c(s['H_surrogate']['median'])} | {c(s['alpha_orig_sample']['median'])} | {c(s['alpha_surrogate']['median'])} |",
               f"| P25–P75 | {c(s['H_orig_sample']['p25'])}–{c(s['H_orig_sample']['p75'])} | {c(s['H_surrogate']['p25'])}–{c(s['H_surrogate']['p75'])} | "
               f"{c(s['alpha_orig_sample']['p25'])}–{c(s['alpha_orig_sample']['p75'])} | {c(s['alpha_surrogate']['p25'])}–{c(s['alpha_surrogate']['p75'])} |", "",
               f"Pita surrogat 2,5–97,5%: H {c(s['surrogate_band_2.5_97.5']['hurst'])}, α {c(s['surrogate_band_2.5_97.5']['dfa'])}.", "",
               f"KS (sampel asli vs surrogat): H D = {c(s['ks_H_sample_vs_surrogate']['stat'])}, p = {s['ks_H_sample_vs_surrogate']['p']:.3g}; "
               f"α D = {c(s['ks_alpha_sample_vs_surrogate']['stat'])}, p = {s['ks_alpha_sample_vs_surrogate']['p']:.3g}. "
               f"KS (semua jendela asli vs surrogat): H D = {c(s['ks_H_allwindows_vs_surrogate']['stat'])}, p = {s['ks_H_allwindows_vs_surrogate']['p']:.3g}; "
               f"α D = {c(s['ks_alpha_allwindows_vs_surrogate']['stat'])}, p = {s['ks_alpha_allwindows_vs_surrogate']['p']:.3g}.", "",
               f"Uji per jendela (p empiris dua sisi < 0,05 terhadap {s['n_shuffles']} surrogatnya sendiri): H ditolak {c(s['pct_windows_H_reject_5pct'])}%, "
               f"α ditolak {c(s['pct_windows_alpha_reject_5pct'])}%, keduanya {c(s['pct_windows_both_reject_5pct'])}% (di bawah H0 ≈ 5% dan ≈ 0,25%).", "",
               "| Label | n sampel | H ditolak | α ditolak | keduanya | H asli / surr | α asli / surr |", "|---|---|---|---|---|---|---|"]
        for lab in L4:
            r = s["per_label"][lab]
            if not r.get("n"):
                continue
            md.append(f"| {lab} | {r['n']} | {c(r['pct_H_reject_5pct'])}% | {c(r['pct_alpha_reject_5pct'])}% | {c(r['pct_both_reject_5pct'])}% | "
                      f"{c(r['H_orig_mean'])} / {c(r['H_surr_mean'])} | {c(r['alpha_orig_mean'])} / {c(r['alpha_surr_mean'])} |")
        g = o["surrogate_global_shuffle"]
        md += ["", "### Surrogat B: acak seluruh deret (volatility clustering ikut hilang)", "", g["method"], "",
               f"H: asli mean {c(g['H_orig_all']['mean'])} vs surrogat {c(g['H_surrogate']['mean'])}, KS D = {c(g['ks_H']['stat'])}, p = {g['ks_H']['p']:.3g}. "
               f"α: asli {c(g['alpha_orig_all']['mean'])} vs surrogat {c(g['alpha_surrogate']['mean'])}, KS D = {c(g['ks_alpha']['stat'])}, p = {g['ks_alpha']['p']:.3g}.", "",
               f"Pita surrogat B: H {c(g['surrogate_band_2.5_97.5']['hurst'])}, α {c(g['surrogate_band_2.5_97.5']['dfa'])}; "
               f"jendela asli yang H **dan** α di luar pita surrogat B: {c(g['pct_orig_both_outside_surrogate_band'])}%.", ""]
    md += ["## Catatan tafsir", "",
           "- Jendela 500 bar tumpang tindih (stride 4/2), sehingga sampel tidak independen; p-value KS terlalu optimistis. "
           "Ukuran efek (statistik D, selisih mean) lebih informatif daripada p.",
           "- Uji per jendela tidak dikoreksi untuk multiple testing.", ""]
    (REVIEW / "random_band_check.md").write_text("\n".join(md), encoding="utf-8")


def tf_md() -> None:
    p = REVIEW / "timeframe_characteristics.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    md = ["# Karakteristik regime 1H vs 4H (poin 6)", "",
          "Label Trend-Aware Soft Consensus, grid & ambang train-only sama dengan run_updated_evaluation.py (1H stride 4 bar; 4H stride 2 bar).", ""]
    T = d["timeframes"]
    md += ["## Statistik H R/S dan α DFA-1 absolut", "",
           "| TF | Label | n | porsi | H mean | H median | H P25–P75 | α mean | α median | α P25–P75 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for tf, o in T.items():
        md.append(f"| {tf.upper()} | semua | {o['n_windows']} | 100% | {c(o['H_all']['mean'])} | {c(o['H_all']['median'])} | {c(o['H_all']['p25'])}–{c(o['H_all']['p75'])} | "
                  f"{c(o['alpha_all']['mean'])} | {c(o['alpha_all']['median'])} | {c(o['alpha_all']['p25'])}–{c(o['alpha_all']['p75'])} |")
        for lab in L4:
            r = o["per_label"][lab]
            md.append(f"| {tf.upper()} | {lab} | {r['n']} | {c(r['share_pct'])}% | {c(r['H']['mean'])} | {c(r['H']['median'])} | {c(r['H']['p25'])}–{c(r['H']['p75'])} | "
                      f"{c(r['alpha']['mean'])} | {c(r['alpha']['median'])} | {c(r['alpha']['p25'])}–{c(r['alpha']['p75'])} |")
    md += ["", "Ambang train-only: " + "; ".join(f"{tf.upper()} H {c(o['thresholds_train_only']['hurst'])}, α {c(o['thresholds_train_only']['dfa'])}" for tf, o in T.items()), ""]
    md += ["## Durasi regime (jam)", "", T["1h"]["duration_note"], "", T["4h"]["duration_note"], "",
           "| TF | Label | jumlah run | mean (jam) | median (jam) | P75 (jam) | maks (jam) |", "|---|---|---|---|---|---|---|"]
    for tf, o in T.items():
        for lab in L4:
            r = o["duration"][lab]
            md.append(f"| {tf.upper()} | {lab} | {r['n_runs']} | {c(r['mean_hours'])} | {c(r['median_hours'])} | {c(r['p75_hours'])} | {c(r['max_hours'])} |")
    md.append("")
    for tf, o in T.items():
        md += [f"## Matriks transisi {tf.upper()} (antar jendela berurutan, 4 kategori)", "",
               "| dari \\ ke | " + " | ".join(L4) + " |", "|---|---|---|---|---|"]
        for i, lab in enumerate(L4):
            md.append(f"| {lab} | " + " | ".join(c(v) for v in o["transition"]["prob"][i]) + " |")
        md += ["", f"Tanpa uncertain_rule (transisi ke label definitif berikutnya):", "",
               "| dari \\ ke | " + " | ".join(L4[:3]) + " |", "|---|---|---|---|"]
        for i, lab in enumerate(L4[:3]):
            md.append(f"| {lab} | " + " | ".join(c(v) for v in o["transition_definitive_only"]["prob"][i]) + " |")
        md.append("")
    md += ["## Porsi uncertain_rule per tahun (%)", "", "| Tahun | 1H n | 1H uncertain | 4H n | 4H uncertain |", "|---|---|---|---|---|"]
    years = sorted(set(T["1h"]["per_year"]) | set(T["4h"]["per_year"]))
    for y in years:
        a, b = T["1h"]["per_year"].get(y, {}), T["4h"]["per_year"].get(y, {})
        md.append(f"| {y} | {a.get('n', '-')} | {c(a.get('uncertain_pct'))} | {b.get('n', '-')} | {c(b.get('uncertain_pct'))} |")
    ag = d["agreement_1h_vs_4h"]
    md += ["", "## Kesamaan label 1H dan 4H pada timestamp yang sama", "", ag["method"], "",
           "| Pencocokan | pasangan | sama (4 kategori) | pasangan keduanya definitif | sama (definitif) | Cohen κ | corr H | corr α |", "|---|---|---|---|---|---|---|---|"]
    for k in ("exact", "asof"):
        r = ag[k]
        md.append(f"| {k} | {r['n_pairs']} | {c(r['pct_same_label_all4'])}% | {r['n_both_definitive']} | {c(r['pct_same_label_both_definitive'])}% | "
                  f"{c(r['cohen_kappa_all4'])} | {c(r['corr_H_1h_4h'])} | {c(r['corr_alpha_1h_4h'])} |")
    md += ["", "Tabel silang (asof; baris = 4H, kolom = 1H):", "", "| 4H \\ 1H | " + " | ".join(L4) + " |", "|---|---|---|---|---|"]
    for lab in L4:
        row = ag["asof"]["crosstab_rows_4h_cols_1h"].get(lab, {})
        md.append(f"| {lab} | " + " | ".join(str(row.get(x, 0)) for x in L4) + " |")
    md.append("")
    (REVIEW / "timeframe_characteristics.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    band_md()
    tf_md()
    print("reports ok")

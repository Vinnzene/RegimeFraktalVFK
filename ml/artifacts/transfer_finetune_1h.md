# Fase 0b: pralatih sintetis + fine-tune — 1H

Praregistrasi: `docs/praregistrasi_fase0b_transfer.md`. Skrip: `ml/src/transfer_finetune_study.py`.
Split identik Fase 0: {'train': 5951, 'validation': 1211, 'test': 1610}.

## Kinerja (rata-rata ± std 3 seed)

| Model | BA latih | BA validasi | BA uji | Macro-F1 uji | Recall random-like | Selisih latih − uji |
|---|---|---|---|---|---|---|
| Hybrid PS dari nol | 0.759 ± 0.032 | 0.572 | 0.711 ± 0.013 | 0.697 | 0.506 | 0.048 |
| Hybrid PS pralatih sintetis + fine-tune | 0.712 ± 0.040 | 0.554 | 0.633 ± 0.032 | 0.630 | 0.325 | 0.079 |
| T1 + label smoothing 0,1 | 0.777 ± 0.009 | 0.572 | 0.651 ± 0.003 | 0.644 | 0.404 | 0.126 |
| Detektor sintetis tanpa fine-tune | – | – | 0.372 | 0.166 | – | – |

Overfitting berkurang (selisih T1 < B0 pada ketiga seed): **tidak**

Referensi Fase 0 (BA uji, masukan dan scaler Fase 0): logreg 0.665, structural_mlp 0.632, hybrid_ps 0.698

## Hipotesis (ensemble 3 seed, bootstrap blok 125, Holm atas 4 uji 1H+4H)

| ID | B vs A | ΔMacro-F1 [CI95] | ΔBA [CI95] | p mentah | p Holm | Keputusan |
|---|---|---|---|---|---|---|
| T-H1 | T1 vs B0 | -0.074 [-0.121, -0.032] | -0.081 [-0.128, -0.040] | 1.0000 | 1.0 | **BERLAWANAN** |
| T-H2 | T2 vs T1 | +0.019 [-0.017, +0.061] | +0.024 [-0.015, +0.071] | 0.1565 | 0.626 | **TIDAK TERBUKTI** |

## Walk-forward 5 fold (sekunder)

| Model | Fold 1 | Fold 2 | Fold 3 | Fold 4 | Fold 5 | Rata-rata ± std |
|---|---|---|---|---|---|---|
| Hybrid PS dari nol | 0.384 | 0.566 | 0.517 | 0.614 | 0.687 | 0.554 ± 0.102 |
| Hybrid PS pralatih sintetis + fine-tune | 0.317 | 0.491 | 0.558 | 0.605 | 0.645 | 0.523 ± 0.115 |

T1 > B0 pada 1/5 fold; stabil lebih baik (≥ 3/5): **tidak**

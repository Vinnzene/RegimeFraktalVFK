# Fase 0b: pralatih sintetis + fine-tune — 4H

Praregistrasi: `docs/praregistrasi_fase0b_transfer.md`. Skrip: `ml/src/transfer_finetune_study.py`.
Split identik Fase 0: {'train': 1446, 'validation': 354, 'test': 261}.

## Kinerja (rata-rata ± std 3 seed)

| Model | BA latih | BA validasi | BA uji | Macro-F1 uji | Recall random-like | Selisih latih − uji |
|---|---|---|---|---|---|---|
| Hybrid PS dari nol | 0.811 ± 0.008 | 0.622 | 0.607 ± 0.015 | 0.603 | 0.402 | 0.204 |
| Hybrid PS pralatih sintetis + fine-tune | 0.735 ± 0.007 | 0.565 | 0.541 ± 0.002 | 0.542 | 0.325 | 0.193 |
| T1 + label smoothing 0,1 | 0.755 ± 0.013 | 0.566 | 0.510 ± 0.011 | 0.514 | 0.197 | 0.245 |
| Detektor sintetis tanpa fine-tune | – | – | 0.343 | 0.151 | – | – |

Overfitting berkurang (selisih T1 < B0 pada ketiga seed): **ya**

Referensi Fase 0 (BA uji, masukan dan scaler Fase 0): logreg 0.524, structural_mlp 0.574, hybrid_ps 0.593

## Hipotesis (ensemble 3 seed, bootstrap blok 125, Holm atas 4 uji 1H+4H)

| ID | B vs A | ΔMacro-F1 [CI95] | ΔBA [CI95] | p mentah | p Holm | Keputusan |
|---|---|---|---|---|---|---|
| T-H1 | T1 vs B0 | -0.048 [-0.274, +0.098] | -0.066 [-0.299, +0.072] | 0.5710 | 1.0 | **TIDAK TERBUKTI** |
| T-H2 | T2 vs T1 | -0.009 [-0.030, +0.010] | -0.013 [-0.046, +0.016] | 0.8390 | 1.0 | **TIDAK TERBUKTI** |

## Walk-forward 5 fold (sekunder)

| Model | Fold 1 | Fold 2 | Fold 3 | Fold 4 | Fold 5 | Rata-rata ± std |
|---|---|---|---|---|---|---|
| Hybrid PS dari nol | 0.344 | 0.470 | 0.304 | 0.506 | 0.611 | 0.447 ± 0.111 |
| Hybrid PS pralatih sintetis + fine-tune | 0.405 | 0.316 | 0.487 | 0.420 | 0.577 | 0.441 ± 0.087 |

T1 > B0 pada 2/5 fold; stabil lebih baik (≥ 3/5): **tidak**

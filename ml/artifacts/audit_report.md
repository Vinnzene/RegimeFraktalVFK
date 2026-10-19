# Audit artefak (24 berkas)

config.yaml sekarang: `7a3bddc67d72`  (L=500, J=4, stride=4, threshold=quantile, h=500, split=[0.7, 0.15, 0.15])

| file | task | h_bars | hash_match | n_test | seeds | acc | ba | macro_f1 | mcc | baseline | status | alasan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| horizon_study_1h.json | forecasting | - | ya | - | 1 | - | - | - | - | tidak | ULANG | tugas FORECASTING (h=None), bukan identifikasi |
| hybrid_attention_bilstm_binary_1h.json | identification | 0 | ya | 1324 | 1 | 0.856 | 0.842 | - | 0.709 | tidak | SAH (perlu dilengkapi) | 1 seed saja; tanpa baseline mayoritas |
| hybrid_attention_bilstm_binary_4h.json | identification | 0 | ya | 207 | 1 | 0.797 | 0.770 | - | 0.551 | tidak | SAH (perlu dilengkapi) | 1 seed saja; tanpa baseline mayoritas |
| hybrid_attention_bilstm_multiclass_1h.json | identification | 0 | ya | 1586 | 1 | 0.690 | 0.622 | - | 0.519 | tidak | SAH (perlu dilengkapi) | 1 seed saja; tanpa baseline mayoritas |
| hybrid_attention_bilstm_multiclass_4h.json | identification | 0 | ya | 248 | 1 | 0.645 | 0.590 | - | 0.438 | tidak | SAH (perlu dilengkapi) | 1 seed saja; tanpa baseline mayoritas |
| jump_penalty_tuning_1h.json | identification | 0 | ya | - | 1 | - | - | - | - | tidak | SAH (perlu dilengkapi) | 1 seed saja; tanpa baseline mayoritas |
| orderflow_ablation_1h.json | identification | 0 | ya | 1616 | 3 | 0.454 | 0.393 | 0.365 | 0.110 | tidak | SAH (perlu dilengkapi) | tanpa baseline mayoritas |
| orderflow_ablation_4h.json | identification | 0 | ya | 254 | 3 | 0.457 | 0.416 | 0.376 | 0.195 | tidak | SAH (perlu dilengkapi) | tanpa baseline mayoritas |
| orderflow_analysis_1h.json | identification | 0 | - | - | 1 | - | - | - | - | tidak | SAH | - |
| orderflow_analysis_4h.json | identification | 0 | - | - | 1 | - | - | - | - | tidak | SAH | - |
| structural_mlp_binary_1h.json | identification | 0 | ya | 1324 | 1 | 0.897 | 0.900 | - | 0.794 | tidak | SAH (perlu dilengkapi) | 1 seed saja; tanpa baseline mayoritas |
| structural_mlp_binary_4h.json | identification | 0 | ya | 207 | 1 | 0.778 | 0.764 | - | 0.522 | tidak | SAH (perlu dilengkapi) | 1 seed saja; tanpa baseline mayoritas |
| structural_mlp_multiclass_1h.json | identification | 0 | ya | 1586 | 1 | 0.661 | 0.612 | - | 0.483 | tidak | SAH (perlu dilengkapi) | 1 seed saja; tanpa baseline mayoritas |
| structural_mlp_multiclass_4h.json | identification | 0 | ya | 248 | 1 | 0.569 | 0.544 | - | 0.368 | tidak | SAH (perlu dilengkapi) | 1 seed saja; tanpa baseline mayoritas |
| swt_attention_bilstm_1h.json | forecasting | 500 | ya | 1481 | 1 | 0.328 | 0.357 | - | 0.032 | ya | ULANG | tugas FORECASTING (h=500), bukan identifikasi |
| swt_attention_bilstm_4h.json | forecasting | 500 | ya | 169 | 1 | 0.391 | 0.378 | - | 0.064 | ya | ULANG | tugas FORECASTING (h=500), bukan identifikasi |
| swt_bilstm_1h.json | forecasting | 500 | ya | 1481 | 1 | 0.319 | 0.352 | - | 0.016 | ya | ULANG | tugas FORECASTING (h=500), bukan identifikasi |
| swt_bilstm_4h.json | forecasting | 500 | ya | 169 | 1 | 0.308 | 0.320 | - | -0.007 | ya | ULANG | tugas FORECASTING (h=500), bukan identifikasi |
| walk_forward_1h_binary_jump.json | identification | 0 | ya | - | 1 | 0.810 | 0.805 | 0.805 | - | tidak | SAH (perlu dilengkapi) | tanpa baseline mayoritas |
| walk_forward_1h_binary_threshold.json | identification | 0 | ya | - | 1 | 0.820 | 0.816 | 0.818 | - | tidak | SAH (perlu dilengkapi) | tanpa baseline mayoritas |
| walk_forward_1h_multiclass_jump.json | identification | 0 | ya | - | 1 | 0.530 | 0.454 | 0.455 | - | tidak | SAH (perlu dilengkapi) | tanpa baseline mayoritas |
| walk_forward_1h_multiclass_threshold.json | identification | 0 | ya | - | 1 | 0.605 | 0.559 | 0.546 | - | tidak | SAH (perlu dilengkapi) | tanpa baseline mayoritas |
| walk_forward_4h_binary_jump.json | identification | 0 | ya | - | 1 | - | - | - | - | tidak | SAH (perlu dilengkapi) | tanpa baseline mayoritas |
| walk_forward_4h_multiclass_threshold.json | identification | 0 | ya | - | 1 | 0.492 | 0.475 | 0.477 | - | tidak | SAH (perlu dilengkapi) | tanpa baseline mayoritas |

Walk-forward (expanding): sebaran balanced accuracy per fold

- walk_forward_1h_binary_jump.json: 5 fold, BA 0.63-0.89
- walk_forward_1h_binary_threshold.json: 5 fold, BA 0.60-0.88
- walk_forward_1h_multiclass_jump.json: 5 fold, BA 0.40-0.50
- walk_forward_1h_multiclass_threshold.json: 5 fold, BA 0.42-0.62
- walk_forward_4h_multiclass_threshold.json: 3 fold, BA 0.43-0.49

# Ablasi fitur energi SWT pada detektor resmi

Praregistrasi: `docs/praregistrasi_fase1_sintetis.md` adendum 4. Skrip: `ml/src/swt_ablation.py`.

## Balanced accuracy uji (rata-rata ± simpangan baku 3 seed)

| Varian | S1 | S2 | S3 | S4 | S4k |
|---|---|---|---|---|---|
| Detektor resmi (50 fitur) | 0.861 ± 0.001 | 0.847 ± 0.002 | 0.822 ± 0.001 | 0.815 ± 0.001 | 0.834 ± 0.003 |
| Tanpa energi SWT (38 fitur) | 0.861 ± 0.002 | 0.846 ± 0.003 | 0.820 ± 0.002 | 0.812 ± 0.002 | 0.834 ± 0.003 |

## Hipotesis S-SWT (set uji S4, probabilitas rata-rata 3 seed)

| ΔBA (A0 − A1) | CI95 | Keputusan |
|---|---|---|
| -0.0003 | [-0.0053, +0.0049] | **Kontribusi fitur SWT tidak terdeteksi** |

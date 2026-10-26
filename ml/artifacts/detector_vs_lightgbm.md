# Uji formal detektor resmi vs LightGBM (Fase 1 adendum 6)

Analisis tambahan setelah benchmark dibaca; ditulis dan di-commit sebelum dijalankan.
Data uji sintetis n = 500, deret independen, ambang 0,47/0,53. Utama: S4.

| Skenario | BA detektor | BA LightGBM | ΔBA [CI95] | p bootstrap (1 sisi) | Hanya detektor benar | Hanya LightGBM benar | p McNemar |
|---|---|---|---|---|---|---|---|
| S4 (utama) | 0,813 | 0,805 | +0,008 [-0,004; +0,019] | 0,0995 | 167 | 144 | 0,2121 |
| S1 | 0,863 | 0,864 | -0,001 [-0,008; +0,006] | 0,6125 | 53 | 56 | 0,8482 |
| S4k | 0,836 | 0,812 | +0,024 [+0,014; +0,034] | 0,0000 | 163 | 91 | 0,0000 |

**Keputusan:** SETARA: selisih tidak melampaui variasi sampling.

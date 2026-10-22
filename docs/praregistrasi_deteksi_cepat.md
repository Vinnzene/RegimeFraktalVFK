# Praregistrasi: mempercepat deteksi pergantian regime

Status: **dikunci 2026-10-22** (commit "Praregistrasi deteksi cepat (dikunci)").
Perubahan hanya lewat adendum bertanggal di bagian bawah.

## 1. Pertanyaan

Detektor resmi (D0) mengenali pergantian regime dengan median keterlambatan
296 bar (±12 hari di 1H), hampir seluruhnya karena jendela 500 bar
(`ml/artifacts/regime_change_study.md`). Diuji dua cara memangkasnya:

1. **Latih pergantian**: model dilatih juga pada jendela yang regime-nya
   berganti di dalam jendela, berlabel regime **terbaru**, sehingga belajar
   menimbang bagian akhir jendela.
2. **Jendela pendek**: 256 bar sebagai pengganti 500.

**Yang sudah diketahui:** D0 gagal pada S5 (BA ±0,28); jendela 256 tanpa latih
pergantian memberi BA S4 0,732 pada benchmark Fase 1 (model LightGBM); hasil
uji pergantian regime D0 dan konsensus Hurst-DFA; studi multi-skala. Belum ada
model yang dilatih pada data berganti regime.

## 2. Model

Arsitektur Hybrid PS (Attention-BiLSTM), konfigurasi latih sama dengan detektor
resmi (Adam 1e-3, batch 64, maks. 80 epoch, early stopping patience 12,
ReduceLROnPlateau, bobot kelas), seed 42, 43, 44. Normalisasi per jendela ke
σ = 0,0066.

| Kode | Jendela | Data latih |
|---|---|---|
| **D0** | 500 | Detektor resmi, tidak dilatih ulang |
| **A** | 500 | Stasioner S1–S4 + berganti regime |
| **B0** | 256 (sub-jendela PS 70) | Stasioner S1–S4 saja |
| **B** | 256 (sub-jendela PS 70) | Stasioner S1–S4 + berganti regime |

B0 memisahkan efek jendela pendek dari efek latih pergantian.

## 3. Data

- **Stasioner:** `make_series` S1–S4 dengan satu H, 6.000 deret latih dan
  1.500 validasi per skenario.
- **Berganti regime:** `make_series("S5")` (proses S4, H berganti satu kali di
  posisi acak 40–90% panjang jendela, kelas sebelum ≠ sesudah), label = kelas
  segmen **terakhir**. 12.000 latih dan 3.000 validasi.
- Seed `SeedSequence([9300 + split, skenario, idx])`, deret yang sama dibangkitkan
  untuk panjang 500 dan 256 secara terpisah (panjang berbeda = deret berbeda).
- **Uji ketepatan:** 3.000 deret S4 dan 3.000 deret S5 per panjang jendela.

## 4. Uji kecepatan

40 deret panjang yang sama dengan adendum 5 Fase 1 (`regime_change_study.py`,
seed `SeedSequence([8000, i])`, 20.000 bar, 8–12 titik ganti). Titik deteksi
sama untuk semua model (setiap 4 bar mulai bar 499); jendela 256 berakhir di
titik yang sama. Konfirmasi K = 3. Metrik: median keterlambatan, salah alarm
per 1.000 bar, proporsi terlewat. Probabilitas rata-rata 3 seed per model.

## 5. Hipotesis

Bootstrap per deret panjang (B = 2.000), koreksi Holm atas 2 uji.

| ID | Pernyataan | Kriteria |
|---|---|---|
| CEPAT-H1 | Latih pergantian mempercepat deteksi | Batas atas CI95 selisih median keterlambatan (A − D0) < 0 |
| CEPAT-H2 | Jendela pendek + latih pergantian mempercepat deteksi | Batas atas CI95 (B − D0) < 0 |

p satu sisi = proporsi bootstrap dengan selisih ≥ 0.

**Deskriptif:** BA S4 dan S5 (rata-rata ± std 3 seed) semua model; selisih
B0 vs B; bobot attention rata-rata pada 8 langkah terakhir (dari 32) untuk
model A dan D0 pada uji S5.

## 6. Keputusan untuk sistem (ditetapkan sekarang)

Sebuah model (A atau B) **direkomendasikan** sebagai detektor sistem bila
semua syarat ini terpenuhi:

1. hipotesis kecepatannya terbukti;
2. BA S4 ≥ BA S4 D0 − 0,03 (ketepatan pada kondisi stabil tidak turun berarti);
3. salah alarm per 1.000 bar ≤ 1,5 × D0;
4. proporsi terlewat ≤ D0 + 5 poin persen.

Bila keduanya memenuhi, dipilih yang median keterlambatannya lebih kecil.
Penggantian detektor di sistem dilakukan sebagai langkah terpisah setelah
hasil dilaporkan, dengan ambang abstain dipilih ulang di validasi memakai aturan
adendum 5 Fase 1.

| Hasil | Kesimpulan yang ditulis |
|---|---|
| H1 terbukti | Melatih model pada pergantian regime mempercepat deteksi tanpa memperpendek jendela |
| H2 terbukti, H1 tidak | Percepatan berasal dari jendela pendek |
| Keduanya tidak terbukti | Keterlambatan ±300 bar adalah batas wajar metode ini pada jendela 500 |

## 7. Yang tidak dilakukan

- Tidak ada penyetelan jendela, proporsi data berganti, atau arsitektur setelah hasil terlihat.
- Tidak ada pelatihan atau evaluasi pada data BTC.

## 8. Keluaran

- `ml/src/fast_detection_study.py`
- `ml/artifacts/fast_detection_study.{json,md}`

## Adendum

(belum ada)

# Praregistrasi Fase 0b: pralatih sintetis + fine-tune label BTC

Status: **dikunci 2026-10-22** (commit "Praregistrasi Fase 0b (dikunci)").
Perubahan hanya lewat adendum bertanggal di bagian bawah.

## 1. Latar dan pertanyaan

Fase 0 (label konsensus Hurst R/S–DFA pada BTC, protokol `train_only`)
menunjukkan:

- overfitting jelas di 4H (BA latih ±0,82 vs uji ±0,59) dan ringan di 1H
  (±0,74 vs ±0,68);
- recall kelas random-like rendah (±0,45);
- Hybrid PS tidak terbukti lebih baik daripada MLP (H5, p Holm 0,0575) dan
  setara dengan regresi logistik.

Literatur menyarankan dua perbaikan untuk data kecil dan label berderau:
pralatih pada data sumber lalu fine-tune (Ismail Fawaz dkk., 2018; Da Silva &
Shi, 2019), dan label smoothing (Müller dkk., 2019; Song dkk., 2023).

**Pertanyaan:** apakah model Hybrid PS yang **dipralatih pada data sintetis
berkebenaran dasar** (detektor resmi Fase 1) lalu di-fine-tune pada label BTC
lebih akurat dan kurang overfitting daripada Hybrid PS yang dilatih dari nol
pada label BTC yang sama?

**Yang sudah diketahui saat dokumen ini ditulis:** seluruh hasil Fase 0
(termasuk data uji), hasil Fase 1, uji generalisasi, Fase 2, dan ablasi SWT.
Belum ada model yang dipralatih sintetis lalu di-fine-tune pada BTC. Karena
data uji Fase 0 sudah pernah dilihat, **semua konfigurasi ditetapkan di dokumen
ini tanpa penyetelan**, dan data uji dipakai satu kali di akhir.

## 2. Data dan split (identik dengan Fase 0)

- BTC/USDT 1H dan 4H, tabel regime yang sama, label konsensus R/S–DFA dengan
  ambang `train_only`, kelas `uncertain_rule` dibuang.
- Data dipotong pada jumlah jendela yang mereproduksi split Fase 0: **1H =
  16.952 jendela pertama, 4H = 4.129 jendela pertama**. Ukuran split yang wajib
  sama (diperiksa dengan `assert` di skrip):

  | TF | Latih | Validasi | Uji |
  |---|---|---|---|
  | 1H | 5.951 | 1.211 | 1.610 |
  | 4H | 1.446 | 354 | 261 |

- Split kronologis 70/15/15, purge 125 jendela, sama dengan `leakage_study.make_split`.

## 3. Masukan

Agar bobot pralatih bermakna, masukan BTC dibentuk persis seperti masukan
detektor resmi (`backend/app/services/ai_detector.py`):

- return tiap jendela 500 bar diskalakan ke simpangan baku 0,0066 sebelum fitur
  dihitung;
- 50 fitur struktural + sekuens PS 32 × 11;
- standarisasi memakai **statistik detektor sintetis** (`detector_meta.json`:
  `feature_mean`, `feature_std`, `ps_scaler`), tidak dihitung ulang dari BTC.

Kedua model utama (B0 dan T1) memakai masukan yang sama, sehingga satu-satunya
perbedaan adalah inisialisasi bobot.

## 4. Model

| Kode | Inisialisasi | Lainnya |
|---|---|---|
| **B0** | Acak (dari nol) | Arsitektur Hybrid PS Fase 0, Adam lr 1e-3 |
| **T1** | Bobot detektor resmi `ml/artifacts/detector/hybrid_ps_sintetis.keras` | Semua lapisan dilatih, Adam lr **1e-4** |
| **T2** | Sama dengan T1 | T1 + label smoothing **0,1** |
| T0 (deskriptif) | Detektor resmi tanpa fine-tune | Tidak dilatih |

- Lapisan keluaran T1/T2 dipertahankan; kolomnya diurutkan ulang menurut nama
  kelas ke urutan kelas BTC. (Makna kelas berbeda: sintetis memakai H
  0,47/0,53, label BTC memakai kuantil R/S–DFA, sehingga fine-tune diperlukan.)
- Semua model: batch 64, maksimum 80 epoch, early stopping `val_loss`
  patience 12 dengan pemulihan bobot terbaik, ReduceLROnPlateau (faktor 0,5,
  patience 6, min 1e-5), bobot kelas berbanding terbalik frekuensi, seed 42,
  43, 44.
- Nilai lr 1e-4 dan label smoothing 0,1 ditetapkan sekarang (nilai lazim untuk
  fine-tune dan label smoothing) dan **tidak disetel**.

## 5. Metrik dan hipotesis

Metrik utama: Macro-F1 dan balanced accuracy (BA) pada data uji. Uji
berpasangan: ensemble probabilitas rata-rata 3 seed, moving-block bootstrap
blok 125 jendela, B = 2.000, satu sisi, sama dengan `block_bootstrap_eval.py`.

| ID | Pernyataan | Pembanding | TF |
|---|---|---|---|
| **T-H1 (utama)** | Pralatih sintetis meningkatkan akurasi | ΔMacro-F1 (T1 − B0) > 0 | 1H, 4H |
| T-H2 | Label smoothing menambah nilai di atas pralatih | ΔMacro-F1 (T2 − T1) > 0 | 1H, 4H |

Koreksi Holm atas 4 uji (T-H1 dan T-H2 × 1H dan 4H). Terbukti bila p Holm < 0,05
dan batas bawah CI95 > 0.

**Overfitting (deskriptif, kriteria ditetapkan sekarang):**
selisih = BA latih − BA uji, rata-rata 3 seed. "Overfitting berkurang" bila
selisih T1 lebih kecil daripada B0 pada **ketiga** seed.

**Recall random-like:** dilaporkan per model (deskriptif).

**Pembanding sederhana:** BA uji regresi logistik dan MLP Fase 0
(`ps_study_*.json`) dilaporkan berdampingan tanpa uji tambahan.

**Walk-forward (sekunder):** B0 dan T1 dievaluasi pada 5 fold expanding yang
sama dengan `walk_forward_neural.py` (1H dan 4H). Dilaporkan BA rata-rata ± std
dan jumlah fold T1 > B0; "stabil lebih baik" bila T1 > B0 pada ≥ 3 dari 5 fold.

## 6. Tafsir hasil (ditetapkan sekarang)

| Hasil | Kesimpulan yang ditulis |
|---|---|
| T-H1 terbukti | Pralatih pada data sintetis berkebenaran dasar meningkatkan identifikasi regime pada label BTC |
| T-H1 tidak terbukti, overfitting berkurang | Pralatih menstabilkan pelatihan tetapi tidak menaikkan akurasi; batas akurasi berasal dari derau label Hurst-DFA |
| T-H1 tidak terbukti, overfitting tidak berkurang | Pralatih sintetis tidak membantu pada label BTC; dilaporkan sebagai hasil negatif |
| T1 lebih buruk (batas atas CI95 < 0) | Pengetahuan dari data sintetis tidak berpindah ke definisi label Hurst-DFA BTC (*negative transfer*, Ismail Fawaz dkk., 2018) |

## 7. Yang tidak dilakukan

- Tidak ada penyetelan lr, label smoothing, arsitektur, atau epoch setelah hasil terlihat.
- Detektor resmi sistem (dashboard) **tidak diganti** apa pun hasilnya. Model
  Fase 0b mempelajari label Hurst-DFA BTC, sedangkan detektor sistem mempelajari
  kebenaran dasar H.
- Hasil Fase 0 tidak diubah; Fase 0b dilaporkan sebagai eksperimen tambahan.

## 8. Keluaran

- `ml/src/transfer_finetune_study.py`
- `ml/artifacts/transfer_finetune_{1h,4h}.{json,md}`

## 9. Rujukan

- Ismail Fawaz, H., Forestier, G., Weber, J., Idoumghar, L., & Muller, P.-A. (2018). Transfer learning for time series classification. *IEEE International Conference on Big Data*.
- Da Silva, B., & Shi, S. S. (2019). Style transfer with time series: Generating synthetic financial data. arXiv:1906.03232.
- Müller, R., Kornblith, S., & Hinton, G. (2019). When does label smoothing help? *NeurIPS 2019*.
- Song, H., Kim, M., Park, D., Shin, Y., & Lee, J.-G. (2023). Learning from noisy labels with deep neural networks: A survey. *IEEE TNNLS*, 34(11), 8135–8153.
- Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2017). The probability of backtest overfitting. *Journal of Computational Finance*, 20(4).

## Adendum

(belum ada)

# Praregistrasi Fase 2: Pemilihan strategi berbasis regime lintas aset

Status: **dikunci 2026-10-20** (commit "Praregistrasi Fase 2 (dikunci)").
Perubahan hanya lewat adendum bertanggal di bagian bawah.

Menjawab RM4 (`rencana_pengembangan.md`): apakah memilih strategi berdasarkan
regime memberi kinerja bersih lebih baik daripada memakai satu strategi terus,
di 20 aset?

Saat dokumen ini ditulis, kinerja strategi apa pun pada data aset nyata belum
dihitung. Yang sudah diketahui dari aset nyata hanya hasil uji generalisasi
(validitas ke depan) dan proporsi label detektor per aset.

## 1. Aset, data, dan titik keputusan

- Aset dan timeframe: sama dengan praregistrasi generalisasi §2 (7 kripto 1H,
  PAXGUSDT 1H, GC=F 1D, IHSG + 10 saham IDX 1D).
- Label regime diambil dari titik deteksi uji generalisasi
  (`ml/artifacts/generalization_cache/`): setiap 4 bar, window 500 bar,
  normalisasi per window. Label pada titik t berlaku untuk bar t+1 … t+4
  (sampai titik deteksi berikutnya). Bar setelah titik deteksi terakhir tidak
  dievaluasi.
- Tidak ada parameter yang disetel pada data aset nyata: detektor dilatih
  sintetis, aturan strategi dan biaya ditetapkan di dokumen ini. Karena itu
  seluruh periode bersifat luar sampel; tidak diperlukan walk-forward. Untuk
  D-BTC pada BTC, hanya periode setelah batas latih BTC yang dipakai.

## 2. Strategi (parameter tetap, sama dengan `regime_strategy_demo.py`)

Posisi diputuskan pada penutupan bar t dan berlaku untuk return bar t+1.

| Kode | Aturan |
|---|---|
| MOM | Momentum: posisi = tanda return 24 bar terakhir |
| MR | Mean-reversion: z = (log harga − rata-rata 24 bar) / simpangan baku 24 bar; masuk −tanda(z) bila \|z\| > 1, keluar saat z melewati 0 |
| SW(D) | Switching dengan detektor D: persistent → MOM; anti-persistent → MR; random-like atau tidak pasti → tidak memegang posisi |
| BH | Beli dan tahan |
| FLAT | Tidak pernah memegang posisi (return 0) |

Detektor untuk SW: D-sintetis (utama), D-klasik, D-konsensus, D-BTC (definisi
sama dengan uji generalisasi).

**Arah posisi dan biaya per kelompok:**

| Kelompok | Arah | Biaya per sisi (fee + slippage) | Bar per tahun |
|---|---|---|---|
| Kripto, PAXGUSDT | Long dan short (setara kontrak perpetual) | 0,085% | 8.760 |
| GC=F | Long dan short (kontrak berjangka) | 0,03% | 252 |
| Saham IDX, IHSG | **Long saja** (posisi short menjadi tanpa posisi) | 0,25% | 242 |

Biaya dikenakan pada setiap perubahan posisi sebesar |Δposisi| × biaya per
sisi. IHSG diperlakukan seperti reksa dana indeks (long saja, biaya sama).

## 3. Metrik

Return bersih per bar → total return, Sharpe tahunan (rata-rata/simpangan baku
× √bar per tahun), drawdown maksimum, persentase waktu memegang posisi, dan
perputaran (turnover).

## 4. Hipotesis

Uji per aset dengan bootstrap blok sirkular berpasangan atas return bersih per
bar (blok 168 bar untuk 1H, 20 bar untuk 1D; B = 2.000). "Lebih baik" = batas
bawah CI95 selisih Sharpe > 0; "lebih buruk" = batas atas < 0.

| ID | Pernyataan | Pembanding |
|---|---|---|
| F1 (utama) | SW(D-sintetis) lebih baik daripada strategi tunggal terbaik | max(Sharpe MOM, Sharpe MR) pada aset yang sama, dipilih per aset sesudah melihat hasil (pembanding sengaja dibuat kuat) |
| F2 | SW(D-sintetis) lebih baik daripada beli-dan-tahan | BH |
| F3 | Detektor AI lebih berguna daripada estimator klasik | SW(D-klasik) |
| F4 | Detektor AI lebih berguna daripada label Bab 4 | SW(D-konsensus) |
| F5 | Detektor latih-sintetis lebih berguna daripada latih-BTC | SW(D-BTC) |

Kriteria kelompok (kripto; emas; saham IDX): suatu hipotesis dinyatakan
**berlaku untuk kelompok** bila "lebih baik" pada ≥ 2/3 aset kelompok itu dan
"lebih buruk" pada 0 aset. Jumlah aset lebih baik dan lebih buruk dilaporkan
untuk setiap hipotesis. Tidak ada koreksi berganda antar aset; kesimpulan
kelompok memakai aturan ≥ 2/3 di atas.

### Tafsir hasil (ditetapkan sekarang)

| Hasil | Kesimpulan yang ditulis |
|---|---|
| F1 berlaku | Memilih strategi berdasarkan regime lebih baik daripada strategi tunggal terbaik pada kelompok tersebut |
| F1 tidak berlaku, tetapi SW tidak lebih buruk dan drawdown lebih kecil | Pemilihan strategi berbasis regime tidak menambah Sharpe, tetapi mengurangi risiko; nilai praktisnya sebagai filter "jangan trading" |
| SW lebih buruk | Pemilihan strategi berbasis regime tidak berguna pada kelompok tersebut setelah biaya |

## 5. Analisis eksploratif (tidak dipakai untuk klaim utama)

- **E1**: VR maju setelah label anti-persistent dibanding setelah label
  random-like (uji generalisasi hanya membandingkan persistent vs
  anti-persistent, dan kelas persistent nyaris kosong pada kripto 1H). Analisis
  ini dirancang setelah melihat hasil uji generalisasi, sehingga hanya
  dilaporkan sebagai eksploratif.
- **E2**: kinerja MOM dan MR **di dalam** periode berlabel random-like, untuk
  mengukur kerugian yang dihindari oleh aturan "tidak trading".

## 6. Yang tidak dilakukan

- Tidak ada penyetelan lookback, ambang z, atau biaya setelah hasil terlihat.
- Tidak ada penghapusan aset karena hasilnya buruk.

## 7. Keluaran

- `ml/src/strategy_selection.py`
- `ml/artifacts/strategy_selection.{json,md}` dan gambar ekuitas per kelompok.

## Adendum

(belum ada)

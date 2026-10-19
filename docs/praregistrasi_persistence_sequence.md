# Praregistrasi eksperimen: Sekuens Statistik Persistensi (PS) untuk Attention-BiLSTM

Ditulis 2026-10-04, SEBELUM eksperimen dijalankan. Isi dokumen ini tidak
boleh diubah setelah hasil keluar; perubahan apa pun ditulis sebagai
adendum bertanggal di bagian bawah.

## Latar

Evaluasi utama (`main_eval_{tf}.md`) dan ablation (`leakage_study_{tf}.md`)
menunjukkan:

- Attention-BiLSTM atas sekuens koefisien SWT hanya mencapai BA ~0,39.
- Daya beda model berasal dari ringkasan statistik persistensi (variance
  ratio, autokorelasi) yang masuk sebagai SATU vektor di akhir window.
- Bobot attention hampir seragam (entropi ternormalisasi 0,94–0,98).
- Sekuens SWT saat ini hanya mencakup 32 bar terakhir dari window label 500
  bar.

## Hipotesis rancangan

Regime fraktal adalah sifat bagaimana persistensi berubah sepanjang window.
Bila cabang sekuens membaca DERET statistik persistensi yang membentang di
seluruh window, Attention-BiLSTM punya sinyal temporal yang bermakna untuk
dimodelkan.

## Rancangan input PS (ditetapkan sekarang, tidak disetel)

- Sub-window W = 128 bar, panjang sekuens T = 32 (sama dengan model existing).
- Jarak antar langkah s = (L − W) / (T − 1) = (500 − 128) / 31 = 12 bar,
  sehingga sekuens menutup tepat 500 bar = window label. Tidak ada bar di
  luar window label yang dipakai, jadi purge L bar tetap cukup.
- 11 kanal per langkah, semuanya dihitung mundur (kausal) atas sub-window
  yang berakhir di langkah itu: variance ratio q = 2, 4, 8, 16;
  autokorelasi return lag 1, 2, 3, 5; autokorelasi |return| lag 1; laju
  pergantian tanda; log volatilitas.
- Hurst dan DFA TIDAK dipakai.
- Scaler dari baris train saja. Split, purge, seed (42, 43, 44), epoch maks
  80, early stopping patience 12, class weight: identik `main_evaluation.py`.

## Model yang dibandingkan

| Kunci | Cabang sekuens | Fitur ringkasan 50 |
|---|---|---|
| structural_mlp | – | ya |
| swt_attention_bilstm | SWT | – |
| hybrid_swt | SWT | ya (model usulan saat ini) |
| ps_bilstm | PS, tanpa attention | – |
| ps_attention_bilstm | PS | – |
| ps_attention_bilstm_shuffled | PS, urutan langkah diacak per sampel | – |
| hybrid_ps | PS | ya |

## Hipotesis dan kriteria (dinilai pada data TEST, per timeframe)

ΔF1 = Macro F1(B) − Macro F1(A), CI95 block bootstrap (blok 50), per seed.

- **Terbukti**: batas bawah CI95 > 0 pada ≥ 2 dari 3 seed.
- **Berlawanan**: batas atas CI95 < 0 pada ≥ 2 dari 3 seed.
- Selain itu: **tidak terbukti (setara)**.

| H | A (pembanding) | B | Pertanyaan |
|---|---|---|---|
| H1 | swt_attention_bilstm | ps_attention_bilstm | Apakah input PS lebih informatif dari SWT? |
| H2 | ps_attention_bilstm_shuffled | ps_attention_bilstm | Apakah URUTAN waktu persistensi membawa informasi? |
| H3 | ps_bilstm | ps_attention_bilstm | Apakah attention menambah nilai? |
| H4 | hybrid_swt | hybrid_ps | Apakah PS memperbaiki model hybrid? |
| H5 | structural_mlp | hybrid_ps | Apakah hybrid_ps melampaui MLP? |
| H6 | structural_mlp | ps_attention_bilstm | Apakah model sekuens murni menyamai/melampaui MLP? |

## Pemilihan model usulan

Dipilih di antara {hybrid_swt, hybrid_ps, ps_attention_bilstm} berdasarkan
rata-rata balanced accuracy VALIDASI (bukan test), per timeframe. Bila
pilihan 1H dan 4H berbeda, dipilih yang rata-rata validasi kedua timeframe
lebih tinggi. Hasil test dilaporkan untuk semua model apa pun hasilnya.

## Klaim yang diizinkan

- "Lebih baik dari MLP" hanya bila H5 (atau H6) terbukti di 1H DAN 4H, dan
  walk-forward menunjukkan model itu unggul di ≥ 3 dari 5 fold pada kedua
  timeframe.
- Bila tidak, klaimnya "setara/kompetitif", dan kontribusi yang dilaporkan
  adalah jawaban H1–H3 (apa yang membuat Attention-BiLSTM bekerja).

## Walk-forward

Dijalankan untuk structural_mlp, hybrid_swt, hybrid_ps, dan
ps_attention_bilstm dengan fold, purge, dan seed yang sama seperti
`walk_forward_neural.py`, apa pun hasil split tunggal.

## Adendum

(kosong)

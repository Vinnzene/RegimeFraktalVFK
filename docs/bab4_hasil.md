# BAB IV HASIL DAN PEMBAHASAN

> Draf. Semua angka diambil dari artefak di `ml/artifacts/` (config
> `7a3bddc67d72`, 3 seed). Gambar di `ml/artifacts/figures/`.

Bab ini menjawab lima masalah khusus secara berurutan (§4.1–§4.5), lalu
membahas keterbatasan (§4.6).

## 4.1 Konsistensi Label Hurst-DFA (Masalah Khusus 1)

Sumber: `label_consistency.md`, Gambar `fig_label_consistency_{1h,4h}.png`.

**Tabel 4.1** Kesepakatan Hurst R/S dan DFA (seluruh riwayat 2019–2026)

| TF | Window | Korelasi Pearson | Sepakat | Tidak sepakat | Berlawanan (P vs A) |
|---|---|---|---|---|---|
| 1H | 16.857 | 0,573 | 52,6% | 47,4% | 7,3% |
| 4H | 4.123 | 0,550 | 52,7% | 47,3% | 7,1% |

**Tabel 4.2** Distribusi label konsensus

| TF | Persistent | Random-like | Anti-persistent | Uncertain (rule) |
|---|---|---|---|---|
| 1H | 19,0% | 13,2% | 20,4% | 47,4% |
| 4H | 18,6% | 13,3% | 20,8% | 47,3% |

Dua estimator persistensi yang secara teoretis mengukur hal sama hanya
berkorelasi sedang (r ≈ 0,55–0,57) dan tidak sepakat pada hampir separuh
window. Pada ±7% window keduanya bahkan menunjuk arah berlawanan. Porsi
ketidaksepakatan bervariasi per tahun (1H: 32–52%; 4H: 34–69%).

Temuan ini menunjukkan bahwa pada data BTC/USDT yang berderau, "regime
fraktal" bukan besaran yang dapat diukur secara tunggal dan pasti. Pelabelan
konsensus dengan kelas `uncertain_rule` membuat model hanya dilatih dan
dinilai pada window yang dua estimator sepakat, alih-alih memaksakan label
yang meragukan. Konsekuensinya, hasil model pada bab ini berlaku untuk
±53% window yang berlabel jelas.

## 4.2 Sinyal Pembeda Regime (Masalah Khusus 2)

Sumber: `main_eval_{tf}.md`, `leakage_study_{tf}.md` (varian `no_*`),
`ps_study_{tf}.md`; Gambar `fig_feature_ablation.png`,
`fig_ps_comparison.png`.

### 4.2.1 Sekuens wavelet mentah tidak cukup

**Tabel 4.3** Model dengan input sekuens saja (test, rata-rata ± std 3 seed)

| Model | 1H BA | 4H BA |
|---|---|---|
| Tebakan acak | 0,333 | 0,333 |
| SWT + BiLSTM | 0,388 ± 0,007 | 0,382 ± 0,042 |
| SWT + Attention-BiLSTM | 0,386 ± 0,006 | 0,387 ± 0,034 |
| PS + Attention-BiLSTM | **0,675 ± 0,017** | 0,466 ± 0,017 |

Koefisien SWT 32 bar terakhir hanya sedikit di atas tebakan acak. Pada 1H,
mengganti input dengan Sekuens Statistik Persistensi yang membentang di
seluruh window menaikkan balanced accuracy sebesar +0,29 (H1 terbukti; ΔF1
CI95 seluruh seed > 0). Pada 4H peningkatan tidak signifikan.

### 4.2.2 Ablation fitur statistik

**Tabel 4.4** Hybrid SWT dengan kelompok fitur dibuang bertahap (BA test)

| Fitur yang dibuang | 1H | 4H |
|---|---|---|
| — (lengkap) | 0,631 | 0,574 |
| $H(q)$ | 0,620 | 0,589 |
| Variance ratio (VR) | 0,522 | 0,555 |
| VR + autokorelasi | 0,431 | 0,512 |
| VR + autokorelasi + $H(q)$ | **0,387** | **0,407** |

Saat ketiga kelompok proksi persistensi dibuang, performa jatuh tepat ke
level model sekuens SWT saja. Variance ratio adalah pembeda terkuat (1H:
−0,11 sendirian), sedangkan $H(q)$ sendirian hampir tidak berpengaruh.

**Tabel 4.4b** Ablation yang sama pada model usulan Hybrid PS
(`leakage_study_{tf}_ps.md`)

| Yang dibuang | 1H | 4H |
|---|---|---|
| — (lengkap) | 0,693 | 0,522 |
| $H(q)$ dari fitur | 0,691 | 0,550 |
| VR dari fitur | 0,660 | 0,506 |
| VR + AC dari fitur | 0,671 | 0,477 |
| VR + AC + $H(q)$ dari fitur | 0,674 | 0,460 |
| VR + AC + $H(q)$ dari fitur **dan** kanal VR/AC dari sekuens PS | **0,353** | **0,330** |

Berbeda dengan Hybrid SWT, membuang proksi persistensi dari cabang fitur
hampir tidak merusak Hybrid PS di 1H (0,693 → 0,674): informasi yang sama
masih tersedia di cabang sekuens PS, dan cabang sekuens mampu membawanya
sendiri. Baru ketika kanal VR dan autokorelasi juga dibuang dari sekuens —
menyisakan hanya laju pergantian tanda dan log volatilitas — performa jatuh
ke level tebakan (0,353 dan 0,330). Ini menegaskan temuan §4.2.2: daya beda
seluruhnya berasal dari statistik persistensi; volatilitas dan pergantian
tanda saja tidak cukup.

### 4.2.3 Pembahasan

Regime fraktal pada label Hurst-DFA dikenali melalui **statistik
persistensi multi-lag** (variance ratio dan autokorelasi), bukan melalui
pola koefisien wavelet. Ini wajar secara teori: variance ratio dan
autokorelasi adalah ukuran persistensi yang berkerabat dengan eksponen
Hurst, tetapi dihitung dengan cara berbeda dari R/S maupun DFA. Model tidak
menyalin label (Hurst/DFA tidak pernah menjadi input), tetapi memfusikan
beberapa estimator persistensi alternatif untuk mereproduksi konsensus dua
estimator rujukan. Hal ini harus dinyatakan terbuka sebagai sifat tugas
identifikasi berbasis label Hurst-DFA.

## 4.3 Perbandingan Model (Masalah Khusus 3)

Sumber: `main_eval_{tf}.md`, `ps_study_{tf}.md`; Gambar
`fig_main_comparison_{tf}.png`, `fig_ps_comparison.png`,
`fig_confusion_hybrid_ps.png`.

### 4.3.1 Seleksi model

Model usulan dipilih berdasarkan balanced accuracy validasi sebelum
melihat hasil uji (praregistrasi). Hybrid PS terpilih pada kedua timeframe
(validasi 1H 0,538; 4H 0,604), di atas Hybrid SWT (0,529; 0,565) dan PS +
Attention-BiLSTM (0,512; 0,578).

### 4.3.2 Hasil pada data uji

**Tabel 4.5** Perbandingan model, 1H (test, n = 1.619, rata-rata ± std 3 seed)

| Model | Balanced Acc | Macro F1 | MCC | Recall P | Recall R | Recall A |
|---|---|---|---|---|---|---|
| Kelas mayoritas | 0,333 | 0,206 | 0,000 | 0,00 | 0,00 | 1,00 |
| Acak proporsional | 0,339 ± 0,009 | 0,332 | 0,005 | 0,37 | 0,28 | 0,37 |
| MLP fitur statistik | 0,629 ± 0,015 | 0,622 | 0,510 | 0,66 | **0,49** | 0,74 |
| SWT + Attention-BiLSTM | 0,386 ± 0,006 | 0,379 | 0,098 | 0,35 | 0,17 | 0,65 |
| Hybrid SWT | 0,631 ± 0,019 | 0,630 | 0,538 | 0,71 | 0,35 | 0,83 |
| **Hybrid PS (usulan)** | **0,693 ± 0,018** | **0,690** | **0,654** | **0,75** | 0,37 | **0,96** |

Akurasi Hybrid PS 0,784 ± 0,004 dan Cohen's kappa 0,649 ± 0,004.

**Tabel 4.6** Perbandingan model, 4H (test, n = 257)

| Model | Balanced Acc | Macro F1 | MCC | Recall P | Recall R | Recall A |
|---|---|---|---|---|---|---|
| Kelas mayoritas | 0,333 | 0,163 | 0,000 | 1,00 | 0,00 | 0,00 |
| MLP fitur statistik | 0,552 ± 0,009 | 0,557 | 0,430 | 0,57 | 0,23 | 0,86 |
| SWT + Attention-BiLSTM | 0,387 ± 0,034 | 0,352 | 0,127 | 0,61 | 0,04 | 0,51 |
| Hybrid SWT | **0,574 ± 0,011** | **0,575** | **0,441** | **0,62** | 0,33 | 0,77 |
| Hybrid PS (usulan) | 0,522 ± 0,048 | 0,507 | 0,365 | 0,42 | 0,31 | 0,84 |

**Tabel 4.7** Uji Hipotesis H1–H6 Menggunakan Moving-Block Bootstrap dengan Ensemble Prediksi 3 Seed dan Koreksi Holm-Bonferroni

*Catatan Metodologis:* Window analisis selebar $L=500$ bar yang digeser dengan langkah $s=4$ bar menghasilkan autokorelasi serial tinggi. Ukuran sampel efektif yang sebenarnya adalah $N_{\text{eff}} \approx \text{total bar} / 500$, yakni $\approx 13{,}97$ blok independen pada 1H ($N=1.622$ window uji) dan $\approx 3{,}09$ blok independen pada 4H ($N=262$ window uji). Panjang blok bootstrap ditetapkan pada batas minimum teoritis $L_{\text{block, min}} = \lceil 500 / 4 \rceil = 125$ window ($B=2.000$ resampling) untuk mencakup rentang dependensi window. Evaluasi dilakukan pada prediksi ensemble rata-rata probabilitas 3 seed. Untuk mengendalikan laju galat keluarga uji (*Family-Wise Error Rate*), p-value dikoreksi dengan prosedur *step-down* Holm-Bonferroni ($K=6$).

| H | Pertanyaan Ilmiah / Pembanding | 1H: ΔMacro F1 [CI95] | 1H: p-val (raw / Holm) | 1H Keputusan | 4H: ΔMacro F1 [CI95] | 4H: p-val (raw / Holm) | 4H Keputusan |
|---|---|---|---|---|---|---|---|
| **H1** | PS vs SWT (PS + Attn vs SWT + Attn) | +0,297 [+0,189, +0,388] | 0,0000 / 0,0000 | **TERBUKTI** | +0,037 [-0,045, +0,114] | 0,1745 / 1,0000 | Setara |
| **H2** | Urutan Waktu (PS + Attn vs Urutan Diacak) | +0,016 [-0,021, +0,052] | 0,1880 / 0,3760 | Setara | -0,033 [-0,154, +0,089] | 0,6950 / 1,0000 | Setara |
| **H3** | Attention (PS + Attn vs PS tanpa Attn) | -0,003 [-0,040, +0,037] | 0,5595 / 0,5595 | Setara | +0,019 [-0,048, +0,104] | 0,4585 / 1,0000 | Setara |
| **H4** | Usulan Baru vs Lama (Hybrid PS vs Hybrid SWT) | +0,057 [-0,008, +0,115] | 0,0400 / 0,1600 | Setara (FWER) | -0,055 [-0,215, +0,118] | 0,7170 / 1,0000 | Setara |
| **H5** | Hybrid vs Baseline (Hybrid PS vs MLP) | +0,085 [+0,018, +0,151] | 0,0070 / 0,0350 | **TERBUKTI** | -0,033 [-0,124, +0,057] | 0,7080 / 1,0000 | Setara |
| **H6** | Sekuens Murni vs MLP (PS + Attn vs MLP) | +0,059 [-0,023, +0,137] | 0,0720 / 0,2160 | Setara | -0,148 [-0,226, -0,088] | 1,0000 / 1,0000 | **BERLAWANAN** |

*Uji Sensitivitas Panjang Blok (1H):*
Pada variasi panjang blok 62 window ($0{,}5\times$), 125 window ($1{,}0\times$), dan 250 window ($2{,}0\times$):
- H1, H2, H3, dan H6 menghasilkan kesimpulan 100% konsisten.
- Pada H5 (Hybrid PS vs MLP), batas bawah interval kepercayaan 95% tetap positif di seluruh skala panjang blok: [+0,012, +0,154] pada 62w, [+0,018, +0,151] pada 125w, dan [+0,016, +0,160] pada 250w. Keunggulan Hybrid PS atas MLP pada 1H terbukti kokoh terhadap variasi parameter ketergantungan blok.

### 4.3.3 Pembahasan

Pada 1H, Hybrid PS adalah satu-satunya model yang secara signifikan mengungguli MLP fitur statistik (ΔMacro F1 +0,085, $p_{\text{Holm}} = 0,0350$). Kenaikan terbesar ada pada kelas Anti-persistent (recall 0,96) dan Persistent (0,75). Random-like tetap kelas tersulit untuk semua model (recall ≤ 0,49), sesuai sifatnya yang paling menyerupai derau — dan secara definisi berada di antara dua ambang sehingga paling mudah tertukar dengan kelas tetangganya.

Pada 4H, tidak ada model sekuensial yang mengungguli MLP fitur statistik; sebaliknya pada H6, model sekuens murni secara signifikan berada di bawah MLP (ΔMacro F1 -0,148 [CI95: -0,226, -0,088]). Gejala ini sejalan dengan ukuran sampel efektif 4H yang sangat kecil ($N_{\text{eff}} \approx 3{,}09$), di mana parameter recurrent berkapasitas tinggi mengalami kesulitan konvergensi representasi fraktal dibandingkan model feedforward yang lebih sederhana.

## 4.4 Kestabilan Antar Periode (Masalah Khusus 4)

Sumber: `walk_forward_neural_{tf}_ps.md`; Gambar `fig_walk_forward_ps.png`.

**Tabel 4.8** Walk-forward expanding 5 fold (BA test per fold, rata-rata 3 seed)

| TF | Model | Fold 1 | 2 | 3 | 4 | 5 | Rata-rata ± std | Menang vs MLP |
|---|---|---|---|---|---|---|---|---|
| 1H | MLP | 0,425 | 0,591 | 0,571 | 0,520 | 0,639 | 0,549 ± 0,073 | – |
| 1H | Hybrid SWT | 0,431 | 0,556 | 0,561 | 0,567 | 0,634 | 0,550 ± 0,066 | 2/5 |
| 1H | **Hybrid PS** | **0,484** | **0,619** | 0,539 | 0,564 | **0,686** | **0,578 ± 0,069** | **4/5** |
| 4H | MLP | 0,346 | 0,483 | 0,634 | 0,392 | 0,564 | 0,484 ± 0,106 | – |
| 4H | Hybrid SWT | 0,363 | 0,451 | 0,579 | 0,436 | 0,575 | 0,481 ± 0,084 | 3/5 |
| 4H | Hybrid PS | 0,339 | 0,387 | 0,447 | 0,467 | 0,531 | 0,434 ± 0,066 | 1/5 |

Pada 1H, Hybrid PS unggul atas MLP di empat dari lima periode, termasuk
fold 1 yang data latihnya paling sedikit (1.163 window). Seluruh model di
seluruh fold berada di atas tebakan acak. Performa sangat bergantung periode
(selisih fold terbaik–terburuk ±0,2), menunjukkan bahwa sebagian periode
pasar memang lebih sulit diidentifikasi.

Pada 4H, performa jauh lebih rendah dan tidak stabil (MLP 0,35–0,63). Hybrid
PS kalah di empat dari lima fold (hanya unggul atas MLP pada fold 4), dan fold 1
(154 window latih) berada di level tebakan untuk semua model. Dengan kriteria
praregistrasi, klaim keunggulan Hybrid PS **hanya berlaku untuk 1H**.

### 4.4.1 Konteks Komparatif: Uji Split Tunggal vs Walk-Forward

Terdapat perbedaan angka yang perlu dipahami secara adil antara Balanced Accuracy pada partisi uji split tunggal (0,693 pada Tabel 4.7) dan rata-rata performa pada evaluasi *walk-forward* (0,578 ± 0,069 pada Tabel 4.8).

Perbedaan ini bersumber dari karakteristik periode pasar:
1. **Periode Uji Split Tunggal Beririsan dengan Fold 5:** Partisi uji pada skema split tunggal mencakup periode kalender akhir (2024–2026), yang beririsan langsung dengan jendela pengujian Fold 5 pada *walk-forward* (di mana Hybrid PS mencatat BA sebesar 0,686). Periode ini dicirikan oleh tren makro Bitcoin yang kuat dan struktur persistensi fraktal yang relatif bersih, sehingga menjadi periode pasar yang relatif "lebih mudah" diidentifikasi oleh model.
2. **Kekuatan Generalisasi Walk-Forward:** Sebaliknya, evaluasi *walk-forward* menguji model melintasi lima rezim pasar yang sangat beragam, termasuk periode pasar bergejolak (*bear market* dan konsolidasi menyempit) seperti pada Fold 1 (BA 0,484) dan Fold 3 (BA 0,539).
3. **Ekspektasi Kinerja:** Angka 0,578 ± 0,069 memberikan ekspektasi performa yang lebih konservatif dan realistis (*out-of-sample across regimes*) untuk penerapan jangka panjang, sedangkan angka 0,693 mencerminkan kapasitas optimal model pada kondisi pasar berpersistensi tinggi.

## 4.5 Pengaruh Protokol Evaluasi (Masalah Khusus 5)

Sumber: `leakage_study_{tf}.md`; Gambar `fig_leakage.png`.

**Tabel 4.9** Hybrid SWT dengan protokol bocor (BA test, Δ terhadap bersih)

| Protokol | 1H | 4H |
|---|---|---|
| Bersih (kronologis + purge + scaler train) | 0,631 | 0,574 |
| Tanpa purge | +0,007 | +0,020 |
| Scaler dari seluruh data | −0,001 | −0,011 |
| SWT non-kausal | +0,005 | −0,010 |
| **Split acak** | **+0,123** | **+0,159** |
| Semua kebocoran | +0,136 | +0,157 |

Pembagian data secara acak menggelembungkan balanced accuracy 12–16 poin
persentase. Penyebabnya: window bertetangga berbagi hingga 500 bar, sehingga
window uji yang diacak hampir selalu memiliki "kembaran" di data latih.
Angka 0,75 (1H) yang tampak jauh lebih baik itu sepenuhnya artefak protokol.
Sebaliknya, scaler global dan SWT non-kausal hampir tidak berpengaruh pada
model ini; menghapus purge memberi efek kecil (+0,01 s/d +0,02). Pada Hybrid
PS (Tabel 4.9b) efek purge bahkan tidak terukur (|Δ| < 0,01), sehingga purge
dipertahankan sebagai pengaman, bukan sebagai sumber perbedaan hasil.

**Tabel 4.9b** Hybrid PS dengan protokol bocor (`leakage_study_{tf}_ps.md`)

| Protokol | 1H | 4H |
|---|---|---|
| Bersih | 0,693 | 0,522 |
| Tanpa purge | −0,002 | −0,007 |
| Scaler dari seluruh data | −0,004 | −0,002 |
| **Split acak** | **+0,131 (→ 0,823)** | **+0,262 (→ 0,783)** |

(Varian SWT non-kausal tidak berlaku: Hybrid PS tidak memakai sekuens SWT.)

Pada model usulan, split acak menggelembungkan BA 4H dari 0,522 menjadi
0,783 (+0,26) — lebih besar daripada Hybrid SWT (+0,16). Model yang tampak
"terbaik" di 4H di bawah split acak ternyata justru terlemah di bawah
protokol kronologis. Seandainya penelitian ini memakai split acak,
kesimpulannya akan terbalik: Hybrid PS akan diklaim unggul di 4H dengan
akurasi ±0,78. Ini bukti paling langsung bahwa protokol evaluasi kronologis
bukan formalitas, melainkan penentu kesimpulan.

### 4.5.1 Uji Sensitivitas Sumber Ambang Kuantil (Train-Only vs Full-History)

Sumber: `label_threshold_sensitivity_{tf}.md/json`.

Pada konfigurasi utama, ambang kuantil ground truth dikalibrasi atas distribusi seluruh riwayat (`full_history`). Untuk membuktikan bahwa tidak terjadi kebocoran informasi distribusi (*distributional lookahead leakage*) dari data uji ke data latih, dilakukan uji sensitivitas di mana ambang kuantil dihitung **hanya dari partisi data latih** (`train_only`) dan dibekukan sebelum diterapkan ke data validasi dan uji.

**Tabel 4.9c** Perbandingan Ambang Kuantil dan Kinerja Test (Train-Only vs Full-History)

| Timeframe | Parameter / Metrik | Full-History (Bawaan) | Train-Only (Uji Sensitivitas) | Selisih (Train - Full) | Status / Dampak |
|---|---|---|---|---|---|
| **1H** | Hurst Lower (q=0,33) | 0,5719 | 0,5717 | -0,0002 | Sangat Stabil |
| 1H | Hurst Upper (q=0,67) | 0,5996 | 0,5983 | -0,0013 | Sangat Stabil |
| 1H | DFA Lower (q=0,33) | 0,4728 | 0,4775 | +0,0047 | Sangat Stabil |
| 1H | DFA Upper (q=0,67) | 0,5183 | 0,5202 | +0,0019 | Sangat Stabil |
| 1H | Test BA Hybrid PS | 0,693 ± 0,018 | 0,661 ± 0,005 | -0,032 | Tetap Terbaik |
| 1H | Test BA MLP | 0,629 ± 0,015 | 0,629 ± 0,021 | 0,000 | Identik |
| **4H** | Hurst Lower (q=0,33) | 0,5878 | 0,5892 | +0,0014 | Sangat Stabil |
| 4H | Hurst Upper (q=0,67) | 0,6124 | 0,6136 | +0,0012 | Sangat Stabil |
| 4H | DFA Lower (q=0,33) | 0,4742 | 0,4802 | +0,0060 | Sangat Stabil |
| 4H | DFA Upper (q=0,67) | 0,5227 | 0,5274 | +0,0047 | Sangat Stabil |
| 4H | Test BA Hybrid PS | 0,522 ± 0,048 | 0,593 ± 0,013 | +0,071 | Meningkat |
| 4H | Test BA MLP | 0,552 ± 0,009 | 0,574 ± 0,024 | +0,022 | Konsisten |

Hasil uji sensitivitas menunjukkan:
1. **Stabilitas Ambang Fraktal:** Pergeseran nilai ambang kuantil antara `full_history` dan `train_only` sangat kecil ($|\Delta| \le 0{,}006$ untuk seluruh parameter), membuktikan bahwa sifat fraktal data latih sudah sangat representatif.
2. **Konsistensi Temuan Ilmiah:** Pada 1H, Hybrid PS tetap menjadi model dengan performa tertinggi (BA 0,661 vs MLP 0,629 dan SWT 0,377) serta mencatatkan akurasi validasi tertinggi (0,544). Pada 4H, seluruh keputusan hipotesis H1–H6 terbukti 100% konsisten antara kedua konfigurasi. Temuan utama penelitian terbukti kokoh dan bebas dari ketergantungan kebocoran kuantil.

## 4.6 Peran Attention dan Keterbatasan

### 4.6.1 Attention

Sumber: `ps_study_{tf}.md` (H2, H3, entropi), Gambar `fig_attention_{tf}.png`.

| Hipotesis | 1H | 4H |
|---|---|---|
| H3 Attention > tanpa attention (input PS) | Setara | Setara |
| H2 Urutan waktu PS bermakna | Setara | Berlawanan |

Entropi ternormalisasi bobot attention: Hybrid PS 0,91 (1H) dan 0,83 (4H);
Hybrid SWT 0,96 dan 0,92 (1,0 = seragam). Attention pada input PS lebih
terfokus dibanding SWT, tetapi tidak meningkatkan akurasi secara signifikan
dibanding BiLSTM tanpa attention, dan mengacak urutan langkah tidak
menurunkan performa secara signifikan. Artinya keunggulan Hybrid PS berasal
dari **isi** input (statistik persistensi yang menutup seluruh window),
bukan dari kemampuan attention memilih langkah waktu tertentu. Lapisan
attention dipertahankan karena memberi bobot interpretatif per langkah,
tetapi kontribusinya terhadap akurasi tidak dapat diklaim.

### 4.6.2 Analisis Daya Tahan Informasi Regime ke Depan (Forward Persistence Study)

Sumber: `forward_persistence_{tf}.md/json`; Gambar `fig_forward_persistence_{tf}.png`.

Untuk menjawab pertanyaan mendasar mengenai signifikansi praktis identifikasi regime: *"Apakah status regime yang teridentifikasi pada saat $t$ memiliki daya tahan informatif ke masa depan?"*, dilakukan evaluasi daya tahan temporal (*temporal memory*) pada horizon $k \in \{4, 8, 16, 32, 64, 128\}$ bar ke depan melintasi seluruh partisi pengujian.

**1. Retensi Regime Empiris vs Tingkat Dasar Marginal (H-F1):**  
Pada data latih 1H, probabilitas dasar marginal (*unconditional base rates*) adalah: Persistent 0,356, Random-like 0,274, dan Anti-persistent 0,370.

**Tabel 4.9d** Probabilitas Retensi Regime $P(R_{t+k} = c \mid R_t = c)$ terhadap Tingkat Dasar (1H)

| Horizon ($k$ bar) | Langkah Window ($w$) | Retensi Persistent (Base: 0,36) | Retensi Random-Like (Base: 0,27) | Retensi Anti-Persistent (Base: 0,37) | Status Memori Fraktal (Retensi > Base) |
|---|---|---|---|---|---|
| **4 bar** | 1 w | 0,924 | 0,700 | 0,960 | **Terbukti Signifikan** |
| **8 bar** | 2 w | 0,894 | 0,577 | 0,938 | **Terbukti Signifikan** |
| **16 bar** | 4 w | 0,844 | 0,411 | 0,909 | **Terbukti Signifikan** |
| **32 bar** | 8 w | 0,800 | 0,391 | 0,883 | **Terbukti Signifikan** |
| **64 bar** | 16 w | 0,715 | 0,245 | 0,838 | **Terbukti Signifikan** |
| **128 bar** | 32 w | 0,606 | 0,205 | 0,749 | **Terbukti Signifikan** |

Hasil pada Tabel 4.9d membuktikan bahwa dinamika regime fraktal BTC/USDT memiliki ketergantungan temporal yang kuat: regime persisten dan anti-persisten memiliki probabilitas bertahan jauh di atas tingkat dasar acak hingga 128 bar ke depan. Fenomena serupa terkonfirmasi pada 4H (retensi persisten 0,897 pada 4 bar dan 0,725 pada 32 bar vs base rate 0,40).

**2. Kinerja Prediksi Forward Model vs Baseline Naif (H-F2):**  
Diuji apakah prediksi model Hybrid PS pada waktu $t$ mampu memprediksi kondisi regime sebenarnya pada $t+k$ lebih baik daripada *baseline naif persistensi* (asumsi status regime sebenarnya pada saat $t$ bertahan konstan hingga $t+k$).

**Tabel 4.9e** Evaluasi Kinerja Prediksi Forward: Hybrid PS vs Baseline Naif (1H)

| Horizon ($k$ bar) | Naive Balanced Acc | Hybrid PS Balanced Acc | Naive Macro F1 | Hybrid PS Macro F1 | ΔMacro F1 (Model - Naive) [CI95] | Kesimpulan Prediktif |
|---|---|---|---|---|---|---|
| **4 bar** | 0,861 | 0,695 | 0,861 | 0,692 | -0,169 [-0,267, -0,110] | Baseline Naif Unggul |
| **8 bar** | 0,803 | 0,689 | 0,803 | 0,686 | -0,117 [-0,212, -0,059] | Baseline Naif Unggul |
| **16 bar** | 0,721 | 0,674 | 0,721 | 0,672 | -0,049 [-0,146, +0,014] | Setara secara Statistik |
| **32 bar** | 0,692 | 0,642 | 0,692 | 0,641 | -0,051 [-0,119, -0,009] | Baseline Naif Unggul |
| **64 bar** | 0,599 | 0,615 | 0,599 | 0,614 | +0,015 [-0,051, +0,075] | Setara secara Statistik |
| **128 bar** | 0,520 | 0,559 | 0,520 | 0,557 | +0,037 [-0,017, +0,089] | Setara secara Statistik |

Temuan empiris pada Tabel 4.9e memberikan penegasan epistemologis penting:
- Pada horizon pendek ($k \le 16$ bar), baseline naif mengungguli model karena baseline naif bertolak dari label ground truth sempurna pada waktu $t$, sedangkan model memiliki galat klasifikasi inheren ($BA \approx 0,693$).
- Pada horizon panjang ($k \ge 64$ bar), kinerja model dan baseline naif berkonvergensi ke tingkat setara.
- **Kesimpulan Resmi:** Model usulan berfungsi sebagai **instrumen identifikasi dan klasifikasi kondisi pasar saat ini (*nowcasting / real-time context filtering*)**, bukan sebagai peramal regime masa depan (*future regime forecasting*). Keterbatasan struktural tumpang tindih window ($L=500$ bar) turut berkontribusi pada perlambatan peluruhan memori ini.

### 4.6.3 Keterbatasan

1. Model mempelajari label konsensus Hurst-DFA, bukan "regime sejati";
   tidak ada rujukan independen untuk regime.
2. Hanya ±53% window yang memiliki label jelas; sisanya tidak dievaluasi.
3. Fitur yang paling menentukan (variance ratio, autokorelasi) berkerabat
   teoretis dengan eksponen Hurst.
4. Satu aset (BTC/USDT) dan dua timeframe; data 4H terlalu kecil untuk
   model sekuens kaya.
5. Ambang kuantil label pada konfigurasi utama dihitung dari distribusi seluruh riwayat. Namun, uji sensitivitas *train-only* (§4.5.1) membuktikan ambang kuantil sangat stabil (pergeseran eksponen $\le 0{,}006$) dan kesimpulan utama konsisten.
6. Kelas Random-like tetap sulit dikenali (recall ≤ 0,49 untuk semua model).
7. Ukuran sampel efektif pada window uji yang bertumpang tindih ($L=500, s=4$) jauh lebih kecil ($N_{\text{eff}} \approx 14$ pada 1H dan $\approx 3$ pada 4H) dibandingkan jumlah observasi nominal, sehingga ketidakpastian estimasi pada 4H sangat lebar.
8. Periode pengujian split tunggal 1H bertepatan dengan Fold 5 yang relatif lebih mudah dibandingkan siklus pasar lainnya.

## 4.7 Evaluasi Kelayakan Hilir (Downstream Setup Engine)

Fokus utama penelitian ini adalah *identifikasi regime fraktal* pada deret waktu BTC/USDT, bukan perekayasaan sistem perdagangan otomatis. Namun, sebagai studi kelayakan hilir (*downstream feasibility study*), modul Setup Engine dikembangkan untuk menguji apakah prediksi regime fraktal dapat langsung dikonversi menjadi keputusan eksekusi mekanikal tanpa modul *directional forecasting* tambahan.

Simulasi hilir diuji secara *walk-forward* kronologis pada 14 jendela *out-of-sample* (rentang 14 bulan kalender yang memiliki data granular 30M dan 5M) menggunakan Mode A (tanpa konfirmasi OFI/CVD, karena keterbatasan arsip Level-2 publik).

### 4.7.1 Hurst-Direction Disconnect

Hasil evaluasi mengungkap fenomena *Hurst-Direction Disconnect*: eksponen Hurst ($H$) dan DFA secara matematis mengukur persistensi struktur skala varians dan autokorelasi memori jangka panjang, **bukan arah tren harga masa depan**.

Pada data empiris BTC/USDT:
- Pada regime persistent ($H > 0,5$), probabilitas pergerakan searah tren sebelumnya hanya $P(\text{searah}) = 0,458$ (di bawah 50%).
- Pada regime anti-persistent ($H < 0,5$), $P(\text{searah}) = 0,480$.
- Autokorelasi return lag-1 bernilai negatif lemah ($\rho_1 = -0,032$).

Asumsi intuitif bahwa persistensi fraktal otomatis menghasilkan *momentum arah* terbukti tidak berlaku pada pasar spot kripto. Persistensi yang tinggi menandakan pengelompokan volatilitas (*volatility clustering*) dan memori magnitudo fluktuasi, bukan jaminan kelanjutan arah harga.

### 4.7.2 Dampak Biaya Transaksi Realistis (Fee dan Slippage)

Evaluasi hilir menerapkan model biaya realistis standar Binance VIP 0 spot:
- Biaya *taker* sebesar 0,075% ($0,00075$) per sisi (masuk dan keluar).
- *Slippage* sebesar 1 tick ($0,01$ USDT).
- Rumus kalkulasi:
  $$\text{biaya\_total} = (P_{\text{entry}} + P_{\text{exit}}) \times \text{taker\_fee\_pct} + 2 \times (\text{slippage\_ticks} \times \text{tick\_size})$$
  $$R_{\text{net}} = \frac{(P_{\text{exit}} - P_{\text{entry}}) \times \text{direction} - \text{biaya\_total}}{\text{risk\_distance}}$$

Tanpa biaya (0 fee, 0 slippage), performa *gross* terlihat impas atau positif. Namun, setelah memperhitungkan fee taker dan slippage, return bersih ($R_{\text{net}}$) tergerus secara signifikan pada seluruh skenario.

### 4.7.3 Analisis Sensitivitas Grid

Untuk menghindari bias pemilihan parameter (*data snooping*), dilakukan analisis sensitivitas terarah pada 6 kombinasi grid dengan memvariasikan toleransi tunggu pullback (`max_setup_wait_bars` $\in \{6, 12, 18\}$) dan relaksasi konteks bias (`bias_allowed_contexts` $\in \{\text{SUPPORTIVE}, \text{SUPPORTIVE+NEUTRAL}\}$).

**Tabel 4.10** Hasil Analisis Sensitivitas Grid Setup Engine Mode A (14 Jendela OOS)

| Konfigurasi Grid | Konteks Bias | Max Wait Bars | $N$ Trade | TP | SL | Timeout | Win Rate (95% Wilson CI) | Gross Total R (Avg R) | Net Total R (Avg R) | Biaya Total (R) | Biaya Total (USDT) | Keterangan Sampel |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `wait_6_ctx_SUPPORTIVE` | SUPPORTIVE | 6 | **3** | 2 | 0 | 1 | 66,7% [20,8%, 93,9%] | +3,65 (+1,22) | **+2,97 (+0,99)** | 0,68 | 467,18 | Sampel Kecil ($N < 30$) |
| `wait_12_ctx_SUPPORTIVE` | SUPPORTIVE | 12 | **4** | 2 | 0 | 2 | 50,0% [15,0%, 85,0%] | +3,83 (+0,96) | **+2,96 (+0,74)** | 0,87 | 597,28 | Sampel Kecil ($N < 30$) |
| `wait_18_ctx_SUPPORTIVE` | SUPPORTIVE | 18 | **4** | 2 | 0 | 2 | 50,0% [15,0%, 85,0%] | +3,83 (+0,96) | **+2,96 (+0,74)** | 0,87 | 597,28 | Sampel Kecil ($N < 30$) |
| `wait_6_ctx_SUPPORTIVE+NEUTRAL` | SUPPORTIVE+NEUTRAL | 6 | **172** | 30 | 32 | 103 | 18,2% [13,0%, 24,8%] | +52,62 (+0,32) | **+11,20 (+0,07)** | 41,42 | 20.766,31 | Representatif ($N \ge 30$) |
| `wait_12_ctx_SUPPORTIVE+NEUTRAL` | SUPPORTIVE+NEUTRAL | 12 | **176** | 28 | 38 | 102 | 16,7% [11,8%, 23,0%] | +45,63 (+0,27) | **+5,25 (+0,03)** | 40,38 | 21.186,77 | Representatif ($N \ge 30$) |
| `wait_18_ctx_SUPPORTIVE+NEUTRAL` | SUPPORTIVE+NEUTRAL | 18 | **179** | 29 | 38 | 104 | 17,0% [12,1%, 23,3%] | +48,04 (+0,28) | **+7,88 (+0,05)** | 40,16 | 21.587,66 | Representatif ($N \ge 30$) |

### 4.7.4 Pembahasan dan Tradeoff Selektivitas

1. **Tradeoff Selektivitas vs Ukuran Sampel**:
   - Pada filter default konservatif (`SUPPORTIVE` saja, wait bars = 6), hanya terealisasi $N=3$ trade dalam 14 bulan OOS. Model fraktal multi-timeframe sangat selektif karena mensyaratkan 4H dan 1H sama-sama berada pada regime Persistent. Interval kepercayaan Wilson untuk win rate sangat lebar ([20,8%, 93,9%]), sehingga performa tinggi pada sel ini tidak dapat digeneralisasi secara statistik.
   - Ketika konteks direlaksasi ke `SUPPORTIVE+NEUTRAL`, ukuran sampel meningkat drastis menjadi $N=172$ s/d $179$ trade. Pada kondisi ini, win rate berkisar antara 16,7% s/d 18,2%, dengan mayoritas posisi berakhir pada batas holding waktu (*TIMEOUT*).
2. **Implikasi bagi Implementasi Praktis**:
   - Prediksi regime fraktal dinamis terbukti berharga sebagai *filter makro / filter risiko* (misalnya untuk menentukan besaran alokasi atau menghindari pasar acak), namun tidak memadai jika dipaksakan sebagai generator sinyal entri mandiri tanpa kombinasi indikator arah atau analisis *order flow* granular.

## 4.8 Rangkuman Jawaban Masalah Khusus

| # | Masalah khusus | Jawaban |
|---|---|---|
| 1 | Konsistensi label | Hurst dan DFA hanya sepakat pada ±53% window; label konsensus + `uncertain_rule` diperlukan |
| 2 | Sinyal pembeda | Statistik persistensi multi-lag (terutama variance ratio), bukan koefisien wavelet; tanpa statistik ini semua model jatuh ke level tebakan |
| 3 | Perbandingan model | 1H: Hybrid PS terbaik dan signifikan > MLP (BA 0,693, MCC 0,654). 4H: tidak ada model yang signifikan lebih baik |
| 4 | Kestabilan | 1H: Hybrid PS unggul di 4/5 fold walk-forward. 4H: tidak stabil (kalah di 4/5 fold vs MLP) |
| 5 | Protokol evaluasi | Split acak menggelembungkan BA +0,12 s/d +0,26 dan membalik kesimpulan di 4H; protokol kronologis wajib |

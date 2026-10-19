# Kerangka Skripsi — Bingkai B

Status: draf untuk dibahas dengan dosen pembimbing. Semua angka di bawah
berasal dari run selesai 2026-10-04 (config `7a3bddc67d72`, 3 seed).

## Usulan judul

1. **Identifikasi Regime Fraktal Dinamis BTC/USDT Multi-Timeframe Menggunakan
   Hybrid Attention-BiLSTM dengan Fitur Wavelet dan Statistik Persistensi**
2. Analisis Sinyal Pembeda Regime Fraktal pada Deret Waktu Kripto Berderau
   Menggunakan Hybrid Attention-BiLSTM

Judul 1 paling dekat dengan judul lama (hanya menambah "Hybrid" dan
"Statistik Persistensi" agar sesuai isi).

## Masalah umum

Bagaimana mengidentifikasi regime fraktal (persistent, random-like,
anti-persistent) secara otomatis pada deret waktu BTC/USDT yang berderau
tinggi, dengan evaluasi yang bebas kebocoran data?

## Masalah khusus → eksperimen → artefak

| # | Masalah khusus | Eksperimen | Artefak |
|---|---|---|---|
| 1 | Hurst dan DFA sering tidak sepakat sehingga label tidak konsisten | Label konsensus + kelas `uncertain_rule`; ukur porsi ketidaksepakatan | `label_consistency.md`, `figures/fig_label_consistency_{tf}.png` |
| 2 | Sinyal apa yang membuat regime dapat dikenali di tengah derau? | Ablation fitur: SWT saja, tanpa VR, tanpa VR+AC, tanpa VR+AC+H(q) | `leakage_study_{tf}.md` (varian `no_*`) |
| 3 | Apakah Hybrid Attention-BiLSTM lebih baik dari pembanding? | 6 model, split identik, 3 seed, ΔF1 + CI95, McNemar | `main_eval_{tf}.md` |
| 4 | Apakah hasilnya stabil antar periode dan timeframe? | Walk-forward 5 fold (expanding), 1H vs 4H | `walk_forward_neural_{tf}.md` |
| 5 | Seberapa besar evaluasi bocor menggelembungkan hasil? | Protokol bersih vs 5 varian bocor | `leakage_study_{tf}.md` (varian bocor) |

## Temuan yang sudah ada (jujur, termasuk yang negatif)

- Konsistensi label (masalah khusus 1, `label_consistency.md`). Seluruh
  riwayat 2019–2026: Hurst R/S dan DFA hanya sepakat di 52,6% window (1H) dan
  52,7% (4H); korelasi Pearson 0,57 / 0,55. Pada 7% window keduanya bahkan
  berlawanan (satu persistent, satu anti-persistent). Label yang dipakai
  model = window yang disepakati saja (P 19%, R 13%, A 20%); 47% sisanya
  `uncertain_rule`. Durasi regime rata-rata ~3,3 window (~13 jam pada 1H).
- Attention (sumber: `figures/attention_stats_{tf}.json` untuk Hybrid SWT seed 42, serta `ps_study_{tf}.md` untuk perbandingan model). Pada model Hybrid SWT (input sekuens SWT 32 langkah, seed 42), bobot attention nyaris seragam: entropi ternormalisasi 0,98 (1H) dan 0,94 (4H), dengan 32 langkah terakhir tidak ada yang mendominasi. Pada studi lanjutan `ps_study_{tf}.md` (rata-rata 3 seed), entropi ternormalisasi adalah 0,91 (1H) dan 0,83 (4H) untuk Hybrid PS, serta 0,96 (1H) dan 0,92 (4H) untuk Hybrid SWT. Pola per regime tidak berbeda jelas. Artinya attention di model ini tidak memilih langkah waktu tertentu — konsisten dengan temuan bahwa urutan langkah bukan sumber utama daya beda. Wajib dilaporkan sebagai batasan bagian "Attention" di judul.
- Learning curve: model terbaik tercapai cepat (1H epoch 1, 4H epoch 5 pada
  seed 42) lalu val_loss memburuk; early stopping menghentikan training di
  epoch 13/17. Ini bukti overfitting cepat, bukan kurang epoch.

- Model hanya dengan sekuens SWT gagal: BA 0,386 (1H) dan 0,387 (4H), sedikit
  di atas tebakan (0,333).
- Hybrid: BA 0,631 ± 0,019 (1H), 0,574 ± 0,011 (4H); jauh di atas baseline
  dan model SWT saja (CI95 tidak memuat 0).
- Hybrid vs MLP fitur statistik: setara (CI95 ΔF1 memuat 0 di semua seed).
  Hybrid unggul di Persistent dan Anti-persistent; MLP lebih baik di
  Random-like. Klaim yang sah: kompetitif, bukan lebih unggul.
- Random-like adalah kelas tersulit (recall 0,35 Hybrid 1H) — konsisten
  dengan sifatnya yang paling mirip derau.
- Ablation fitur (jawaban masalah khusus 2). Tanpa variance ratio,
  autokorelasi, dan H(q), BA jatuh ke level model SWT saja:
  1H 0,631 → tanpa VR 0,522 → tanpa VR+AC 0,431 → tanpa VR+AC+H(q) 0,387;
  4H 0,574 → 0,555 → 0,512 → 0,407. Pembeda utama adalah variance ratio
  (1H: −0,11 sendirian); H(q) sendirian hampir tidak berpengaruh (−0,01).
  Pengenalan regime bertumpu pada statistik persistensi multi-lag, bukan
  pada sekuens wavelet mentah.
- Kebocoran (masalah khusus 5). Split acak menggelembungkan BA 1H 0,631 →
  0,754 (+0,123) dan 4H 0,574 → 0,733 (+0,159). Semua kebocoran sekaligus:
  +0,136 (1H). Tanpa purge +0,007 (1H) / +0,020 (4H). Scaler global dan SWT
  non-kausal hampir tidak berpengaruh (|Δ| ≤ 0,01) — dilaporkan apa adanya.
- Walk-forward 5 fold (masalah khusus 4). Hybrid vs MLP setara di semua
  periode: 1H BA rata-rata fold 0,550 vs 0,549 (std 0,066 vs 0,073), 4H
  0,481 vs 0,484. Hybrid unggul di 2/5 fold (1H) dan 3/5 fold (4H); hampir
  semua CI95 ΔF1 memuat 0. Hybrid sedikit lebih stabil (std antar fold lebih
  kecil). Performa sangat bergantung periode: fold 1 terendah (1H 0,43, 4H
  0,36 ≈ tebakan) karena data latih paling sedikit; 4H fold 4 juga rendah.
- Walk-forward 4H rata-rata 0,48 — jauh di bawah split tunggal 0,574. Hasil
  4H tidak stabil dan harus disimpulkan hati-hati (data 4H 4× lebih sedikit).

## Hasil eksperimen praregistrasi: Sekuens Statistik Persistensi (PS)

Rancangan & kriteria: `docs/praregistrasi_persistence_sequence.md`.
Artefak: `ps_study_{tf}.md`, `walk_forward_neural_{tf}_ps.md`.

Split tunggal (test, 3 seed):

| Model | 1H BA | 1H MCC | 4H BA | 4H MCC |
|---|---|---|---|---|
| MLP fitur statistik | 0,629 | 0,51 | 0,552 | 0,43 |
| Hybrid SWT (usulan lama) | 0,631 | 0,54 | 0,574 | 0,44 |
| PS + Attention-BiLSTM | 0,675 | 0,62 | 0,466 | 0,27 |
| Hybrid PS | **0,693** | **0,65** | 0,522 | 0,37 |

| H | 1H | 4H |
|---|---|---|
| H1 PS > SWT (sekuens murni) | TERBUKTI | setara |
| H2 urutan waktu bermakna | setara | BERLAWANAN |
| H3 attention menambah nilai | setara | setara |
| H4 PS memperbaiki hybrid | TERBUKTI | setara |
| H5 Hybrid PS > MLP | TERBUKTI | setara |
| H6 PS-Attention ≥ MLP | setara | BERLAWANAN |

Walk-forward (5 fold, 3 seed):

| Model | 1H BA rata-rata fold | menang vs MLP | 4H BA rata-rata fold | menang vs MLP |
|---|---|---|---|---|
| MLP | 0,549 | – | 0,484 | – |
| Hybrid SWT | 0,550 | 2/5 | 0,481 | 3/5 |
| Hybrid PS | **0,578** | **4/5** | 0,434 | 2/5 |
| PS + Attention | 0,554 | – | 0,393 | 1/5 |

Penilaian sesuai aturan praregistrasi:

- Seleksi berbasis BA validasi memilih **Hybrid PS** di 1H (0,538) dan 4H
  (0,604) → model usulan = Hybrid PS.
- Klaim "lebih baik dari MLP" mensyaratkan H5 terbukti di 1H DAN 4H plus
  walk-forward ≥ 3/5 di kedua TF. Hanya 1H yang memenuhi → klaim yang sah:
  **Hybrid PS lebih baik dari MLP pada 1H; tidak lebih baik pada 4H**.
- Di 4H, seleksi validasi (0,604) tidak tercermin di test (0,522) dan
  walk-forward (0,434): model PS overfit pada data 4H yang 4× lebih kecil.
  Ini temuan, bukan disembunyikan.
- H3 tidak terbukti di kedua TF: attention tidak menambah akurasi di atas
  BiLSTM biasa. H2 tidak terbukti: urutan waktu persistensi tidak terbukti
  membawa informasi tambahan; di 4H justru urutan acak lebih baik.
  Keunggulan PS datang dari cakupan seluruh window 500 bar dan kanal
  statistik persistensi, bukan dari dinamika temporal yang dipilih attention.

## Yang dikeluarkan dari skripsi

- Setup engine / simulasi trading (lebih ke keuangan; bisa jadi lampiran
  atau saran penelitian lanjutan).
- Order flow OFI/CVD: hasil negatif, cukup satu subbab ablation.
- Artefak forecasting `swt_attention_bilstm_*`, `swt_bilstm_*`,
  `horizon_study_1h` (tugas berbeda, h = 500).

## Batasan yang wajib ditulis

- Label berasal dari Hurst-DFA; model mempelajari label itu, bukan "regime
  sejati". Fitur VR, autokorelasi, dan H(q) berkerabat matematis dengan
  eksponen Hurst — dibuktikan lewat ablation, bukan disembunyikan.
- Satu aset (BTC/USDT), dua timeframe.
- Window `uncertain_rule` dikeluarkan dari training/evaluasi.

## Gambar Bab 4 (`ml/artifacts/figures/`)

| Gambar | Isi | Masalah khusus |
|---|---|---|
| fig_label_consistency_{tf} | scatter Hurst vs DFA + % uncertain per tahun | 1 |
| fig_feature_ablation | BA saat VR/AC/H(q) dibuang bertahap | 2 |
| fig_main_comparison_{tf} | BA & Macro F1 6 model | 3 |
| fig_confusion_{tf} | confusion matrix MLP vs Hybrid | 3 |
| fig_walk_forward | BA per fold, MLP vs Hybrid, 1H & 4H | 4 |
| fig_leakage | inflasi BA protokol bocor | 5 |
| fig_learning_curve_{tf} | loss/akurasi train vs validasi, titik early stop | metodologi |
| fig_attention_{tf} | bobot attention per regime | pembahasan |

## Reproduksi

```
python ml/src/audit_artifacts.py --write
python ml/src/label_consistency.py --plot
python ml/src/main_evaluation.py --timeframe 1h
python ml/src/main_evaluation.py --timeframe 4h
python ml/src/leakage_study.py --timeframe 1h
python ml/src/leakage_study.py --timeframe 4h
python ml/src/walk_forward_neural.py --timeframe 1h
python ml/src/walk_forward_neural.py --timeframe 4h
python ml/src/make_figures.py
python ml/src/persistence_sequence_study.py --timeframe 1h
python ml/src/persistence_sequence_study.py --timeframe 4h
python ml/src/walk_forward_neural.py --timeframe 1h --models structural_mlp hybrid_swt hybrid_ps ps_attention_bilstm --tag _ps
python ml/src/walk_forward_neural.py --timeframe 4h --models structural_mlp hybrid_swt hybrid_ps ps_attention_bilstm --tag _ps
```

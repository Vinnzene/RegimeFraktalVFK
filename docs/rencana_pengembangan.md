# Rencana Pengembangan Skripsi (8 minggu)

Ditulis 2026-10-19. Fokus tetap **identifikasi** regime (nowcasting), dengan
dua perubahan pokok:

1. Kebenaran regime tidak lagi didefinisikan sebagai keluaran Hurst-DFA.
   Regime dianggap laten; R/S, DFA, dan model sama-sama alat identifikasi yang
   diadu pada data sintetis dengan H diketahui.
2. Identifikasi pada BTC dibuktikan bermakna lewat masalah nyata:
   **pemilihan strategi** (momentum vs mean-reversion vs tidak trading).

## Usulan judul

> Identifikasi Regime Persistensi Fraktal Bitcoin untuk Pemilihan Strategi
> Trading: Model Deep Learning yang Divalidasi pada Data Sintetis dan Kinerja
> Strategi Out-of-Sample

## Masalah nyata

Strategi momentum menguntungkan saat pasar persisten dan merugi saat pasar
berbalik; mean-reversion sebaliknya. Trader umumnya memakai satu strategi di
semua kondisi. Skripsi menjawab: apakah regime yang teridentifikasi saat ini
dapat dipakai memilih strategi yang tepat, setelah biaya transaksi?

## Rumusan masalah

| # | Rumusan | Bukti |
|---|---|---|
| RM1 | Seberapa akurat R/S dan DFA mengidentifikasi regime pada sampel terbatas dengan ekor tebal dan volatility clustering? | Benchmark sintetis |
| RM2 | Apakah model yang diusulkan mengidentifikasi regime lebih akurat daripada R/S dan DFA pada kondisi tersebut? | Benchmark sintetis |
| RM3 | Apakah regime BTC hasil identifikasi berbeda perilaku secara nyata (validasi konstruk)? | Statistik per regime pada BTC |
| RM4 | Apakah pemilihan strategi berdasarkan regime memberi kinerja bersih lebih baik daripada strategi tunggal? | Backtest walk-forward + uji SPA |
| RM5 | Seberapa besar protokol evaluasi bocor menggelembungkan hasil? | Studi kebocoran (sudah ada) |

## Fase 0 — Perbaikan wajib (minggu 1)

- [x] Satuan biaya Tabel 4.10 (USDT tertulis sebagai R) — `run_setup_sensitivity_grid.py`, `bab4_hasil.md`.
- [ ] `threshold_source: train_only` menjadi konfigurasi utama; `full_history` jadi sensitivitas.
- [ ] Walk-forward dijadikan angka utama; hapus narasi "periode mudah" §4.4.1 atau buktikan dengan statistik per periode.
- [ ] Seragamkan N uji (1.619/1.622, 257/262) dan laporkan p < 1/B, bukan 0,0000.
- [ ] Baseline tambahan: regresi logistik, LightGBM (50 fitur), Statistical Jump Model, HMM.
- [ ] Repo git sendiri di folder project (saat ini repo git berada di folder home) dan commit praregistrasi sebelum eksperimen baru, agar waktunya dapat diverifikasi.

## Fase 1 — Benchmark sintetis (minggu 2–4) → RM1, RM2

Generator (`ml/src/synthetic.py` diperluas), H diketahui pasti:

| Skenario | Proses |
|---|---|
| S1 bersih | fGn |
| S2 ekor tebal | fGn dengan inovasi Student-t (ν = 3–5) |
| S3 volatility clustering | fGn × volatilitas GARCH(1,1) dikalibrasi ke BTC |
| S4 lengkap | S2 + S3 + lompatan (jumps) |
| S5 regime berganti | H berubah di dalam window (titik ganti acak) |

- Label kebenaran dari H pembangkit dengan **ambang absolut** (mis. H < 0,45 anti-persistent, 0,45–0,55 random-like, > 0,55 persistent), bukan kuantil.
- Pembanding: R/S, R/S termodifikasi Lo (1991), DFA-1, uji VR Lo-MacKinlay, MLP, LightGBM, Hybrid PS.
- Metrik: BA dan Macro F1 terhadap regime sebenarnya, bias dan RMSE estimasi H, sebagai fungsi panjang window (128 / 256 / 500).
- Set uji sintetis dibangkitkan dengan seed terpisah dan tidak pernah dipakai untuk tuning.

## Fase 2 — Validasi pada BTC (minggu 4–6) → RM3, RM4

**Validasi konstruk (RM3).** Per regime hasil identifikasi: autokorelasi
return ke depan, VR ke depan, volatilitas, dan return strategi; uji beda antar
regime dengan standar error HAC.

**Pemilihan strategi (RM4).** Semua sinyal hanya memakai data ≤ t; posisi
dibuka pada bar berikutnya.

| Strategi | Aturan |
|---|---|
| Momentum | arah = tanda return k bar terakhir |
| Mean-reversion | arah = kebalikan z-score harga terhadap rata-rata bergerak |
| Buy & hold | pembanding pasif |
| **Switching (usulan)** | persistent → momentum, anti-persistent → mean-reversion, random-like → tidak masuk |
| Switching dengan regime R/S, DFA, Jump Model, HMM | pembanding identifikasi |

- Biaya: taker 0,075% per sisi + slippage realistis (mis. 1–2 bps), bukan 1 tick.
- Walk-forward expanding, parameter strategi dipilih hanya di data latih tiap fold.
- Metrik: return bersih, Sharpe, Sortino, max drawdown, turnover.
- Uji: beda Sharpe (Ledoit-Wolf 2008), Hansen SPA terhadap seluruh pembanding, regresi return strategi pada dummy regime dengan HAC.
- Hipotesis, aturan, dan parameter ditulis di praregistrasi **sebelum** dijalankan.

Risiko yang diketahui: temuan "Hurst-Direction Disconnect" (§4.7.1)
menunjukkan persistensi tidak otomatis berarti momentum arah. Hasil negatif
tetap sah bila dipraregistrasi; regime dari estimator yang lebih akurat (Fase
1) juga bisa memberi gambaran berbeda.

## Fase 3 — Penulisan dan dashboard (minggu 6–7)

- Bab 3–5 ditulis ulang mengikuti RM1–RM5; setup engine dipindah ke lampiran.
- Dashboard: halaman "Regime saat ini → strategi yang direkomendasikan" beserta
  bukti historis per regime (kinerja tiap strategi, interval kepercayaan).

## Fase 4 — Cadangan dan persiapan sidang (minggu 8)

- Perbarui `tanya_jawab_sidang.md` dengan pertanyaan sirkularitas, N_eff, dan
  biaya transaksi.
- Jika waktu tersisa: uji lintas aset (ETH/USDT) tanpa pelatihan ulang.

## Yang dipertahankan

Pipeline data, fitur PS dan statistik, arsitektur model, purge, scaler dari
data latih, walk-forward, studi kebocoran, block bootstrap + Holm.

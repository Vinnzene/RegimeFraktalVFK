# Status Pekerjaan — catatan lanjut

Dokumen singkat untuk melanjutkan pekerjaan tanpa menelusuri ulang riwayat.
Terakhir diperbarui: 23 September 2026.

## Cara menjalankan

```powershell
# Terminal 1
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2
cd frontend
npm run dev
```

Dashboard: <http://localhost:3000> · API: <http://localhost:8000/docs>

## Yang sudah selesai

| Bagian | Status |
|---|---|
| Pipeline analisis (Hurst, DFA, SWT causal) | selesai, 302 unit test lulus |
| Metrik dua lapis (argmax + pasca-τ + cakupan) | selesai |
| Sensitivitas horizon (4 nilai h) | selesai untuk 1H |
| Diagnostik backtest (edge/drag/biaya, uji acak) | selesai |
| Order flow (OFI/CVD) | Mode A standar (NaN), Mode B menolak tanpa data riil |
| Setup Engine (Friksi Pasar Realistis) | Taker fee 0,075% + slippage 1 tick, gross & net R |
| Sensitivitas Grid Setup Engine | 6 sel, 14 window OOS, N naik hingga 172 trade |
| Statistical Jump Model (flow.md langkah 3) | selesai, λ perlu keputusan |
| Generalized Hurst H(q) & Spektrum Multifraktal | selesai, visualisasi frontend di `/multifractal` |
| Pretraining fBm & Multi-task | skrip selesai di `ml/src/` |
| Walk-forward 5-fold expanding | selesai (Hybrid PS 1H menang 4/5, 4H menang 1/5) |
| Sensitivitas Ambang Kuantil (T1.3) | `train_only` vs `full_history` terverifikasi sangat stabil |
| Block Bootstrap & Koreksi FWER (T1.4) | $N_{\text{eff}}$ eksplisit, $L_{\text{block}}=125$, Holm-Bonferroni $K=6$ |
| Analisis Forward Persistence (T2.1) | Retensi vs base rate & Hybrid PS vs Naive Persistence |
| Demo Kesiapan Offline (T3.2) | `check_offline_ready.py` (26/26 file) & `launch_demo.ps1` |
| Dokumen Tanya Jawab Sidang (T3.4) | `docs/tanya_jawab_sidang.md` siap berbasis data artefak |
| 11 halaman frontend | selesai (Ringkasan, Detail, Multifraktal, dsb.) |

## Hasil training

Metrik dari `/api/v1/model/compare` pada 1H, `tau = 0.40`, h = 500 bar:

```
MODEL                    CAKUPAN   ARGMAX_BA   SETELAH_TAU_BA   N_DIJAWAB
swt_attention_bilstm       36.3%      0.4089           0.4897        3180
swt_bilstm                  6.3%      0.3741           0.4073         552
rule_based                 94.6%      0.3261           0.3248        8288
persistence (baseline)     53.2%      0.1437           0.2709        4662

tebakan acak 3 kelas = 0.3333
```

**Temuan utama:**

1. SWT + Attention-BiLSTM mengungguli seluruh pembanding (BA argmax 0.409 vs
   baseline naif 0.144 dan rule-based 0.326).
2. Komponen attention memberi kontribusi terukur: 0.409 dengan attention vs
   0.374 tanpa attention. Ini justifikasi empiris untuk arsitektur usulan.
3. Model bersifat selektif, bukan gagal. Pada 36% window yang dijawab, balanced
   accuracy naik ke 0.490 — model menahan diri saat tidak yakin.

Catatan revisi: kesimpulan sebelumnya ("model tidak mengungguli tebakan acak")
keliru. Metrik lama menghitung setiap `uncertain_lowconf` sebagai kesalahan,
sehingga BA jatuh ke 0.0 dan menyembunyikan daya diskriminasi yang sebenarnya
ada. Setelah metrik dipisah menjadi lapis argmax dan lapis pasca-tau, gambarannya
berubah.

Seluruh angka diperoleh setelah fitur SWT dinormalisasi memakai statistik subset
training saja, bobot kelas diseimbangkan, dan purge gap diterapkan di batas split.

Waktu respons `/model/compare` pada 1H (16.735 window): ~13 detik saat cache
dingin, di bawah 100 ms setelahnya.

## Sensitivitas horizon

`ml/src/horizon_study.py` melatih ulang model pada beberapa nilai `h` dengan
konfigurasi identik, lalu membandingkan tiap horizon terhadap Baseline
Persistence **pada horizon yang sama**. Hasil 1H, SWT + Attention-BiLSTM:

```
  h (bar)    hari   BA model   baseline   selisih
      125     5.2     0.3925     0.6380   -0.2455
      250    10.4     0.3698     0.4925   -0.1227
      500    20.8     0.3463     0.2709   +0.0754
     1000    41.7     0.3229     0.3482   -0.0253
```

Tiga pola yang terbaca:

1. **BA model menurun monoton** seiring bertambahnya horizon (0.393 → 0.323),
   sejalan dengan berkurangnya informasi yang tersedia untuk horizon jauh.
2. **Baseline juga menurun, tetapi jauh lebih curam** (0.638 → 0.271). Pada
   horizon pendek regime jarang berubah sehingga tebakan naif sangat kuat.
3. **Model hanya unggul pada h = 500 bar** (+0.0754). Di horizon pendek,
   persistensi regime terlalu mudah ditebak; di horizon sangat panjang,
   sinyalnya habis.

Konsekuensi metodologis: membandingkan balanced accuracy mentah antar horizon
menyesatkan. Yang sebanding adalah selisih terhadap baseline pada horizon yang
sama — itulah yang ditonjolkan panel Sensitivitas Horizon.

Menjalankan ulang:

```bash
python ml/src/horizon_study.py --timeframe 1h --horizons 125 250 500 1000
```

Hasil dibaca lewat `GET /api/v1/model/horizon-study?tf=1h`.

Belum dijalankan untuk 4H.

## Hasil backtest dan diagnostiknya

Aturan Bab 3 (persistent → ikut arah, anti-persistent → kontrarian) menghasilkan
kerugian besar. Diagnostik menunjukkan penyebabnya bukan biaya transaksi maupun
implementasi, melainkan asumsi arah yang tidak berlaku pada data.

```
Dekomposisi log-equity (rule-based, 1H):
  edge (arah posisi)   −2.62   ← penyumbang utama
  volatility drag      −0.48
  biaya transaksi      −3.33
```

Bahkan tanpa biaya sama sekali, strategi rugi −95.5%.

```
Pembanding posisi acak (200 simulasi, exposure identik):
  median acak      −36.9%
  strategi regime  −95.5%  → persentil 0.5
```

Kalah dari 99.5% tebakan acak bukan pertanda sinyal kosong — sinyal kosong akan
mendarat di sekitar persentil 50. Nilai serendah ini menunjukkan arah posisi
terbalik secara **sistematis**.

```
Asumsi arah (P = 0.5 berarti tidak ada informasi):
  persistent       P(searah) = 0.458   diasumsikan > 0.5   TIDAK BERLAKU
  anti_persistent  P(searah) = 0.480   diasumsikan < 0.5   berlaku
  autokorelasi lag-1 = −0.032
```

Akar masalahnya konseptual: Hurst Exponent mengukur persistensi struktur skala
dan volatilitas, bukan tanda return. Aturan Bab 3 menerjemahkan H > 0.5 menjadi
prediksi arah — lompatan yang tidak didukung teori maupun data.

Membalik aturan **bukan** solusi. Pengujian per segmen menunjukkan pembalikan
tidak stabil: train +533%, validation −14%, test +51%. Validation berlawanan
tanda, jadi pembalikan hanya overfitting ke train.

Keputusan: aturan Bab 3 dipertahankan apa adanya, dan seluruh bukti di atas
ditampilkan sebagai diagnostik di halaman `/backtest`. Hasil negatif yang
terdokumentasi lebih kuat daripada aturan yang diam-diam diganti agar terlihat
baik.

Endpoint: `GET /api/v1/backtest/diagnostics?tf=1h&regime_source=rule_based_causal`

## Order flow: diuji, tidak dipakai

Tahap A dari PRD HR-SOAB — menambahkan sinyal mikrostruktur — sudah diuji dan
**hasilnya negatif**. Fitur tetap ada di kode, dinonaktifkan secara bawaan.

### Ketersediaan data (terverifikasi)

| Data | Status |
|---|---|
| `takerBuyBaseAssetVolume` di kline | tersedia sejak 2019, 100% bar |
| aggTrades arsip | tersedia, ~89 MB/bulan |
| `bookTicker` spot | **HTTP 404** — tidak ada arsip |
| `bookDepth` spot | **HTTP 404** |
| `bookDepth` futures | tersedia harian |

OBI historis untuk BTC/USDT **spot** tidak tersedia. OFI dapat dihitung penuh
tanpa mengunduh aggTrades karena kline sudah memuat volume taker.

### Hasil ablation (1H, identifikasi)

```
fitur                    dim   akurasi       BA   macro F1
SWT saja                 160    0.5899   0.5632     0.5573
+ struktural              44    0.8686   0.8584     0.8636   ← terbaik
+ struktural + OFI        70    0.8399   0.8230     0.8305
OFI saja                  26    0.6020   0.5544     0.5156
```

OFI menurunkan akurasi pada kedua mode (biner 0.8686 → 0.8399; tiga kelas
0.6895 → 0.6814). Fitur OFI memperoleh 28,4% feature importance namun tetap
memperburuk hasil — pola khas fitur derau yang dipakai pohon untuk memecah
secara semu. Seleksi 2–8 fitur OFI terbaik pun tidak menolong (0.8293–0.8391).

### Tafsir

Persistensi yang diukur Hurst-DFA adalah sifat struktur **harga** pada rentang
window ratusan bar, sedangkan OFI per bar merangkum tekanan beli-jual sesaat.
Keduanya bekerja pada skala waktu yang berbeda.

Ini temuan yang layak dilaporkan: hipotesis PRD tentang mikrostruktur sebagai
penambah ketepatan **tidak terdukung** pada tugas identifikasi regime.

Mengaktifkan kembali: `build_dataset(with_orderflow=True, ohlcv=...)`.

## Langkah 3 — Statistical Jump Model

Menjawab masalah flip-flop label yang ditandai dosen pembimbing. Pengukuran
membenarkan kekhawatiran itu: kelas `random_like` hanya bertahan 1,8 window
dengan peluang bertahan 0,446, padahal window bertetangga berbagi 99,2% data
yang sama.

`backend/app/services/jump_model.py` mengimplementasikan Jump Model
(Nystrup, Kolm & Lindström, 2020) — coordinate descent dengan penugasan state
lewat dynamic programming.

### Hasil tuning λ (1H)

```
metode              durasi   median   switch   entropi   distribusi
ambang kuantil        3,31        -     5071         -   4 kelas
jump λ=0,0            5,25      2,0     3196     0,962   23/46/31
jump λ=0,5           12,29      7,0     1363     0,953   21/47/31
jump λ=1,0           18,29     11,0      916     0,954   22/47/31
jump λ=10,0          73,56     48,5      227     0,945   24/50/26
jump λ=100          284,25    174,0       58     0,814   19/65/16
```

λ=100 ditolak: entropi turun dan `random_like` menelan 65% data.

### Pertukaran yang ditemukan

Pada subset yang sama (8.794 window berlabel tegas):

```
labeling           durasi   akurasi       BA   macroF1
ambang kuantil       7,25    0,6923   0,6018    0,6021
jump λ=0,0           6,91    0,6853   0,6331    0,6297
jump λ=0,5           9,35    0,6627   0,6270    0,6231
jump λ=10           39,43    0,5859   0,5919    0,5635
```

Akurasi mentah turun, tetapi **balanced accuracy dan macro F1 justru naik**
pada λ rendah — Jump Model memperbaiki pengenalan kelas minoritas. Ini sejalan
dengan penekanan PRD bahwa macro F1 lebih relevan daripada akurasi.

Kesepakatan dengan label lama tetap tinggi: 94,5% pada λ=0,5. Jadi Jump Model
menghaluskan, bukan mengubah struktur.

Tafsir: label ambang lebih mudah ditebak karena dibentuk dari aturan
deterministik atas Hurst dan DFA. Jump Model memindahkan sebagian window ke
kelas tetangga demi kontinuitas temporal, dan perpindahan itu tidak selalu
tercermin pada fitur struktural.

**Keputusan λ perlu persetujuan pembimbing** karena menyangkut definisi ground
truth. Saran: λ=0,5 sebagai titik tengah.

```bash
python ml/src/tune_jump_penalty.py --timeframe 1h
```

## Langkah 7 — Validasi walk-forward

`backend/app/services/walk_forward.py` + `ml/src/walk_forward_study.py`.
Model dilatih ULANG pada tiap fold, seluruh prediksi digabung menjadi satu
confusion matrix agregat.

### Temuan utama: split tunggal terlalu optimis

```
                        akurasi
split tunggal            0,6923
walk-forward agregat     0,6011   ← selisih 9 poin
```

### Hasil (1H, expanding, purge 125 baris)

```
mode      labeling    akurasi       BA   macroF1   simpangan
3 kelas   ambang       0,6011   0,5524    0,5369      0,0852
biner     ambang       0,8204   0,8164    0,8180      0,0757
biner     jump λ=0,5   0,8103   0,8052    0,8049      0,0959
```

Skema rolling konsisten lebih rendah (0,7928 vs 0,8204 pada mode biner),
menandakan data lama tetap berguna — tidak ada pergeseran rezim yang membuatnya
usang.

Fold 1 selalu terendah (0,4369 pada mode 3 kelas) karena hanya punya 1.330
sampel latih, lalu naik konsisten sampai 0,6918 pada fold 5. Model memerlukan
data yang cukup.

```bash
python ml/src/walk_forward_study.py --timeframe 1h --binary
python ml/src/walk_forward_study.py --timeframe 1h --binary --labeling jump
```

Hasil dibaca lewat `GET /api/v1/model/walk-forward?tf=1h&mode=binary`.

## Langkah 2 & 5 — Generalized Hurst H(q)

`backend/app/services/multifractal.py`. H(q) untuk q = 1, 2, 4 lewat metode
**fungsi struktur**: K_q(tau) = <|Y(t+tau) − Y(t)|^q> ~ tau^(q·H(q)), dengan Y
profil kumulatif log-return.

Estimatornya sengaja BERBEDA dari R/S dan DFA yang membentuk label, sehingga
penambahannya sebagai fitur tidak membuat label sirkular. Yang ditambahkan
adalah informasi multifraktalitas — bagaimana persistensi berubah antar orde
momen — yang tidak tertangkap H tunggal.

Enam fitur: `hq_1`, `hq_2`, `hq_4`, `hq_width` (= H(1) − H(4)), `hq_slope`,
`tau_curvature`. Aktif secara bawaan lewat `build_dataset(with_multifractal=True)`.

Validasi di `tests/test_multifractal.py` (9 test):

1. H(q) memulihkan H pada fBm untuk H = 0.3, 0.5, 0.7.
2. **fBm monofraktal**: lebar spektrum rata-rata < 0.12. Kalau estimator
   melaporkan lebar besar pada data monofraktal, klaim multifraktalitas pada
   BTC tidak bermakna.
3. **Kontrol positif**: deret dengan volatilitas berlompat harus punya spektrum
   lebih lebar. Tanpa ini, lebar yang selalu kecil bisa berarti estimatornya
   tidak peka terhadap apa pun.
4. Kausalitas: fitur pada t identik apakah deret dipotong di t atau tidak.

Panel: `GET /api/v1/analysis/multifractal?tf=1h`. Endpoint ikut melaporkan
`cross_check` — korelasi H(2) fungsi-struktur terhadap Hurst R/S. Keduanya
estimator berbeda sehingga selisih sistematis wajar; korelasi tinggi menandakan
keduanya mengukur sifat yang sama.

## Langkah 4 & 6 — Pretraining fBm + multi-task

Digabung dalam `ml/src/train_multitask.py` karena saling bergantung: head
regresi H adalah alasan utama pretraining fBm berguna — di sana H diketahui
persis, bukan ditaksir.

**Arsitektur** (`build_multitask_attention_bilstm`): badan jaringan sama dengan
model usulan, dua head berbagi encoder.

```
head regime : softmax n_classes   ← target label Hurst-DFA
head hurst  : sigmoid 1 unit      ← target H kontinu
loss = CE(regime) + lambda * MSE(hurst)      lambda bawaan 0.3
```

Sigmoid dipakai karena H terdefinisi pada (0, 1). Bobot 0.3 berasal dari skala
kedua loss, bukan selera: CE tiga kelas bermula di ~1.1, MSE pada H bermula di
~0.01–0.05. Tanpa penimbang, gradien regresi praktis tidak terasa.

Alasan head kedua: label regime adalah hasil diskretisasi H lewat ambang, dan
diskretisasi membuang informasi — window dengan H = 0.56 dan H = 0.85 mendapat
label sama padahal jaraknya jauh. Head regresi memaksa representasi internal
tetap membawa besaran kontinu itu.

**Pretraining** (`ml/src/synthetic.py`): fBm dengan H diketahui pada grid
0.2–0.8, label dari H pembangkit (bukan dari estimator, supaya galat estimasi
tidak ikut terbawa). Fitur dibentuk dengan fungsi yang SAMA seperti data riil;
kalau berbeda, bobot hasil pretraining memetakan masukan yang tak pernah muncul
saat fine-tuning. Pemisahan train/val dilakukan per LINTASAN, bukan per sampel —
memisah per sampel menempatkan potongan lintasan yang sama di kedua sisi.

Scaler sintetis TIDAK dibawa ke fine-tuning: koefisien SWT fBm dan BTC berbeda
skala. Yang dipindahkan hanya bobot, sah karena bentuk masukan identik.
Learning rate fine-tuning diturunkan ke 3e-4 agar tidak langsung menghapus
hasil pretraining.

```bash
python ml/src/train_multitask.py --timeframe 1h
python ml/src/train_multitask.py --timeframe 1h --no-pretrain    # ablasi langkah 4
python ml/src/train_multitask.py --timeframe 1h --lambda-reg 0   # ablasi langkah 6
```

Dua ablasi itu yang membuktikan apakah langkah 4 dan 6 benar-benar
berkontribusi. **Belum dijalankan penuh** — baru diverifikasi jalan
end-to-end pada konfigurasi kecil. Hasil sesungguhnya masih perlu diproduksi.

Metrik regresi selalu dilaporkan bersama `mae_baseline_mean` (tebakan "selalu
rata-rata"). Tanpa pembanding itu MAE 0.05 tidak bisa dinilai: bisa saja
sebaran H memang hanya selebar itu.

Catatan: pada data BTC target head regresi adalah H hasil estimasi R/S, yang
sendirinya mengandung galat. MAE di sana mengukur kesesuaian terhadap
estimator, bukan terhadap H sejati. Hanya pada tahap fBm H diketahui persis.

## Perkembangan Pengembangan Lanjutan (Instruksi S1 UBM 2026)

Seluruh butir prioritas pengembangan lanjutan telah selesai diimplementasikan dan diverifikasi:

1. **Prioritas 1 (Validitas & Metodologi):**
   - Tabel 4.8 & narasi sinkron (Hybrid PS 4H menang 1/5 fold, kalah 4/5 fold).
   - Skrip verifikasi angka Bab 4 (`ml/src/verify_bab4_numbers.py`) dibuat dan lulus verifikasi.
   - Entropi attention disamakan antar seluruh dokumen (Hybrid PS: 0,91 di 1H, 0,83 di 4H; Hybrid SWT: 0,96 dan 0,92).
   - Uji sensitivitas ambang kuantil `train_only` vs `full_history` terbukti sangat stabil ($|\Delta| \le 0{,}006$).
   - Block bootstrap dengan sampel efektif eksplisit ($N_{\text{eff}} \approx 13{,}97$ pada 1H, $3{,}09$ pada 4H), panjang blok teoritis $L_{\text{block}}=125$, ensemble 3-seed, dan koreksi Holm-Bonferroni ($K=6$).
   - Mode A dijadikan standar resmi (kolom OFI/CVD diisi NaN; Mode B menolak tanpa data riil).
   - Friksi pasar Binance VIP 0 (fee taker 0,075% + slippage 1 tick) diterapkan pada setup engine, menampilkan $R_{\text{gross}}$ dan $R_{\text{net}}$.
   - Sensitivitas grid 6 sel pada 14 window OOS mengatasi $N=3$ (naik hingga $N=172$), mendokumentasikan tradeoff selektivitas vs sampel.

2. **Prioritas 2 (Daya Guna Informasi Regime):**
   - Analisis persistensi forward (`forward_persistence_analysis.py`) membuktikan memori fraktal nyata pada $k \le 32$ bar ($P(R_{t+k} = c \mid R_t = c) > P(c)$).
   - Perbandingan terhadap baseline naif mengonfirmasi batas klaim ilmiah: model berfungsi sebagai instrumen identifikasi (*nowcasting*), bukan peramal transisi masa depan.
   - Konteks performa BA test 1H (0,693) disandingkan secara adil dengan rata-rata walk-forward (0,578 ± 0,069) di Subbab 4.4.1.
   - Subbab 4.7 "Evaluasi Kelayakan Hilir" mendokumentasikan fenomena *Hurst-direction disconnect*.

3. **Prioritas 3 (Kesiapan Sidang & Demo):**
   - Halaman frontend `/multifractal` menampilkan kurva $H(q)$ ($q \in \{1, 2, 4\}$), lebar spektrum $\Delta H$, verifikasi silang $H(2)$ vs $H_{\text{R/S}}$, dan rumus KaTeX.
   - Skrip pemeriksa kesiapan offline (`scripts/check_offline_ready.py`) memvalidasi 26/26 berkas lokal.
   - Peluncur demo offline satu perintah (`scripts/launch_demo.ps1`).
   - Panduan tanya-jawab sidang komprehensif berbasis artefak (`docs/tanya_jawab_sidang.md`).

## Catatan penting

- `config.yaml` adalah satu-satunya sumber parameter. Setelah mengubahnya,
  panggil `POST /api/v1/meta/config/reload` atau restart backend.
- Ambang terkalibrasi saat ini: H `[0.5717, 0.5993]`, α `[0.4724, 0.5177]`.
  Ambang tetap 0.45/0.55 membuat `uncertain_rule` mencapai 83% dan kelas
  `anti_persistent` kosong — mode `fixed` tetap tersedia untuk pembanding.
- Test memakai data mock di direktori sementara, tidak menyentuh jaringan
  maupun `data/processed/`.

# Flow Implementasi: Identifikasi Regime Fraktal Dinamis BTC/USDT
### SWT + Attention-BiLSTM Berbasis Hurst-DFA (Multi-Timeframe)

Dokumen ini adalah panduan langkah-demi-langkah untuk implementasi, disusun sesuai urutan pengerjaan riil (bukan urutan bab skripsi). Setiap langkah mencantumkan **apa yang dikerjakan**, **kenapa**, dan **pakai alat/library apa**.

---

## Peta Alur Keseluruhan

```
[0] Akuisisi Data
        │
        ▼
[1] Preprocessing & Resampling Multi-Timeframe
        │
        ▼
[2] Estimasi Hurst-DFA Robust (Ground Truth Kontinu)
        │
        ▼
[3] Labeling Regime via Statistical Jump Model (Persistence-Aware)
        │
        ▼
[4] Pretraining Sintetis (fBm/ARFIMA dengan H Diketahui)
        │
        ▼
[5] Ekstraksi Fitur Multi-Skala via SWT
        │
        ▼
[6] Training Attention-BiLSTM (Multi-Task: Klasifikasi + Regresi H)
        │
        ▼
[7] Validasi Walk-Forward + Confusion Matrix
        │
        ▼
[8] Ablation Study & Interpretasi Attention
```

---

## Langkah 0 — Akuisisi Data

**Apa:** Kumpulkan data harga OHLCV BTC/USDT untuk timeframe 1H dan 4H, historis sepanjang mungkin (idealnya beberapa tahun agar mencakup berbagai regime pasar: bull, bear, sideways, crash).

**Kenapa:** Semakin panjang data, semakin representatif regime yang tertangkap — mengacu ke pendekatan Garnier & Solna yang memakai data sejak 2010.

**Pakai apa:**
- Sumber: [data.binance.vision](https://data.binance.vision/) untuk bulk historis (gratis, tanpa rate limit), atau Binance REST API untuk update terbaru
- Library Python: `requests` / `python-binance` / `ccxt` untuk fetch API, `pandas` untuk load dan gabungkan file CSV/ZIP

```python
# Contoh kerangka
import pandas as pd
# df_1h = pd.read_csv(...)  # dari data.binance.vision, resolusi 1H
# df_4h = pd.read_csv(...)  # resolusi 4H
```

---

## Langkah 1 — Preprocessing & Resampling Multi-Timeframe

**Apa:**
1. Hitung log-return: $r_t = \ln(P_t / P_{t-1})$
2. Pastikan tidak ada gap/missing candle (forward-fill minimal, atau exclude periode dengan gap besar)
3. Siapkan versi 1H dan 4H selaras (4H adalah agregasi dari 1H, pastikan timestamp align)

**Kenapa:** Kualitas input menentukan kualitas estimasi Hurst — data dengan gap akan merusak asumsi kontinuitas di DFA/wavelet.

**Pakai apa:** `pandas` (resample, rolling), `numpy`

```python
df['log_return'] = np.log(df['close'] / df['close'].shift(1))
df_4h = df.resample('4H', on='timestamp').agg({'close':'last', 'high':'max', 'low':'min', 'open':'first', 'volume':'sum'})
```

---

## Langkah 2 — Estimasi Hurst-DFA Robust (Ground Truth Kontinu)

**Apa:**
1. Hitung $\hat{H}(\tau_k)$ secara rolling window (mis. lebar 1 tahun untuk data harian, sesuaikan untuk 1H/4H — pertimbangkan window yang proporsional, mis. 500–1000 candle)
2. Terapkan estimator ganda (dual weighting matrix $R^1$, $R^3$ ala Garnier & Solna) untuk mengambil hasil paling robust
3. Threshold hasil ke rentang [0.05, 0.95] untuk hindari nilai singular

**Kenapa:** Ini fondasi seluruh model — nilai H inilah yang nanti dikonversi jadi label regime.

**Pakai apa:**
- Library siap pakai: `nolds` (fungsi `nolds.dfa`), atau `MFDFA` (Python package khusus multifractal DFA)
- Untuk versi wavelet ala Garnier & Solna: `PyWavelets` (`pywt`) untuk transformasi Haar, kombinasikan dengan regresi manual (`numpy.linalg.lstsq` atau `scipy.optimize`) sesuai persamaan (16)-(20) di paper referensi

```python
# Opsi cepat: pakai nolds untuk DFA klasik
import nolds
H = nolds.dfa(window_data)

# Opsi lengkap: implementasi wavelet + regresi robust custom
# mengikuti Garnier & Solna Appendix B
```

> Jika ingin memperkuat ground truth lebih jauh (opsional, sesuai diskusi sebelumnya): kombinasikan beberapa metode estimasi (DFA, R/S classic via `nolds.hurst_rs`, wavelet, periodogram) dan ambil median sebagai estimasi konsensus.

---

## Langkah 3 — Labeling Regime via Statistical Jump Model

**Apa:** Konversi deret kontinu $\hat{H}(\tau_k)$ menjadi label diskrit (persistent / random-like / anti-persistent) **tanpa** threshold naif per titik — gunakan **Statistical Jump Model** yang menghukum pergantian regime terlalu sering:

$$\min_{\Theta, S} \sum_{t} l(x_t, \theta_{s_t}) + \lambda \sum_{t} \mathbf{1}_{\{s_{t-1} \neq s_t\}}$$

**Kenapa:** Threshold sederhana menghasilkan label yang "berkedip" (flip-flop), tidak realistis secara ekonomi karena regime pasar biasanya persisten. Ini isu yang sudah kita diskusikan dan solusi ini langsung dari literatur regime-switching finansial modern (Nystrup et al., 2020; Aydınhan et al., 2024).

**Pakai apa:**
- Package: `jumpmodels` (implementasi Python untuk statistical jump model, tersedia di GitHub oleh tim Nystrup/Kolm) — cek ketersediaan dan kompatibilitas versi
- Alternatif custom: implementasi coordinate descent sederhana (bisa ditulis manual dengan `numpy`/`scipy`) jika package tidak kompatibel
- Pilih $\lambda$ via cross-validation atau grid search, evaluasi dengan melihat jumlah transisi regime yang dihasilkan (masuk akal secara historis atau tidak)

```python
# Kerangka konseptual (pseudocode jika implementasi manual)
# for lambda_val in grid:
#     states = fit_jump_model(H_series, n_states=3, jump_penalty=lambda_val)
#     evaluate_transition_count(states)
```

> **Opsional:** gunakan versi *continuous/probabilistic* jump model (Aydınhan et al., 2024) untuk mendapat label lunak (probabilitas tiap regime), berguna sebagai target soft-label di Langkah 6.

---

## Langkah 4 — Pretraining Sintetis (fBm/ARFIMA)

**Apa:** Sebelum melatih model pada data BTC riil, latih dulu Attention-BiLSTM pada data simulasi **fractional Brownian motion (fBm)** atau **ARFIMA** dengan nilai H yang **sudah diketahui pasti** (mis. H = 0.3, 0.4, 0.5, 0.6, 0.7).

**Kenapa:** Model belajar "bentuk" pola tiap regime secara bersih tanpa noise pasar riil terlebih dahulu — pendekatan yang divalidasi di literatur (*Time Series Classification with DNN Based on Hurst Exponent Analysis*). Ini juga berfungsi ganda sebagai **validasi sintetis** yang sudah direncanakan sebelumnya.

**Pakai apa:**
- Library simulasi: `fbm` (Python package untuk generate fractional Brownian motion dengan H tertentu), atau implementasi ARFIMA manual dengan `statsmodels`
- Simulasikan ratusan/ribuan sekuens per nilai H sebagai data pretraining

```python
from fbm import FBM
f = FBM(n=1024, hurst=0.7, length=1, method='daviesharte')
synthetic_series = f.fbm()
```

---

## Langkah 5 — Ekstraksi Fitur Multi-Skala via SWT

**Apa:**
1. Terapkan **Stationary Wavelet Transform** pada loglanjut-return (dan/atau harga) di tiap timeframe (1H dan 4H)
2. Hitung juga **generalized Hurst exponent** $H(q)$ untuk $q = 1, 2, 4$ sebagai fitur tambahan (menangkap derajat multifraktalitas)
3. (Opsional, jika waktu memungkinkan) terapkan wavelet shrinkage untuk denoising sebelum ekstraksi

**Kenapa:** SWT dipilih (bukan DWT biasa) karena sifatnya *shift-invariant* — tidak mengalami downsampling, sehingga hasil dekomposisi tetap selaras panjangnya dengan data asli, penting untuk model sequence seperti BiLSTM.

**Pakai apa:** `PyWavelets` (`pywt.swt`)

```python
import pywt
coeffs = pywt.swt(log_return_series, wavelet='db4', level=4)
# coeffs berisi list (cA, cD) untuk tiap level — jadikan fitur multi-kanal
```

---

## Langkah 6 — Training Attention-BiLSTM (Multi-Task)

**Apa:**
1. **Arsitektur**: BiLSTM memproses sekuens fitur (SWT multi-skala + $H(q)$ + fitur "waktu sejak regime terakhir berganti"), dilengkapi attention layer di atasnya
2. **Dua output head**:
   - Klasifikasi 3 kelas regime (softmax) — target dari Langkah 3
   - Regresi $\hat{H}$ kontinu (auxiliary task) — target dari Langkah 2
3. **Fine-tune** dari bobot hasil pretraining sintetis (Langkah 4)
4. **Loss gabungan**: weighted/focal cross-entropy (klasifikasi) + MSE (regresi), dengan bobot $\lambda_1$ sebagai hyperparameter

**Kenapa:** Multi-task learning memperkuat representasi internal model (regresi H membantu klasifikasi lebih akurat), dan fine-tuning dari sintetis mempercepat konvergensi serta mengurangi overfitting pada data BTC yang relatif terbatas.

**Pakai apa:** `PyTorch` (lebih fleksibel untuk custom multi-task loss dan attention) atau `TensorFlow/Keras`

```python
import torch, torch.nn as nn

class AttentionBiLSTM(nn.Module):
    def __init__(self, input_dim, hidden_dim, n_classes):
        super().__init__()
        self.bilstm = nn.LSTM(input_dim, hidden_dim, bidirectional=True, batch_first=True)
        self.attn = nn.Linear(hidden_dim*2, 1)
        self.classifier = nn.Linear(hidden_dim*2, n_classes)
        self.regressor = nn.Linear(hidden_dim*2, 1)

    def forward(self, x):
        h, _ = self.bilstm(x)                      # (batch, seq, hidden*2)
        attn_weights = torch.softmax(self.attn(h), dim=1)
        context = (attn_weights * h).sum(dim=1)     # (batch, hidden*2)
        return self.classifier(context), self.regressor(context), attn_weights

# loss = CE(class_out, y_class) + lambda1 * MSE(reg_out, y_H)
```

---

## Langkah 7 — Validasi Walk-Forward + Confusion Matrix

**Apa:**
1. Bagi data dengan skema **walk-forward** (expanding/rolling window), bukan random split
2. Kumpulkan prediksi dari semua fold, gabung jadi satu confusion matrix agregat
3. Hitung accuracy, precision, recall, F1 per kelas, dan **macro F1** sebagai metrik utama

**Kenapa:** Time series tidak boleh di-split acak (kebocoran data masa depan); macro F1 diprioritaskan karena kelas "random-like" biasanya dominan di data riil.

**Pakai apa:** `sklearn.model_selection.TimeSeriesSplit` (atau custom expanding window loop), `sklearn.metrics.confusion_matrix`, `classification_report`

```python
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import confusion_matrix, classification_report

tscv = TimeSeriesSplit(n_splits=5)
for train_idx, test_idx in tscv.split(X):
    # train model pada train_idx, predict pada test_idx
    pass

cm = confusion_matrix(y_true_all, y_pred_all)
print(classification_report(y_true_all, y_pred_all, target_names=['Persistent','Random-like','Anti-persistent']))
```

---

## Langkah 8 — Ablation Study & Interpretasi Attention

**Apa:**
1. Bandingkan performa beberapa varian model untuk mengisolasi kontribusi tiap komponen:
   - Baseline: Hurst-DFA murni (tanpa ML)
   - SWT + BiLSTM tanpa attention
   - SWT + Attention-BiLSTM tanpa multi-task (klasifikasi saja)
   - Model penuh (semua komponen)
2. Visualisasikan bobot attention pada titik-titik transisi regime historis (mis. crash 2018, 2020, dst.) untuk interpretasi kualitatif

**Kenapa:** Membuktikan kontribusi tiap komponen secara kuantitatif — penting untuk menjawab pertanyaan penguji soal "kenapa arsitektur ini, bukan yang lain".

**Pakai apa:** `matplotlib`/`seaborn` untuk visualisasi attention heatmap, `pandas` untuk tabel perbandingan hasil

---

## Ringkasan Tools per Langkah

| Langkah | Tools/Library Utama |
|---|---|
| 0. Akuisisi Data | `requests`, `python-binance`, `ccxt`, `pandas` |
| 1. Preprocessing | `pandas`, `numpy` |
| 2. Hurst-DFA Robust | `nolds`, `MFDFA`, `PyWavelets`, `numpy`/`scipy` (custom regresi) |
| 3. Labeling (Jump Model) | `jumpmodels` (jika tersedia) atau implementasi custom `numpy`/`scipy` |
| 4. Pretraining Sintetis | `fbm`, `statsmodels` (ARFIMA) |
| 5. Fitur SWT | `PyWavelets` (`pywt.swt`) |
| 6. Attention-BiLSTM | `PyTorch` atau `TensorFlow/Keras` |
| 7. Validasi | `scikit-learn` (`TimeSeriesSplit`, `confusion_matrix`, `classification_report`) |
| 8. Ablation & Visualisasi | `matplotlib`, `seaborn`, `pandas` |

---

## Catatan Penting

- **Urutan Langkah 2 → 3 → 4 bisa paralel**: pretraining sintetis (Langkah 4) tidak bergantung pada hasil labeling data riil (Langkah 3), jadi bisa dikerjakan lebih dulu/bersamaan untuk hemat waktu.
- **Jangan lewati Langkah 7 (walk-forward)** — ini yang membuktikan model bekerja secara real-time-compatible, sesuai kebutuhan Anda di awal.
- Semua langkah di atas **100% berbasis data harga** (tidak ada order flow/order book/data eksternal), sesuai kesepakatan untuk tetap dalam cakupan judul skripsi.
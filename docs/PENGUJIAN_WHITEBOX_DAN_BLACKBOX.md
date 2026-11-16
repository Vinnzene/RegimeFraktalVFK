# Dokumentasi Lengkap Pengujian White-Box dan Black-Box (Jira)

**Proyek:** `RegimeFraktalVFK` (BTC/USDT & Multi-Asset Regime Identification Dashboard)  
**Tujuan Dokumen:** Menjadi rujukan siap pakai untuk **Bab 3 (Metodologi Pengujian)**, **Bab 4 (Hasil Pengujian Perangkat Lunak)**, dan pegangan saat menjawab pertanyaan Dosen Penguji mengenai perbedaan serta implementasi **White-Box Testing** dan **Black-Box Testing (Jira)**.

---

## 1. Perbedaan Konseptual & Posisi di Skripsi Anda

| Aspek | White-Box Testing (*Pengujian Kotak Putih*) | Black-Box Testing (*Pengujian Kotak Hitam*) |
| :--- | :--- | :--- |
| **Sudut Pandang** | Menguji **ke dalam kode sumber (*internal logic & code structure*)**. | Menguji **dari luar sistem (*user interface & API input-output*)** tanpa melihat kode internal. |
| **Fokus Utama** | Memastikan seluruh jalur percabangan `if-else`, rumus matematika (Hurst-DFA), dan aturan kausalitas (SWT tanpa *look-ahead bias*) bebas dari kesalahan logika. | Memastikan seluruh fitur fungsional pada website Next.js, grafik TradingView, endpoint FastAPI, dan Bot Telegram berjalan sesuai spesifikasi kebutuhan (PRD). |
| **Metode RPL** | 1. *Basis Path Testing* & *Cyclomatic Complexity* $V(G)$ <br>2. *Automated Unit & Mathematical Invariant Testing* | 1. *Equivalence Partitioning* (Partisi Input Valid vs Invalid) <br>2. *End-to-End Functional Test Cases* & *Defect Tracking* |
| **Alat (*Tools*)** | **`pytest`** (251 pengujian otomatis) & **GitHub Actions CI** (`.github/workflows/ci.yml`) | **Atlassian Jira Software** (`Project Key: RFVFK` — Tiket *Test Case* & *Bug*) |

---

## 2. Pengujian White-Box (*White-Box Testing*)

### 2.1 *Basis Path Testing* & *Cyclomatic Complexity* $V(G)$
Pengujian jalur dasar (*Basis Path Testing*) dilakukan pada algoritma keputusan inti sistem, yaitu fungsi **`label_from_exponents()`** pada file `backend/app/services/regime_labeling.py` (baris 130–173).

#### A. Kode Sumber yang Diuji (`regime_labeling.py`)
```python
def label_from_exponents(
    hurst: float,
    alpha: float,
    hurst_threshold: Sequence[float],
    dfa_threshold: Sequence[float],
    efficiency_ratio: Optional[float] = None,
    soft_consensus: bool = True,
    er_threshold: Sequence[float] = (0.35, 0.60),
) -> str:
    h_class = _bucket(hurst, hurst_threshold[0], hurst_threshold[1])
    a_class = _bucket(alpha, dfa_threshold[0], dfa_threshold[1])
    if h_class is None or a_class is None:                                  # Predikat P1
        return UNCERTAIN_RULE
    if h_class == a_class:                                                  # Predikat P2
        if (                                                                # Predikat P3
            soft_consensus
            and h_class == RANDOM_LIKE
            and efficiency_ratio is not None
            and np.isfinite(efficiency_ratio)
            and efficiency_ratio >= 0.85
        ):
            return PERSISTENT
        return h_class
    if not soft_consensus or efficiency_ratio is None or not np.isfinite(efficiency_ratio): # Predikat P4
        return UNCERTAIN_RULE
    pair = {h_class, a_class}
    if pair == {PERSISTENT, RANDOM_LIKE} and efficiency_ratio >= float(er_threshold[1]):    # Predikat P5
        return PERSISTENT
    if pair == {ANTI_PERSISTENT, RANDOM_LIKE} and efficiency_ratio <= float(er_threshold[0]): # Predikat P6
        return ANTI_PERSISTENT
    return UNCERTAIN_RULE
```

#### B. Perhitungan *Cyclomatic Complexity* $V(G)$
Berdasarkan jumlah titik keputusan (*predicate nodes* $P = 6$), kompleksitas siklomatik McCabe dihitung sebagai:
$$V(G) = P + 1 = 6 + 1 = 7 \text{ jalur independen}$$

#### C. Matriks Eksekusi 7 Jalur Independen (*Basis Paths*)
| ID Jalur | Alur Predikat | Kasus Uji (Input Parameter) | Output yang Diharapkan | Hasil Eksekusi (`pytest`) |
| :--- | :--- | :--- | :--- | :---: |
| **Path 1** | `P1 = True` | `hurst = NaN`, `alpha = 0.55` | `uncertain_rule` | **PASSED** |
| **Path 2** | `P1=False -> P2=True -> P3=True` | `hurst = 0.50`, `alpha = 0.50`, `ER = 0.90` | `persistent` | **PASSED** |
| **Path 3** | `P1=False -> P2=True -> P3=False` | `hurst = 0.62`, `alpha = 0.65`, `ER = 0.50` | `persistent` | **PASSED** |
| **Path 4** | `P1=False -> P2=False -> P4=True` | `hurst = 0.62`, `alpha = 0.50`, `soft_consensus = False` | `uncertain_rule` | **PASSED** |
| **Path 5** | `P1=False -> P2=False -> P4=False -> P5=True` | `hurst = 0.62`, `alpha = 0.50`, `ER = 0.70` | `persistent` | **PASSED** |
| **Path 6** | `P1=False -> P2..P5=False -> P6=True` | `hurst = 0.38`, `alpha = 0.50`, `ER = 0.25` | `anti_persistent` | **PASSED** |
| **Path 7** | `P1..P6 = False` (Konflik diametral) | `hurst = 0.65` (*Pers*), `alpha = 0.35` (*Anti*), `ER = 0.50` | `uncertain_rule` | **PASSED** |

---

### 2.2 *Automated Unit & Invariant Testing* (`pytest`)
Seluruh modul di `backend/tests/` diuji otomatis menggunakan kerangka kerja `pytest` (total **251 unit test lulus 100%**):

| File Unit Test | Modul yang Diuji | Invarian Matematika / Logika yang Diverifikasi | Status |
| :--- | :--- | :--- | :---: |
| `test_causal_swt.py` | `app/services/swt.py` | Memotong deret pada indeks $t=400$ vs deret penuh $N=600$; membuktikan koefisien `causal_swt_at` identik hingga toleransi $10^{-12}$ (**0% *look-ahead bias***). | **PASSED** |
| `test_hurst_dfa.py` | `app/services/hurst_dfa.py` | Memverifikasi nilai $H$ dan $\alpha$ berada pada rentang valid $[0.05, 0.95]$ dan konsisten terhadap deret acak (*random walk* $H \approx 0.5$). | **PASSED** |
| `test_synthetic_regimes.py` | Estimator & Labeling | Memverifikasi daya pisah estimator pada deret sintetis *fractional Brownian motion (fBm)* dengan $H \in \{0.3, 0.5, 0.7\}$. | **PASSED** |
| `test_ai_detector_abstain.py` | `regime_labeling.py` (`apply_tau`) | Memastikan prediksi dengan $\max(P) < \tau$ otomatis dialihkan ke `uncertain_lowconf`. | **PASSED** |
| `test_threshold_source.py` | `resolve_thresholds` | Memastikan mode `train_only` hanya menghitung kuantil dari bagian *Train* tanpa menyentuh *Validation/Test*. | **PASSED** |
| `test_regressions.py` | `app/db/repository.py` | Memastikan hasil pembaruan fitur inkremental identik 100% dengan perhitungan penuh dari awal. | **PASSED** |

---

## 3. Pengujian Black-Box (*Black-Box Testing* via Atlassian Jira)

Pada tahap **Black-Box Testing**, pengujian dilakukan dari sisi antarmuka pengguna (Browser) dan kontrak REST API menggunakan **Atlassian Jira Software** (`Project Key: RFVFK`). Detail lengkap skenario uji dan siklus hidup bug terdapat pada dokumen `docs/PANDUAN_PENGUJIAN_QA_JIRA_DAN_UAT.md`.

### 3.1 Pengujian *Equivalence Partitioning* (Input Valid vs Tidak Valid)
| Endpoint / Fitur | Kelas Partisi Input Valid | Kelas Partisi Input Tidak Valid (Negatif) | Respons Sistem Aktual | Status |
| :--- | :--- | :--- | :--- | :---: |
| `GET /api/v1/ohlcv` & `/regime` | `symbol=BTCUSDT`, `timeframe` $\in$ `{1h, 4h, 1d}` | `symbol=BTC;DROP`, `timeframe=99m` | Menolak dengan `HTTP 400 Bad Request` (`validate_identifiers`). | **PASSED** |
| `GET /api/v1/model/compare` | Parameter ambang $\tau \in [0.0, 1.0]$ (mis. `tau=0.40`) | Parameter $\tau < 0$ atau $\tau > 1$ (mis. `tau=1.5`) | Menolak dengan `HTTP 422 Unprocessable Entity` (validasi Pydantic). | **PASSED** |
| `GET /api/v1/model/walk-forward-timeline` | Kombinasi 23 aset-timeframe tersedia (mis. `BTCUSDT` `4h`) | Kombinasi simbol yang tidak terdaftar (mis. `UNKNOWN` `1h`) | Mengembalikan `HTTP 404 Not Found` dengan pesan terstruktur tanpa crash. | **PASSED** |

### 3.2 Ringkasan Matriks *Test Case* Fungsional di Jira (`RFVFK-TC01` s/d `RFVFK-TC17`)
Selain 15 skenario utama di `docs/PANDUAN_PENGUJIAN_QA_JIRA_DAN_UAT.md`, pengujian juga mencakup modul **Walk-Forward Multi-Aset (2019–2026)**:
* **`RFVFK-TC16` (API Walk-Forward Multi-Aset):** Memanggil `GET /api/v1/model/walk-forward-multi-asset` $\rightarrow$ Mengembalikan ringkasan akurasi 12 aset lintas kelas (rata-rata BA 88,24%) dalam waktu $<50\text{ ms}$. (**PASSED**)
* **`RFVFK-TC17` (UI Grafik TradingView Walk-Forward 2019–2026):** Membuka halaman `/walk-forward-evaluation`, memilih aset (`BTCUSDT`, `ETHUSDT`, `PAXGUSDT`, dll.) dan timeframe (`1h`, `4h`, `1d`) $\rightarrow$ Grafik *TradingView Lightweight Charts* merender candlestick historis 2019–2026 beserta pita warna regime *out-of-sample* dan tabel rincian per tahun (*yearly folds*) secara reaktif. (**PASSED**)

"""Endpoint metadata: config aktif + hash, dan konten metodologi."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import REGIME_CATEGORIES, get_config, reload_config

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


@router.get("/config")
def read_config() -> dict:
    cfg = get_config()
    return {
        "config": cfg.canonical(),
        "config_hash": cfg.config_hash,
        "short_hash": cfg.short_hash,
        "regime_categories": REGIME_CATEGORIES,
    }


@router.post("/config/reload")
def do_reload_config() -> dict:
    cfg = reload_config()
    return {"config_hash": cfg.config_hash, "short_hash": cfg.short_hash}


@router.get("/methodology")
def methodology() -> dict:
    cfg = get_config()
    lo_h, hi_h = cfg.analysis.hurst_threshold
    return {
        "config_hash": cfg.config_hash,
        "sections": [
            {
                "id": "hurst",
                "title": "Hurst Exponent (R/S)",
                "formula": r"H = \frac{\log(R/S)}{\log(n)}",
                "body": (
                    "Mengukur kecenderungan persistensi deret. H > 0.5 berarti "
                    "gerakan cenderung berlanjut, H < 0.5 cenderung berbalik, "
                    "H = 0.5 menyerupai random walk. Dihitung pada log-return, "
                    "bukan harga level, karena harga bersifat non-stasioner "
                    "(unit root) sehingga H akan selalu mendekati 1."
                ),
            },
            {
                "id": "dfa",
                "title": "Detrended Fluctuation Analysis (DFA)",
                "formula": r"F(s) \sim s^{\alpha}",
                "body": (
                    "Menghitung RMS fluktuasi setelah tren linear dibuang pada "
                    "tiap segmen berukuran s. Kemiringan garis log F(s) terhadap "
                    "log s adalah alpha. DFA lebih tahan terhadap tren "
                    "dibanding R/S. Interpretasi alpha mengikuti Maraun et al. "
                    "(2004): kemiringan log-log saja belum cukup untuk "
                    "menyimpulkan long-range dependence."
                ),
            },
            {
                "id": "threshold",
                "title": "Kriteria Regime",
                "formula": (
                    rf"R = \begin{{cases}} \text{{Anti-persistent}} & H < {lo_h} \\ "
                    rf"\text{{Random-like}} & {lo_h} \le H \le {hi_h} \\ "
                    rf"\text{{Persistent}} & H > {hi_h} \end{{cases}}"
                ),
                "body": (
                    f"Ambang {lo_h}/{hi_h} adalah rancangan awal yang diuji "
                    "sensitivitasnya, bukan angka final. Kriteria yang sama "
                    "diterapkan pada DFA alpha. Bila Hurst dan DFA menghasilkan "
                    "kelas berbeda, window ditandai uncertain_rule dan tidak "
                    "dipaksa masuk salah satu dari tiga kategori."
                ),
            },
            {
                "id": "swt",
                "title": "Stationary Wavelet Transform",
                "formula": r"x(t) = A_J(t) + \sum_{j=1}^{J} D_j(t)",
                "body": (
                    "SWT tidak melakukan desimasi sehingga tiap level punya "
                    "panjang sama dengan sinyal asli. Di sistem ini SWT dihitung "
                    "ulang per window memakai data <= t (causal), karena filter "
                    "simetris pywt.swt pada seluruh deret akan menyerap sampel "
                    "setelah t dan menimbulkan look-ahead bias."
                ),
            },
            {
                "id": "attention",
                "title": "BiLSTM + Attention",
                "formula": r"\alpha_t = \frac{\exp(e_t)}{\sum_k \exp(e_k)},\quad c = \sum_t \alpha_t h_t",
                "body": (
                    "BiLSTM membaca sekuens dua arah; attention memberi bobot "
                    "alpha_t pada tiap timestep sehingga kontribusi tiap bagian "
                    "sekuens dapat diperiksa. Bobot inilah yang divisualisasikan "
                    "di halaman /attention."
                ),
            },
            {
                "id": "leakage",
                "title": "Pencegahan Look-Ahead Bias",
                "formula": r"X_t = f(x_{\le t}),\quad Y_t = \text{Regime}(W_{t+h})",
                "body": (
                    "Fitur hanya memakai data sampai t. Target adalah regime "
                    "window ke depan sejauh h. Split bersifat time-based tanpa "
                    f"shuffle, dan pada tiap batas dibuang {cfg.model.purge_gap} "
                    "bar (purge gap = L + h) agar window training tidak tumpang "
                    "tindih dengan window test."
                ),
            },
        ],
    }

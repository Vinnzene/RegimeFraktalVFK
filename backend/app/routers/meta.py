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
    from app.services import ai_detector

    cfg = get_config()
    # Ambang kelas detektor resmi (kebenaran dasar H), bukan ambang `fixed` lama di config.
    try:
        lo_h, hi_h = ai_detector.meta()["thresholds"]
    except ai_detector.DetectorUnavailable:
        lo_h, hi_h = 0.47, 0.53
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
                    f"Detektor AI mempelajari kelas ini dari deret sintetis yang "
                    f"nilai H-nya diketahui, dengan ambang {lo_h}/{hi_h} yang "
                    "diturunkan dari titik impas ekonomi strategi momentum dan "
                    "mean-reversion setelah biaya (sensitivitas 0,45/0,55). Label "
                    "klasik R/S dan DFA memakai ambang kuantil 1/3 dan 2/3 data "
                    "latih; bila keduanya tidak sepakat, window ditandai "
                    "uncertain_rule."
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
                    "sekuens dapat diperiksa. Pada detektor, bobotnya hampir "
                    "seragam (entropi 0,92) dan attention tidak terbukti menambah "
                    "akurasi (H3): model memakai informasi dari seluruh window."
                ),
            },
            {
                "id": "leakage",
                "title": "Pencegahan Look-Ahead Bias",
                "formula": r"X_t = f(x_{t-L+1}, \dots, x_t),\quad \hat{Y}_t = \text{Regime}(W_t)",
                "body": (
                    "Fitur hanya memakai data sampai t dan target adalah regime "
                    "window yang sama (identifikasi, bukan prediksi). Detektor "
                    "dilatih pada data sintetis, sehingga seluruh riwayat BTC "
                    "adalah data luar sampel. Pada eksperimen berlabel BTC, split "
                    "time-based tanpa shuffle dengan purge 500 bar di tiap batas; "
                    "split acak terbukti menggelembungkan akurasi +0,12 sampai +0,18."
                ),
            },
        ],
    }

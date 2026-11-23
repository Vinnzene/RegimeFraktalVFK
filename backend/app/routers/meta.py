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
    # Ambang label train-only model identifikasi resmi (1H), bukan ambang `fixed` lama di config.
    try:
        thr = ai_detector.meta("1h")["label_thresholds_train_only"]
        (h_lo, h_hi), (a_lo, a_hi) = thr["hurst"], thr["dfa"]
    except ai_detector.DetectorUnavailable:
        h_lo, h_hi, a_lo, a_hi = 0.5718, 0.5985, 0.4778, 0.5207
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
                "title": "Kriteria Regime (Trend-Aware Soft Consensus)",
                "formula": (
                    rf"R = \begin{{cases}} \text{{Persistent}} & H > {h_hi} \wedge \alpha > {a_hi} \\ "
                    rf"\text{{Anti-persistent}} & H < {h_lo} \wedge \alpha < {a_lo} \\ "
                    rf"\text{{Random-like}} & \text{{keduanya di dalam pita}} \\ "
                    rf"\text{{uncertain\_rule}} & \text{{tidak sepakat}} \end{{cases}}"
                ),
                "body": (
                    f"Ambang = kuantil 1/3 dan 2/3 partisi latih 1H (Hurst R/S {h_lo}/{h_hi}, DFA-1 {a_lo}/{a_hi}). "
                    "Ketidaksepakatan bertetangga diselesaikan dengan skor kuantil Efficiency Ratio multiskala: "
                    "persistent bila ER_q >= 0,60, anti-persistent bila ER_q <= 0,35; konflik persistent vs "
                    "anti-persistent tetap uncertain_rule. Model identifikasi (Hybrid Attention-BiLSTM) "
                    "dilatih untuk mengenali label ini pada jendela yang sama (h = 0)."
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
                    "sekuens dapat diperiksa. Pada ablasi pipeline Bab 4, mengganti "
                    "attention dengan global average pooling memberi akurasi setara "
                    "(1H 81,00% vs 81,00%), jadi attention tidak terbukti menambah akurasi."
                ),
            },
            {
                "id": "leakage",
                "title": "Pencegahan Look-Ahead Bias",
                "formula": r"X_t = f(x_{t-L+1}, \dots, x_t),\quad \hat{Y}_t = \text{Regime}(W_t)",
                "body": (
                    "Fitur hanya memakai data sampai t dan target adalah regime "
                    "window yang sama (identifikasi, h = 0, bukan prediksi). Model "
                    "dilatih pada partisi latih BTC (70%), jadi riwayat sebelum batas "
                    "latih adalah data latih model. Split time-based tanpa shuffle "
                    "dengan purge 500 bar di tiap batas; ambang label dari partisi latih saja; "
                    "split acak terbukti menggelembungkan akurasi +0,12 sampai +0,18."
                ),
            },
        ],
    }

"""Gambar tambahan untuk naskah skripsi (diagram dan grafik yang belum ada di ml/artifacts/figures).

    python docs/naskah/buat_gambar.py

Angka grafik disalin dari ml/artifacts/synthetic_benchmark.md, regime_change_study.md,
multiscale_study.md, dan fast_detection_study.md.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).parent / "gambar"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})

BIRU, BIRU_MUDA, ORANYE, ABU = "#1f5fa8", "#9ecae1", "#e8772e", "#8c8c8c"
INK, INK2 = "#222222", "#555555"


def kotak(ax, x, y, w, h, teks, warna="#eef4fb", tepi=BIRU, ukuran=9, tebal=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=warna, ec=tepi, lw=1.2))
    ax.text(x + w / 2, y + h / 2, teks, ha="center", va="center", fontsize=ukuran, color=INK,
            fontweight="bold" if tebal else "normal", wrap=True)


def panah(ax, a, b, gaya="-|>"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=gaya, mutation_scale=12, lw=1.2, color=INK2))


def kanvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def simpan(fig, nama):
    fig.savefig(OUT / nama, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def tahapan_penelitian():
    fig, ax = kanvas(10, 7.2)
    kotak(ax, 0.3, 6.1, 4.2, 0.8, "Data OHLCV BTC/USDT 1H & 4H\n(Binance, 2019–2026)", tebal=True)
    kotak(ax, 5.5, 6.1, 4.2, 0.8, "Deret sintetis fGn, H diketahui\nSkenario S1–S5", "#fff1e6", ORANYE, tebal=True)
    kotak(ax, 0.3, 4.8, 4.2, 0.8, "Pra-pemrosesan kausal: buang candle\nberjalan, log-return, jendela L=500, s=4")
    kotak(ax, 2.9, 3.5, 4.2, 0.8, "Fitur: sekuens PS 32×11 + 50 fitur\nstruktural (termasuk 12 energi SWT)")
    kotak(ax, 0.3, 2.2, 4.2, 0.8, "Fase 0: label konsensus Hurst R/S–DFA\nmodel dilatih & diuji pada label BTC")
    kotak(ax, 5.5, 2.2, 4.2, 0.8, "Fase 1: benchmark berkebenaran dasar\nHurst-DFA klasik vs Attention-BiLSTM", "#fff1e6", ORANYE)
    kotak(ax, 5.5, 0.95, 4.2, 0.8, "Detektor resmi: Hybrid PS latih-sintetis\n+ studi kecepatan, abstain, multi-skala", "#e6f2e6", "#2e7d32", tebal=True)
    kotak(ax, 0.0, 0.0, 3.1, 0.65, "Uji generalisasi 20 aset", ukuran=8.5)
    kotak(ax, 3.45, 0.0, 3.1, 0.65, "Fase 2: pemilihan strategi", ukuran=8.5)
    kotak(ax, 6.9, 0.0, 3.1, 0.65, "Sistem web + Telegram", ukuran=8.5)
    panah(ax, (2.4, 6.1), (2.4, 5.6))
    panah(ax, (2.4, 4.8), (4.0, 4.3))
    panah(ax, (7.6, 6.1), (6.2, 4.3))
    panah(ax, (4.0, 3.5), (2.4, 3.0))
    panah(ax, (6.0, 3.5), (7.6, 3.0))
    panah(ax, (7.6, 2.2), (7.6, 1.75))
    for x in (1.55, 5.0, 8.45):
        panah(ax, (7.6, 0.95), (x, 0.65))
    simpan(fig, "diagram_tahapan_penelitian.png")


def arsitektur_model():
    fig, ax = kanvas(10, 5.6)
    kotak(ax, 0.2, 4.6, 3.6, 0.7, "Sekuens PS (32 langkah × 11 kanal)", tebal=True)
    kotak(ax, 0.2, 3.55, 3.6, 0.7, "BiLSTM 64 unit per arah\n(return_sequences) → 32 × 128")
    kotak(ax, 0.2, 2.5, 3.6, 0.7, "Dropout 0,25")
    kotak(ax, 0.2, 1.45, 3.6, 0.7, "Attention pooling aditif\n→ vektor konteks 128")
    kotak(ax, 6.2, 4.6, 3.6, 0.7, "50 fitur struktural\n(VR, AC, H(q), energi SWT, sebaran)", "#fff1e6", ORANYE, tebal=True)
    kotak(ax, 6.2, 3.55, 3.6, 0.7, "Dense 64 ReLU + Dropout 0,25", "#fff1e6", ORANYE)
    kotak(ax, 6.2, 2.5, 3.6, 0.7, "Dense 32 ReLU", "#fff1e6", ORANYE)
    kotak(ax, 2.6, 0.75, 4.8, 0.55, "Concatenate (160) → Dropout 0,25 → Dense 64 ReLU", "#f2f2f2", ABU, ukuran=8.5)
    kotak(ax, 3.2, 0.0, 3.6, 0.5, "Softmax 3 kelas: P / R / A", "#e6f2e6", "#2e7d32", tebal=True)
    for y in (4.6, 3.55, 2.5):
        panah(ax, (2.0, y), (2.0, y - 0.35))
    for y in (4.6, 3.55):
        panah(ax, (8.0, y), (8.0, y - 0.35))
    panah(ax, (2.0, 1.45), (3.4, 1.33))
    panah(ax, (8.0, 2.5), (6.6, 1.33))
    panah(ax, (5.0, 0.75), (5.0, 0.5))
    simpan(fig, "diagram_arsitektur_model.png")


def arsitektur_sistem():
    fig, ax = kanvas(10, 5.4)
    kotak(ax, 0.1, 4.3, 2.6, 0.8, "Binance Vision /\nYahoo Finance", "#f2f2f2", ABU)
    kotak(ax, 3.4, 4.3, 3.2, 0.8, "Ingestion + cache Parquet\n(candle tertutup saja)")
    kotak(ax, 0.1, 2.75, 3.0, 1.0, "Estimator Hurst R/S & DFA\n(pembanding)")
    kotak(ax, 3.5, 2.75, 3.0, 1.0, "Fitur PS + struktural\n→ Detektor Hybrid PS\n(TensorFlow, cache .npz)", "#e6f2e6", "#2e7d32")
    kotak(ax, 6.9, 2.75, 3.0, 1.0, "Penjadwal: pembaruan\ndata & cek pergantian regime")
    kotak(ax, 3.4, 1.4, 3.2, 0.8, "FastAPI  /api/v1/*", tebal=True)
    kotak(ax, 0.1, 0.0, 3.0, 0.9, "Next.js 14 dashboard\n(Caddy :80, satu alamat)")
    kotak(ax, 3.5, 0.0, 3.0, 0.9, "Firebase Auth + Firestore\n(akun, chat ID Telegram)", "#fff1e6", ORANYE)
    kotak(ax, 6.9, 0.0, 3.0, 0.9, "Bot Telegram\n(long polling, notifikasi)")
    panah(ax, (2.7, 4.7), (3.4, 4.7))
    panah(ax, (4.2, 4.3), (1.6, 3.75))
    panah(ax, (5.0, 4.3), (5.0, 3.75))
    panah(ax, (5.8, 4.3), (8.4, 3.75))
    panah(ax, (1.6, 2.75), (4.0, 2.2))
    panah(ax, (5.0, 2.75), (5.0, 2.2))
    panah(ax, (8.4, 2.75), (8.4, 0.9))
    panah(ax, (4.0, 1.4), (1.6, 0.9), "<|-|>")
    panah(ax, (5.0, 1.4), (5.0, 0.9), "<|-|>")
    panah(ax, (6.0, 1.4), (7.5, 0.9))
    simpan(fig, "diagram_arsitektur_sistem.png")


def grafik_benchmark():
    skenario = ["S1\nbersih", "S2\nekor tebal", "S3\nvolatilitas", "S4\nmirip kripto", "S5\nberganti"]
    seri = [
        ("Konsensus R/S–DFA naif", [0.369, 0.330, 0.302, 0.268, 0.120], ABU),
        ("VR(2) terkalibrasi (klasik terbaik)", [0.795, 0.748, 0.662, 0.654, 0.338], BIRU_MUDA),
        ("Hybrid PS Attention-BiLSTM (M-kripto)", [0.863, 0.848, 0.819, 0.813, 0.276], BIRU),
    ]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    lebar = 0.26
    for i, (nama, nilai, warna) in enumerate(seri):
        xs = [k + (i - 1) * (lebar + 0.02) for k in range(len(skenario))]
        ax.bar(xs, nilai, lebar, color=warna, label=nama, edgecolor="white", linewidth=1)
        if i != 1:
            for x, v in zip(xs, nilai):
                ax.text(x, v + 0.015, f"{v:.2f}".replace(".", ","), ha="center", fontsize=7.5, color=INK)
    ax.axhline(1 / 3, ls="--", lw=1, color=INK2)
    ax.text(4.45, 0.345, "tebakan acak", fontsize=8, color=INK2, ha="right")
    ax.set_xticks(range(len(skenario)), skenario)
    ax.set_ylabel("Balanced accuracy (uji)")
    ax.set_ylim(0, 1)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5", lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3)
    simpan(fig, "grafik_benchmark_sintetis.png")


def grafik_tradeoff():
    titik = [
        ("D0 resmi (500)", 296, 0.818, BIRU),
        ("M2 1H+4H", 424, 0.847, ORANYE),
        ("M3 1H+4H+1D", 403, 0.857, ORANYE),
        ("M4 jendela 2.000", 891, 0.897, ORANYE),
        ("A latih pergantian", 120, 0.680, ABU),
        ("B0 jendela 256", 177, 0.749, ABU),
        ("B 256 + latih pergantian", 72, 0.636, ABU),
    ]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for nama, x, y, w in titik:
        ax.scatter(x, y, s=70, color=w, edgecolor="white", linewidth=1.5, zorder=3)
        dx = -12 if x > 800 else 12
        ax.annotate(nama, (x, y), xytext=(dx, 6), textcoords="offset points", fontsize=8, color=INK,
                    ha="right" if x > 800 else "left")
    ax.set_xlabel("Median keterlambatan deteksi pergantian (bar) — lebih kiri lebih cepat")
    ax.set_ylabel("BA S4 (kondisi stabil)")
    ax.set_xlim(0, 1000)
    ax.set_ylim(0.6, 0.93)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(color="#e5e5e5", lw=0.6)
    ax.set_axisbelow(True)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=c, label=t) for t, c in
                       [("Detektor resmi", BIRU), ("Multi-skala / jendela panjang", ORANYE), ("Deteksi cepat", ABU)]],
              frameon=False, fontsize=8, loc="lower right")
    simpan(fig, "grafik_tradeoff_kecepatan.png")


if __name__ == "__main__":
    tahapan_penelitian()
    arsitektur_model()
    arsitektur_sistem()
    grafik_benchmark()
    grafik_tradeoff()
    print("selesai:", sorted(p.name for p in OUT.glob("*.png")))

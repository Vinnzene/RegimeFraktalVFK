"""Tulis ml/artifacts/review/blackbox_evidence.md dari blackbox_evidence.json + knf02_timing.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "review"
ev = json.loads((R / "blackbox_evidence.json").read_text(encoding="utf-8"))
kn = json.loads((R / "knf02_timing.json").read_text(encoding="utf-8"))
S = ev["scenarios"]


def utc(t: int) -> str:
    return datetime.fromtimestamp(int(t), timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def img(p) -> str:
    ps = p if isinstance(p, list) else [p]
    return "<br>".join(f"`{x}`" for x in ps if x)


def st(k: str) -> str:
    return "**Sesuai**" if S[k]["pass"] else "**Tidak sesuai**"


b2 = S["BB-02"]["output"]
j = b2["job_500"]
o1, o3, o4, o5, o6, o7 = (S[k]["output"] for k in ("BB-01", "BB-03", "BB-04", "BB-05", "BB-06", "BB-07"))
lw, ue = o3["latest_window"], o3["uncertain_example"]
f4 = lambda v: f"{v:.4f}".replace(".", ",")  # noqa: E731
nd = lambda n: f"{int(n):,}".replace(",", ".")  # noqa: E731

rows = [
    ("BB-01", "Memuat data", "Buka Ringkasan; `GET /api/v1/data/status`",
     f"1H {nd(o1['rows']['1h'])} bar, 4H {nd(o1['rows']['4h'])} bar (bar terakhir 1H {utc(o1['last_time']['1h'])}); grafik harga tampil",
     "68.366 dan 17.101 bar, grafik tampil", st("BB-01"), img(S["BB-01"]["screenshot"])),
    ("BB-02", "Menyiapkan data", "Analisis Aset BTCUSDT Binance 1H: 300 bar, lalu 500 bar",
     f"300 bar → HTTP {b2['backend_300']['status']}, UI: “{b2['ui_300_message']}”. 500 bar → status {j['status']}, "
     f"{j['n_bars']} candle tertutup = {j['n_returns']} log-return, {j['windows_identified']} jendela teridentifikasi; "
     f"candle terakhir {utc(j['last_bar_open_time'])} sudah tutup ({utc(j['last_bar_close_time'])} ≤ waktu uji {utc(j['checked_at'])})",
     "300 ditolak dengan pesan jelas (422); 500 diproses; candle berjalan dibuang", st("BB-02"), img(S["BB-02"]["screenshot"])),
    ("BB-03", "Memberi label", "Buka Hurst-DFA Klasik 1H",
     f"{nd(o3['windows'])} jendela (stride {o3['stride']}); jendela terbaru {utc(lw['time'])}: H {f4(lw['hurst'])}, α {f4(lw['dfa_alpha'])}, "
     f"ER_q {f4(lw['efficiency_ratio'])} → {lw['regime']}. Contoh uncertain_rule {utc(ue['time'])}: H {f4(ue['hurst'])}, α {f4(ue['dfa_alpha'])}, "
     f"ER_q {f4(ue['efficiency_ratio'])}",
     "H, α, ER, dan label tampil per jendela; ada contoh uncertain_rule", st("BB-03"), img(S["BB-03"]["screenshot"])),
    ("BB-04", "Membentuk fitur", "Buka Wavelet; `GET /api/v1/analysis/features?tf=1h`",
     f"Komponen SWT {', '.join(o4['swt_components'])}; sekuens PS {o4['ps_shape'][0]}×{o4['ps_shape'][1]} "
     f"({', '.join(o4['ps_channels'])}); fitur ringkasan {o4['summary_length']} (… {', '.join(o4['summary_names_last6'])})",
     "SWT 4 level tampil; 56 fitur ringkasan; sekuens 32×14", st("BB-04"), img(S["BB-04"]["screenshot"])),
    ("BB-05", "Identifikasi", "Buka Ringkasan dan Fokus Model 1H",
     f"Label {o5['current_regime']}; probabilitas " + ", ".join(f"{k} {v * 100:.1f}%" for k, v in o5["probabilities"].items())
     + f" (jumlah {o5['prob_sum'] * 100:.2f}%); keyakinan rendah: {o5['low_confidence']}; attention {o5['attention_steps']} langkah, "
     f"jumlah {o5['attention_sum']:.4f}, entropi {o5['attention_entropy']:.3f}",
     "Label, 3 probabilitas berjumlah 100%, keyakinan, dan bobot attention tampil", st("BB-05"), img(S["BB-05"]["screenshot"])),
    ("BB-06", "Perbandingan 1H dan 4H", "Buka Hurst-DFA 1H vs 4H",
     f"1H {nd(o6['1h']['windows'])} jendela (stride {o6['1h']['stride']}, {nd(o6['1h']['switches'])} perpindahan, aktif {o6['1h']['current']}); "
     f"4H {nd(o6['4h']['windows'])} jendela (stride {o6['4h']['stride']}, {nd(o6['4h']['switches'])} perpindahan, aktif {o6['4h']['current']})",
     "Kedua timeframe tampil berdampingan, jumlah jendela sama dengan naskah (16.967 / 8.301)", st("BB-06"), img(S["BB-06"]["screenshot"])),
    ("BB-07", "Pengujian identifikasi", "Buka Hasil Uji Identifikasi 1H lalu 4H",
     " ".join(f"{tf.upper()}: backtest {c['backtest']}, per kelas " + ", ".join(f"{k} {v}" for k, v in c["backtest_per_class"].items())
              + f"; fold {' · '.join(c['folds'])}; gabungan {c['pooled']}; sama dengan JSON: {c['equal_to_summary']}." for tf, c in o7.items()),
     "Benar per kelas dan per fold tampil, angka = updated_eval_summary.json", st("BB-07"), img(S["BB-07"]["screenshot"])),
]

md = ["# Bukti pengujian black-box (aplikasi berjalan)", "",
      f"Dijalankan {ev['run_at']} WIB pada aplikasi lokal (backend FastAPI :8000, frontend `next start` :3000, sesi demo), "
      "data snapshot naskah (BTCUSDT 1H 68.366 bar, 4H 17.101 bar s.d. 22 Okt 2026). Skrip: `ml/src/review_blackbox.py`, "
      "data mentah: `blackbox_evidence.json`, tangkapan layar: `docs/naskah/gambar/blackbox/`.", "",
      "| Kode | Skenario | Masukan | Keluaran aktual | Harapan | Status | Tangkapan layar |", "|---|---|---|---|---|---|---|"]
for r in rows:
    md.append("| " + " | ".join(x.replace("|", "\\|").replace("\n", " ") for x in r) + " |")
md += ["", f"Ringkasan: {sum(v['pass'] for v in S.values())} dari {len(S)} skenario sesuai.", "",
       "## Perubahan aplikasi yang dibutuhkan skenario", "",
       "- **BB-02**: validasi sudah ada (minimal 1.000 bar, HTTP 400). Diubah: minimal = panjang jendela model 500 bar, maksimal 5.000, "
       "HTTP **422** dengan pesan yang menyebut 500 bar; `bars` = jumlah log-return, data yang diambil = bars + 1 candle tertutup; "
       "pesan backend diteruskan ke antarmuka; input jumlah bar menjadi isian angka bebas. Candle berjalan dibuang "
       "(`drop_open_bar=True` untuk Binance, bar terakhir dibuang untuk Yahoo). Uji otomatis: `test_bar_kurang_dari_jendela_ditolak_422`, "
       "`test_bar_500_diterima`.",
       "- **BB-03**: kolom `efficiency_ratio` (ER_q) disimpan di label regime dan dikirim `/analysis/regime`; garis ER_q dan tabel "
       "'Label per jendela' (H, α, ER_q, label + contoh uncertain_rule terbaru) ditambahkan di halaman Hurst-DFA Klasik; ambang di grafik "
       "kini ambang kuantil train-only, bukan 0,45/0,55.",
       "- **BB-04**: endpoint baru `GET /api/v1/analysis/features` (bentuk dan nilai fitur jendela).",
       "- **BB-05**: endpoint `/analysis/attention` diganti ke model identifikasi (h = 0); halaman Fokus Model diaktifkan lagi.",
       "- **BB-07**: endpoint baru `GET /api/v1/model/evaluation` + halaman **Hasil Uji Identifikasi** (dibaca langsung dari "
       "`updated_eval_summary.json`).", "",
       "## Menu: halaman model prediksi lama (D.2)", "",
       f"Tautan menu (semua grup dibuka): {', '.join('`' + h + '`' for h in ev['menu_check']['menu_links'])}.", "",
       f"- `/model-comparison` di menu: {ev['menu_check']['model_comparison_in_menu']}; `/backtest` di menu: {ev['menu_check']['backtest_in_menu']}.",
       f"- Bila dibuka langsung, keduanya menampilkan pemberitahuan 'Halaman ini dinonaktifkan': {ev['menu_check']['retired_page_shows_notice']}.",
       "- `/attention` di menu: True, kini memakai model identifikasi h = 0.", "",
       "## Kebutuhan non-fungsional KNF-02 (waktu respons < 3 detik)", "",
       "Skrip `ml/src/review_knf02.py`, data `knf02_timing.json`, 10 pengulangan per skenario, localhost (CPU 16 inti).", "",
       "| Skenario | Yang diukur | Rata-rata (s) | Maks (s) | < 3 s |", "|---|---|---|---|---|"]
for key, label, what in [
    ("A_api_cache_terisi", "Cache terisi", "API `/analysis/ai-regime` 1H"),
    ("A_ui_cache_terisi", "Cache terisi", "Halaman Ringkasan sampai kartu identifikasi + grafik harga tampil"),
    ("B_api_1_jendela_baru", "1 jendela baru (cache tanpa jendela terbaru)", "API: hitung fitur + 3 model untuk jendela terbaru"),
    ("B_ui_1_jendela_baru", "1 jendela baru", "Halaman Ringkasan sampai kartu + grafik tampil"),
]:
    v = kn[key]
    md.append(f"| {label} | {what} | {str(v['mean_s']).replace('.', ',')} | {str(v['max_s']).replace('.', ',')} | {'ya' if v['under_3s'] else 'tidak'} |")
c = kn["C_cache_kosong"]
md += ["", f"Cache kosong total (seluruh riwayat 1H dihapus, 1 kali): API menjawab dalam {str(c['first_response_s']).replace('.', ',')} s "
       f"dengan HTTP {c['first_status']} dan pesan 'sedang menghitung riwayat'; {nd(c['windows'])} jendela selesai dihitung di latar "
       f"belakang dalam {str(c['full_history_ready_s']).replace('.', ',')} s. Kondisi ini hanya terjadi sekali setelah pemasangan model.", "",
       "Perbaikan yang dibutuhkan agar KNF-02 terpenuhi (pengukuran pertama: 1 jendela baru rata-rata 8,06 s):",
       "1. Sekuens PS untuk pembaruan bertahap (≤ 64 jendela) dihitung dari 500 return jendela itu saja, bukan seluruh 68 ribu "
       "return (5,5 s → 0,05 s). Hasilnya identik bit demi bit dengan perhitungan atas deret penuh (selisih 0,0 pada 64 jendela "
       "terakhir 1H dan 4H); verifikasi aplikasi tetap 1.624/2.005 dan 568/761.",
       "2. Ketiga model dimuat saat pemanasan startup, sehingga identifikasi pertama setelah restart tidak menunggu TensorFlow (±6 s).",
       "", "Catatan: angka di atas diukur di laptop pengembangan; VPS 2 vCPU akan lebih lambat untuk pembangunan riwayat penuh.", ""]
(R / "blackbox_evidence.md").write_text("\n".join(md), encoding="utf-8")
print("ok")

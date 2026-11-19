"""KNF-02: waktu respons identifikasi jendela terbaru + pembaruan grafik (target < 3 detik).

Skenario (masing-masing 10 kali, aplikasi berjalan di localhost):
  A. cache terisi    : GET /api/v1/analysis/ai-regime (backend) dan muat halaman Ringkasan
                       sampai kartu identifikasi + grafik tampil (browser).
  B. 1 jendela baru  : jendela terbaru dihapus dari cache identifikasi sebelum tiap
                       pengulangan, sehingga backend menghitung fitur + 3 model untuk
                       jendela itu (kondisi setelah candle baru tutup).
  C. cache kosong    : seluruh cache identifikasi 1H dihapus (1 kali; riwayat penuh
                       dihitung ulang di latar belakang).

    python ml/src/review_knf02.py
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import numpy as np
import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "processed" / "cache" / "ai_regime_btcusdt_1h.npz"
OUT = ROOT / "ml" / "artifacts" / "review" / "knf02_timing.json"
FE, BE = "http://localhost:3000", "http://127.0.0.1:8000"
N = 10


def drop_last_window() -> None:
    with np.load(CACHE) as z:
        d = {k: z[k] for k in z.files}
    d["pos"], d["proba"] = d["pos"][:-1], d["proba"][:-1]
    np.savez_compressed(CACHE, **d)


def api_once() -> float:
    t = time.perf_counter()
    r = requests.get(BE + "/api/v1/analysis/ai-regime", params={"tf": "1h"}, timeout=300)
    dt = time.perf_counter() - t
    assert r.status_code == 200, r.text[:200]
    return dt


def stats(xs):
    return {"n": len(xs), "mean_s": round(statistics.mean(xs), 3), "max_s": round(max(xs), 3), "min_s": round(min(xs), 3),
            "runs_s": [round(x, 3) for x in xs], "under_3s": all(x < 3 for x in xs)}


def main() -> None:
    out = {"target_s": 3.0}
    api_once()  # pemanasan: model & cache sudah dimuat backend
    out["A_api_cache_terisi"] = stats([api_once() for _ in range(N)])

    b_api = []
    for _ in range(N):
        drop_last_window()
        b_api.append(api_once())
    out["B_api_1_jendela_baru"] = stats(b_api)

    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", headless=True)
        ctx = br.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        page.goto(FE + "/welcome", wait_until="networkidle")
        page.request.post(FE + "/api/session/demo")

        def ui_once(drop: bool) -> float:
            if drop:
                drop_last_window()
            t = time.perf_counter()
            page.goto(FE + "/", wait_until="commit")
            page.get_by_text("IDENTIFIKASI AI 1H").first.wait_for(timeout=120_000)
            page.locator("canvas").first.wait_for(timeout=120_000)  # grafik harga (lightweight-charts)
            return time.perf_counter() - t

        ui_once(False)
        out["A_ui_cache_terisi"] = stats([ui_once(False) for _ in range(N)])
        out["B_ui_1_jendela_baru"] = stats([ui_once(True) for _ in range(N)])
        br.close()

    # C. cache kosong (1 kali): API langsung menjawab 503 "sedang menghitung", lalu dibangun di latar belakang.
    backup = CACHE.read_bytes()
    CACHE.unlink()
    t0 = time.perf_counter()
    r = requests.get(BE + "/api/v1/analysis/ai-regime", params={"tf": "1h"}, timeout=300)
    first = time.perf_counter() - t0
    first_status = r.status_code
    while True:
        r = requests.get(BE + "/api/v1/analysis/ai-regime", params={"tf": "1h"}, timeout=300)
        if r.status_code == 200:
            break
        time.sleep(2)
    ready = time.perf_counter() - t0
    out["C_cache_kosong"] = {"first_response_s": round(first, 3), "first_status": first_status,
                             "detail": "API tidak menunggu: 503 + pesan 'sedang menghitung', riwayat dibangun di thread latar belakang",
                             "full_history_ready_s": round(ready, 1), "windows": len(r.json().get("series", [])) and r.json()["original_count"]}
    if not CACHE.exists():
        CACHE.write_bytes(backup)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    for k, v in out.items():
        print(k, v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "runs_s"}, flush=True)


if __name__ == "__main__":
    main()

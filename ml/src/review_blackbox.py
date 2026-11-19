"""Pengujian black-box BB-01..BB-07 pada aplikasi yang sedang berjalan (localhost).

Prasyarat: backend di :8000 dan frontend (next start) di :3000, sesi demo lokal.
Keluaran: ml/artifacts/review/blackbox_evidence.json dan tangkapan layar
docs/naskah/gambar/blackbox/BB-0x*.png.

    python ml/src/review_blackbox.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "naskah" / "gambar" / "blackbox"
OUT = ROOT / "ml" / "artifacts" / "review" / "blackbox_evidence.json"
FE, BE = "http://localhost:3000", "http://127.0.0.1:8000"
SUMMARY = json.loads((ROOT / "ml" / "artifacts" / "updated_eval_summary.json").read_text(encoding="utf-8"))


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    ev: dict = {"run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "scenarios": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1.5, color_scheme="light")
        page = ctx.new_page()
        page.goto(FE + "/welcome", wait_until="networkidle")
        assert page.request.post(FE + "/api/session/demo").ok
        api = lambda path: page.request.get(BE + path, timeout=180_000).json()  # noqa: E731

        def shot(name: str, url: str | None = None, wait_text: str | None = None, ms: int = 4000, height: int = 1000) -> str:
            page.set_viewport_size({"width": 1440, "height": height})
            if url:
                page.goto(FE + url, wait_until="networkidle", timeout=180_000)
            if wait_text:
                page.get_by_text(wait_text, exact=False).first.wait_for(timeout=180_000)
            page.wait_for_timeout(ms)
            path = SHOTS / f"{name}.png"
            page.screenshot(path=str(path))
            return str(path.relative_to(ROOT)).replace("\\", "/")

        # ---------------- BB-01 Memuat data
        st = api("/api/v1/data/status")
        rows = {t["timeframe"]: t["rows"] for t in st["timeframes"]}
        ohlcv = api("/api/v1/ohlcv?symbol=BTCUSDT&tf=1h&limit=48")
        ev["scenarios"]["BB-01"] = {
            "input": "Buka Ringkasan; GET /api/v1/data/status",
            "output": {"rows": rows, "last_time": {t["timeframe"]: t["last_time"] for t in st["timeframes"]}, "candles_returned_limit48": len(ohlcv.get("candles", []))},
            "expected": {"1h": 68366, "4h": 17101},
            "pass": rows.get("1h") == 68366 and rows.get("4h") == 17101,
            "screenshot": shot("BB-01_memuat_data", "/", "IDENTIFIKASI AI 1H", 5000),
        }

        # ---------------- BB-02 Menyiapkan data (validasi jumlah bar)
        r300 = page.request.post(BE + "/internal/analyses", data={"source": "binance", "symbol": "BTCUSDT", "timeframe": "1h", "bars": 300})
        page.goto(FE + "/analisis", wait_until="networkidle")
        page.get_by_role("combobox").first.click()
        page.get_by_role("combobox").first.fill("BTCUSDT")
        page.get_by_role("option").filter(has_text="BTCUSDT").first.click()
        bars_input = page.locator('input[type="number"]').first
        bars_input.fill("300")
        page.get_by_role("button", name="Analisis").click()
        err = page.locator("p.text-bearish").first
        err.wait_for(timeout=60_000)
        ui_300 = err.inner_text()
        shot_300 = shot("BB-02a_tolak_300_bar", None, None, 800)
        bars_input.fill("500")
        page.get_by_role("button", name="Analisis").click()
        page.wait_for_url("**/analisis/*", timeout=120_000)
        job_id = page.url.rstrip("/").split("/")[-1]
        page.get_by_text("Riwayat kondisi", exact=False).first.wait_for(timeout=300_000)
        res = page.request.get(FE + f"/api/analyses/{job_id}").json()
        now = int(time.time())
        last_open = int(res.get("last_time", 0))
        ev["scenarios"]["BB-02"] = {
            "input": "Analisis Aset BTCUSDT Binance 1H dengan 300 bar, lalu 500 bar",
            "output": {
                "backend_300": {"status": r300.status, "detail": r300.json().get("detail")},
                "ui_300_message": ui_300,
                "job_500": {"id": job_id, "status": res.get("status"), "n_bars": res.get("n_bars"), "n_returns": res.get("n_returns"),
                            "windows_identified": len(res.get("series", [])), "last_bar_open_time": last_open,
                            "last_bar_close_time": last_open + 3600, "checked_at": now,
                            "last_bar_closed": last_open + 3600 <= now},
            },
            "pass": r300.status == 422 and "500" in ui_300 and res.get("status") == "done" and res.get("n_returns") == 500 and last_open + 3600 <= now,
            "screenshot": [shot_300, shot("BB-02b_proses_500_bar", None, None, 2500)],
        }

        # ---------------- BB-03 Memberi label
        reg = api("/api/v1/analysis/regime?tf=1h")
        last = reg["latest_windows"][-1]
        shot3a = shot("BB-03a_label_grafik", "/regime-explorer", "Label per jendela", 4000, 1000)
        page.get_by_text("Label per jendela").first.scroll_into_view_if_needed()
        shot3b = shot("BB-03b_label_tabel", None, None, 800, 1000)
        ev["scenarios"]["BB-03"] = {
            "input": "Buka Hurst-DFA Klasik (regime-explorer) 1H",
            "output": {"windows": reg["original_count"], "stride": reg["stride_bars"], "thresholds": reg["thresholds"],
                       "latest_window": last, "uncertain_example": reg["uncertain_example"]},
            "pass": all(last.get(k) is not None for k in ("hurst", "dfa_alpha", "efficiency_ratio", "regime")) and reg["uncertain_example"] is not None,
            "screenshot": [shot3a, shot3b],
        }

        # ---------------- BB-04 Membentuk fitur
        swt = api("/api/v1/analysis/swt?tf=1h")
        feats = api("/api/v1/analysis/features?tf=1h")
        ev["scenarios"]["BB-04"] = {
            "input": "Buka halaman Wavelet (SWT); GET /api/v1/analysis/features?tf=1h",
            "output": {"swt_components": sorted(swt.get("components", {}).keys()), "swt_level": swt.get("level") or swt.get("levels"),
                       "ps_shape": feats["ps_shape"], "ps_channels": feats["ps_channels"], "summary_length": feats["summary_length"],
                       "summary_names_first5": feats["summary_names"][:5], "summary_names_last6": feats["summary_names"][-6:]},
            "pass": feats["ps_shape"] == [32, 14] and feats["summary_length"] == 56 and sum(k.startswith("detail") for k in swt.get("components", {})) == 4,
            "screenshot": shot("BB-04_fitur_swt", "/swt", None, 5000),
        }

        # ---------------- BB-05 Identifikasi
        ai = api("/api/v1/analysis/ai-regime?tf=1h&limit=200")
        att = api("/api/v1/analysis/attention?tf=1h")
        psum = sum(ai["current_probabilities"].values())
        ev["scenarios"]["BB-05"] = {
            "input": "Buka Ringkasan dan Fokus Model 1H",
            "output": {"current_regime": ai["current_regime"], "probabilities": ai["current_probabilities"], "prob_sum": psum,
                       "low_confidence": ai["current_low_confidence"], "attention_steps": len(att["attention_weights"]),
                       "attention_sum": sum(w["weight"] for w in att["attention_weights"]), "attention_entropy": att["entropy_normalized"],
                       "attention_regime": att["regime"]},
            "pass": abs(psum - 1) < 1e-3 and len(att["attention_weights"]) == 32 and abs(sum(w["weight"] for w in att["attention_weights"]) - 1) < 1e-3,
            "screenshot": [shot("BB-05a_identifikasi_ringkasan", "/", "IDENTIFIKASI AI 1H", 4000),
                           shot("BB-05b_attention", "/attention", "Bobot attention", 3000)],
        }

        # ---------------- BB-06 Perbandingan 1H dan 4H
        r1, r4 = api("/api/v1/analysis/regime?tf=1h"), api("/api/v1/analysis/regime?tf=4h")
        ev["scenarios"]["BB-06"] = {
            "input": "Buka Hurst-DFA 1H vs 4H (timeframe-comparison)",
            "output": {"1h": {"windows": r1["original_count"], "stride": r1["stride_bars"], "switches": r1["n_switches"], "current": r1["current_regime"]},
                       "4h": {"windows": r4["original_count"], "stride": r4["stride_bars"], "switches": r4["n_switches"], "current": r4["current_regime"]}},
            "pass": r1["original_count"] == 16967 and r4["original_count"] == 8301,
            "screenshot": shot("BB-06_perbandingan_1h_4h", "/timeframe-comparison", "Timeframe 4H", 4000),
        }

        # ---------------- BB-07 Pengujian identifikasi
        evl = api("/api/v1/model/evaluation")
        checks = {}
        for tf in ("1h", "4h"):
            s_bt = SUMMARY[tf]["historical_backtest"]["models"]["hybrid_ps"]["ensemble"]
            a_bt = evl["timeframes"][tf]["backtest"]["hybrid_ps"]
            s_f = [f["models"]["hybrid_ps"]["ensemble"] for f in SUMMARY[tf]["walk_forward_5fold"]["folds"]]
            a_f = [f["models"]["hybrid_ps"] for f in evl["timeframes"][tf]["walk_forward"]["folds"]]
            checks[tf] = {
                "backtest": f"{a_bt['correct']}/{a_bt['total']} ({a_bt['pct']}%)",
                "backtest_per_class": {c: f"{v['correct']}/{v['total']}" for c, v in a_bt["per_class"].items()},
                "folds": [f"{f['correct']}/{f['total']} ({f['pct']}%)" for f in a_f],
                "pooled": f"{evl['timeframes'][tf]['walk_forward']['summary']['hybrid_ps']['total_correct_ensemble']}/"
                          f"{evl['timeframes'][tf]['walk_forward']['summary']['hybrid_ps']['total_test_pooled']}",
                "equal_to_summary": a_bt["correct"] == s_bt["correct"] and a_bt["per_class"] == s_bt["per_class"]
                and all(a["correct"] == s["correct"] and a["per_class"] == s["per_class"] for a, s in zip(a_f, s_f)),
            }
        shots7 = [shot("BB-07a_hasil_uji_1h", "/evaluasi-identifikasi", "Historical backtesting", 2500, 1300)]
        page.get_by_role("button", name="4H").first.click()
        page.get_by_text("Historical backtesting · 4H").first.wait_for(timeout=30_000)
        shots7.append(shot("BB-07b_hasil_uji_4h", None, None, 1500, 1300))
        ev["scenarios"]["BB-07"] = {
            "input": "Buka Hasil Uji Identifikasi 1H lalu 4H; bandingkan dengan updated_eval_summary.json",
            "output": checks,
            "pass": all(c["equal_to_summary"] for c in checks.values()),
            "screenshot": shots7,
        }

        # ---------------- D.2 Halaman model prediksi lama tidak ada di menu
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.goto(FE + "/", wait_until="networkidle")
        nav = page.get_by_role("navigation", name="Navigasi utama")
        hrefs: set = set()
        for i in range(nav.locator(":scope > div > button").count()):
            nav.locator(":scope > div > button").nth(i).click()
            page.wait_for_timeout(300)
            hrefs.update(h for h in page.eval_on_selector_all("nav[aria-label='Navigasi utama'] a", "els => els.map(e => e.getAttribute('href'))") if h)
            page.keyboard.press("Escape")
        retired = {}
        for path in ("/model-comparison", "/backtest"):
            page.goto(FE + path, wait_until="networkidle")
            retired[path] = page.get_by_text("Halaman ini dinonaktifkan").count() > 0
        ev["menu_check"] = {
            "menu_links": sorted(hrefs),
            "model_comparison_in_menu": "/model-comparison" in hrefs,
            "backtest_in_menu": "/backtest" in hrefs,
            "attention_in_menu": "/attention" in hrefs,
            "retired_page_shows_notice": retired,
        }
        browser.close()
    OUT.write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
    for k, v in ev["scenarios"].items():
        print(k, "PASS" if v["pass"] else "FAIL", flush=True)
    print("menu", ev["menu_check"])


if __name__ == "__main__":
    main()

"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

/**
 * Analisa teknikal bebas dengan widget resmi TradingView (gratis).
 *
 * Alat gambar (garis tren, fibonacci, channel, teks, dll.) dan indikator
 * disediakan TradingView. Data dan grafik di halaman ini milik TradingView,
 * bukan hasil sistem identifikasi regime; gambar tidak tersimpan setelah
 * halaman ditutup.
 */

type Asset = { label: string; tv: string; group: string };

// 20 aset proyek (praregistrasi generalisasi §2). XAUUSD spot tersedia di
// TradingView meski tidak bisa diunduh untuk riset (sumber diblokir).
const ASSETS: Asset[] = [
  { label: "BTC", tv: "BINANCE:BTCUSDT", group: "Kripto" },
  { label: "ETH", tv: "BINANCE:ETHUSDT", group: "Kripto" },
  { label: "BNB", tv: "BINANCE:BNBUSDT", group: "Kripto" },
  { label: "SOL", tv: "BINANCE:SOLUSDT", group: "Kripto" },
  { label: "XRP", tv: "BINANCE:XRPUSDT", group: "Kripto" },
  { label: "ADA", tv: "BINANCE:ADAUSDT", group: "Kripto" },
  { label: "DOGE", tv: "BINANCE:DOGEUSDT", group: "Kripto" },
  { label: "XAU/USD", tv: "OANDA:XAUUSD", group: "Emas" },
  { label: "PAXG", tv: "BINANCE:PAXGUSDT", group: "Emas" },
  { label: "IHSG", tv: "IDX:COMPOSITE", group: "Saham IDX" },
  { label: "BBCA", tv: "IDX:BBCA", group: "Saham IDX" },
  { label: "BBRI", tv: "IDX:BBRI", group: "Saham IDX" },
  { label: "BMRI", tv: "IDX:BMRI", group: "Saham IDX" },
  { label: "BBNI", tv: "IDX:BBNI", group: "Saham IDX" },
  { label: "TLKM", tv: "IDX:TLKM", group: "Saham IDX" },
  { label: "ASII", tv: "IDX:ASII", group: "Saham IDX" },
  { label: "ANTM", tv: "IDX:ANTM", group: "Saham IDX" },
  { label: "UNVR", tv: "IDX:UNVR", group: "Saham IDX" },
  { label: "ICBP", tv: "IDX:ICBP", group: "Saham IDX" },
  { label: "ADRO", tv: "IDX:ADRO", group: "Saham IDX" },
];
const GROUPS = Array.from(new Set(ASSETS.map((a) => a.group)));
// Widget gratis TradingView hanya menyediakan data harian ke atas untuk bursa IDX.
const DAILY_ONLY_GROUPS = new Set(["Saham IDX"]);
const DAILY_INTERVALS = new Set(["D", "W"]);

const INTERVALS = [
  { label: "15m", tv: "15" },
  { label: "1H", tv: "60" },
  { label: "4H", tv: "240" },
  { label: "1D", tv: "D" },
  { label: "1W", tv: "W" },
];

function TradingViewChart({ symbol, interval }: { symbol: string; interval: string }) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    el.innerHTML = "";
    const widget = document.createElement("div");
    widget.className = "tradingview-widget-container__widget h-full w-full";
    el.appendChild(widget);
    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.async = true;
    script.type = "text/javascript";
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol,
      interval,
      timezone: "Asia/Jakarta",
      theme: "dark",
      style: "1",
      locale: "id",
      backgroundColor: "#131518",
      gridColor: "rgba(39, 43, 49, 0.6)",
      allow_symbol_change: true,
      hide_side_toolbar: false,
      withdateranges: true,
      details: false,
      calendar: false,
      support_host: "https://www.tradingview.com",
    });
    el.appendChild(script);
    return () => {
      el.innerHTML = "";
    };
  }, [symbol, interval]);

  return <div ref={host} className="tradingview-widget-container h-full w-full" />;
}

export default function AnalisaTeknikalPage() {
  const [asset, setAsset] = useState(ASSETS[0]);
  const [interval, setInterval] = useState("60");
  const [full, setFull] = useState(false);
  const shell = useRef<HTMLDivElement>(null);
  const dailyOnly = DAILY_ONLY_GROUPS.has(asset.group);

  const pickAsset = (a: Asset) => {
    setAsset(a);
    if (DAILY_ONLY_GROUPS.has(a.group) && !DAILY_INTERVALS.has(interval)) setInterval("D");
  };

  useEffect(() => {
    const onChange = () => setFull(document.fullscreenElement === shell.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const toggleFull = () => {
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
    else void shell.current?.requestFullscreen().catch(() => undefined);
  };

  return (
    <div ref={shell} className={`flex h-full min-h-[560px] flex-col gap-2 ${full ? "bg-panelAlt p-2" : ""}`}>
      <div className="flex items-center gap-2 rounded-xl border border-edge bg-panel px-2 py-1.5">
        <h1 className="hidden shrink-0 px-1 text-[14px] font-semibold text-txt xl:block">Analisa teknikal</h1>
        <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto [scrollbar-width:thin]" role="group" aria-label="Aset">
          {GROUPS.map((g, gi) => (
            <div key={g} className="flex shrink-0 items-center gap-1">
              {gi > 0 && <span className="mx-1.5 h-4 w-px bg-edge" aria-hidden />}
              <span className="mr-0.5 text-2xs uppercase tracking-wider text-txtMuted">{g}</span>
              {ASSETS.filter((a) => a.group === g).map((a) => (
                <button
                  key={a.tv}
                  type="button"
                  aria-pressed={asset.tv === a.tv}
                  onClick={() => pickAsset(a)}
                  className={`shrink-0 rounded-md border px-2 py-0.5 text-[12px] font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                    asset.tv === a.tv
                      ? "border-accent/60 bg-accent/15 text-accent"
                      : "border-transparent text-txtDim hover:border-edge hover:text-txt"
                  }`}
                >
                  {a.label}
                </button>
              ))}
            </div>
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-0.5 rounded-lg border border-edge bg-panelAlt p-0.5" role="group" aria-label="Rentang waktu">
          {INTERVALS.map((i) => {
            const blocked = dailyOnly && !DAILY_INTERVALS.has(i.tv);
            return (
              <button
                key={i.tv}
                type="button"
                aria-pressed={interval === i.tv}
                disabled={blocked}
                title={blocked ? "Saham IDX hanya tersedia harian ke atas di TradingView gratis" : undefined}
                onClick={() => setInterval(i.tv)}
                className={`rounded-md px-2 py-0.5 font-mono text-[12px] transition disabled:cursor-not-allowed disabled:opacity-30 ${
                  interval === i.tv ? "bg-accent/20 text-accent" : "text-txtDim hover:bg-surface hover:text-txt"
                }`}
              >
                {i.label}
              </button>
            );
          })}
        </div>
        <button
          type="button"
          onClick={toggleFull}
          aria-pressed={full}
          title={full ? "Keluar layar penuh (Esc)" : "Layar penuh"}
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-edge px-2.5 py-1 text-[12px] text-txtDim transition hover:border-accent/60 hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        >
          <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
            {full ? (
              <path d="M8 3v5H3M12 3v5h5M8 17v-5H3M12 17v-5h5" />
            ) : (
              <path d="M3 8V3h5M17 8V3h-5M3 12v5h5M17 12v5h-5" />
            )}
          </svg>
          <span className="hidden sm:inline">{full ? "Keluar" : "Layar penuh"}</span>
        </button>
      </div>

      {dailyOnly && (
        <p className="rounded-lg border border-edge bg-panel px-3 py-1.5 text-[12px] text-txtDim">
          Saham IDX di TradingView gratis hanya tersedia dalam interval harian, mingguan, dan bulanan.
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-hidden rounded-xl border border-edge bg-panel">
        <TradingViewChart symbol={asset.tv} interval={interval} />
      </div>

      {!full && (
        <p className="shrink-0 truncate px-1 text-[11px] text-txtMuted" title="Data dan grafik milik TradingView; gambar tidak tersimpan setelah halaman ditutup.">
          Grafik dan data dari TradingView, bukan hasil sistem regime; gambar tidak tersimpan. Hasil sistem ada di{" "}
          <Link href="/" className="text-accent hover:underline">Ringkasan pasar</Link> dan{" "}
          <Link href="/strategi" className="text-accent hover:underline">Regime → Strategi</Link>. Bukan saran investasi.
        </p>
      )}
    </div>
  );
}

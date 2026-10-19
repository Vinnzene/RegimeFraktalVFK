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
  const [height, setHeight] = useState(640);
  const dailyOnly = DAILY_ONLY_GROUPS.has(asset.group);

  const pickAsset = (a: Asset) => {
    setAsset(a);
    if (DAILY_ONLY_GROUPS.has(a.group) && !DAILY_INTERVALS.has(interval)) setInterval("D");
  };

  useEffect(() => {
    const resize = () => setHeight(Math.max(480, window.innerHeight - 250));
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  return (
    <div className="mx-auto max-w-[1600px] space-y-3 px-1 pb-6 sm:px-3">
      <header className="flex flex-wrap items-end justify-between gap-3 pt-1">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-txt">Analisa teknikal</h1>
          <p className="mt-0.5 max-w-3xl text-[13px] text-txtDim">
            Tarik garis tren, fibonacci, channel, dan pasang indikator sesuka Anda. Alat gambar ada di sisi kiri grafik;
            simbol lain bisa dicari lewat kolom simbol di kiri atas.
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-edge bg-panel p-1" role="group" aria-label="Rentang waktu">
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
              className={`rounded-md px-2.5 py-1 font-mono text-[12px] transition disabled:cursor-not-allowed disabled:opacity-30 ${
                interval === i.tv ? "bg-accent/20 text-accent" : "text-txtDim hover:bg-surface hover:text-txt"
              }`}
            >
              {i.label}
            </button>
            );
          })}
        </div>
      </header>

      <div className="flex flex-wrap gap-x-5 gap-y-2 rounded-xl border border-edge bg-panel px-3 py-2.5">
        {GROUPS.map((g) => (
          <div key={g} className="flex flex-wrap items-center gap-1.5">
            <span className="mr-0.5 text-2xs uppercase tracking-wider text-txtMuted">{g}</span>
            {ASSETS.filter((a) => a.group === g).map((a) => (
              <button
                key={a.tv}
                type="button"
                aria-pressed={asset.tv === a.tv}
                onClick={() => pickAsset(a)}
                className={`rounded-md border px-2 py-0.5 text-[12px] font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                  asset.tv === a.tv
                    ? "border-accent/60 bg-accent/15 text-accent"
                    : "border-edge text-txtDim hover:border-edgeBright hover:text-txt"
                }`}
              >
                {a.label}
              </button>
            ))}
          </div>
        ))}
      </div>

      {dailyOnly && (
        <p className="rounded-lg border border-edge bg-panel px-3 py-2 text-[12px] text-txtDim">
          Saham IDX di TradingView gratis hanya tersedia dalam interval harian, mingguan, dan bulanan.
        </p>
      )}

      <div className="overflow-hidden rounded-xl border border-edge bg-panel" style={{ height }}>
        <TradingViewChart symbol={asset.tv} interval={interval} />
      </div>

      <p className="text-[11.5px] leading-relaxed text-txtMuted">
        Grafik dan data di halaman ini disediakan TradingView, bukan hasil sistem identifikasi regime; gambar tidak tersimpan
        setelah halaman ditutup. Kondisi regime dari sistem ada di{" "}
        <Link href="/" className="text-accent hover:underline">Ringkasan pasar</Link> dan{" "}
        <Link href="/strategi" className="text-accent hover:underline">Regime → Strategi</Link>. Bukan saran investasi.
      </p>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import CandlestickChart from "@/components/CandlestickChart";
import { api, type Candle } from "@/lib/api-client";

/** Analisa teknikal dengan chart sendiri: semua indikator RFraktal dan alat gambar dasar. */

type Asset = { label: string; source: "binance" | "yahoo"; symbol: string; group: string };

// 20 aset proyek (praregistrasi generalisasi §2).
const ASSETS: Asset[] = [
  { label: "BTC", source: "binance", symbol: "BTCUSDT", group: "Kripto" },
  { label: "ETH", source: "binance", symbol: "ETHUSDT", group: "Kripto" },
  { label: "BNB", source: "binance", symbol: "BNBUSDT", group: "Kripto" },
  { label: "SOL", source: "binance", symbol: "SOLUSDT", group: "Kripto" },
  { label: "XRP", source: "binance", symbol: "XRPUSDT", group: "Kripto" },
  { label: "ADA", source: "binance", symbol: "ADAUSDT", group: "Kripto" },
  { label: "DOGE", source: "binance", symbol: "DOGEUSDT", group: "Kripto" },
  { label: "Emas (GC=F)", source: "yahoo", symbol: "GC=F", group: "Emas" },
  { label: "PAXG", source: "binance", symbol: "PAXGUSDT", group: "Emas" },
  { label: "IHSG", source: "yahoo", symbol: "^JKSE", group: "Saham IDX" },
  { label: "BBCA", source: "yahoo", symbol: "BBCA.JK", group: "Saham IDX" },
  { label: "BBRI", source: "yahoo", symbol: "BBRI.JK", group: "Saham IDX" },
  { label: "BMRI", source: "yahoo", symbol: "BMRI.JK", group: "Saham IDX" },
  { label: "BBNI", source: "yahoo", symbol: "BBNI.JK", group: "Saham IDX" },
  { label: "TLKM", source: "yahoo", symbol: "TLKM.JK", group: "Saham IDX" },
  { label: "ASII", source: "yahoo", symbol: "ASII.JK", group: "Saham IDX" },
  { label: "ANTM", source: "yahoo", symbol: "ANTM.JK", group: "Saham IDX" },
  { label: "UNVR", source: "yahoo", symbol: "UNVR.JK", group: "Saham IDX" },
  { label: "ICBP", source: "yahoo", symbol: "ICBP.JK", group: "Saham IDX" },
  { label: "ADRO", source: "yahoo", symbol: "ADRO.JK", group: "Saham IDX" },
];
const GROUPS = Array.from(new Set(ASSETS.map((a) => a.group)));
const INTERVALS = [
  { label: "15m", tf: "15m" },
  { label: "1H", tf: "1h" },
  { label: "4H", tf: "4h" },
  { label: "1D", tf: "1d" },
  { label: "1W", tf: "1w" },
];
// Rentang awal yang wajar per timeframe.
const DEFAULT_RANGE: Record<string, string> = { "15m": "1D", "1h": "1M", "4h": "3M", "1d": "1Y", "1w": "ALL" };

export default function AnalisaTeknikalPage() {
  const [asset, setAsset] = useState(ASSETS[0]);
  const [tf, setTf] = useState("1h");
  const [candles, setCandles] = useState<Candle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [full, setFull] = useState(false);
  const [chartH, setChartH] = useState(560);
  const shell = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let stop = false;
    setLoading(true);
    setError(null);
    api
      .marketCandles(asset.source, asset.symbol, tf, 1500)
      .then((r) => !stop && setCandles(r.candles))
      .catch((e: Error) => {
        if (stop) return;
        setCandles([]);
        setError(e.message);
      })
      .finally(() => !stop && setLoading(false));
    return () => {
      stop = true;
    };
  }, [asset, tf]);

  // Tinggi chart mengisi layar (dihitung ulang saat ukuran jendela atau layar penuh berubah).
  useEffect(() => {
    // Sisakan ruang untuk navigasi, toolbar, header chart, legenda bawah, dan catatan sumber.
    const calc = () => setChartH(Math.max(400, window.innerHeight - (document.fullscreenElement ? 170 : 360)));
    calc();
    window.addEventListener("resize", calc);
    return () => window.removeEventListener("resize", calc);
  }, [full]);

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
                  key={a.symbol}
                  type="button"
                  aria-pressed={asset.symbol === a.symbol}
                  onClick={() => setAsset(a)}
                  className={`shrink-0 rounded-md border px-2 py-0.5 text-[12px] font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                    asset.symbol === a.symbol ? "border-accent/60 bg-accent/15 text-accent" : "border-transparent text-txtDim hover:border-edge hover:text-txt"
                  }`}
                >
                  {a.label}
                </button>
              ))}
            </div>
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-0.5 rounded-lg border border-edge bg-panelAlt p-0.5" role="group" aria-label="Rentang waktu">
          {INTERVALS.map((i) => (
            <button
              key={i.tf}
              type="button"
              aria-pressed={tf === i.tf}
              onClick={() => setTf(i.tf)}
              className={`rounded-md px-2 py-0.5 font-mono text-[12px] transition ${tf === i.tf ? "bg-accent/20 text-accent" : "text-txtDim hover:bg-surface hover:text-txt"}`}
            >
              {i.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={toggleFull}
          aria-pressed={full}
          title={full ? "Keluar layar penuh (Esc)" : "Layar penuh"}
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-edge px-2.5 py-1 text-[12px] text-txtDim transition hover:border-accent/60 hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        >
          <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
            {full ? <path d="M8 3v5H3M12 3v5h5M8 17v-5H3M12 17v-5h5" /> : <path d="M3 8V3h5M17 8V3h-5M3 12v5h5M17 12v5h-5" />}
          </svg>
          <span className="hidden sm:inline">{full ? "Keluar" : "Layar penuh"}</span>
        </button>
      </div>

      <div className="min-h-0 flex-1">
        {error ? (
          <div className="flex h-full min-h-[420px] items-center justify-center rounded-xl border border-edge bg-panel px-4 text-center text-[13px] text-bearish">
            Data {asset.label} {tf.toUpperCase()} gagal dimuat: {error}
          </div>
        ) : loading && candles.length === 0 ? (
          <div className="flex h-full min-h-[420px] items-center justify-center rounded-xl border border-edge bg-panel text-[13px] text-txtMuted">
            Memuat {asset.label} {tf.toUpperCase()}…
          </div>
        ) : (
          <div className={loading ? "opacity-60 transition" : ""}>
            <CandlestickChart
              key={`${asset.symbol}-${tf}`}
              candles={candles}
              height={chartH}
              showRegime={false}
              symbol={asset.label.includes("(") ? asset.symbol : asset.source === "binance" ? asset.symbol.replace("USDT", "/USDT") : asset.label}
              timeframe={tf}
              defaultRange={DEFAULT_RANGE[tf] ?? "3M"}
              indicators
              depthSymbol={asset.source === "binance" ? asset.symbol : undefined}
              drawingKey={`${asset.symbol}:${tf}`}
            />
          </div>
        )}
      </div>

      {!full && (
        <p className="shrink-0 truncate px-1 text-[11px] text-txtMuted" title="Data dari Binance (kripto, PAXG) dan Yahoo Finance (emas, saham IDX).">
          Data dari Binance dan Yahoo Finance, maksimal 1.500 candle; bukan hasil sistem regime. Gambar tersimpan di peramban ini. Hasil sistem ada di{" "}
          <Link href="/" className="text-accent hover:underline">Ringkasan pasar</Link> dan{" "}
          <Link href="/strategi" className="text-accent hover:underline">Regime → Strategi</Link>. Bukan saran investasi.
        </p>
      )}
    </div>
  );
}

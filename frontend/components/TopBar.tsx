"use client";

import { useEffect, useState } from "react";
import { useAppConfig } from "@/components/ConfigContext";
import { api } from "@/lib/api-client";

/**
 * Bar harga global di puncak layar.
 *
 * Menampilkan harga terakhir dan perubahan 24 jam, mengikuti kebiasaan terminal
 * data kripto. Angka diambil dari bar TERTUTUP terakhir — bar berjalan sengaja
 * dibuang di sisi ingestion, sehingga nilai di sini stabil dan tidak berkedip.
 */
export default function TopBar() {
  const { timeframe, config } = useAppConfig();
  const [stat, setStat] = useState<{
    last: number;
    change: number;
    changePct: number;
    high: number;
    low: number;
    volume: number;
    time: number;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        // 24 jam terakhir pada 1H = 24 bar; pada 4H = 6 bar.
        const bars = timeframe === "4h" ? 12 : 48;
        const r = await api.ohlcv(timeframe, Math.max(bars, 10));
        const c = r.candles ?? [];
        if (cancelled || c.length < 2) return;

        const span = timeframe === "4h" ? 6 : 24;
        const last = c[c.length - 1];
        const ref = c[Math.max(0, c.length - 1 - span)];
        const window = c.slice(Math.max(0, c.length - span));

        setStat({
          last: last.close,
          change: last.close - ref.close,
          changePct: ref.close ? ((last.close - ref.close) / ref.close) * 100 : 0,
          high: Math.max(...window.map((x: any) => x.high)),
          low: Math.min(...window.map((x: any) => x.low)),
          volume: window.reduce((a: number, x: any) => a + x.volume, 0),
          time: last.time,
        });
      } catch {
        /* diamkan: bar harga bersifat pelengkap, tidak boleh menjatuhkan halaman */
      }
    };
    load();
    const timer = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [timeframe]);

  const up = (stat?.change ?? 0) >= 0;
  const fmt = (v: number, d = 2) =>
    v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

  return (
    <header className="flex h-14 shrink-0 items-center gap-5 border-b border-edge bg-panel px-4">
      <div className="flex items-baseline gap-2">
        <span className="font-sans text-sm font-semibold tracking-tight text-txt">
          {config?.data.symbol ?? "BTCUSDT"}
        </span>
        <span className="rounded bg-edge px-1.5 py-0.5 font-mono text-2xs text-txtDim">
          {timeframe.toUpperCase()}
        </span>
      </div>

      {stat ? (
        <>
          <div className="flex items-baseline gap-2">
            <span
              className={`font-mono text-lg font-semibold tabular-nums ${
                up ? "text-bullish" : "text-bearish"
              }`}
            >
              {fmt(stat.last)}
            </span>
            <span className={up ? "badge-up" : "badge-down"} title="Perubahan harga 24 jam terakhir">
              {up ? "+" : ""}
              {stat.changePct.toFixed(2)}% (24 jam)
            </span>
          </div>

          <div className="hidden items-center gap-5 md:flex">
            {[
              ["Tertinggi 24 jam", fmt(stat.high)],
              ["Terendah 24 jam", fmt(stat.low)],
              ["Volume 24 jam (BTC)", fmt(stat.volume, 0)],
            ].map(([label, value]) => (
              <div key={label} className="leading-tight">
                <div className="text-2xs text-txtMuted">{label}</div>
                <div className="font-mono text-[12px] tabular-nums text-txtDim">{value}</div>
              </div>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2 text-2xs text-txtMuted">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-bullish" />
            <span className="font-mono">
              {new Date(stat.time * 1000).toISOString().slice(0, 16).replace("T", " ")} UTC
            </span>
          </div>
        </>
      ) : (
        <div className="h-6 w-40 animate-pulse rounded bg-surface" />
      )}
    </header>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import BookLadder from "@/components/orderflow/BookLadder";
import DeltaCvdCanvas from "@/components/orderflow/DeltaCvdCanvas";
import FootprintCanvas from "@/components/orderflow/FootprintCanvas";
import HeatmapCanvas from "@/components/orderflow/HeatmapCanvas";
import { useOrderFlow } from "@/components/orderflow/useOrderFlow";
import type { Status } from "@/lib/orderflow/engine";

/**
 * Order flow real-time untuk aset kripto Binance: heatmap likuiditas order
 * book, footprint candle, delta/CVD, dan tangga order book.
 *
 * Hanya kripto: order book saham IDX dan emas tidak tersedia gratis. Heatmap
 * dimulai saat halaman dibuka karena order book historis spot tidak tersedia.
 */

const ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "PAXGUSDT"];
const CANDLES = [
  { label: "1m", ms: 60_000 },
  { label: "5m", ms: 300_000 },
];
const DENSITY = [1, 2, 5];
const STATUS: Record<Status, [string, string]> = {
  idle: ["Siap", "bg-txtMuted"],
  connecting: ["Memuat riwayat transaksi…", "bg-warn"],
  syncing: ["Menyinkronkan order book…", "bg-warn"],
  live: ["Live", "bg-bullish"],
  reconnecting: ["Terputus, menyambung ulang…", "bg-warn"],
  error: ["Gagal terhubung", "bg-bearish"],
};

function Seg<T extends string | number>({
  items,
  value,
  onChange,
  label,
}: {
  items: { label: string; value: T }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="flex shrink-0 items-center gap-0.5 rounded-lg border border-edge bg-panelAlt p-0.5" role="group" aria-label={label}>
      {items.map((i) => (
        <button
          key={String(i.value)}
          type="button"
          aria-pressed={value === i.value}
          onClick={() => onChange(i.value)}
          className={`rounded-md px-2 py-0.5 text-[12px] transition ${
            value === i.value ? "bg-accent/20 text-accent" : "text-txtDim hover:bg-surface hover:text-txt"
          }`}
        >
          {i.label}
        </button>
      ))}
    </div>
  );
}

export default function OrderFlowLivePage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [view, setView] = useState<"heatmap" | "footprint">("heatmap");
  const [candleMs, setCandleMs] = useState(60_000);
  const [density, setDensity] = useState(1);
  const [full, setFull] = useState(false);
  const shell = useRef<HTMLDivElement>(null);
  const { engine, version } = useOrderFlow(symbol, candleMs, density);
  const [label, dot] = STATUS[engine.status];

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
    <div ref={shell} className={`flex h-full min-h-[600px] flex-col gap-2 ${full ? "bg-panelAlt p-2" : ""}`}>
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-edge bg-panel px-2 py-1.5">
        <h1 className="hidden shrink-0 px-1 text-[14px] font-semibold text-txt xl:block">Order flow live</h1>
        <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto" role="group" aria-label="Aset">
          {ASSETS.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={symbol === s}
              onClick={() => setSymbol(s)}
              className={`shrink-0 rounded-md border px-2 py-0.5 text-[12px] font-medium transition ${
                symbol === s ? "border-accent/60 bg-accent/15 text-accent" : "border-transparent text-txtDim hover:border-edge hover:text-txt"
              }`}
            >
              {s.replace("USDT", "")}
            </button>
          ))}
        </div>
        <Seg
          label="Tampilan"
          value={view}
          onChange={setView}
          items={[
            { label: "Heatmap", value: "heatmap" },
            { label: "Footprint", value: "footprint" },
          ]}
        />
        <Seg label="Candle" value={candleMs} onChange={setCandleMs} items={CANDLES.map((c) => ({ label: c.label, value: c.ms }))} />
        <Seg label="Kerapatan harga" value={density} onChange={setDensity} items={DENSITY.map((d) => ({ label: `×${d}`, value: d }))} />
        <button
          type="button"
          onClick={() => engine.setPaused(!engine.paused)}
          aria-pressed={engine.paused}
          className="shrink-0 rounded-lg border border-edge px-2.5 py-1 text-[12px] text-txtDim transition hover:border-accent/60 hover:text-accent"
        >
          {engine.paused ? "Lanjutkan" : "Jeda"}
        </button>
        <span className="flex shrink-0 items-center gap-1.5 px-1 text-[12px] text-txtDim" role="status" aria-live="polite">
          <span className={`h-2 w-2 rounded-full ${dot}`} />
          {engine.paused ? "Dijeda" : label}
        </span>
        <button
          type="button"
          onClick={toggleFull}
          title={full ? "Keluar layar penuh (Esc)" : "Layar penuh"}
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-edge px-2.5 py-1 text-[12px] text-txtDim transition hover:border-accent/60 hover:text-accent"
        >
          <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
            {full ? <path d="M8 3v5H3M12 3v5h5M8 17v-5H3M12 17v-5h5" /> : <path d="M3 8V3h5M17 8V3h-5M3 12v5h5M17 12v5h-5" />}
          </svg>
          <span className="hidden sm:inline">{full ? "Keluar" : "Layar penuh"}</span>
        </button>
      </div>

      {engine.status === "error" && (
        <p className="rounded-lg border border-bearish/40 bg-bearish/10 px-3 py-2 text-[12px] text-bearish">
          Tidak bisa terhubung ke data Binance ({engine.error}). Periksa koneksi internet, lalu pilih aset lagi untuk mencoba ulang.
        </p>
      )}

      <div className="grid min-h-0 flex-1 gap-2 lg:grid-cols-[1fr_250px]">
        <div className="flex min-h-0 flex-col gap-2">
          <div className="min-h-0 flex-1 overflow-hidden rounded-xl border border-edge bg-panelAlt">
            {view === "heatmap" ? (
              <HeatmapCanvas engine={engine} version={version} />
            ) : (
              <FootprintCanvas engine={engine} version={version} />
            )}
          </div>
          <div className="h-[110px] shrink-0 overflow-hidden rounded-xl border border-edge bg-panelAlt">
            <DeltaCvdCanvas engine={engine} version={version} />
          </div>
        </div>
        <aside className="hidden min-h-0 overflow-hidden rounded-xl border border-edge bg-panel lg:block" aria-label="Order book">
          <BookLadder engine={engine} version={version} />
        </aside>
      </div>

      {!full && (
        <p className="shrink-0 px-1 text-[11px] leading-relaxed text-txtMuted">
          {view === "heatmap"
            ? "Heatmap: warna terang = antrean order besar di harga itu; garis hijau/merah = bid/ask terbaik; gelembung = transaksi agresif (hijau beli, merah jual). Dimulai saat halaman dibuka."
            : "Footprint: kiri = jual agresif, kanan = beli agresif per level harga; teks tebal = ketimpangan ≥ 3× (diagonal); kotak oranye = POC. Gulir untuk menggeser harga. Riwayat 30 menit."}{" "}
          Data Binance spot real-time, hanya kripto. Bukan hasil sistem regime dan bukan saran investasi.
        </p>
      )}
    </div>
  );
}

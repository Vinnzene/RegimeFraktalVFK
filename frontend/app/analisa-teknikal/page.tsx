"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import CandlestickChart from "@/components/CandlestickChart";
import { api, type Candle } from "@/lib/api-client";

/** Analisa teknikal dengan chart penuh layar: semua indikator RFraktal dan alat gambar dasar. */

type Asset = { label: string; name: string; source: "binance" | "yahoo"; symbol: string; group: string };

// 20 aset proyek (praregistrasi generalisasi §2).
const ASSETS: Asset[] = [
  { label: "BTC/USDT", name: "Bitcoin", source: "binance", symbol: "BTCUSDT", group: "Kripto" },
  { label: "ETH/USDT", name: "Ethereum", source: "binance", symbol: "ETHUSDT", group: "Kripto" },
  { label: "BNB/USDT", name: "BNB", source: "binance", symbol: "BNBUSDT", group: "Kripto" },
  { label: "SOL/USDT", name: "Solana", source: "binance", symbol: "SOLUSDT", group: "Kripto" },
  { label: "XRP/USDT", name: "XRP", source: "binance", symbol: "XRPUSDT", group: "Kripto" },
  { label: "ADA/USDT", name: "Cardano", source: "binance", symbol: "ADAUSDT", group: "Kripto" },
  { label: "DOGE/USDT", name: "Dogecoin", source: "binance", symbol: "DOGEUSDT", group: "Kripto" },
  { label: "GC=F", name: "Emas berjangka (COMEX)", source: "yahoo", symbol: "GC=F", group: "Emas" },
  { label: "PAXG/USDT", name: "PAX Gold", source: "binance", symbol: "PAXGUSDT", group: "Emas" },
  { label: "IHSG", name: "Indeks Harga Saham Gabungan", source: "yahoo", symbol: "^JKSE", group: "Saham IDX" },
  { label: "BBCA", name: "Bank Central Asia", source: "yahoo", symbol: "BBCA.JK", group: "Saham IDX" },
  { label: "BBRI", name: "Bank Rakyat Indonesia", source: "yahoo", symbol: "BBRI.JK", group: "Saham IDX" },
  { label: "BMRI", name: "Bank Mandiri", source: "yahoo", symbol: "BMRI.JK", group: "Saham IDX" },
  { label: "BBNI", name: "Bank Negara Indonesia", source: "yahoo", symbol: "BBNI.JK", group: "Saham IDX" },
  { label: "TLKM", name: "Telkom Indonesia", source: "yahoo", symbol: "TLKM.JK", group: "Saham IDX" },
  { label: "ASII", name: "Astra International", source: "yahoo", symbol: "ASII.JK", group: "Saham IDX" },
  { label: "ANTM", name: "Aneka Tambang", source: "yahoo", symbol: "ANTM.JK", group: "Saham IDX" },
  { label: "UNVR", name: "Unilever Indonesia", source: "yahoo", symbol: "UNVR.JK", group: "Saham IDX" },
  { label: "ICBP", name: "Indofood CBP", source: "yahoo", symbol: "ICBP.JK", group: "Saham IDX" },
  { label: "ADRO", name: "Alamtri Resources (Adaro)", source: "yahoo", symbol: "ADRO.JK", group: "Saham IDX" },
];
const GROUPS = Array.from(new Set(ASSETS.map((a) => a.group)));
const INTERVALS = [
  { label: "15m", tf: "15m", name: "15 menit" },
  { label: "1H", tf: "1h", name: "1 jam" },
  { label: "4H", tf: "4h", name: "4 jam" },
  { label: "1D", tf: "1d", name: "1 hari" },
  { label: "1W", tf: "1w", name: "1 minggu" },
];
// Rentang awal yang wajar per timeframe.
const DEFAULT_RANGE: Record<string, string> = { "15m": "1D", "1h": "1M", "4h": "3M", "1d": "1Y", "1w": "ALL" };

/** Menu tarik-turun sederhana: tutup saat klik di luar atau tekan Esc. */
function useDismiss(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);
  return ref;
}

const chevron = (
  <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 text-txtMuted" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
    <path d="M5 8 L10 13 L15 8" />
  </svg>
);

function SymbolPicker({ asset, onPick }: { asset: Asset; onPick: (a: Asset) => void }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useDismiss(open, () => setOpen(false));
  const hits = useMemo(() => {
    const t = q.trim().toLowerCase();
    return t ? ASSETS.filter((a) => `${a.label} ${a.name} ${a.symbol}`.toLowerCase().includes(t)) : ASSETS;
  }, [q]);
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => {
          setQ("");
          setOpen((o) => !o);
        }}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex items-center gap-2 rounded-md px-2 py-1 transition hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
      >
        <svg viewBox="0 0 20 20" className="h-4 w-4 text-txtMuted" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <circle cx="8.5" cy="8.5" r="5.5" />
          <path d="M13 13 L17 17" />
        </svg>
        <span className="text-[14px] font-semibold tracking-tight text-txt">{asset.label}</span>
        <span className="hidden text-[11.5px] text-txtMuted md:inline">{asset.source === "binance" ? "Binance" : "Yahoo"}</span>
        {chevron}
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-[320px] overflow-hidden rounded-lg border border-edge bg-panel shadow-panel">
          <div className="border-b border-edge p-2">
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && hits[0]) {
                  onPick(hits[0]);
                  setOpen(false);
                }
              }}
              placeholder="Cari aset, mis. ETH, emas, BBCA"
              aria-label="Cari aset"
              className="w-full rounded-md border border-edge bg-panelAlt px-2.5 py-1.5 text-[13px] text-txt placeholder:text-txtMuted focus:border-accent/60 focus:outline-none"
            />
          </div>
          <div className="max-h-[60vh] overflow-y-auto py-1" role="listbox" aria-label="Aset">
            {GROUPS.map((g) => {
              const items = hits.filter((a) => a.group === g);
              if (!items.length) return null;
              return (
                <div key={g}>
                  <div className="px-3 pb-1 pt-2 text-2xs uppercase tracking-wider text-txtMuted">{g}</div>
                  {items.map((a) => (
                    <button
                      key={a.symbol}
                      type="button"
                      role="option"
                      aria-selected={a.symbol === asset.symbol}
                      onClick={() => {
                        onPick(a);
                        setOpen(false);
                      }}
                      className={`flex w-full items-center justify-between gap-3 px-3 py-1.5 text-left transition hover:bg-surface ${
                        a.symbol === asset.symbol ? "bg-accent/10" : ""
                      }`}
                    >
                      <span className="min-w-0">
                        <span className={`block text-[13px] font-medium ${a.symbol === asset.symbol ? "text-accent" : "text-txt"}`}>{a.label}</span>
                        <span className="block truncate text-[11.5px] text-txtMuted">{a.name}</span>
                      </span>
                      <span className="shrink-0 text-[11px] text-txtMuted">{a.source === "binance" ? "Binance" : "Yahoo"}</span>
                    </button>
                  ))}
                </div>
              );
            })}
            {!hits.length && <div className="px-3 py-4 text-center text-[12.5px] text-txtMuted">Aset tidak ditemukan.</div>}
          </div>
        </div>
      )}
    </div>
  );
}

function IntervalPicker({ tf, onPick }: { tf: string; onPick: (tf: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(open, () => setOpen(false));
  const cur = INTERVALS.find((i) => i.tf === tf) ?? INTERVALS[1];
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
        title="Timeframe"
        className="flex items-center gap-1 rounded-md px-2 py-1 font-mono text-[13px] font-semibold text-txt transition hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
      >
        {cur.label}
        {chevron}
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-40 overflow-hidden rounded-lg border border-edge bg-panel py-1 shadow-panel" role="listbox" aria-label="Timeframe">
          {INTERVALS.map((i) => (
            <button
              key={i.tf}
              type="button"
              role="option"
              aria-selected={i.tf === tf}
              onClick={() => {
                onPick(i.tf);
                setOpen(false);
              }}
              className={`flex w-full items-center justify-between px-3 py-1.5 text-[13px] transition hover:bg-surface ${i.tf === tf ? "text-accent" : "text-txt"}`}
            >
              <span>{i.name}</span>
              <span className="font-mono text-[12px] text-txtMuted">{i.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AnalisaTeknikalPage() {
  const [asset, setAsset] = useState(ASSETS[0]);
  const [tf, setTf] = useState("1h");
  const [candles, setCandles] = useState<Candle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [full, setFull] = useState(false);
  const shell = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let stop = false;
    // Kosongkan dulu agar candle aset lama tidak tampil dengan nama aset baru.
    setCandles([]);
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

  useEffect(() => {
    const onChange = () => setFull(document.fullscreenElement === shell.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  const toggleFull = () => {
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
    else void shell.current?.requestFullscreen().catch(() => undefined);
  };

  const sep = <span className="mx-1 h-5 w-px bg-edge" aria-hidden />;

  return (
    <div ref={shell} className="h-full bg-panel">
      <CandlestickChart
        key={`${asset.symbol}-${tf}`}
        fill
        candles={candles}
        showRegime={false}
        symbol={asset.label}
        timeframe={tf}
        defaultRange={DEFAULT_RANGE[tf] ?? "3M"}
        indicators
        depthSymbol={asset.source === "binance" ? asset.symbol : undefined}
        drawingKey={`${asset.symbol}:${tf}`}
        emptyMessage={
          error ? `Data ${asset.label} ${tf.toUpperCase()} gagal dimuat: ${error}` : loading ? `Memuat ${asset.label} ${tf.toUpperCase()}…` : undefined
        }
        toolbarStart={
          <>
            <SymbolPicker asset={asset} onPick={setAsset} />
            {sep}
            <IntervalPicker tf={tf} onPick={setTf} />
          </>
        }
        toolbarEnd={
          <button
            type="button"
            onClick={toggleFull}
            aria-pressed={full}
            title={full ? "Keluar layar penuh (Esc)" : "Layar penuh"}
            aria-label={full ? "Keluar layar penuh" : "Layar penuh"}
            className="rounded-md p-1.5 text-txtMuted transition hover:bg-surface hover:text-txt focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            <svg viewBox="0 0 20 20" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
              {full ? <path d="M8 3v5H3M12 3v5h5M8 17v-5H3M12 17v-5h5" /> : <path d="M3 8V3h5M17 8V3h-5M3 12v5h5M17 12v5h-5" />}
            </svg>
          </button>
        }
        footerNote={
          <span title="Data dari Binance (kripto, PAXG) dan Yahoo Finance (emas, saham IDX), maksimal 1.500 candle. Gambar tersimpan di peramban ini.">
            {asset.source === "binance" ? "Binance" : "Yahoo Finance"} · bukan hasil sistem regime, lihat{" "}
            <Link href="/" className="text-accent hover:underline">Ringkasan</Link> · bukan saran investasi
          </span>
        }
      />
    </div>
  );
}

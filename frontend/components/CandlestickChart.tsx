"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ColorType,
  createChart,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { Candle, RegimePoint } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, SEGMENT_META, type Regime } from "@/lib/regime";
import { themeColor, useTheme } from "@/lib/theme";

/**
 * Candlestick bergaya terminal perdagangan.
 *
 * Tiga lapis digambar pada satu chart:
 *  1. Band regime  — HistogramSeries tinggi penuh pada price scale tersembunyi,
 *     dibuat lebih dulu agar berada di lapisan paling belakang.
 *  2. Candlestick  — deret utama.
 *  3. Volume       — histogram di 18% bawah, price scale terpisah.
 *
 * Legend OHLC mengikuti posisi crosshair; saat kursor keluar area, legend
 * kembali menampilkan bar terakhir supaya tidak pernah kosong.
 */

const EMPTY_REGIMES: RegimePoint[] = [];
const EMPTY_SEGMENTS: { segment: string; start_time: number; end_time: number }[] = [];

// Rentang dinyatakan dalam DETIK, bukan jumlah bar. Versi berbasis bar
// menganggap 1 bar = 1 jam, sehingga "1Y" pada 4H menampilkan empat tahun.
const DAY = 24 * 3600;
const RANGES = [
  { label: "1D", seconds: DAY },
  { label: "1M", seconds: 30 * DAY },
  { label: "3M", seconds: 90 * DAY },
  { label: "1Y", seconds: 365 * DAY },
  { label: "ALL", seconds: 0 },
];

function hexToRgba(hex: string, alpha: number): string {
  const v = hex.replace("#", "");
  const n = parseInt(v, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function regimeBandColor(regime: string): string {
  const meta = REGIME_META[regime as Regime];
  if (!meta) return "rgba(51,65,85,0.10)";
  // Acak adalah kondisi paling umum (±76% waktu); pitanya dibuat paling samar
  // agar kondisi yang jarang (berlanjut/berbalik) menonjol.
  const alpha = regime === "random_like" ? 0.05 : meta.pattern === "solid" ? 0.12 : 0.16;
  return hexToRgba(meta.color, alpha);
}

interface HoverInfo {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  regime?: string;
}

export default function CandlestickChart({
  candles,
  regimes = EMPTY_REGIMES,
  segments = EMPTY_SEGMENTS,
  height = 420,
  showRegime = true,
  symbol = "BTC/USDT",
  timeframe = "1H",
  showToolbar = true,
  defaultRange = "ALL",
  legend,
}: {
  candles: Candle[];
  regimes?: RegimePoint[];
  segments?: { segment: string; start_time: number; end_time: number }[];
  height?: number;
  showRegime?: boolean;
  symbol?: string;
  timeframe?: string;
  showToolbar?: boolean;
  /** Rentang yang terlihat saat pertama tampil. Seluruh data tetap dimuat. */
  defaultRange?: string;
  legend?: React.ReactNode;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const bandRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const regimeByTime = useRef<Map<number, string>>(new Map());

  const [hover, setHover] = useState<HoverInfo | null>(null);
  const [activeRange, setActiveRange] = useState<string>(defaultRange);

  // Efek 1 — membuat chart. Hanya bergantung pada `height`, sehingga instance
  // tidak dibongkar setiap kali data berubah.
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#131518" },
        textColor: "#a8a29b",
        fontSize: 11,
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      },
      grid: {
        vertLines: { color: "rgba(39,43,49,0.45)" },
        horzLines: { color: "rgba(39,43,49,0.45)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: "rgba(139,148,158,0.5)",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#323b48",
        },
        horzLine: {
          color: "rgba(139,148,158,0.5)",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#323b48",
        },
      },
      rightPriceScale: {
        borderColor: "#272b31",
        scaleMargins: { top: 0.08, bottom: 0.24 },
      },
      timeScale: {
        borderColor: "#272b31",
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true },
    });
    chartRef.current = chart;

    // Band regime dibuat lebih dulu agar berada di lapisan belakang.
    const band = chart.addHistogramSeries({
      priceScaleId: "regime-band",
      priceLineVisible: false,
      lastValueVisible: false,
      base: 0,
    });
    chart.priceScale("regime-band").applyOptions({
      scaleMargins: { top: 0, bottom: 0 },
      visible: false,
    });
    bandRef.current = band;

    seriesRef.current = chart.addCandlestickSeries({
      upColor: "#2ebd85",
      downColor: "#f6465d",
      borderUpColor: "#2ebd85",
      borderDownColor: "#f6465d",
      wickUpColor: "#2ebd85",
      wickDownColor: "#f6465d",
      priceLineColor: "rgba(139,148,158,0.5)",
      priceLineStyle: LineStyle.Dotted,
    });

    const volume = chart.addHistogramSeries({
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
      visible: false,
    });
    volumeRef.current = volume;

    const observer = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      bandRef.current = null;
      volumeRef.current = null;
    };
  }, [height]);

  // Efek 1b — warna mengikuti tema. Canvas tidak memahami var(), jadi token
  // tema dibaca sebagai warna jadi dan diterapkan ulang saat tema berganti.
  const theme = useTheme();
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const edge = themeColor("edge");
    const label = themeColor("txt-dim");
    chart.applyOptions({
      layout: { background: { type: ColorType.Solid, color: themeColor("panel") }, textColor: themeColor("txt-dim") },
      grid: { vertLines: { color: themeColor("edge", 0.55) }, horzLines: { color: themeColor("edge", 0.55) } },
      crosshair: { vertLine: { labelBackgroundColor: label }, horzLine: { labelBackgroundColor: label } },
      rightPriceScale: { borderColor: edge },
      timeScale: { borderColor: edge },
    });
  }, [theme, height]);

  // Rentang aktif dibaca lewat ref agar efek data tidak ikut berjalan ulang
  // setiap kali pengguna menekan tombol rentang.
  const rangeRef = useRef(activeRange);
  rangeRef.current = activeRange;

  const showRange = useCallback(
    (label: string) => {
      const chart = chartRef.current;
      if (!chart || candles.length === 0) return;
      const spec = RANGES.find((r) => r.label === label);
      const last = candles[candles.length - 1].time;
      const from = spec && spec.seconds > 0 ? last - spec.seconds : null;
      if (from === null || from <= candles[0].time) {
        chart.timeScale().fitContent();
        return;
      }
      chart.timeScale().setVisibleRange({ from: from as Time, to: last as Time });
    },
    [candles]
  );

  // Efek 2a — candle & volume. Hanya berjalan saat candle berganti.
  //
  // Dipisah dari overlay regime: regime datang belakangan, dan dulu
  // kedatangannya memicu setData ulang atas seluruh candle — pada riwayat
  // penuh (~68 ribu bar) itu pekerjaan sia-sia yang membuat chart tersendat
  // tepat saat halaman baru terbuka.
  useEffect(() => {
    const series = seriesRef.current;
    const volume = volumeRef.current;
    if (!series || !volume || candles.length === 0) return;

    series.setData(
      candles.map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    volume.setData(
      candles.map((c) => ({
        time: c.time as Time,
        value: c.volume,
        color: c.close >= c.open ? "rgba(46,189,133,0.35)" : "rgba(246,70,93,0.35)",
      }))
    );

    showRange(rangeRef.current);

    const last = candles[candles.length - 1];
    setHover({
      time: last.time,
      open: last.open,
      high: last.high,
      low: last.low,
      close: last.close,
      volume: last.volume,
      regime: regimeByTime.current.get(last.time),
    });
  }, [candles, showRange]);

  // Efek 2b — overlay regime dan penanda split.
  useEffect(() => {
    const series = seriesRef.current;
    const band = bandRef.current;
    if (!series || !band || candles.length === 0) return;

    const lookup = new Map<number, string>();
    if (showRegime && regimes.length > 0) {
      // Regime dihitung per window (lebih jarang dari bar) — perluas ke depan
      // sampai window berikutnya supaya bandnya kontinu.
      const sorted = [...regimes].sort((a, b) => a.time - b.time);
      let ptr = 0;
      band.setData(
        candles.map((c) => {
          while (ptr + 1 < sorted.length && sorted[ptr + 1].time <= c.time) ptr += 1;
          const active = sorted[ptr] && sorted[ptr].time <= c.time ? sorted[ptr] : null;
          if (active) lookup.set(c.time, active.regime);
          return {
            time: c.time as Time,
            value: 1,
            color: active ? regimeBandColor(active.regime) : "rgba(0,0,0,0)",
          };
        })
      );
    } else {
      band.setData([]);
    }
    regimeByTime.current = lookup;

    series.setMarkers(
      segments
        .filter((s) => s.segment !== "train")
        .map((s) => ({
          time: s.start_time as Time,
          position: "aboveBar" as const,
          color: s.segment.startsWith("purge") ? "#f6465d" : "#f0b90b",
          shape: "arrowDown" as const,
          text: SEGMENT_META[s.segment.replace(/_\d+$/, "")]?.label ?? s.segment,
        }))
    );

    // Tanpa fitContent di sini: overlay yang datang belakangan tidak boleh
    // melempar pengguna keluar dari rentang yang sedang dilihatnya.
    const last = candles[candles.length - 1];
    setHover((h) =>
      h && h.time !== last.time ? h : { ...(h ?? last), regime: lookup.get(last.time) }
    );
  }, [candles, regimes, segments, showRegime]);

  // Efek 3 — legend OHLC mengikuti crosshair.
  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series || candles.length === 0) return;

    const byTime = new Map(candles.map((c) => [c.time, c]));

    const handler = (param: any) => {
      const t = param?.time as number | undefined;
      if (t === undefined) {
        // Kursor keluar area: kembalikan ke bar terakhir agar legend tidak kosong.
        const last = candles[candles.length - 1];
        setHover({
          time: last.time,
          open: last.open,
          high: last.high,
          low: last.low,
          close: last.close,
          volume: last.volume,
          regime: regimeByTime.current.get(last.time),
        });
        return;
      }
      const c = byTime.get(t);
      if (c) {
        setHover({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
          regime: regimeByTime.current.get(c.time),
        });
      }
    };

    chart.subscribeCrosshairMove(handler);
    return () => chart.unsubscribeCrosshairMove(handler);
  }, [candles]);

  const applyRange = useCallback(
    (label: string) => {
      setActiveRange(label);
      showRange(label);
    },
    [showRange]
  );

  if (candles.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded border border-edge text-xs text-txtMuted"
        style={{ height }}
      >
        Tidak ada data candle.
      </div>
    );
  }

  const change = hover ? hover.close - hover.open : 0;
  const changePct = hover && hover.open ? (change / hover.open) * 100 : 0;
  const up = change >= 0;
  const fmt = (v: number) =>
    v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="overflow-hidden rounded-md border border-edge bg-panel">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-edge bg-surface/40 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="font-sans text-[13px] font-semibold tracking-tight text-txt">
            {symbol}
          </span>
          <span className="rounded bg-edge px-1.5 py-0.5 font-mono text-2xs text-txtDim">
            {timeframe.toUpperCase()}
          </span>
        </div>

        {hover && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] tabular-nums">
            {(
              [
                ["O", hover.open],
                ["H", hover.high],
                ["L", hover.low],
                ["C", hover.close],
              ] as [string, number][]
            ).map(([k, v]) => (
              <span key={k} className="text-txtMuted">
                {k}
                <span className={`ml-1 ${up ? "text-bullish" : "text-bearish"}`}>{fmt(v)}</span>
              </span>
            ))}
            <span className={up ? "badge-up" : "badge-down"}>
              {up ? "+" : ""}
              {fmt(change)} ({up ? "+" : ""}
              {changePct.toFixed(2)}%)
            </span>
            <span className="text-txtMuted">
              Vol<span className="ml-1 text-txtDim">{hover.volume.toFixed(2)}</span>
            </span>
            {hover.regime && (
              <span
                className="rounded px-1.5 py-0.5 text-2xs font-medium"
                style={{
                  backgroundColor: hexToRgba(
                    REGIME_META[hover.regime as Regime]?.color ?? "#252c37",
                    0.16
                  ),
                  color: REGIME_META[hover.regime as Regime]?.color ?? "#8b949e",
                }}
              >
                {REGIME_PLAIN[hover.regime as Regime]?.name ?? hover.regime}
              </span>
            )}
          </div>
        )}

        {showToolbar && (
          <div className="ml-auto flex overflow-hidden rounded border border-edge">
            {RANGES.map((r) => (
              <button
                key={r.label}
                onClick={() => applyRange(r.label)}
                className={`px-2.5 py-1 font-mono text-2xs transition ${
                  activeRange === r.label
                    ? "bg-accent/20 text-accent"
                    : "text-txtMuted hover:bg-surface hover:text-txtDim"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div ref={containerRef} className="w-full" />

      {legend && <div className="border-t border-edge px-3 py-2">{legend}</div>}
    </div>
  );
}

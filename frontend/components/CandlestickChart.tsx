"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ColorType,
  createChart,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import IndicatorPicker from "@/components/IndicatorPicker";
import type { Candle, RegimePoint } from "@/lib/api-client";
import {
  INDICATOR_COLORS,
  bollinger,
  crosses,
  depthRows,
  loadActive,
  saveActive,
  sma,
  type IndicatorId,
} from "@/lib/indicators";
import { REGIME_META, REGIME_PLAIN, SEGMENT_META, type Regime } from "@/lib/regime";
import { themeColor, useTheme } from "@/lib/theme";

/** Candlestick bergaya terminal perdagangan. */

const EMPTY_REGIMES: RegimePoint[] = [];
const EMPTY_SEGMENTS: { segment: string; start_time: number; end_time: number }[] = [];

// Rentang dinyatakan dalam DETIK, bukan jumlah bar.
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
  // Acak adalah kondisi paling umum (±76% waktu).
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
  indicators = false,
  depthSymbol,
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
  /** Tampilkan tombol Indikator (MA 15 + MA 50, Bollinger, liquidity heatmap). */
  indicators?: boolean;
  /** Simbol Binance spot untuk liquidity heatmap, mis. "BTCUSDT". */
  depthSymbol?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const bandRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const lineRefs = useRef<Record<string, ISeriesApi<"Line">>>({});
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const depthRef = useRef<{ bids: [number, number][]; asks: [number, number][]; at: number } | null>(null);
  const regimeByTime = useRef<Map<number, string>>(new Map());

  const [hover, setHover] = useState<HoverInfo | null>(null);
  const [activeRange, setActiveRange] = useState<string>(defaultRange);
  const [active, setActive] = useState<IndicatorId[]>([]);
  const [depthStatus, setDepthStatus] = useState<string | null>(null);

  // Pilihan indikator dibaca setelah mount agar tidak beda dengan render server.
  useEffect(() => {
    if (indicators) setActive(loadActive());
  }, [indicators]);
  const toggleIndicator = useCallback((id: IndicatorId) => {
    setActive((cur) => {
      const next = cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
      saveActive(next);
      return next;
    });
  }, []);
  const show = (id: IndicatorId) => indicators && active.includes(id) && (id !== "heatmap" || Boolean(depthSymbol));

  // Efek 1 — membuat chart.
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

    // Garis indikator; kosong sampai diaktifkan.
    const line = (color: string, width: 1 | 2, style: LineStyle = LineStyle.Solid) =>
      chart.addLineSeries({
        color,
        lineWidth: width,
        lineStyle: style,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    lineRefs.current = {
      ma15: line(INDICATOR_COLORS.ma15, 2),
      ma50: line(INDICATOR_COLORS.ma50, 2),
      bbUpper: line(hexToRgba(INDICATOR_COLORS.bb, 0.75), 1),
      bbMid: line(INDICATOR_COLORS.bb, 1, LineStyle.Dashed),
      bbLower: line(hexToRgba(INDICATOR_COLORS.bb, 0.75), 1),
    };

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
      lineRefs.current = {};
    };
  }, [height]);

  // Efek 1b — warna mengikuti tema.
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

  // Rentang aktif dibaca lewat ref.
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

  // Efek 2a — candle & volume.
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
      // Regime dihitung per window (lebih jarang dari bar).
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

    // Tanpa fitContent di sini: overlay.
    const last = candles[candles.length - 1];
    setHover((h) =>
      h && h.time !== last.time ? h : { ...(h ?? last), regime: lookup.get(last.time) }
    );
  }, [candles, regimes, segments, showRegime]);

  const showTrend = show("trend");
  const showMeanrev = show("meanrev");
  const showHeatmap = show("heatmap");

  // Efek 2c — garis indikator dan penanda (split + persilangan MA).
  useEffect(() => {
    const series = seriesRef.current;
    const L = lineRefs.current;
    if (!series || !L.ma15 || candles.length === 0) return;
    const closes = candles.map((c) => c.close);
    const toLine = (vals: (number | null)[]) =>
      vals.flatMap((v, i) => (v == null ? [] : [{ time: candles[i].time as Time, value: v }]));

    const ma15 = sma(closes, 15);
    const ma50 = sma(closes, 50);
    L.ma15.setData(showTrend ? toLine(ma15) : []);
    L.ma50.setData(showTrend ? toLine(ma50) : []);
    const bb = showMeanrev ? bollinger(closes, 20, 2) : null;
    L.bbUpper.setData(bb ? toLine(bb.upper) : []);
    L.bbMid.setData(bb ? toLine(bb.mid) : []);
    L.bbLower.setData(bb ? toLine(bb.lower) : []);

    const markers: SeriesMarker<Time>[] = segments
      .filter((s) => s.segment !== "train")
      .map((s) => ({
        time: s.start_time as Time,
        position: "aboveBar" as const,
        color: s.segment.startsWith("purge") ? "#f6465d" : "#f0b90b",
        shape: "arrowDown" as const,
        text: SEGMENT_META[s.segment.replace(/_\d+$/, "")]?.label ?? s.segment,
      }));
    if (showTrend) {
      // Hanya persilangan terbaru agar chart tidak penuh panah.
      for (const x of crosses(ma15, ma50).slice(-12)) {
        markers.push({
          time: candles[x.i].time as Time,
          position: x.dir === "up" ? "belowBar" : "aboveBar",
          color: x.dir === "up" ? "#2ebd85" : "#f6465d",
          shape: x.dir === "up" ? "arrowUp" : "arrowDown",
          size: 0.6,
        });
      }
    }
    markers.sort((a, b) => (a.time as number) - (b.time as number));
    series.setMarkers(markers);
  }, [candles, segments, showTrend, showMeanrev]);

  // Efek 2d — liquidity heatmap: ambil order book Binance tiap 15 detik.
  useEffect(() => {
    if (!showHeatmap || !depthSymbol) {
      depthRef.current = null;
      setDepthStatus(null);
      return;
    }
    let stop = false;
    const load = async () => {
      try {
        const res = await fetch(`https://data-api.binance.vision/api/v3/depth?symbol=${encodeURIComponent(depthSymbol)}&limit=5000`, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const snap = await res.json();
        const bids: [number, number][] = snap.bids.map((x: string[]) => [Number(x[0]), Number(x[1])]);
        const asks: [number, number][] = snap.asks.map((x: string[]) => [Number(x[0]), Number(x[1])]);
        if (stop || !bids.length || !asks.length) return;
        depthRef.current = { bids, asks, at: Date.now() };
        const lo = bids[bids.length - 1][0], hi = asks[asks.length - 1][0];
        setDepthStatus(
          `order book ${lo.toLocaleString("en-US", { maximumFractionDigits: 2 })}–${hi.toLocaleString("en-US", { maximumFractionDigits: 2 })} · ${new Date().toLocaleTimeString("id-ID")}`,
        );
      } catch (e: any) {
        if (!stop) setDepthStatus(`order book gagal dimuat (${e?.message ?? "jaringan"})`);
      }
    };
    void load();
    const id = window.setInterval(load, 15000);
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [showHeatmap, depthSymbol]);

  // Efek 2e — gambar heatmap di kanvas di atas chart, mengikuti skala harga.
  useEffect(() => {
    const canvas = overlayRef.current;
    if (!showHeatmap || !canvas) return;
    let raf = 0;
    let lastKey = "";
    const ROW = 3; // tinggi baris heatmap (piksel)
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const chart = chartRef.current;
      const series = seriesRef.current;
      const box = containerRef.current;
      const ctx = canvas.getContext("2d");
      if (!chart || !series || !box || !ctx) return;
      const data = depthRef.current;
      const w = box.clientWidth, h = box.clientHeight;
      const paneW = chart.timeScale().width();
      const paneH = h - chart.timeScale().height();
      // Gambar ulang hanya bila skala harga, ukuran, atau data berubah.
      const key = `${series.coordinateToPrice(0)}|${series.coordinateToPrice(paneH)}|${w}|${h}|${paneW}|${data?.at ?? 0}`;
      if (key === lastKey) return;
      lastKey = key;
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
        canvas.style.width = `${w}px`;
        canvas.style.height = `${h}px`;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      if (!data) return;
      const rows = depthRows(data.bids, data.asks, (p) => series.priceToCoordinate(p), ROW, paneH);
      const max = Math.max(...rows.map((r) => Math.max(r.bid, r.ask)), 1e-12);
      let topBid = rows[0], topAsk = rows[0];
      for (const r of rows) {
        for (const side of ["bid", "ask"] as const) {
          const q = r[side];
          if (q <= 0) continue;
          const s = Math.sqrt(q / max);
          const [cr, cg, cb] = INDICATOR_COLORS[side];
          // Pita tipis selebar chart + profil kedalaman di tepi kanan.
          ctx.fillStyle = `rgba(${cr},${cg},${cb},${0.02 + 0.14 * s})`;
          ctx.fillRect(0, r.y, paneW, ROW);
          ctx.fillStyle = `rgba(${cr},${cg},${cb},${0.3 + 0.6 * s})`;
          const len = Math.max(2, paneW * 0.25 * s);
          ctx.fillRect(paneW - len, r.y, len, ROW);
        }
        if (r.bid > topBid.bid) topBid = r;
        if (r.ask > topAsk.ask) topAsk = r;
      }
      ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
      ctx.textAlign = "right";
      for (const side of ["bid", "ask"] as const) {
        const r = side === "bid" ? topBid : topAsk;
        if (!r || r[side] <= 0) continue;
        const price = side === "bid" ? r.bidPrice : r.askPrice;
        const y = r.y + (side === "bid" ? ROW + 11 : -3);
        if (y < 10 || y > paneH - 2) continue;
        const [cr, cg, cb] = INDICATOR_COLORS[side];
        const label = `${side} ${price.toLocaleString("en-US", { maximumFractionDigits: 2 })} · ${r[side].toLocaleString("en-US", { maximumFractionDigits: 1 })}`;
        const tw = ctx.measureText(label).width;
        ctx.fillStyle = themeColor("panel", 0.85);
        ctx.fillRect(paneW - 10 - tw, y - 10, tw + 8, 13);
        ctx.fillStyle = `rgb(${cr},${cg},${cb})`;
        ctx.fillText(label, paneW - 6, y);
      }
    };
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
    };
  }, [showHeatmap, theme]);

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

        {indicators && (
          <div className="ml-auto">
            <IndicatorPicker
              active={active}
              onToggle={toggleIndicator}
              currentRegime={regimes.length ? regimes[regimes.length - 1].regime : null}
              unavailable={depthSymbol ? {} : { heatmap: "Liquidity heatmap hanya tersedia untuk aset kripto Binance." }}
            />
          </div>
        )}

        {showToolbar && (
          <div className={`${indicators ? "" : "ml-auto "}flex overflow-hidden rounded border border-edge`}>
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

      {(showTrend || showMeanrev || showHeatmap) && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-edge px-3 py-1.5 font-mono text-2xs text-txtMuted">
          {showTrend && (
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-3" style={{ background: INDICATOR_COLORS.ma15 }} />
              MA 15
              <span className="ml-1.5 h-0.5 w-3" style={{ background: INDICATOR_COLORS.ma50 }} />
              MA 50 · panah = persilangan
            </span>
          )}
          {showMeanrev && (
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-3" style={{ background: INDICATOR_COLORS.bb }} />
              Bollinger 20, 2σ
            </span>
          )}
          {showHeatmap && (
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-3 rounded-sm" style={{ background: "linear-gradient(90deg, rgba(46,189,133,0.7), rgba(246,70,93,0.7))" }} />
              Likuiditas: {depthStatus ?? "memuat order book…"}
            </span>
          )}
        </div>
      )}

      <div className="relative w-full">
        <div ref={containerRef} className="w-full" />
        {showHeatmap && <canvas ref={overlayRef} className="pointer-events-none absolute left-0 top-0 z-[2]" aria-hidden />}
      </div>

      {legend && <div className="border-t border-edge px-3 py-2">{legend}</div>}
    </div>
  );
}

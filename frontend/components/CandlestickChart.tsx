"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ColorType,
  createChart,
  CrosshairMode,
  LineStyle,
  LineType,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import IndicatorPicker from "@/components/IndicatorPicker";
import { DRAW_TOOLS, fibPrices, loadDrawings, nearestIndex, saveDrawings, type DrawTool, type Drawing, type Point } from "@/lib/drawings";
import type { Candle, RegimePoint } from "@/lib/api-client";
import {
  INDICATOR_COLORS,
  bollinger,
  crosses,
  depthRows,
  loadActive,
  regimeAtCandles,
  regimeZSignals,
  saveActive,
  sma,
  zscore,
  type IndicatorId,
} from "@/lib/indicators";
import { anchoredVwap, sessionProfile, stopZones, type VwapAnchor } from "@/lib/orderflow-vwap";
import { REGIME_META, REGIME_PLAIN, SEGMENT_META, type Regime } from "@/lib/regime";
import { combine, statisticalTrailing, summarize, type StatsRow } from "@/lib/statistical-trailing";
import { rollingHurst } from "@/lib/hurst-rs";
import { orderBlocks, type OrderBlock } from "@/lib/order-blocks";
import { PROFILE_ROWS, formatVolume, volumetricStructure } from "@/lib/volumetric-structure";
import { themeColor, useTheme } from "@/lib/theme";

/** Candlestick bergaya terminal perdagangan. */

const EMPTY_REGIMES: RegimePoint[] = [];
const EMPTY_SEGMENTS: { segment: string; start_time: number; end_time: number }[] = [];

// Rentang dinyatakan dalam DETIK, bukan jumlah bar.
const DAY = 24 * 3600;
// seconds 0 = seluruh data, -1 = sejak 1 Januari tahun candle terakhir (YTD).
// compact = ikut tampil di tata letak kartu (Ringkasan); tata letak penuh menampilkan semuanya.
const RANGES = [
  { label: "1D", seconds: DAY, compact: true },
  { label: "7D", seconds: 7 * DAY, compact: false },
  { label: "1M", seconds: 30 * DAY, compact: true },
  { label: "3M", seconds: 90 * DAY, compact: true },
  { label: "6M", seconds: 182 * DAY, compact: false },
  { label: "YTD", seconds: -1, compact: false },
  { label: "1Y", seconds: 365 * DAY, compact: true },
  { label: "ALL", seconds: 0, compact: true },
];

/** Jam UTC di bar bawah tata letak penuh. */
function UtcClock() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <span className="shrink-0 font-mono text-[11.5px] tabular-nums text-txtDim">
      {now ? now.toISOString().slice(11, 19) : "--:--:--"} <span className="text-txtMuted">UTC</span>
    </span>
  );
}

function hexToRgba(hex: string, alpha: number): string {
  const v = hex.replace("#", "");
  const n = parseInt(v, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

/** Label kecil berlatar di kanvas (gaya seragam untuk semua indikator). */
function drawTag(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  color: string,
  align: "left" | "right" | "center" = "right",
) {
  ctx.font = "500 10px ui-sans-serif, system-ui, sans-serif";
  const tw = ctx.measureText(text).width;
  const w = tw + 8, h = 14;
  const left = align === "right" ? x - w : align === "center" ? x - w / 2 : x;
  ctx.fillStyle = themeColor("panel", 0.88);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(left, y - h / 2, w, h, 3);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText(text, left + 4, y + 0.5);
}

/** Mencegah label bertumpuk: true bila posisi y masih bebas (jarak minimal gap piksel). */
function claimRow(used: number[], y: number, gap = 15): boolean {
  if (used.some((u) => Math.abs(u - y) < gap)) return false;
  used.push(y);
  return true;
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

/** Satu baris legenda indikator bergaya TradingView: nama, nilai, mata (sembunyikan), silang (hapus). */
function LegendRow({
  name,
  values = [],
  note,
  hidden,
  onHide,
  onRemove,
}: {
  name: string;
  values?: { v: number | null | undefined; c: string; signed?: boolean }[];
  note?: string;
  hidden: boolean;
  onHide: () => void;
  onRemove?: () => void;
}) {
  const f = (x: { v: number | null | undefined; signed?: boolean }) =>
    x.v == null
      ? "–"
      : x.signed
        ? x.v.toLocaleString("en-US", { maximumFractionDigits: 2, signDisplay: "always" })
        : x.v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (
    <div className={`group flex items-center gap-2 ${hidden ? "opacity-50" : ""}`}>
      <span className="font-sans text-[12px] font-medium text-txt">{name}</span>
      {!hidden &&
        values.map((x, i) => (
          <span key={i} style={{ color: x.c }} className="tabular-nums">
            {f(x)}
          </span>
        ))}
      {!hidden && note && <span className="text-txtMuted">{note}</span>}
      <span className="pointer-events-auto flex items-center gap-0.5 text-txtMuted">
        <button
          type="button"
          onClick={onHide}
          title={hidden ? "Tampilkan" : "Sembunyikan"}
          aria-label={hidden ? `Tampilkan ${name}` : `Sembunyikan ${name}`}
          className="rounded px-1 hover:bg-surface hover:text-txt"
        >
          <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
            <path d="M1.5 10s3-6 8.5-6 8.5 6 8.5 6-3 6-8.5 6-8.5-6-8.5-6z" />
            {hidden ? <path d="M3 17L17 3" /> : <circle cx="10" cy="10" r="2.5" />}
          </svg>
        </button>
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            title="Hapus dari chart"
            aria-label={`Hapus ${name}`}
            className="rounded px-1 hover:bg-surface hover:text-txt"
          >
            ✕
          </button>
        )}
      </span>
    </div>
  );
}

/** Tabel statistik trailing stop statistik (adaptasi LuxAlgo, CC BY-NC-SA 4.0). */
function TrailStatsTable({ stats }: { stats: { long: StatsRow; short: StatsRow; total: StatsRow } }) {
  const p = (v: number | null, d = 2) => (v == null ? "–" : v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const rows: [string, (s: StatsRow) => string][] = [
    ["PnL (poin harga)", (s) => p(s.pnl)],
    ["Laba kotor", (s) => p(s.profit)],
    ["Rugi kotor", (s) => p(s.loss)],
    ["Trade", (s) => String(s.trades)],
    ["Menang / kalah", (s) => `${s.winners} / ${s.losers}`],
    ["Rata-rata menang", (s) => p(s.avgWinner)],
    ["Rata-rata kalah", (s) => p(s.avgLoser)],
    ["Win rate", (s) => (s.winRate == null ? "–" : `${(100 * s.winRate).toFixed(1)}%`)],
    ["R/R", (s) => p(s.rr)],
    ["Ekspektasi per trade", (s) => p(s.expectancy)],
    ["Rata-rata lama (candle)", (s) => (s.avgBars == null ? "–" : String(Math.round(s.avgBars)))],
  ];
  return (
    <details className="border-b border-edge px-3 py-1.5 text-2xs text-txtMuted">
      <summary className="cursor-pointer select-none">
        Statistik trailing stop pada seluruh data chart: {stats.total.trades} trade · win rate{" "}
        {stats.total.winRate == null ? "–" : `${(100 * stats.total.winRate).toFixed(1)}%`} · R/R {p(stats.total.rr)} · tanpa biaya transaksi
      </summary>
      <table className="mt-1.5 w-full max-w-[560px] font-mono">
        <thead>
          <tr className="border-b border-edge">
            <th className="py-1 text-left font-medium" />
            <th className="py-1 text-right font-medium">Beli</th>
            <th className="py-1 text-right font-medium">Jual</th>
            <th className="py-1 text-right font-medium">Total</th>
          </tr>
        </thead>
        <tbody className="text-txtDim">
          {rows.map(([label, f]) => (
            <tr key={label} className="border-b border-edge/40">
              <td className="py-0.5 font-sans">{label}</td>
              <td className="py-0.5 text-right">{f(stats.long)}</td>
              <td className="py-0.5 text-right">{f(stats.short)}</td>
              <td className="py-0.5 text-right text-txt">{f(stats.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
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
  abstainTau = 0.75,
  drawingKey,
  fill = false,
  toolbarStart,
  toolbarEnd,
  footerNote,
  emptyMessage,
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
  /** Di bawah keyakinan ini, regime dianggap ragu (tanpa sinyal dan tanpa rekomendasi). */
  abstainTau?: number;
  /** Aktifkan alat gambar; gambar disimpan di peramban per kunci ini (mis. aset + timeframe). */
  drawingKey?: string;
  /** Tata letak penuh bergaya terminal: mengisi tinggi induk, alat gambar di kiri, rentang di bawah. */
  fill?: boolean;
  /** Isi kiri toolbar atas pada tata letak penuh (mis. pemilih aset dan timeframe). */
  toolbarStart?: React.ReactNode;
  /** Isi kanan toolbar atas pada tata letak penuh (mis. tombol layar penuh). */
  toolbarEnd?: React.ReactNode;
  /** Catatan kecil di bar bawah tata letak penuh. */
  footerNote?: React.ReactNode;
  /** Pesan di area chart saat belum ada candle (tata letak penuh). */
  emptyMessage?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const bandRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const hurstRef = useRef<ISeriesApi<"Baseline"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const lineRefs = useRef<Record<string, ISeriesApi<"Line">>>({});
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const flowRef = useRef<HTMLCanvasElement>(null);
  const drawRef = useRef<HTMLCanvasElement>(null);
  const obRef = useRef<HTMLCanvasElement>(null);
  const vofsRef = useRef<HTMLCanvasElement>(null);
  const depthRef = useRef<{ bids: [number, number][]; asks: [number, number][]; at: number } | null>(null);
  const regimeByTime = useRef<Map<number, string>>(new Map());

  // Tata letak penuh: tinggi chart mengikuti tinggi area yang tersedia.
  const areaRef = useRef<HTMLDivElement>(null);
  const [fillH, setFillH] = useState(0);
  useEffect(() => {
    if (!fill || !areaRef.current) return;
    const el = areaRef.current;
    const ro = new ResizeObserver(() => setFillH(Math.floor(el.clientHeight)));
    ro.observe(el);
    return () => ro.disconnect();
  }, [fill]);
  const effH = fill ? Math.max(240, fillH || 480) : height;

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
  // Indikator aktif bisa disembunyikan sementara dari legenda (mata) tanpa dihapus.
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const toggleHidden = useCallback((id: string) => {
    setHidden((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);
  const isOn = (id: IndicatorId) =>
    indicators && active.includes(id) && (id !== "heatmap" || Boolean(depthSymbol)) && (id !== "zregime" || regimes.length > 0);
  const show = (id: IndicatorId) => isOn(id) && !hidden.has(id);
  // Regime berkeyakinan rendah diperlakukan sebagai ragu, sama seperti kartu kondisi pasar.
  const confidentRegimes = useMemo(
    () =>
      regimes.map((r) => {
        const conf = (r as RegimePoint & { confidence?: number }).confidence;
        return { time: r.time, regime: conf != null && conf < abstainTau ? "uncertain_lowconf" : r.regime };
      }),
    [regimes, abstainTau],
  );

  // Efek 1 — membuat chart.
  useEffect(() => {
    if (!containerRef.current) return;

    // TradingView Lightweight Charts™, Copyright (c) TradingView, Inc. https://www.tradingview.com/
    // Logo di chart dimatikan; atribusi dan tautan ke tradingview.com ada di komponen ChartCredits.
    const chart = createChart(containerRef.current, {
      height: effH,
      layout: {
        attributionLogo: false,
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
    // Label nilai terakhir di sumbu harga (seperti TradingView) untuk garis yang penting.
    const line = (color: string, width: 1 | 2, style: LineStyle = LineStyle.Solid, axisLabel = true) =>
      chart.addLineSeries({
        color,
        lineWidth: width,
        lineStyle: style,
        priceLineVisible: false,
        lastValueVisible: axisLabel,
        crosshairMarkerVisible: false,
      });
    lineRefs.current = {
      ma15: line(INDICATOR_COLORS.ma15, 2),
      ma50: line(INDICATOR_COLORS.ma50, 2),
      bbUpper: line(hexToRgba(INDICATOR_COLORS.bb, 0.75), 1),
      bbMid: line(INDICATOR_COLORS.bb, 1, LineStyle.Dashed, false),
      bbLower: line(hexToRgba(INDICATOR_COLORS.bb, 0.75), 1),
    };
    // Z-score di pita bawah chart (skala sendiri), dengan garis ±2 dan 0.
    const z = chart.addLineSeries({
      color: INDICATOR_COLORS.z,
      lineWidth: 1,
      priceScaleId: "zscore",
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
      autoscaleInfoProvider: () => ({ priceRange: { minValue: -3.5, maxValue: 3.5 } }),
    });
    chart.priceScale("zscore").applyOptions({ scaleMargins: { top: 0.8, bottom: 0.02 }, visible: false });
    for (const [price, title] of [[2, "+2"], [0, "0"], [-2, "−2"]] as const) {
      z.createPriceLine({
        price,
        color: price === 0 ? "rgba(148,163,184,0.7)" : price > 0 ? "rgba(246,70,93,0.85)" : "rgba(46,189,133,0.85)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: false,
        title,
      });
    }
    lineRefs.current.z = z;
    // VWAP sesi: garis netral; pita ±2σ tipis bertitik, koridornya diarsir di kanvas.
    lineRefs.current.vwap = line(INDICATOR_COLORS.neutral, 2);
    lineRefs.current.vwapUp = line(hexToRgba(INDICATOR_COLORS.neutral, 0.55), 1, LineStyle.Dotted, false);
    lineRefs.current.vwapLo = line(hexToRgba(INDICATOR_COLORS.neutral, 0.55), 1, LineStyle.Dotted, false);
    // Trailing stop sebagai garis bertangga: stop hanya bergeser pada candle tertentu.
    lineRefs.current.trail = line(INDICATOR_COLORS.up, 2);
    lineRefs.current.trail.applyOptions({ lineType: LineType.WithSteps });
    // Hurst bergulir: panel bawah sendiri, warna mengikuti warna kondisi pasar aplikasi
    // (biru = cenderung tren, kuning = cenderung berbalik, abu-abu = acak).
    const hPers = REGIME_META.persistent.color, hAnti = REGIME_META.anti_persistent.color;
    const hurst = chart.addBaselineSeries({
      priceScaleId: "hurst",
      baseValue: { type: "price", price: 0.5 },
      topLineColor: hPers,
      bottomLineColor: hAnti,
      topFillColor1: hexToRgba(hPers, 0.28),
      topFillColor2: hexToRgba(hPers, 0.02),
      bottomFillColor1: hexToRgba(hAnti, 0.02),
      bottomFillColor2: hexToRgba(hAnti, 0.28),
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
      priceFormat: { type: "price", precision: 3, minMove: 0.001 },
      autoscaleInfoProvider: (orig: () => { priceRange: { minValue: number; maxValue: number } } | null) => {
        const r = orig();
        return r ? { priceRange: { minValue: Math.min(r.priceRange.minValue, 0.4), maxValue: Math.max(r.priceRange.maxValue, 0.6) } } : null;
      },
    });
    chart.priceScale("hurst").applyOptions({ scaleMargins: { top: 0.8, bottom: 0.02 }, visible: false });
    for (const [price, color] of [[0.55, hexToRgba(hPers, 0.5)], [0.5, hexToRgba(REGIME_META.random_like.color, 0.6)], [0.45, hexToRgba(hAnti, 0.5)]] as const) {
      hurst.createPriceLine({ price, color, lineWidth: 1, lineStyle: price === 0.5 ? LineStyle.Solid : LineStyle.Dotted, axisLabelVisible: false, title: "" });
    }
    hurstRef.current = hurst;

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
      hurstRef.current = null;
      lineRefs.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fill ? 0 : height]);

  // Tata letak penuh: ubah tinggi tanpa membuat ulang chart (zoom dan geser tetap).
  useEffect(() => {
    if (fill) chartRef.current?.applyOptions({ height: effH });
  }, [fill, effH]);

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
      // Tanda air nama aset di tengah chart (tata letak penuh saja).
      watermark: {
        visible: fill,
        text: `${symbol} · ${timeframe.toUpperCase()}`,
        fontSize: 44,
        fontFamily: "ui-sans-serif, system-ui, sans-serif",
        fontStyle: "600",
        color: themeColor("txt-muted", 0.09),
        horzAlign: "center",
        vertAlign: "center",
      },
    });
  }, [theme, height, fill, symbol, timeframe]);

  // Rentang aktif dibaca lewat ref.
  const rangeRef = useRef(activeRange);
  rangeRef.current = activeRange;

  // Ruang kosong di kanan candle (dalam porsi rentang); dipakai profil volume Order Flow VWAP.
  const rightSpaceRef = useRef(0);

  const showRange = useCallback(
    (label: string) => {
      const chart = chartRef.current;
      if (!chart || candles.length === 0) return;
      const spec = RANGES.find((r) => r.label === label);
      const lastIdx = candles.length - 1;
      const last = candles[lastIdx].time;
      const from =
        spec && spec.seconds > 0
          ? last - spec.seconds
          : spec?.seconds === -1
            ? Date.UTC(new Date(last * 1000).getUTCFullYear(), 0, 1) / 1000
            : null;
      let fromIdx = 0;
      if (from !== null && from > candles[0].time) {
        fromIdx = candles.findIndex((c) => c.time >= from);
        if (fromIdx < 0) fromIdx = 0;
      }
      const span = Math.max(1, lastIdx - fromIdx);
      const extra = rightSpaceRef.current > 0 ? Math.max(span * rightSpaceRef.current, 30) : 6;
      chart.timeScale().setVisibleLogicalRange({ from: fromIdx, to: lastIdx + extra });
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
  const showZ = show("zregime");
  const showHeatmap = show("heatmap");
  const showFlow = show("ofvwap");
  const tfLower = timeframe.toLowerCase();
  const vwapAnchor: VwapAnchor = tfLower === "4h" ? "week" : tfLower === "1d" || tfLower === "1w" ? "month" : "day";
  // Order Flow VWAP Deviation: dihitung sekali per perubahan candle.
  const flow = useMemo(() => {
    if (!showFlow || candles.length === 0) return null;
    return { vwap: anchoredVwap(candles, vwapAnchor, 2), stops: stopZones(candles, 50, 10) };
  }, [showFlow, candles, vwapAnchor]);

  // Sisakan ruang kosong di kanan candle: ~35% untuk profil volume VWAP, ~12% (min. 30 candle)
  // untuk histogram order block Volumetric Order Flow Structure.
  const wantVofsSpace = show("vofs");
  useEffect(() => {
    rightSpaceRef.current = showFlow ? 0.35 : wantVofsSpace ? 0.12 : 0;
    showRange(rangeRef.current);
  }, [showFlow, wantVofsSpace, showRange]);

  // Pita kondisi pasar bisa disembunyikan dari legenda.
  const showBand = !hidden.has("regime");
  useEffect(() => {
    bandRef.current?.applyOptions({ visible: showBand });
  }, [showBand]);
  const showTrail = show("trail");
  const trail = useMemo(() => (showTrail && candles.length ? statisticalTrailing(candles, 100, 2) : null), [showTrail, candles]);
  const trailStats = useMemo(
    () => (trail ? { long: summarize(trail.long), short: summarize(trail.short), total: summarize(combine(trail.long, trail.short)) } : null),
    [trail],
  );
  const showHurst = show("hurst");
  const hurstCalc = useMemo(
    () => (showHurst && candles.length ? rollingHurst(candles.map((c) => c.close), 128, 5, 0.05) : null),
    [showHurst, candles],
  );

  // Panel bawah: Hurst paling bawah, Z-score di atasnya bila keduanya aktif; volume disembunyikan.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.priceScale("hurst").applyOptions({ scaleMargins: { top: 0.8, bottom: 0.02 } });
    chart.priceScale("zscore").applyOptions({ scaleMargins: showHurst ? { top: 0.6, bottom: 0.22 } : { top: 0.8, bottom: 0.02 } });
    chart.priceScale("right").applyOptions({ scaleMargins: { top: 0.08, bottom: showHurst && showZ ? 0.44 : 0.24 } });
    volumeRef.current?.applyOptions({ visible: !showZ && !showHurst });
    const s = hurstRef.current;
    if (!s) return;
    s.setData(
      hurstCalc
        ? candles.flatMap((c, i) => {
            const v = hurstCalc.smooth[i];
            if (v == null) return [];
            // Di dalam pita netral garis berwarna abu-abu.
            const neutral = hurstCalc.state[i] === 0;
            const grey = REGIME_META.random_like.color;
            return [{ time: c.time as Time, value: v, ...(neutral ? { topLineColor: grey, bottomLineColor: grey } : {}) }];
          })
        : [],
    );
  }, [hurstCalc, showHurst, showZ, candles]);

  // Deret indikator dihitung sekali per perubahan candle; dipakai garis dan legenda.
  const calc = useMemo(() => {
    if (candles.length === 0) return null;
    const closes = candles.map((c) => c.close);
    return {
      ma15: showTrend ? sma(closes, 15) : null,
      ma50: showTrend ? sma(closes, 50) : null,
      bb: showMeanrev ? bollinger(closes, 20, 2) : null,
      z: showZ ? zscore(closes, 20) : null,
    };
  }, [candles, showTrend, showMeanrev, showZ]);
  const indexByTime = useMemo(() => new Map(candles.map((c, i) => [c.time, i])), [candles]);
  const hoverIdx = hover ? indexByTime.get(hover.time) ?? candles.length - 1 : candles.length - 1;

  // Efek 2c — garis indikator dan penanda (split + persilangan MA).
  useEffect(() => {
    const series = seriesRef.current;
    const L = lineRefs.current;
    if (!series || !L.ma15 || !calc) return;
    const toLine = (vals: (number | null)[]) =>
      vals.flatMap((v, i) => (v == null ? [] : [{ time: candles[i].time as Time, value: v }]));

    const { ma15, ma50, bb, z } = calc;
    L.ma15.setData(ma15 ? toLine(ma15) : []);
    L.ma50.setData(ma50 ? toLine(ma50) : []);
    L.bbUpper.setData(bb ? toLine(bb.upper) : []);
    L.bbMid.setData(bb ? toLine(bb.mid) : []);
    L.bbLower.setData(bb ? toLine(bb.lower) : []);
    L.z.setData(z ? toLine(z) : []);
    // Pita bawah dipakai garis Z, jadi volume disembunyikan selama indikator ini aktif.
    volumeRef.current?.applyOptions({ visible: !showZ && !showHurst });
    L.vwap.setData(flow ? toLine(flow.vwap.vwap) : []);
    L.vwapUp.setData(flow ? toLine(flow.vwap.upper) : []);
    L.vwapLo.setData(flow ? toLine(flow.vwap.lower) : []);
    // Trailing stop: satu garis berwarna per titik. Warna segmen diambil dari titik awalnya,
    // jadi candle tepat sebelum pembalikan dibuat transparan agar lompatan tidak tergambar.
    const flipSet = new Set((trail?.flips ?? []).map((i) => i - 1));
    L.trail.setData(
      trail
        ? candles.flatMap((c, i) => {
            const v = trail.level[i];
            if (v == null) return [];
            const color = flipSet.has(i) ? "rgba(0,0,0,0)" : trail.bias[i] === "long" ? INDICATOR_COLORS.up : INDICATOR_COLORS.down;
            return [{ time: c.time as Time, value: v, color }];
          })
        : [],
    );

    const markers: SeriesMarker<Time>[] = segments
      .filter((s) => s.segment !== "train")
      .map((s) => ({
        time: s.start_time as Time,
        position: "aboveBar" as const,
        color: s.segment.startsWith("purge") ? "#f6465d" : "#f0b90b",
        shape: "arrowDown" as const,
        text: SEGMENT_META[s.segment.replace(/_\d+$/, "")]?.label ?? s.segment,
      }));
    if (ma15 && ma50) {
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
    if (z) {
      const reg = regimeAtCandles(candles.map((c) => c.time), confidentRegimes);
      // Sinyal terbaru saja agar chart tetap terbaca.
      for (const s of regimeZSignals(z, reg).slice(-40)) {
        markers.push(
          s.kind === "exit"
            ? { time: candles[s.i].time as Time, position: "inBar", color: "#94a3b8", shape: "circle", size: 0.5 }
            : {
                time: candles[s.i].time as Time,
                position: s.kind === "buy" ? "belowBar" : "aboveBar",
                color: s.kind === "buy" ? "#2ebd85" : "#f6465d",
                shape: s.kind === "buy" ? "arrowUp" : "arrowDown",
              },
        );
      }
    }
    if (trail) {
      // Pembalikan arah trailing stop: panah naik di bawah candle (beli), panah turun di atas (jual).
      // Hanya pembalikan terakhir yang diberi teks agar chart tidak penuh tulisan.
      const flips = trail.flips.slice(-80);
      flips.forEach((i, k) => {
        const long = trail.bias[i] === "long";
        markers.push({
          time: candles[i].time as Time,
          position: long ? "belowBar" : "aboveBar",
          color: long ? INDICATOR_COLORS.up : INDICATOR_COLORS.down,
          shape: long ? "arrowUp" : "arrowDown",
          size: 0.7,
          ...(k === flips.length - 1 ? { text: long ? "Beli" : "Jual" } : {}),
        });
      });
    }
    markers.sort((a, b) => (a.time as number) - (b.time as number));
    series.setMarkers(markers);
  }, [candles, segments, confidentRegimes, calc, flow, trail]);

  const times = useMemo(() => candles.map((c) => c.time), [candles]);

  // ---------------------------------------------------------------- order blocks
  const showOb = show("orderblocks");
  const obs = useMemo(() => {
    if (!showOb || candles.length === 0) return null;
    const r = orderBlocks(candles, 10, 3, 3, false);
    return [...r.bull, ...r.bear];
  }, [showOb, candles]);

  useEffect(() => {
    const canvas = obRef.current;
    if (!obs || !canvas) return;
    // Zona beli = hijau, zona jual = merah. Breaker berganti fungsi, jadi warnanya ikut berganti
    // (breaker dari zona beli kini menahan harga = merah) dan digambar sebagai garis putus-putus tanpa isian penuh.
    const UP = INDICATOR_COLORS.up, DOWN = INDICATOR_COLORS.down;
    const OB_CSS = {
      bull: { main: UP, brk: DOWN, name: "Zona beli", brkName: "Breaker · kini zona jual" },
      bear: { main: DOWN, brk: UP, name: "Zona jual", brkName: "Breaker · kini zona beli" },
    } as const;
    let raf = 0;
    let lastKey = "";
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const chart = chartRef.current, series = seriesRef.current, box = containerRef.current;
      const ctx = canvas.getContext("2d");
      if (!chart || !series || !box || !ctx) return;
      const ts = chart.timeScale();
      const w = box.clientWidth, h = box.clientHeight;
      const paneW = ts.width(), paneH = h - ts.height();
      const range = ts.getVisibleLogicalRange();
      const key = `${range?.from}|${range?.to}|${series.coordinateToPrice(0)}|${series.coordinateToPrice(paneH)}|${w}|${h}|${theme}`;
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
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, paneW, paneH);
      ctx.clip();
      const X = (t: number) => ts.logicalToCoordinate(nearestIndex(times, t) as any) ?? 0;
      const hLine = (x1: number, x2: number, y: number, color: string, dashed: boolean) => {
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.setLineDash(dashed ? [4, 4] : []);
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();
        ctx.setLineDash([]);
      };
      // Zona: isian tipis + garis tepi kiri tebal sebagai "pegangan" asal zona.
      const zone = (x1: number, x2: number, top: number, hh: number, color: string) => {
        ctx.fillStyle = hexToRgba(color, 0.1);
        ctx.fillRect(x1, top, Math.max(0, x2 - x1), hh);
        ctx.fillStyle = color;
        ctx.fillRect(x1, top, 2, hh);
      };
      const labels: { y: number; text: string; color: string }[] = [];
      for (const ob of obs as OrderBlock[]) {
        const css = OB_CSS[ob.side];
        const yTop = series.priceToCoordinate(ob.top), yBtm = series.priceToCoordinate(ob.btm);
        if (yTop == null || yBtm == null) continue;
        const top = Math.min(yTop, yBtm), hh = Math.max(2, Math.abs(yBtm - yTop));
        const x1 = X(ob.loc);
        if (ob.breaker && ob.breakLoc != null) {
          const xb = X(ob.breakLoc);
          zone(x1, xb, top, hh, css.main);
          ctx.fillStyle = hexToRgba(css.brk, 0.05);
          ctx.fillRect(xb, top, paneW - xb, hh);
          hLine(xb, paneW, top, hexToRgba(css.brk, 0.8), true);
          hLine(xb, paneW, top + hh, hexToRgba(css.brk, 0.8), true);
          labels.push({ y: top + hh / 2, text: css.brkName, color: css.brk });
        } else {
          zone(x1, paneW, top, hh, css.main);
          hLine(x1, paneW, top, hexToRgba(css.main, 0.45), false);
          hLine(x1, paneW, top + hh, hexToRgba(css.main, 0.45), false);
          labels.push({ y: top + hh / 2, text: css.name, color: css.main });
        }
      }
      // Label di tepi kanan, dilewati bila akan bertumpuk dengan label lain.
      const used: number[] = [];
      for (const l of labels.sort((a, b) => a.y - b.y)) {
        if (l.y < 8 || l.y > paneH - 8 || !claimRow(used, l.y)) continue;
        drawTag(ctx, l.text, paneW - 6, l.y, l.color, "right");
      }
      ctx.restore();
    };
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
    };
  }, [obs, times, theme]);

  // ---------------------------------------------------------------- volumetric order flow structure
  const showVofs = show("vofs");
  const vofs = useMemo(() => (showVofs && candles.length ? volumetricStructure(candles, 3, 5, 1) : null), [showVofs, candles]);

  useEffect(() => {
    const canvas = vofsRef.current;
    if (!vofs || !canvas) return;
    const UP = INDICATOR_COLORS.up, DOWN = INDICATOR_COLORS.down, POC = INDICATOR_COLORS.highlight;
    let raf = 0;
    let lastKey = "";
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const chart = chartRef.current, series = seriesRef.current, box = containerRef.current;
      const ctx = canvas.getContext("2d");
      if (!chart || !series || !box || !ctx) return;
      const ts = chart.timeScale();
      const w = box.clientWidth, h = box.clientHeight;
      const paneW = ts.width(), paneH = h - ts.height();
      const range = ts.getVisibleLogicalRange();
      const key = `${range?.from}|${range?.to}|${series.coordinateToPrice(0)}|${series.coordinateToPrice(paneH)}|${w}|${h}|${theme}`;
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
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, paneW, paneH);
      ctx.clip();
      const X = (i: number) => ts.logicalToCoordinate(i as any);
      const Y = (p: number) => series.priceToCoordinate(p);
      const rect = (x1: number, x2: number, p1: number, p2: number, color: string) => {
        const ya = Y(p1), yb = Y(p2);
        if (ya == null || yb == null) return;
        ctx.fillStyle = color;
        ctx.fillRect(Math.min(x1, x2), Math.min(ya, yb), Math.abs(x2 - x1), Math.max(1, Math.abs(yb - ya)));
      };
      const lo = Math.floor(range?.from ?? 0) - 1, hi = Math.ceil(range?.to ?? candles.length) + 1;
      const last = candles.length - 1;
      const hseg = (x1: number, x2: number, y: number, color: string, width: number) => {
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();
      };

      // Order block aktif: zona tipis dari candle pivot sampai bar terakhir + 10, histogram bobot di bar + 11.
      for (const ob of vofs.blocks) {
        const col = ob.bullish ? UP : DOWN;
        const xs = X(ob.start), xe = X(last + 10), xb = X(last + 11);
        if (xs == null || xe == null || xb == null) continue;
        const step = (ob.high - ob.low) / PROFILE_ROWS;
        const bodyMax = Math.max(ob.open, ob.close), bodyMin = Math.min(ob.open, ob.close);
        // Lebar minimum per unit bobot agar histogram tetap terlihat saat chart di-zoom keluar.
        const barW = Math.max(3, ts.options().barSpacing);
        for (let r = 0; r < PROFILE_ROWS; r++) {
          const top = ob.high - r * step, btm = top - step;
          const inBody = top <= bodyMax && top >= bodyMin;
          rect(xs, xe, top, btm, hexToRgba(col, inBody ? 0.11 : 0.05));
          const len = ob.weights[r] * barW;
          rect(xb, xb + len, top, btm, hexToRgba(r === ob.poc ? POC : col, r === ob.poc ? 0.85 : 0.4));
        }
        const yHi = Y(ob.high), yLo = Y(ob.low);
        if (yHi != null) hseg(xs, xe, yHi, hexToRgba(col, 0.35), 1);
        if (yLo != null) hseg(xs, xe, yLo, hexToRgba(col, 0.35), 1);
        // Sapuan order block (gelembung): cincin berisi tipis, ukuran mengikuti volume relatif 200 candle.
        for (const bb of ob.bubbles) {
          if (bb.i < lo || bb.i > hi) continue;
          const x = X(bb.i), y = Y(bb.price);
          if (x == null || y == null) continue;
          const r = bb.scale > 0.8 ? 12 : bb.scale > 0.6 ? 9.5 : bb.scale > 0.4 ? 7 : bb.scale > 0.2 ? 5 : 3.5;
          const bc = bb.high ? DOWN : UP;
          ctx.beginPath();
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.fillStyle = hexToRgba(bc, 0.16);
          ctx.fill();
          ctx.strokeStyle = hexToRgba(bc, 0.9);
          ctx.lineWidth = 1.25;
          ctx.stroke();
          // Angka volume hanya untuk sapuan besar.
          if (bb.scale > 0.5) {
            ctx.font = "10px ui-sans-serif, system-ui, sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = bb.high ? "bottom" : "top";
            ctx.fillStyle = themeColor("txt-dim");
            ctx.fillText(formatVolume(bb.volume), x, bb.high ? y - r - 2 : y + r + 2);
          }
        }
      }

      // Penembusan struktur: garis tipis di level pivot, ruas tebal sepanjang dominasi volume (delta),
      // label BOS/CHoCH hanya untuk 8 penembusan terbaru dan tidak boleh saling menimpa.
      const recent = vofs.breaks.slice(-20);
      const boxes: [number, number, number, number][] = [];
      recent.forEach((s, k) => {
        if (s.end < lo || s.start > hi) return;
        const xs = X(s.start), xe = X(s.end), xf = X(s.fillEnd), y = Y(s.level);
        if (xs == null || xe == null || xf == null || y == null) return;
        const col = s.bullish ? UP : DOWN;
        hseg(xs, xe, y, hexToRgba(col, 0.55), 1);
        hseg(xs, xf, y, hexToRgba(col, 0.95), 3);
        if (k < recent.length - 8) return;
        const lx = (xs + xe) / 2, ly = s.bullish ? y - 10 : y + 10;
        const bw = s.kind.length * 6.5 + 10;
        const box: [number, number, number, number] = [lx - bw / 2, ly - 7, lx + bw / 2, ly + 7];
        if (boxes.some((o) => box[0] < o[2] && box[2] > o[0] && box[1] < o[3] && box[3] > o[1])) return;
        boxes.push(box);
        drawTag(ctx, s.kind, lx, ly, col, "center");
      });
      ctx.restore();
    };
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
    };
  }, [vofs, candles, theme]);

  // ---------------------------------------------------------------- alat gambar
  const [drawings, setDrawings] = useState<Drawing[]>([]);
  const [tool, setTool] = useState<DrawTool | null>(null);
  const pendingRef = useRef<Point | null>(null);
  const cursorRef = useRef<Point | null>(null);
  const [, setTick] = useState(0); // memicu gambar ulang pratinjau

  useEffect(() => {
    if (drawingKey) setDrawings(loadDrawings(drawingKey));
    setTool(null);
    pendingRef.current = null;
  }, [drawingKey]);
  const commit = useCallback(
    (next: Drawing[]) => {
      setDrawings(next);
      if (drawingKey) saveDrawings(drawingKey, next);
    },
    [drawingKey],
  );
  useEffect(() => {
    if (!tool) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setTool(null);
        pendingRef.current = null;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [tool]);

  const pointAt = (e: React.MouseEvent<HTMLCanvasElement>): Point | null => {
    const chart = chartRef.current, series = seriesRef.current;
    if (!chart || !series || !times.length) return null;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    const logical = chart.timeScale().coordinateToLogical(x);
    const price = series.coordinateToPrice(y);
    if (logical == null || price == null) return null;
    const idx = Math.max(0, Math.min(times.length - 1, Math.round(logical)));
    return { time: times[idx], price };
  };
  const onDrawClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const p = pointAt(e);
    if (!p || !tool) return;
    if (tool === "hline") {
      commit([...drawings, { kind: "hline", price: p.price }]);
      setTool(null);
      return;
    }
    if (!pendingRef.current) {
      pendingRef.current = p;
      setTick((n) => n + 1);
      return;
    }
    commit([...drawings, { kind: tool, a: pendingRef.current, b: p }]);
    pendingRef.current = null;
    setTool(null);
  };
  const onDrawMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    cursorRef.current = pointAt(e);
    if (pendingRef.current) setTick((n) => n + 1);
  };

  // Gambar ulang garis-garis saat skala, gambar, atau pratinjau berubah.
  useEffect(() => {
    const canvas = drawRef.current;
    if (!drawingKey || !canvas) return;
    let raf = 0;
    let lastKey = "";
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const chart = chartRef.current, series = seriesRef.current, box = containerRef.current;
      const ctx = canvas.getContext("2d");
      if (!chart || !series || !box || !ctx) return;
      const ts = chart.timeScale();
      const w = box.clientWidth, h = box.clientHeight;
      const paneW = ts.width(), paneH = h - ts.height();
      const range = ts.getVisibleLogicalRange();
      const pend = pendingRef.current, cur = cursorRef.current;
      const key = `${range?.from}|${range?.to}|${series.coordinateToPrice(0)}|${series.coordinateToPrice(paneH)}|${w}|${h}|${drawings.length}|${pend?.time}|${pend?.price}|${cur?.time}|${cur?.price}`;
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
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, paneW, paneH);
      ctx.clip();
      ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
      ctx.textBaseline = "bottom";
      const X = (t: number) => ts.logicalToCoordinate(nearestIndex(times, t) as any);
      const Y = (p: number) => series.priceToCoordinate(p);
      const accent = themeColor("accent");
      const txt = themeColor("txt-dim");
      const paint = (d: Drawing, preview = false) => {
        ctx.globalAlpha = preview ? 0.6 : 1;
        if (d.kind === "hline") {
          const y = Y(d.price);
          if (y == null) return;
          ctx.strokeStyle = accent;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(paneW, y);
          ctx.stroke();
          ctx.fillStyle = accent;
          ctx.textAlign = "right";
          ctx.fillText(d.price.toLocaleString("en-US", { maximumFractionDigits: 2 }), paneW - 4, y - 2);
          return;
        }
        const x1 = X(d.a.time), x2 = X(d.b.time), y1 = Y(d.a.price), y2 = Y(d.b.price);
        if (x1 == null || x2 == null || y1 == null || y2 == null) return;
        if (d.kind === "trend") {
          ctx.strokeStyle = accent;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.stroke();
          return;
        }
        // Fibonacci: garis tiap level dari titik pertama ke kanan, dengan label level dan harga.
        const left = Math.min(x1, x2);
        ctx.strokeStyle = txt;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
        ctx.setLineDash([]);
        const levels = fibPrices(d.a, d.b);
        levels.forEach((lv, i) => {
          const y = Y(lv.price);
          if (y == null) return;
          const next = levels[i + 1] ? Y(levels[i + 1].price) : null;
          if (next != null) {
            ctx.fillStyle = hexToRgba(i % 2 ? "#38bdf8" : "#a78bfa", 0.06);
            ctx.fillRect(left, Math.min(y, next), paneW - left, Math.abs(next - y));
          }
          ctx.strokeStyle = lv.level === 0.618 || lv.level === 0.5 ? accent : txt;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(left, y);
          ctx.lineTo(paneW, y);
          ctx.stroke();
          ctx.fillStyle = ctx.strokeStyle;
          ctx.textAlign = "left";
          ctx.fillText(`${lv.level} (${lv.price.toLocaleString("en-US", { maximumFractionDigits: 2 })})`, left + 4, y - 2);
        });
      };
      for (const d of drawings) paint(d);
      if (pend && cur && tool && tool !== "hline") paint({ kind: tool, a: pend, b: cur }, true);
      ctx.globalAlpha = 1;
      ctx.restore();
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [drawingKey, drawings, tool, times, theme]);

  // Efek 2f — stop zones dan profil volume sesi digambar di kanvas, mengikuti skala waktu dan harga.
  useEffect(() => {
    const canvas = flowRef.current;
    if (!flow || !canvas) return;
    let raf = 0;
    let lastKey = "";
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const chart = chartRef.current;
      const series = seriesRef.current;
      const box = containerRef.current;
      const ctx = canvas.getContext("2d");
      if (!chart || !series || !box || !ctx) return;
      const ts = chart.timeScale();
      const w = box.clientWidth, h = box.clientHeight;
      const paneW = ts.width();
      const paneH = h - ts.height();
      const range = ts.getVisibleLogicalRange();
      const key = `${range?.from}|${range?.to}|${series.coordinateToPrice(0)}|${series.coordinateToPrice(paneH)}|${w}|${h}|${theme}`;
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
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, paneW, paneH);
      ctx.clip();

      const lo = Math.floor(range?.from ?? 0) - 1, hi = Math.ceil(range?.to ?? candles.length) + 1;

      // Koridor ±2σ VWAP: area arsir tipis di antara kedua pita, ruas demi ruas candle yang terlihat.
      const vw = flow.vwap;
      ctx.fillStyle = hexToRgba(INDICATOR_COLORS.neutral, 0.07);
      for (let i = Math.max(1, lo); i <= Math.min(candles.length - 1, hi); i++) {
        const u0 = vw.upper[i - 1], u1 = vw.upper[i], l0 = vw.lower[i - 1], l1 = vw.lower[i];
        if (u0 == null || u1 == null || l0 == null || l1 == null) continue;
        const x0 = ts.logicalToCoordinate((i - 1) as any), x1 = ts.logicalToCoordinate(i as any);
        const yu0 = series.priceToCoordinate(u0), yu1 = series.priceToCoordinate(u1);
        const yl0 = series.priceToCoordinate(l0), yl1 = series.priceToCoordinate(l1);
        if (x0 == null || x1 == null || yu0 == null || yu1 == null || yl0 == null || yl1 == null) continue;
        ctx.beginPath();
        ctx.moveTo(x0, yu0);
        ctx.lineTo(x1, yu1);
        ctx.lineTo(x1, yl1);
        ctx.lineTo(x0, yl0);
        ctx.closePath();
        ctx.fill();
      }

      // Stop zones: garis titik-titik redup dari pivot sampai tersentuh, dengan tanda kecil di ujungnya.
      ctx.setLineDash([2, 4]);
      ctx.lineWidth = 1;
      for (const l of flow.stops.lines) {
        if (l.to < lo || l.from > hi) continue;
        const x1 = ts.logicalToCoordinate(l.from as any), x2 = ts.logicalToCoordinate(l.to as any);
        const y = series.priceToCoordinate(l.price);
        if (x1 == null || x2 == null || y == null) continue;
        const col = l.side === "high" ? INDICATOR_COLORS.down : INDICATOR_COLORS.up;
        ctx.strokeStyle = hexToRgba(col, 0.35);
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();
        ctx.fillStyle = hexToRgba(col, 0.6);
        ctx.fillRect(x1 - 1, y - 3, 2, 6);
      }
      ctx.setLineDash([]);

      // Stop terpicu: titik kecil redup sedikit di luar high/low candle, supaya tidak bersaing dengan sinyal lain.
      for (const t of flow.stops.triggers.slice(-60)) {
        if (t.i < lo || t.i > hi) continue;
        const c = candles[t.i];
        const x = ts.logicalToCoordinate(t.i as any), y = series.priceToCoordinate(t.side === "high" ? c.high : c.low);
        if (x == null || y == null) continue;
        ctx.fillStyle = hexToRgba(t.side === "high" ? INDICATOR_COLORS.down : INDICATOR_COLORS.up, 0.7);
        ctx.beginPath();
        ctx.arc(x, t.side === "high" ? y - 5 : y + 5, 2, 0, Math.PI * 2);
        ctx.fill();
      }

      // Profil volume rentang yang terlihat, di ruang kosong sebelah kanan candle terakhir.
      // Batang abu-abu; baris bervolume tinggi lebih pekat dengan ujung berwarna dominasi beli (hijau) / jual (merah);
      // POC disorot dan satu-satunya yang diberi label.
      const iFrom = Math.max(0, Math.floor(range?.from ?? 0));
      const iTo = Math.min(candles.length - 1, Math.ceil(range?.to ?? candles.length - 1));
      const rows = iTo > iFrom ? sessionProfile(candles.slice(iFrom, iTo + 1), 40, 1.5) : [];
      const xLast = ts.logicalToCoordinate((candles.length - 1) as any);
      if (rows.length) {
        const labelW = 70;
        // Mulai setelah candle terakhir; bila ruangnya sempit, profil menempel di 30% kanan chart.
        const x0 = Math.min(Math.max((xLast ?? 0) + 12, paneW * 0.55), paneW * 0.7);
        const maxW = Math.max(30, paneW - labelW - x0);
        const maxV = Math.max(...rows.map((r) => r.vol), 1e-12);
        let poc: { y: number; len: number; mult: number } | null = null;
        for (const r of rows) {
          if (r.vol <= 0) continue;
          const yTop = series.priceToCoordinate(r.high), yBot = series.priceToCoordinate(r.low);
          if (yTop == null || yBot == null) continue;
          const top = Math.min(yTop, yBot), hh = Math.max(1, Math.abs(yBot - yTop) - 1);
          const len = Math.max(2, (r.vol / maxV) * maxW);
          ctx.fillStyle = r.poc
            ? hexToRgba(INDICATOR_COLORS.highlight, 0.85)
            : hexToRgba(INDICATOR_COLORS.neutral, r.stop ? 0.42 : 0.18);
          ctx.fillRect(x0, top, len, hh);
          if (r.stop && !r.poc) {
            ctx.fillStyle = r.buy > r.sell ? INDICATOR_COLORS.up : INDICATOR_COLORS.down;
            ctx.fillRect(x0 + len - 2, top, 2, hh);
          }
          if (r.poc) poc = { y: top + hh / 2, len, mult: r.mult };
        }
        if (poc) drawTag(ctx, `POC ${poc.mult.toFixed(1)}×`, x0 + poc.len + 6, poc.y, INDICATOR_COLORS.highlight, "left");
      }
      ctx.restore();
    };
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
    };
  }, [flow, theme]);

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

  const empty = candles.length === 0;
  if (empty && !fill) {
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

  // Nilai OHLC candle di bawah kursor.
  const ohlcValues = hover && (
    <>
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
            backgroundColor: hexToRgba(REGIME_META[hover.regime as Regime]?.color ?? "#252c37", 0.16),
            color: REGIME_META[hover.regime as Regime]?.color ?? "#8b949e",
          }}
        >
          {REGIME_PLAIN[hover.regime as Regime]?.name ?? hover.regime}
        </span>
      )}
    </>
  );
  // Baris pertama legenda dalam chart pada tata letak penuh: aset, timeframe, OHLC.
  const ohlcRow = (
    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-0.5 tabular-nums">
      <span className="font-sans text-[12.5px] font-semibold text-txt">{symbol}</span>
      <span className="font-sans text-[12px] text-txtMuted">{timeframe.toUpperCase()}</span>
      {ohlcValues}
    </div>
  );

  const toolBtn = (on: boolean) =>
    `rounded-md p-1.5 transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
      on ? "bg-accent/20 text-accent" : "text-txtMuted hover:bg-surface hover:text-txt"
    }`;
  const drawButtons = (vertical: boolean) => {
    const icon = vertical ? "h-[18px] w-[18px]" : "h-3.5 w-3.5";
    return (
      <>
        {vertical && (
          <button
            type="button"
            title="Kursor"
            aria-label="Kursor"
            aria-pressed={tool === null}
            onClick={() => {
              pendingRef.current = null;
              setTool(null);
            }}
            className={toolBtn(tool === null)}
          >
            <svg viewBox="0 0 20 20" className={icon} fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
              <path d="M5 3 L5 16 L8.5 12.5 L11 17.5 L13 16.5 L10.5 11.5 L15 11.5 Z" strokeLinejoin="round" />
            </svg>
          </button>
        )}
        {DRAW_TOOLS.map((t) => (
          <button
            key={t.id}
            type="button"
            title={t.label}
            aria-label={t.label}
            aria-pressed={tool === t.id}
            onClick={() => {
              pendingRef.current = null;
              setTool((cur) => (cur === t.id ? null : t.id));
            }}
            className={toolBtn(tool === t.id)}
          >
            <svg viewBox="0 0 20 20" className={icon} fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
              {t.id === "trend" && <path d="M3 16 L17 4 M3 16 h0 M17 4 h0" strokeLinecap="round" />}
              {t.id === "hline" && <path d="M2 10 H18" />}
              {t.id === "fib" && <path d="M2 4 H18 M2 8 H18 M2 12 H18 M2 16 H18" strokeWidth="1.3" />}
            </svg>
          </button>
        ))}
        <span className={vertical ? "my-1 h-px w-5 bg-edge" : "mx-0.5 h-4 w-px bg-edge"} aria-hidden />
        <button
          type="button"
          title="Batalkan gambar terakhir"
          aria-label="Batalkan gambar terakhir"
          disabled={!drawings.length}
          onClick={() => commit(drawings.slice(0, -1))}
          className={`${toolBtn(false)} disabled:opacity-30`}
        >
          <svg viewBox="0 0 20 20" className={icon} fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
            <path d="M7 5 L3 9 L7 13 M3 9 H12 a5 5 0 0 1 0 10 H9" />
          </svg>
        </button>
        <button
          type="button"
          title="Hapus semua gambar"
          aria-label="Hapus semua gambar"
          disabled={!drawings.length}
          onClick={() => commit([])}
          className={`${toolBtn(false)} disabled:opacity-30`}
        >
          <svg viewBox="0 0 20 20" className={icon} fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
            <path d="M4 6 H16 M8 6 V4 H12 V6 M6 6 L7 17 H13 L14 6" />
          </svg>
        </button>
      </>
    );
  };

  const picker = indicators && (
    <IndicatorPicker
      active={active}
      onToggle={toggleIndicator}
      currentRegime={confidentRegimes.length ? confidentRegimes[confidentRegimes.length - 1].regime : null}
      unavailable={{
        ...(depthSymbol ? {} : { heatmap: "Liquidity heatmap hanya tersedia untuk aset kripto Binance." }),
        ...(regimes.length
          ? {}
          : { zregime: "Indikator ini butuh hasil identifikasi kondisi pasar dari model, yang hanya ada di Ringkasan (BTC/USDT 1H dan 4H)." }),
      }}
    />
  );

  const rangeButtons = (compact: boolean) =>
    RANGES.filter((r) => !compact || r.compact).map((r) => (
      <button
        key={r.label}
        type="button"
        onClick={() => applyRange(r.label)}
        aria-pressed={activeRange === r.label}
        className={
          compact
            ? `px-2.5 py-1 font-mono text-2xs transition ${
                activeRange === r.label ? "bg-accent/20 text-accent" : "text-txtMuted hover:bg-surface hover:text-txtDim"
              }`
            : `rounded px-2 py-0.5 font-mono text-[12px] transition ${
                activeRange === r.label ? "bg-accent/15 text-accent" : "text-txtDim hover:bg-surface hover:text-txt"
              }`
        }
      >
        {r.label}
      </button>
    ));

  const area = (
      <div ref={areaRef} className={fill ? "relative min-h-0 flex-1 overflow-hidden" : "relative w-full"}>
        <div ref={containerRef} className="w-full" />
        {showHeatmap && <canvas ref={overlayRef} className="pointer-events-none absolute left-0 top-0 z-[2]" aria-hidden />}
        {showOb && <canvas ref={obRef} className="pointer-events-none absolute left-0 top-0 z-[2]" aria-hidden />}
        {showVofs && <canvas ref={vofsRef} className="pointer-events-none absolute left-0 top-0 z-[2]" aria-hidden />}
        {showFlow && <canvas ref={flowRef} className="pointer-events-none absolute left-0 top-0 z-[3]" aria-hidden />}
        {drawingKey && (
          <canvas
            ref={drawRef}
            onClick={onDrawClick}
            onMouseMove={onDrawMove}
            className={`absolute left-0 top-0 z-[5] ${tool ? "cursor-crosshair" : "pointer-events-none"}`}
            aria-label={tool ? "Area gambar" : undefined}
            aria-hidden={tool ? undefined : true}
          />
        )}
        {tool && (
          <div className="pointer-events-none absolute bottom-10 left-1/2 z-[6] -translate-x-1/2 rounded-md bg-panel/90 px-3 py-1 text-[11.5px] text-txt shadow-panel">
            {DRAW_TOOLS.find((t) => t.id === tool)?.hint} · Esc untuk batal
          </div>
        )}

        {/* Legenda ringkas di dalam chart: nama, nilai di posisi kursor, sembunyikan, hapus. */}
        {(fill || indicators || (showRegime && regimes.length > 0)) && (
          <div className="pointer-events-none absolute left-2 top-1.5 z-[4] flex max-w-[78%] flex-col gap-0.5 rounded-md bg-panel/80 px-1.5 py-1 font-mono text-[11px] backdrop-blur-[2px]">
            {fill && ohlcRow}
            {showRegime && regimes.length > 0 && (
              <LegendRow name="Pita kondisi pasar" hidden={!showBand} onHide={() => toggleHidden("regime")} />
            )}
            {isOn("trend") && (
              <LegendRow
                name="MA 15 · MA 50"
                hidden={hidden.has("trend")}
                onHide={() => toggleHidden("trend")}
                onRemove={() => toggleIndicator("trend")}
                values={[
                  { v: calc?.ma15?.[hoverIdx], c: INDICATOR_COLORS.ma15 },
                  { v: calc?.ma50?.[hoverIdx], c: INDICATOR_COLORS.ma50 },
                ]}
              />
            )}
            {isOn("meanrev") && (
              <LegendRow
                name="BB 20 2"
                hidden={hidden.has("meanrev")}
                onHide={() => toggleHidden("meanrev")}
                onRemove={() => toggleIndicator("meanrev")}
                values={[
                  { v: calc?.bb?.mid[hoverIdx], c: INDICATOR_COLORS.bb },
                  { v: calc?.bb?.upper[hoverIdx], c: INDICATOR_COLORS.bb },
                  { v: calc?.bb?.lower[hoverIdx], c: INDICATOR_COLORS.bb },
                ]}
              />
            )}
            {isOn("zregime") && (
              <LegendRow
                name="Z-score 20 · filter Cenderung Berbalik"
                hidden={hidden.has("zregime")}
                onHide={() => toggleHidden("zregime")}
                onRemove={() => toggleIndicator("zregime")}
                values={[{ v: calc?.z?.[hoverIdx], c: INDICATOR_COLORS.z, signed: true }]}
              />
            )}
            {isOn("ofvwap") && (
              <LegendRow
                name="VWAP Sesi & Zona Stop"
                hidden={hidden.has("ofvwap")}
                onHide={() => toggleHidden("ofvwap")}
                onRemove={() => toggleIndicator("ofvwap")}
                values={[
                  { v: flow?.vwap.vwap[hoverIdx], c: INDICATOR_COLORS.neutral },
                  { v: flow?.vwap.upper[hoverIdx], c: hexToRgba(INDICATOR_COLORS.neutral, 0.7) },
                  { v: flow?.vwap.lower[hoverIdx], c: hexToRgba(INDICATOR_COLORS.neutral, 0.7) },
                ]}
              />
            )}
            {isOn("trail") && (
              <LegendRow
                name="Trailing Stop Statistik"
                hidden={hidden.has("trail")}
                onHide={() => toggleHidden("trail")}
                onRemove={() => toggleIndicator("trail")}
                values={
                  trail
                    ? [{ v: trail.level[hoverIdx], c: trail.bias[hoverIdx] === "long" ? INDICATOR_COLORS.up : INDICATOR_COLORS.down }]
                    : []
                }
                note={trail ? (trail.bias[hoverIdx] === "long" ? "posisi beli" : trail.bias[hoverIdx] === "short" ? "posisi jual" : undefined) : undefined}
              />
            )}
            {isOn("vofs") && (
              <LegendRow
                name="Struktur Pasar & Volume"
                hidden={hidden.has("vofs")}
                onHide={() => toggleHidden("vofs")}
                onRemove={() => toggleIndicator("vofs")}
                note={
                  vofs
                    ? `tren ${vofs.trend === 1 ? "naik" : vofs.trend === -1 ? "turun" : "–"} · ${
                        vofs.breaks.length ? `penembusan terakhir ${vofs.breaks[vofs.breaks.length - 1].kind}` : "belum ada penembusan"
                      } · ${vofs.blocks.length} zona aktif`
                    : undefined
                }
              />
            )}
            {isOn("orderblocks") && (
              <LegendRow
                name="Zona Order Block & Breaker"
                hidden={hidden.has("orderblocks")}
                onHide={() => toggleHidden("orderblocks")}
                onRemove={() => toggleIndicator("orderblocks")}
                note={
                  obs
                    ? `${obs.filter((o) => o.side === "bull").length} zona beli · ${obs.filter((o) => o.side === "bear").length} zona jual · ${obs.filter((o) => o.breaker).length} breaker`
                    : undefined
                }
              />
            )}
            {isOn("hurst") && (
              <LegendRow
                name="Hurst Bergulir (R/S 128)"
                hidden={hidden.has("hurst")}
                onHide={() => toggleHidden("hurst")}
                onRemove={() => toggleIndicator("hurst")}
                values={
                  hurstCalc
                    ? [
                        {
                          v: hurstCalc.smooth[hoverIdx],
                          c: hurstCalc.state[hoverIdx] === 1 ? REGIME_META.persistent.color : hurstCalc.state[hoverIdx] === -1 ? REGIME_META.anti_persistent.color : REGIME_META.random_like.color,
                        },
                      ]
                    : []
                }
                note={
                  hurstCalc && hurstCalc.smooth[hoverIdx] != null
                    ? `${hurstCalc.state[hoverIdx] === 1 ? "cenderung tren" : hurstCalc.state[hoverIdx] === -1 ? "cenderung berbalik" : "acak"} · R² ${
                        hurstCalc.r2[hoverIdx] == null ? "–" : (hurstCalc.r2[hoverIdx] as number).toFixed(2)
                      }`
                    : undefined
                }
              />
            )}
            {isOn("heatmap") && (
              <LegendRow
                name="Liquidity heatmap"
                hidden={hidden.has("heatmap")}
                onHide={() => toggleHidden("heatmap")}
                onRemove={() => toggleIndicator("heatmap")}
                note={showHeatmap ? depthStatus ?? "memuat…" : undefined}
              />
            )}
          </div>
        )}
        {fill && empty && (
          <div className="absolute inset-0 z-[6] flex items-center justify-center px-4 text-center text-[13px] text-txtMuted">
            {emptyMessage ?? "Tidak ada data candle."}
          </div>
        )}
        {fill && showTrail && trailStats && (
          <div className="absolute bottom-9 left-2 z-[4] max-w-[calc(100%-90px)] rounded-md border border-edge bg-panel/95 shadow-panel">
            <TrailStatsTable stats={trailStats} />
          </div>
        )}
      </div>
  );

  if (fill) {
    return (
      <div className="flex h-full min-h-0 flex-col overflow-hidden bg-panel">
        <div className="flex h-11 shrink-0 items-center gap-1 border-b border-edge px-2">
          {toolbarStart}
          {picker && (
            <>
              <span className="mx-1 h-5 w-px bg-edge" aria-hidden />
              {picker}
            </>
          )}
          <div className="ml-auto flex items-center gap-1">{toolbarEnd}</div>
        </div>
        <div className="flex min-h-0 flex-1">
          {drawingKey && (
            <div className="flex w-11 shrink-0 flex-col items-center gap-1 border-r border-edge py-2" role="group" aria-label="Alat gambar">
              {drawButtons(true)}
            </div>
          )}
          {area}
        </div>
        <div className="flex h-9 shrink-0 items-center gap-3 border-t border-edge px-2">
          <div className="flex shrink-0 items-center gap-0.5" role="group" aria-label="Rentang tampilan">
            {rangeButtons(false)}
          </div>
          <div className="min-w-0 flex-1 truncate text-[11px] text-txtMuted">{footerNote}</div>
          <UtcClock />
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border border-edge bg-panel">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-edge bg-surface/40 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="font-sans text-[13px] font-semibold tracking-tight text-txt">{symbol}</span>
          <span className="rounded bg-edge px-1.5 py-0.5 font-mono text-2xs text-txtDim">{timeframe.toUpperCase()}</span>
        </div>

        {hover && <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] tabular-nums">{ohlcValues}</div>}

        {drawingKey && (
          <div className="ml-auto flex items-center gap-0.5 rounded border border-edge p-0.5" role="group" aria-label="Alat gambar">
            {drawButtons(false)}
          </div>
        )}

        {picker && <div className={drawingKey ? "" : "ml-auto"}>{picker}</div>}

        {showToolbar && (
          <div className={`${indicators ? "" : "ml-auto "}flex overflow-hidden rounded border border-edge`}>{rangeButtons(true)}</div>
        )}
      </div>

      {area}

      {showTrail && trailStats && <TrailStatsTable stats={trailStats} />}

      {legend && <div className="border-t border-edge px-3 py-2">{legend}</div>}
    </div>
  );
}

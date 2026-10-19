/** Klien API tunggal ke backend FastAPI. */

function getBaseUrl(): string {
  const envBase = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (envBase) return envBase;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

async function get<T>(path: string, params: Record<string, string | number | undefined> = {}) {
  const url = new URL(path, getBaseUrl());
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  });
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${url.pathname}`);
  return (await res.json()) as T;
}

async function post<T>(path: string, body: unknown = {}) {
  const res = await fetch(new URL(path, getBaseUrl()).toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return (await res.json()) as T;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface RegimePoint {
  time: number;
  close: number;
  hurst: number | null;
  dfa_alpha: number | null;
  regime: string;
  segment: string;
}

type OhlcvResponse = {
  candles: Candle[];
  config_hash: string;
  is_mock: boolean;
  count: number;
  total_count?: number;
};

type ColumnarOhlcv = Omit<OhlcvResponse, "candles"> & {
  columns: Record<"time" | "open" | "high" | "low" | "close" | "volume", number[]>;
};

/** Ubah payload kolom menjadi array candle yang dipakai komponen chart. */
function decodeColumnar(r: ColumnarOhlcv): OhlcvResponse {
  const { time, open, high, low, close, volume } = r.columns;
  const candles: Candle[] = new Array(time.length);
  for (let i = 0; i < time.length; i++) {
    candles[i] = {
      time: time[i],
      open: open[i],
      high: high[i],
      low: low[i],
      close: close[i],
      volume: volume[i],
    };
  }
  const { columns: _omit, ...rest } = r;
  return { ...rest, candles };
}

/**
 * Cache riwayat penuh per timeframe, hidup selama tab terbuka.
 *
 * Riwayat penuh ~1,4 MB di kabel. Tanpa cache, setiap pindah halaman atau
 * ganti timeframe bolak-balik mengunduhnya ulang. Promise yang disimpan —
 * bukan hasilnya — supaya dua komponen yang meminta bersamaan berbagi satu
 * request, dan kegagalan tidak ikut di-cache.
 */
const historyCache = new Map<string, Promise<OhlcvResponse>>();

function ohlcvHistory(tf: string): Promise<OhlcvResponse> {
  const hit = historyCache.get(tf);
  if (hit) return hit;
  const p = get<ColumnarOhlcv>("/api/v1/ohlcv", { tf, format: "columnar" })
    .then(decodeColumnar)
    .catch((e) => {
      historyCache.delete(tf);
      throw e;
    });
  historyCache.set(tf, p);
  return p;
}

export const api = {
  config: () => get<any>("/api/v1/meta/config"),
  methodology: () => get<any>("/api/v1/meta/methodology"),
  dataStatus: (symbol = "BTCUSDT") => get<any>("/api/v1/data/status", { symbol }),
  connectivity: () => get<any>("/api/v1/data/connectivity"),
  refreshData: (full = false, tf?: string) =>
    post<any>("/api/v1/data/refresh", { full, tf }),
  ohlcv: (tf: string, limit?: number) =>
    get<OhlcvResponse>("/api/v1/ohlcv", { tf, limit }),
  /** Seluruh riwayat candle dalam format kolom, di-cache per timeframe. */
  ohlcvHistory,
  /** Buang cache riwayat, dipakai setelah refresh data. */
  clearOhlcvHistory: (tf?: string) =>
    tf ? historyCache.delete(tf) : historyCache.clear(),
  regime: (tf: string) =>
    get<{
      series: RegimePoint[];
      distribution: Record<string, { count: number; share: number }>;
      current_regime: string;
      config_hash: string;
    }>("/api/v1/analysis/regime", { tf }),
  hurstDfa: (tf: string, limit?: number) =>
    get<any>("/api/v1/analysis/hurst-dfa", { tf, limit }),
  multifractal: (tf: string, limit?: number) =>
    get<any>("/api/v1/analysis/multifractal", { tf, limit }),
  swt: (tf: string, levels?: number, endIndex?: number) =>
    get<any>("/api/v1/analysis/swt", { tf, levels, end_index: endIndex }),
  attention: (tf: string, windowId?: number, seqLen?: number) =>
    get<any>("/api/v1/analysis/attention", { tf, window_id: windowId, seq_len: seqLen }),
  transitionMatrix: (tf: string) => get<any>("/api/v1/analysis/transition-matrix", { tf }),
  regimeDuration: (tf: string) => get<any>("/api/v1/analysis/regime-duration", { tf }),
  splitBoundaries: (tf: string) => get<any>("/api/v1/data/split-boundaries", { tf }),
  compare: (tf: string) => get<any>("/api/v1/model/compare", { tf }),
  horizonStudy: (tf: string) => get<any>("/api/v1/model/horizon-study", { tf }),
  identification: (tf: string) => get<any>("/api/v1/model/identification", { tf }),
  consistency: (tf: string, mode = "multiclass") =>
    get<any>("/api/v1/model/consistency", { tf, mode }),
  walkForward: (tf: string, mode = "binary", labeling = "threshold") =>
    get<any>("/api/v1/model/walk-forward", { tf, mode, labeling }),
  orderflowAblation: (tf: string) => get<any>("/api/v1/model/orderflow-ablation", { tf }),
  orderflowTimeline: (tf: string, limit = 600) =>
    get<any>("/api/v1/model/orderflow-timeline", { tf, limit }),
  rawProbabilities: (tf: string, modelKey: string) =>
    get<any>("/api/v1/model/raw-probabilities", { tf, model_key: modelKey }),
  predict: (body: Record<string, unknown>) => post<any>("/api/v1/model/predict", body),
  runBacktest: (body: Record<string, unknown>) => post<any>("/api/v1/backtest/run", body),
  backtestDiagnostics: (
    tf: string,
    regimeSource: string,
    modelKey: string,
    feeBps: number
  ) =>
    get<any>("/api/v1/backtest/diagnostics", {
      tf,
      regime_source: regimeSource,
      model_key: modelKey,
      fee_bps: feeBps,
    }),
};

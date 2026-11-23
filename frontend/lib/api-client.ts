/** Klien API tunggal ke backend FastAPI. */

function getBaseUrl(): string {
  const envBase = process.env.NEXT_PUBLIC_API_BASE?.trim();
  // "same-origin": backend diakses lewat reverse proxy di domain/IP yang sama
  // (/api/v1/* diteruskan ke FastAPI), sehingga tidak ada port 8000 di browser.
  if (envBase === "same-origin" && typeof window !== "undefined") return window.location.origin;
  if (envBase && envBase !== "same-origin") return envBase;
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
  if (!res.ok) {
    // FastAPI mengirim alasan di `detail` (mis. cache detektor sedang dibangun).
    const detail = await res.json().then((j) => (typeof j?.detail === "string" ? j.detail : null)).catch(() => null);
    throw new Error(detail ?? `${res.status} ${res.statusText} — ${url.pathname}`);
  }
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
  regime: string;
  /** Hanya pada label konsensus Hurst–DFA (`/analysis/regime`). */
  hurst?: number | null;
  dfa_alpha?: number | null;
  /** Skor kuantil Efficiency Ratio multiskala (ER_q) yang dipakai soft consensus. */
  efficiency_ratio?: number | null;
  segment?: string;
}

export type AiRegimeClass = "persistent" | "random_like" | "anti_persistent";

/** Titik identifikasi model AI; `hurst`, `dfa_alpha`, `segment` tidak ada (bukan label konsensus). */
export interface AiRegimePoint extends RegimePoint {
  confidence: number;
  p_persistent: number;
  p_random_like: number;
  p_anti_persistent: number;
}

export interface IdentificationScore {
  n: number;
  correct: number;
  accuracy: number;
  balanced_accuracy: number;
  macro_f1?: number;
  mcc?: number;
}

/** Model identifikasi resmi (Hybrid Attention-BiLSTM, h = 0). */
export interface DetectorInfo {
  name: string;
  task: string;
  horizon_bars: number;
  inputs: string;
  trained_on: string;
  label: string;
  label_thresholds: { hurst: [number, number]; dfa: [number, number] };
  classes: AiRegimeClass[];
  window: number;
  stride_bars: number;
  model_timeframe: string;
  ensemble_seeds: number[];
  test_backtest: IdentificationScore;
  walk_forward_pooled: IdentificationScore | null;
  abstain_tau: number;
  abstain_validation: { tau: number; coverage: number; accuracy_covered: number; note: string } | null;
}

export interface AttentionResponse {
  timeframe: string;
  model: string;
  horizon_bars: number;
  window_time: number;
  window_index: number;
  n_windows: number;
  regime: AiRegimeClass;
  confidence: number;
  probabilities: Record<AiRegimeClass, number>;
  seq_len: number;
  sub_window_bars: number;
  step_bars: number;
  entropy_normalized: number;
  per_seed: Record<string, number[]>;
  attention_weights: { step: number; end_offset_bars: number; time: number; weight: number }[];
  candles: { time: number; open: number; high: number; low: number; close: number }[];
}

export interface FeaturesResponse {
  timeframe: string;
  window_time: number;
  regime: AiRegimeClass;
  ps_shape: [number, number];
  ps_channels: string[];
  summary_length: number;
  summary_names: string[];
  summary_values: number[];
  ps_last_step: number[];
}

export interface SplitTimes {
  train_end_time: number;
  validation_start_time: number;
  validation_end_time: number;
  test_start_time: number;
  test_end_time: number;
}

export interface AiRegimeResponse {
  timeframe: string;
  symbol: string;
  config_hash: string;
  detector: DetectorInfo;
  split_boundaries: SplitTimes | null;
  current_regime: AiRegimeClass | null;
  current_time: number | null;
  current_probabilities: Record<AiRegimeClass, number> | null;
  /** Keyakinan di bawah `detector.abstain_tau`: label dianggap tidak pasti. */
  current_low_confidence: boolean | null;
  low_confidence_share: number | null;
  distribution: Record<string, { count: number; share: number }>;
  series: AiRegimePoint[];
  original_count: number;
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

function ohlcvHistory(tf: string, symbol = "BTCUSDT"): Promise<OhlcvResponse> {
  const key = `${symbol.toUpperCase()}_${tf.toLowerCase()}`;
  const hit = historyCache.get(key);
  if (hit) return hit;
  const p = get<ColumnarOhlcv>("/api/v1/ohlcv", {
    symbol: symbol.toUpperCase(),
    tf: tf.toLowerCase(),
    format: "columnar",
  })
    .then(decodeColumnar)
    .catch((e) => {
      historyCache.delete(key);
      throw e;
    });
  historyCache.set(key, p);
  return p;
}

export interface WalkForwardPoint {
  time: number;
  year: number;
  hurst: number;
  dfa_alpha: number;
  er_score: number;
  ret_500: number;
  true_regime: AiRegimeClass;
  pred_regime: AiRegimeClass;
  regime: string;
  confidence: number;
  is_correct: boolean;
}

export interface WalkForwardAssetSummary {
  symbol: string;
  name: string;
  category: string;
  timeframe: string;
  status: string;
  total_bars: number;
  start_date: string;
  end_date: string;
  years_available: number[];
  overall_test_windows: number;
  overall_correct_identifications: number;
  overall_identification_rate_pct: number;
  per_class_identification: Record<
    string,
    { total: number; correct: number; rate_pct: number }
  >;
  per_market_condition_identification: Record<
    string,
    { total: number; correct: number; rate_pct: number }
  >;
  yearly_results: {
    test_year: number;
    train_years_range: string;
    n_train: number;
    n_val: number;
    n_test: number;
    correct_identifications: number;
    identification_rate_pct: number;
    per_class: Record<string, { total: number; correct: number; rate_pct: number }>;
    per_market_condition: Record<string, { total: number; correct: number; rate_pct: number }>;
  }[];
}

export interface WalkForwardMultiAssetResponse {
  available: boolean;
  experiment: string;
  model_architecture: string;
  overall_summary: {
    total_asset_timeframe_pairs: number;
    grand_total_test_windows: number;
    grand_total_correct_identifications: number;
    grand_overall_identification_rate_pct: number;
  };
  assets_evaluated: WalkForwardAssetSummary[];
}

export interface WalkForwardTimelineResponse {
  symbol: string;
  timeframe: string;
  year_filter: number | null;
  source: string;
  count: number;
  correct_count: number;
  identification_rate_pct: number;
  asset_summary: WalkForwardAssetSummary | null;
  year_segments: { segment: string; start_time: number; end_time: number }[];
  series: WalkForwardPoint[];
}

export const api = {
  config: () => get<any>("/api/v1/meta/config"),
  methodology: () => get<any>("/api/v1/meta/methodology"),
  dataStatus: (symbol = "BTCUSDT") => get<any>("/api/v1/data/status", { symbol }),
  connectivity: () => get<any>("/api/v1/data/connectivity"),
  refreshData: (full = false, tf?: string) =>
    post<any>("/api/v1/data/refresh", { full, tf }),
  ohlcv: (tf: string, limit?: number, symbol = "BTCUSDT") =>
    get<OhlcvResponse>("/api/v1/ohlcv", { symbol, tf, limit }),
  /** Seluruh riwayat candle dalam format kolom, di-cache per aset & timeframe. */
  ohlcvHistory,
  /** Buang cache riwayat, dipakai setelah refresh data. */
  clearOhlcvHistory: (tf?: string) =>
    tf ? historyCache.delete(`BTCUSDT_${tf.toLowerCase()}`) : historyCache.clear(),
  regime: (tf: string) =>
    get<{
      series: RegimePoint[];
      distribution: Record<string, { count: number; share: number }>;
      current_regime: string;
      config_hash: string;
      /** Jumlah jendela pada deret PENUH (series bisa dijarangkan untuk grafik). */
      original_count: number;
      stride_bars: number;
      /** Jumlah pergantian label pada deret penuh. */
      n_switches: number;
      thresholds: { hurst: [number, number]; dfa: [number, number]; source: string } | null;
      latest_windows: RegimePoint[];
      uncertain_example: RegimePoint | null;
    }>("/api/v1/analysis/regime", { tf }),
  /** Regime hasil identifikasi model resmi (Hybrid Attention-BiLSTM, h = 0). */
  aiRegime: (tf: string) => get<AiRegimeResponse>("/api/v1/analysis/ai-regime", { tf }),
  hurstDfa: (tf: string, limit?: number) =>
    get<any>("/api/v1/analysis/hurst-dfa", { tf, limit }),
  multifractal: (tf: string, limit?: number) =>
    get<any>("/api/v1/analysis/multifractal", { tf, limit }),
  swt: (tf: string, levels?: number, endIndex?: number) =>
    get<any>("/api/v1/analysis/swt", { tf, levels, end_index: endIndex }),
  /** Bobot attention 32 langkah model identifikasi (h = 0), rata-rata 3 seed. */
  attention: (tf: string, atTime?: number) => get<AttentionResponse>("/api/v1/analysis/attention", { tf, at_time: atTime }),
  /** Hasil uji identifikasi Bab 4 (updated_eval_summary.json): backtest + walk-forward per kelas/fold. */
  evaluation: () => get<any>("/api/v1/model/evaluation"),
  // Uji Ketahanan Metode tidak dibaca dari sini: datanya terkunci per akun dan
  // hanya dikirim rute Next.js /api/robustness (lihat app/uji-ketahanan/page.tsx).
  /** Bentuk dan nilai fitur masukan model identifikasi untuk satu jendela. */
  features: (tf: string, atTime?: number) => get<FeaturesResponse>("/api/v1/analysis/features", { tf, at_time: atTime }),
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
  walkForwardMultiAsset: () =>
    get<WalkForwardMultiAssetResponse>("/api/v1/model/walk-forward-multi-asset"),
  walkForwardTimeline: (symbol: string, tf: string, year?: number) =>
    get<WalkForwardTimelineResponse>("/api/v1/model/walk-forward-timeline", {
      symbol,
      tf,
      year,
    }),
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

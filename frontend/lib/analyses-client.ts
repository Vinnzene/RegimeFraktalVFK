import type { AiRegimeClass, AiRegimePoint, Candle } from "@/lib/api-client";
import type { RandomBand } from "@/components/RegimeOverview";

/** Klien halaman Analisis Aset; memanggil rute Next.js /api/analyses (sesi login). */

export type AnalysisSource = "binance" | "yahoo";

export const SOURCE_META: Record<AnalysisSource, { label: string; timeframes: string[]; placeholder: string; examples: string[] }> = {
  binance: { label: "Binance", timeframes: ["15m", "1h", "4h", "1d"], placeholder: "ETHUSDT", examples: ["ETHUSDT", "SOLUSDT", "BNBUSDT", "PAXGUSDT"] },
  yahoo: { label: "Yahoo Finance", timeframes: ["1h", "1d"], placeholder: "BBCA.JK", examples: ["BBCA.JK", "^JKSE", "GC=F", "EURUSD=X"] },
};

export type AnalysisRecord = {
  id: string;
  source: AnalysisSource;
  symbol: string;
  timeframe: string;
  bars: number;
  created_at: number;
  status: "queued" | "running" | "done" | "failed";
  current_regime?: AiRegimeClass | null;
  confidence?: number | null;
  low_confidence?: boolean | null;
  error?: string | null;
};

export type AnalysisResult = {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  progress?: number;
  error?: string;
  source: AnalysisSource;
  symbol: string;
  timeframe: string;
  created_at: number;
  processing_seconds?: number;
  n_bars?: number;
  first_time?: number;
  last_time?: number;
  experimental?: boolean;
  detector?: { name: string; window: number; stride_bars: number; abstain_tau: number; validated_on: string; test_ba_synthetic?: Record<string, number> };
  random_band?: RandomBand;
  candles?: Record<keyof Candle, number[]>;
  series?: (AiRegimePoint & { hurst: number; dfa_alpha: number })[];
  current_regime?: AiRegimeClass;
  current_probabilities?: Record<AiRegimeClass, number>;
  current_low_confidence?: boolean;
  low_confidence_share?: number;
  distribution?: Record<string, { count: number; share: number }>;
};

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
  return data as T;
}

export const analyses = {
  list: () => call<{ items: AnalysisRecord[]; quota: { used: number; limit: number; remaining: number } }>("/api/analyses"),
  create: (body: { source: AnalysisSource; symbol: string; timeframe: string; bars: number }) =>
    call<{ id: string }>("/api/analyses", { method: "POST", body: JSON.stringify(body) }),
  get: (id: string) => call<AnalysisResult>(`/api/analyses/${encodeURIComponent(id)}`),
};

export function toCandles(c: AnalysisResult["candles"]): Candle[] {
  if (!c) return [];
  return c.time.map((t, i) => ({ time: t, open: c.open[i], high: c.high[i], low: c.low[i], close: c.close[i], volume: c.volume[i] }));
}

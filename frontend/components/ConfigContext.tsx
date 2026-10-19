"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api-client";

/**
 * Konteks config global.
 *
 * Semua parameter analisis (L, J, threshold, h, τ) berasal dari config.yaml di
 * backend dan ditampilkan apa adanya — tidak ada parameter tersembunyi.
 * `configHash` ikut ditempel di footer setiap panel sebagai jejak reproducibility.
 */

export interface AppConfig {
  data: { symbol: string; timeframes: string[]; start: string | null; end: string | null };
  analysis: {
    L: number;
    J: number;
    hurst_threshold: [number, number];
    dfa_threshold: [number, number];
    input: string;
  };
  model: { h: number; stride: number; purge_gap: number; tau: number; seed: number };
  split: { ratios: number[] };
  runtime: { use_mock: boolean; storage: string };
}

interface Ctx {
  config: AppConfig | null;
  configHash: string;
  shortHash: string;
  loading: boolean;
  error: string | null;
  timeframe: string;
  setTimeframe: (tf: string) => void;
}

const ConfigContext = createContext<Ctx>({
  config: null,
  configHash: "",
  shortHash: "",
  loading: true,
  error: null,
  timeframe: "1h",
  setTimeframe: () => {},
});

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configHash, setConfigHash] = useState("");
  const [shortHash, setShortHash] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState("1h");

  useEffect(() => {
    api
      .config()
      .then((r) => {
        setConfig(r.config);
        setConfigHash(r.config_hash);
        setShortHash(r.short_hash);
      })
      .catch((e) => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo(
    () => ({ config, configHash, shortHash, loading, error, timeframe, setTimeframe }),
    [config, configHash, shortHash, loading, error, timeframe]
  );

  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export const useAppConfig = () => useContext(ConfigContext);

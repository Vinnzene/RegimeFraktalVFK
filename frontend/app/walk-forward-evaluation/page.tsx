"use client";

import { useEffect, useMemo, useState } from "react";
import CandlestickChart from "@/components/CandlestickChart";
import RegimeLegend from "@/components/RegimeLegend";
import { ApiState, useApi } from "@/components/useApi";
import {
  api,
  type RegimePoint,
  type WalkForwardAssetSummary,
  type WalkForwardPoint,
} from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

const ASSET_CATALOG: {
  symbol: string;
  display: string;
  shortName: string;
  group: string;
  defaultTf: string;
  tfs: string[];
}[] = [
  {
    symbol: "BTCUSDT",
    display: "BTC/USDT",
    shortName: "Bitcoin (Aset Utama)",
    group: "Kripto Utama",
    defaultTf: "1h",
    tfs: ["1h", "4h"],
  },
  {
    symbol: "ETHUSDT",
    display: "ETH/USDT",
    shortName: "Ethereum",
    group: "Kripto Utama",
    defaultTf: "1h",
    tfs: ["1h", "4h"],
  },
  {
    symbol: "TAOUSDT",
    display: "TAO/USDT",
    shortName: "Bittensor (AI Crypto)",
    group: "Kripto AI & Altcoin",
    defaultTf: "1h",
    tfs: ["1h", "4h"],
  },
  {
    symbol: "PAXGUSDT",
    display: "PAXG/USDT",
    shortName: "Emas Spot Tokenized (24/7)",
    group: "Emas & Perak",
    defaultTf: "1h",
    tfs: ["1h", "4h"],
  },
  {
    symbol: "GCF",
    display: "XAU/USD (GC=F)",
    shortName: "Emas Berjangka COMEX",
    group: "Emas & Perak",
    defaultTf: "1h",
    tfs: ["1h", "1d"],
  },
  {
    symbol: "SIF",
    display: "XAG/USD (SI=F)",
    shortName: "Perak Berjangka COMEX",
    group: "Emas & Perak",
    defaultTf: "1h",
    tfs: ["1h", "1d"],
  },
  {
    symbol: "BNBUSDT",
    display: "BNB/USDT",
    shortName: "Binance Coin",
    group: "Kripto Utama",
    defaultTf: "1h",
    tfs: ["1h", "4h"],
  },
  {
    symbol: "SOLUSDT",
    display: "SOL/USDT",
    shortName: "Solana",
    group: "Kripto AI & Altcoin",
    defaultTf: "1h",
    tfs: ["1h", "4h"],
  },
  {
    symbol: "XRPUSDT",
    display: "XRP/USDT",
    shortName: "Ripple",
    group: "Kripto AI & Altcoin",
    defaultTf: "1h",
    tfs: ["1h", "4h"],
  },
  {
    symbol: "ADAUSDT",
    display: "ADA/USDT",
    shortName: "Cardano",
    group: "Kripto AI & Altcoin",
    defaultTf: "1h",
    tfs: ["1h", "4h"],
  },
  {
    symbol: "DOGEUSDT",
    display: "DOGE/USDT",
    shortName: "Dogecoin",
    group: "Kripto AI & Altcoin",
    defaultTf: "1h",
    tfs: ["1h", "4h"],
  },
  {
    symbol: "ANTMJK",
    display: "ANTM.JK",
    shortName: "Aneka Tambang Tbk (Saham Emas/Nikel)",
    group: "Saham Komoditas",
    defaultTf: "1h",
    tfs: ["1h", "1d"],
  },
];

function RegimeDot({ regime }: { regime: string }) {
  const meta = REGIME_META[regime as Regime] ?? REGIME_META.uncertain_rule;
  const plain = REGIME_PLAIN[regime as Regime]?.name ?? regime;
  return (
    <span className="inline-flex items-center gap-1.5 font-medium text-txt">
      <span
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: meta.color }}
      />
      <span>{plain}</span>
    </span>
  );
}

export default function WalkForwardEvaluationPage() {
  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [tf, setTf] = useState<string>("1h");
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [bandSource, setBandSource] = useState<"pred" | "true">("pred");
  const [tableFilter, setTableFilter] = useState<"all" | "correct" | "diff">("all");
  const [chartHeight, setChartHeight] = useState(500);

  useEffect(() => {
    const resize = () =>
      setChartHeight(Math.max(380, Math.min(540, window.innerHeight - 340)));
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  const currentAssetMeta = useMemo(
    () =>
      ASSET_CATALOG.find((a) => a.symbol === symbol) ?? ASSET_CATALOG[0],
    [symbol]
  );

  const handleSelectAsset = (newSym: string, forcedTf?: string) => {
    const meta = ASSET_CATALOG.find((a) => a.symbol === newSym) ?? ASSET_CATALOG[0];
    setSymbol(newSym);
    if (forcedTf && meta.tfs.includes(forcedTf)) {
      setTf(forcedTf);
    } else if (!meta.tfs.includes(tf)) {
      setTf(meta.defaultTf);
    }
    setSelectedYear(null);
  };

  // Muat ringkasan lintas 12 aset
  const multiSummary = useApi(() => api.walkForwardMultiAsset(), []);

  // Muat seluruh candle OHLCV untuk aset & timeframe aktif
  const ohlcv = useApi(() => api.ohlcvHistory(tf, symbol), [symbol, tf]);

  // Muat timeline walk-forward untuk aset & timeframe aktif
  const timeline = useApi(
    () => api.walkForwardTimeline(symbol, tf),
    [symbol, tf]
  );

  const allSeries: WalkForwardPoint[] = timeline.data?.series ?? [];

  // Filter berdasarkan tahun bila dipilih
  const filteredSeries = useMemo(() => {
    if (selectedYear === null) return allSeries;
    return allSeries.filter((p) => p.year === selectedYear);
  }, [allSeries, selectedYear]);

  // Konversi ke format RegimePoint untuk CandlestickChart
  const chartRegimes: RegimePoint[] = useMemo(() => {
    return filteredSeries.map((p) => ({
      time: p.time,
      close: 0,
      regime: bandSource === "pred" ? p.pred_regime : p.true_regime,
      hurst: p.hurst,
      dfa_alpha: p.dfa_alpha,
    }));
  }, [filteredSeries, bandSource]);

  // Hitung metrik dinamis untuk tampilan kartu (mengikuti filter tahun jika dipilih)
  const activeStats = useMemo(() => {
    const assetSum: WalkForwardAssetSummary | null =
      timeline.data?.asset_summary ?? null;

    if (selectedYear !== null && assetSum?.yearly_results) {
      const yrObj = assetSum.yearly_results.find(
        (y) => y.test_year === selectedYear
      );
      if (yrObj) {
        return {
          total: yrObj.n_test,
          correct: yrObj.correct_identifications,
          ratePct: yrObj.identification_rate_pct,
          trainRange: yrObj.train_years_range,
          nTrain: yrObj.n_train,
          perClass: yrObj.per_class,
          perCond: yrObj.per_market_condition,
        };
      }
    }

    if (assetSum) {
      const years = assetSum.yearly_results ?? [];
      const firstTrain = years[0]?.train_years_range ?? "<= 2019";
      const lastTrain =
        years[years.length - 1]?.train_years_range ?? "<= 2025";
      return {
        total: assetSum.overall_test_windows,
        correct: assetSum.overall_correct_identifications,
        ratePct: assetSum.overall_identification_rate_pct,
        trainRange: `${firstTrain} s/d ${lastTrain}`,
        nTrain: years.reduce((acc, y) => Math.max(acc, y.n_train), 0),
        perClass: assetSum.per_class_identification,
        perCond: assetSum.per_market_condition_identification,
      };
    }

    const total = filteredSeries.length;
    const correct = filteredSeries.filter((s) => s.is_correct).length;
    return {
      total,
      correct,
      ratePct: total > 0 ? Number(((correct / total) * 100).toFixed(2)) : 0,
      trainRange: "Expanding 2019 -> 2025",
      nTrain: 0,
      perClass: {},
      perCond: {},
    };
  }, [timeline.data, selectedYear, filteredSeries]);

  const tableRows = useMemo(() => {
    const base = [...filteredSeries].reverse();
    if (tableFilter === "correct") return base.filter((r) => r.is_correct).slice(0, 120);
    if (tableFilter === "diff") return base.filter((r) => !r.is_correct).slice(0, 120);
    return base.slice(0, 120);
  }, [filteredSeries, tableFilter]);

  const availableYears = useMemo(() => {
    const assetSum = timeline.data?.asset_summary;
    if (assetSum?.yearly_results) {
      return assetSum.yearly_results.map((y) => y.test_year);
    }
    const set = new Set<number>();
    allSeries.forEach((s) => set.add(s.year));
    return Array.from(set).sort((a, b) => a - b);
  }, [timeline.data, allSeries]);

  const latestWindow =
    filteredSeries.length > 0 ? filteredSeries[filteredSeries.length - 1] : null;

  return (
    <div className="mx-auto max-w-[1560px] space-y-4 px-1 pb-10 sm:px-4">
      {/* HEADER UTAMA (Gaya Halaman Ringkasan) */}
      <header className="flex flex-wrap items-end justify-between gap-3 pt-2">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-[26px] font-bold tracking-tight text-txt">
              {currentAssetMeta.display}
            </h1>
            <span className="rounded-md border border-accent/50 bg-accent/10 px-2.5 py-0.5 text-[12px] font-semibold text-accent">
              Walk-Forward (2019 → 2026)
            </span>
            <span className="rounded-md border border-edge bg-panel px-2 py-0.5 text-[12px] font-medium text-txt">
              Identifikasi Regime Murni (h = 0)
            </span>
            <span className="rounded-md bg-surface px-2 py-0.5 text-[12px] font-medium text-txtDim">
              Hybrid Attention-BiLSTM · {tf.toUpperCase()}
            </span>
          </div>
          <p className="mt-1 text-[13px] text-txtMuted">
            Simulasi berjalan kronologis tahun demi tahun (berdiri di 2019, menguji 2020, lalu menambah pengetahuan ke 2021–2026) dengan{" "}
            <span className="font-medium text-txt">Purge Gap 500 bar</span>. Mengukur kesesuaian identifikasi model AI terhadap label acuan konsensus Hurst R/S &amp; DFA-1.
          </p>
        </div>

        {/* Toggle Skala Waktu */}
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-txtMuted">Skala waktu</span>
          <div className="inline-flex rounded-md border border-edge bg-panel p-0.5">
            {currentAssetMeta.tfs.map((itemTf) => (
              <button
                key={itemTf}
                type="button"
                onClick={() => setTf(itemTf)}
                className={`rounded px-3 py-1 font-mono text-[12px] font-semibold uppercase transition-colors ${
                  tf === itemTf
                    ? "bg-accent text-canvas"
                    : "text-txtDim hover:text-txt"
                }`}
              >
                {itemTf}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* PEMILIH 12 ASET & FILTER TAHUN WALK-FORWARD */}
      <section className="rounded-xl border border-edge bg-panel p-3.5 shadow-panel space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-[12px] font-semibold uppercase tracking-wider text-txtDim">
            Pilih Aset Uji Walk-Forward (12 Koin, Emas, Perak &amp; Komoditas)
          </span>
          <span className="text-[11.5px] text-txtMuted">
            Total Lintas 23 Kombinasi Aset-Timeframe:{" "}
            <strong className="font-mono text-txt">
              {multiSummary.data?.overall_summary?.grand_total_correct_identifications?.toLocaleString("id-ID") ?? "62.258"}
            </strong>{" "}
            /{" "}
            <span className="font-mono">
              {multiSummary.data?.overall_summary?.grand_total_test_windows?.toLocaleString("id-ID") ?? "88.586"}
            </span>{" "}
            jendela sesuai (
            <strong className="font-mono text-up">
              {multiSummary.data?.overall_summary?.grand_overall_identification_rate_pct ?? 70.28}%
            </strong>
            )
          </span>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {ASSET_CATALOG.map((item) => {
            const active = item.symbol === symbol;
            return (
              <button
                key={item.symbol}
                type="button"
                onClick={() => handleSelectAsset(item.symbol)}
                className={`group flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-left transition-all ${
                  active
                    ? "border-accent bg-accent/15 text-txt shadow-sm"
                    : "border-edge bg-surface/40 text-txtDim hover:border-edgeBright hover:bg-surface hover:text-txt"
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    active ? "bg-accent" : "bg-txtMuted/40 group-hover:bg-txtDim"
                  }`}
                />
                <div>
                  <div className="font-mono text-[12px] font-semibold leading-none">
                    {item.display}
                  </div>
                  <div className="mt-0.5 text-[10px] text-txtMuted">
                    {item.shortName}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Bar Filter Tahun & Mode Pita Warna */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-edge pt-2.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-[11.5px] font-medium text-txtMuted">
              Tahun Uji Walk-Forward:
            </span>
            <button
              type="button"
              onClick={() => setSelectedYear(null)}
              className={`rounded-md px-2.5 py-1 text-[11.5px] font-medium transition-colors ${
                selectedYear === null
                  ? "bg-accent text-canvas font-semibold"
                  : "bg-surface/60 text-txtDim hover:bg-surface hover:text-txt"
              }`}
            >
              Semua Tahun ({availableYears[0] ?? 2020}–{availableYears[availableYears.length - 1] ?? 2026})
            </button>
            {availableYears.map((yr) => (
              <button
                key={yr}
                type="button"
                onClick={() => setSelectedYear(yr)}
                className={`rounded-md px-2.5 py-1 font-mono text-[11.5px] transition-colors ${
                  selectedYear === yr
                    ? "bg-accent text-canvas font-semibold"
                    : "bg-surface/60 text-txtDim hover:bg-surface hover:text-txt"
                }`}
                title={`Model dilatih hanya pada data <= ${yr - 1}, lalu diuji mengidentifikasi tahun ${yr}`}
              >
                {yr}{" "}
                <span className="text-[10px] opacity-75">
                  (Latih ≤{yr - 1})
                </span>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-[11.5px] text-txtMuted">Pita Warna Chart:</span>
            <div className="inline-flex rounded-md border border-edge bg-surface/50 p-0.5 text-[11.5px]">
              <button
                type="button"
                onClick={() => setBandSource("pred")}
                className={`rounded px-2.5 py-0.5 font-medium transition-colors ${
                  bandSource === "pred"
                    ? "bg-panel text-accent shadow-sm"
                    : "text-txtDim hover:text-txt"
                }`}
              >
                Identifikasi AI (ŷ_t)
              </button>
              <button
                type="button"
                onClick={() => setBandSource("true")}
                className={`rounded px-2.5 py-0.5 font-medium transition-colors ${
                  bandSource === "true"
                    ? "bg-panel text-accent shadow-sm"
                    : "text-txtDim hover:text-txt"
                }`}
              >
                Label Acuan Hurst-DFA (y_t)
              </button>
            </div>
          </div>
        </div>
      </section>

      <ApiState loading={ohlcv.loading} error={ohlcv.error} />

      {!ohlcv.loading && !ohlcv.error && (
        <>
          {/* 4 KARTU RINGKASAN KEBENARAN IDENTIFIKASI */}
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {/* Kartu 1: Kebenaran Identifikasi Utama */}
            <div className="rounded-xl border border-edge bg-panel p-4 shadow-panel">
              <div className="flex items-center justify-between">
                <span className="text-[11.5px] font-medium uppercase tracking-wider text-txtMuted">
                  Kebenaran Identifikasi ({selectedYear ?? "2020–2026"})
                </span>
                <span className="rounded bg-up/15 px-1.5 py-0.5 font-mono text-[10.5px] font-semibold text-up">
                  h = 0 (Nowcasting)
                </span>
              </div>
              <div className="mt-2 flex items-baseline gap-2.5">
                <span className="font-mono text-[30px] font-bold tracking-tight text-txt">
                  {activeStats.ratePct.toFixed(2)}%
                </span>
                <span className="font-mono text-[12.5px] text-txtDim">
                  ({activeStats.correct.toLocaleString("id-ID")} /{" "}
                  {activeStats.total.toLocaleString("id-ID")} jendela)
                </span>
              </div>
              <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-surface">
                <div
                  className="h-full rounded-full bg-up transition-all"
                  style={{ width: `${Math.min(100, activeStats.ratePct)}%` }}
                />
              </div>
              <p className="mt-2 text-[11.5px] text-txtMuted">
                Data Latih: <strong className="text-txt">{activeStats.trainRange}</strong> · Tanpa bocoran masa depan (Purge 500 bar).
              </p>
            </div>

            {/* Kartu 2: Rincian per Kelas Regime */}
            <div className="rounded-xl border border-edge bg-panel p-4 shadow-panel">
              <div className="text-[11.5px] font-medium uppercase tracking-wider text-txtMuted">
                Kesesuaian per Kelas Regime Fraktal
              </div>
              <div className="mt-2.5 space-y-2 text-[12px]">
                {(["persistent", "anti_persistent", "random_like"] as const).map(
                  (cls) => {
                    const info = activeStats.perClass?.[cls];
                    const rate = info?.rate_pct ?? 0;
                    const corr = info?.correct ?? 0;
                    const tot = info?.total ?? 0;
                    const meta = REGIME_META[cls];
                    return (
                      <div key={cls} className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="flex items-center gap-1.5 text-txt">
                            <span
                              className="h-2 w-2 rounded-full"
                              style={{ backgroundColor: meta.color }}
                            />
                            {REGIME_PLAIN[cls].name}
                          </span>
                          <span className="font-mono text-[12px] text-txt">
                            <strong>{rate.toFixed(1)}%</strong>{" "}
                            <span className="text-[11px] text-txtMuted">
                              ({corr}/{tot})
                            </span>
                          </span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${Math.min(100, rate)}%`,
                              backgroundColor: meta.color,
                            }}
                          />
                        </div>
                      </div>
                    );
                  }
                )}
              </div>
            </div>

            {/* Kartu 3: Rincian per Kondisi Arah Pasar */}
            <div className="rounded-xl border border-edge bg-panel p-4 shadow-panel">
              <div className="text-[11.5px] font-medium uppercase tracking-wider text-txtMuted">
                Kesesuaian Saat Uptrend, Downtrend &amp; Sideways
              </div>
              <div className="mt-2.5 space-y-2 text-[12px]">
                {[
                  { key: "uptrend", label: "Fase Uptrend (Bullish)", color: "#2ebd85" },
                  { key: "downtrend", label: "Fase Downtrend (Bearish)", color: "#f6465d" },
                  { key: "sideways", label: "Fase Sideways (Konsolidasi)", color: "#38bdf8" },
                ].map((cond) => {
                  const info = activeStats.perCond?.[cond.key];
                  const rate = info?.rate_pct ?? 0;
                  const corr = info?.correct ?? 0;
                  const tot = info?.total ?? 0;
                  return (
                    <div key={cond.key} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-txtDim">{cond.label}</span>
                        <span className="font-mono text-[12px] text-txt">
                          <strong>{rate.toFixed(1)}%</strong>{" "}
                          <span className="text-[11px] text-txtMuted">
                            ({corr}/{tot})
                          </span>
                        </span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(100, rate)}%`,
                            backgroundColor: cond.color,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Kartu 4: Verifikasi Objektif Jendela Terakhir */}
            <div className="rounded-xl border border-edge bg-panel p-4 shadow-panel">
              <div className="flex items-center justify-between">
                <span className="text-[11.5px] font-medium uppercase tracking-wider text-txtMuted">
                  Bukti Verifikasi Jendela Terakhir
                </span>
                {latestWindow && (
                  <span
                    className={`rounded px-1.5 py-0.5 font-mono text-[10.5px] font-semibold ${
                      latestWindow.is_correct
                        ? "bg-up/15 text-up"
                        : "bg-down/15 text-down"
                    }`}
                  >
                    {latestWindow.is_correct ? "SESUAI (BENAR)" : "BERBEDA"}
                  </span>
                )}
              </div>
              {latestWindow ? (
                <div className="mt-2 space-y-1.5 text-[12px]">
                  <div className="flex justify-between text-txtDim">
                    <span>Waktu Jendela:</span>
                    <span className="font-mono text-txt">
                      {new Date(latestWindow.time * 1000).toLocaleDateString(
                        "id-ID",
                        { day: "2-digit", month: "short", year: "numeric" }
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between text-txtDim">
                    <span>Eksponen Fraktal:</span>
                    <span className="font-mono text-txt">
                      H={latestWindow.hurst.toFixed(3)} · α=
                      {latestWindow.dfa_alpha.toFixed(3)} · ER=
                      {latestWindow.er_score.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between text-txtDim">
                    <span>Label Acuan (Hurst-DFA):</span>
                    <RegimeDot regime={latestWindow.true_regime} />
                  </div>
                  <div className="flex justify-between text-txtDim">
                    <span>Hasil Identifikasi AI:</span>
                    <RegimeDot regime={latestWindow.pred_regime} />
                  </div>
                </div>
              ) : (
                <p className="mt-3 text-[12px] text-txtMuted">
                  Memuat titik verifikasi jendela…
                </p>
              )}
            </div>
          </section>

          {/* BAGIAN UTAMA: TRADINGVIEW CANDLESTICK CHART + TABEL BUKTI IDENTIFIKASI JENDELA */}
          <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_450px]">
            <div className="rounded-xl border border-edge bg-panel p-4 shadow-panel">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <div>
                  <h2 className="text-[16px] font-semibold text-txt">
                    Grafik Harga TradingView dengan Pita Walk-Forward{" "}
                    {bandSource === "pred"
                      ? "Identifikasi Model AI (ŷ_t)"
                      : "Label Acuan Konsensus Hurst-DFA (y_t)"}
                  </h2>
                  <p className="text-[12px] text-txtMuted">
                    Panah kuning di atas bar menandai awal tahun uji Walk-Forward baru · Gunakan tombol 1D–ALL atau gulir mouse untuk memperbesar periode tertentu.
                  </p>
                </div>
              </div>

              <CandlestickChart
                candles={ohlcv.data?.candles ?? []}
                regimes={chartRegimes}
                segments={timeline.data?.year_segments ?? []}
                height={chartHeight}
                symbol={currentAssetMeta.display}
                timeframe={tf.toUpperCase()}
                defaultRange="ALL"
                legend={<RegimeLegend compact />}
              />
            </div>

            {/* Tabel Bukti Verifikasi per Jendela (Hurst-DFA vs Identifikasi AI) */}
            <div className="flex h-full max-h-[620px] flex-col rounded-xl border border-edge bg-panel shadow-panel">
              <div className="border-b border-edge px-4 pb-3 pt-4">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-[15.5px] font-semibold text-txt">
                    Bukti Identifikasi per Jendela (h = 0)
                  </h2>
                  <span className="font-mono text-[11px] text-txtMuted">
                    {filteredSeries.length.toLocaleString("id-ID")} jendela
                  </span>
                </div>
                <p className="mt-0.5 text-[11.5px] text-txtMuted">
                  Membandingkan Label Acuan Konsensus (Hurst R/S + DFA-1) terhadap Hasil Identifikasi AI pada jendela waktu yang sama.
                </p>
                <div className="mt-2.5 flex gap-1">
                  {[
                    { key: "all", label: "Semua" },
                    { key: "correct", label: "Sesuai (Benar)" },
                    { key: "diff", label: "Berbeda" },
                  ].map((tab) => (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() =>
                        setTableFilter(tab.key as "all" | "correct" | "diff")
                      }
                      className={`rounded px-2.5 py-1 text-[11px] font-medium transition-colors ${
                        tableFilter === tab.key
                          ? "bg-accent text-canvas font-semibold"
                          : "bg-surface/60 text-txtDim hover:text-txt"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto">
                <table className="w-full text-[12px]">
                  <thead className="sticky top-0 bg-surface/90 backdrop-blur">
                    <tr className="text-left text-[11px] text-txtDim">
                      <th className="py-2 pl-3 font-medium">Waktu</th>
                      <th className="py-2 font-medium" title="Eksponen Hurst R/S dan DFA-1 pada jendela 500 bar">
                        H / α
                      </th>
                      <th className="py-2 font-medium" title="Label Acuan Konsensus Hurst-DFA (Ground Truth y_t)">
                        Acuan (y_t)
                      </th>
                      <th className="py-2 font-medium" title="Hasil Identifikasi Model Hybrid Attention-BiLSTM (ŷ_t)">
                        Model AI (ŷ_t)
                      </th>
                      <th className="py-2 pr-3 text-right font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.map((row) => (
                      <tr
                        key={row.time}
                        className="border-t border-edge/70 hover:bg-surface/40"
                      >
                        <td className="py-2 pl-3 font-mono text-[11px] text-txtDim">
                          {new Date(row.time * 1000).toLocaleDateString("id-ID", {
                            day: "2-digit",
                            month: "short",
                            year: "2-digit",
                          })}
                        </td>
                        <td className="py-2 font-mono text-[11px] text-txtMuted">
                          {row.hurst.toFixed(2)} / {row.dfa_alpha.toFixed(2)}
                        </td>
                        <td className="py-2">
                          <RegimeDot regime={row.true_regime} />
                        </td>
                        <td className="py-2">
                          <RegimeDot regime={row.pred_regime} />
                        </td>
                        <td className="py-2 pr-3 text-right">
                          <span
                            className={`inline-block rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
                              row.is_correct
                                ? "bg-up/15 text-up"
                                : "bg-down/15 text-down"
                            }`}
                          >
                            {row.is_correct ? "SESUAI" : "BEDA"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          {/* TABEL EVOLUSI TAHUN DEMI TAHUN (2020 -> 2026) UNTUK ASET AKTIF */}
          {timeline.data?.asset_summary?.yearly_results && (
            <section className="rounded-xl border border-edge bg-panel p-5 shadow-panel">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <h2 className="text-[16px] font-semibold text-txt">
                    Evolusi Walk-Forward Tahun demi Tahun — {currentAssetMeta.display} ({tf.toUpperCase()})
                  </h2>
                  <p className="mt-0.5 text-[12px] text-txtMuted">
                    Klik baris tahun mana pun untuk memfokuskan metrik dan tabel verifikasi di atas pada tahun tersebut.
                  </p>
                </div>
                {selectedYear !== null && (
                  <button
                    type="button"
                    onClick={() => setSelectedYear(null)}
                    className="rounded-md border border-edge px-2.5 py-1 text-[11.5px] text-accent hover:bg-surface"
                  >
                    Tampilkan Semua Tahun
                  </button>
                )}
              </div>

              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-[12.5px]">
                  <thead>
                    <tr className="border-b border-edge text-left text-[11.5px] text-txtDim">
                      <th className="py-2.5 pl-3 font-medium">Tahun Uji</th>
                      <th className="py-2.5 font-medium">Rentang Latih</th>
                      <th className="py-2.5 text-right font-medium">Sampel Latih</th>
                      <th className="py-2.5 text-right font-medium">Jendela Uji</th>
                      <th className="py-2.5 text-right font-medium">Identifikasi Benar</th>
                      <th className="py-2.5 text-right font-medium">% Kebenaran</th>
                      <th className="py-2.5 text-right font-medium">Berlanjut (P)</th>
                      <th className="py-2.5 text-right font-medium">Acak (R)</th>
                      <th className="py-2.5 pr-3 text-right font-medium">Berbalik (A)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timeline.data.asset_summary.yearly_results.map((yr) => {
                      const isSel = selectedYear === yr.test_year;
                      return (
                        <tr
                          key={yr.test_year}
                          onClick={() =>
                            setSelectedYear(isSel ? null : yr.test_year)
                          }
                          className={`cursor-pointer border-b border-edge/60 transition-colors ${
                            isSel
                              ? "bg-accent/15 font-medium"
                              : "hover:bg-surface/60"
                          }`}
                        >
                          <td className="py-2.5 pl-3 font-mono font-semibold text-txt">
                            Tahun {yr.test_year}
                          </td>
                          <td className="py-2.5 font-mono text-[12px] text-txtDim">
                            {yr.train_years_range}
                          </td>
                          <td className="py-2.5 text-right font-mono text-txtDim">
                            {yr.n_train.toLocaleString("id-ID")}
                          </td>
                          <td className="py-2.5 text-right font-mono text-txt">
                            {yr.n_test.toLocaleString("id-ID")}
                          </td>
                          <td className="py-2.5 text-right font-mono text-up">
                            {yr.correct_identifications.toLocaleString("id-ID")}
                          </td>
                          <td className="py-2.5 text-right font-mono font-bold text-txt">
                            {yr.identification_rate_pct.toFixed(2)}%
                          </td>
                          <td className="py-2.5 text-right font-mono text-[12px] text-txtDim">
                            {yr.per_class?.persistent?.rate_pct?.toFixed(1) ?? "—"}%
                          </td>
                          <td className="py-2.5 text-right font-mono text-[12px] text-txtDim">
                            {yr.per_class?.random_like?.rate_pct?.toFixed(1) ?? "—"}%
                          </td>
                          <td className="py-2.5 pr-3 text-right font-mono text-[12px] text-txtDim">
                            {yr.per_class?.anti_persistent?.rate_pct?.toFixed(1) ?? "—"}%
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* TABEL REKAPITULASI LINTAS 12 ASET (KLIK UNTUK GANTI GRAFIK) */}
          {multiSummary.data?.assets_evaluated && (
            <section className="rounded-xl border border-edge bg-panel p-5 shadow-panel">
              <div>
                <h2 className="text-[16px] font-semibold text-txt">
                  Tabel Rekapitulasi Walk-Forward Lintas 12 Aset &amp; Komoditas (2019 → 2026)
                </h2>
                <p className="mt-0.5 text-[12px] text-txtMuted">
                  Klik baris aset mana pun untuk langsung menampilkan grafik TradingView dan pita identifikasi walk-forward aset tersebut di atas.
                </p>
              </div>

              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="border-b border-edge text-left text-[11px] text-txtDim">
                      <th className="py-2.5 pl-3 font-medium">Aset</th>
                      <th className="py-2.5 font-medium">TF</th>
                      <th className="py-2.5 text-right font-medium">2020</th>
                      <th className="py-2.5 text-right font-medium">2021</th>
                      <th className="py-2.5 text-right font-medium">2022</th>
                      <th className="py-2.5 text-right font-medium">2023</th>
                      <th className="py-2.5 text-right font-medium">2024</th>
                      <th className="py-2.5 text-right font-medium">2025</th>
                      <th className="py-2.5 text-right font-medium">2026</th>
                      <th className="py-2.5 text-right font-medium">Benar / Total</th>
                      <th className="py-2.5 pr-3 text-right font-medium">Total %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {multiSummary.data.assets_evaluated
                      .filter((a) => a.status === "ok")
                      .map((item) => {
                        const isCurrent =
                          item.symbol === symbol && item.timeframe === tf;
                        const yrMap = new Map(
                          (item.yearly_results ?? []).map((y) => [
                            y.test_year,
                            y.identification_rate_pct,
                          ])
                        );
                        return (
                          <tr
                            key={`${item.symbol}_${item.timeframe}`}
                            onClick={() =>
                              handleSelectAsset(item.symbol, item.timeframe)
                            }
                            className={`cursor-pointer border-b border-edge/60 transition-colors ${
                              isCurrent
                                ? "bg-accent/15 font-medium"
                                : "hover:bg-surface/60"
                            }`}
                          >
                            <td className="py-2 pl-3">
                              <div className="font-mono font-semibold text-txt">
                                {item.symbol}
                              </div>
                              <div className="text-[10.5px] text-txtMuted">
                                {item.name}
                              </div>
                            </td>
                            <td className="py-2 font-mono uppercase text-txtDim">
                              {item.timeframe}
                            </td>
                            {[2020, 2021, 2022, 2023, 2024, 2025, 2026].map(
                              (yr) => {
                                const v = yrMap.get(yr);
                                return (
                                  <td
                                    key={yr}
                                    className="py-2 text-right font-mono text-txtDim"
                                  >
                                    {v !== undefined ? `${v.toFixed(1)}%` : "—"}
                                  </td>
                                );
                              }
                            )}
                            <td className="py-2 text-right font-mono text-txt">
                              {item.overall_correct_identifications.toLocaleString(
                                "id-ID"
                              )}{" "}
                              /{" "}
                              {item.overall_test_windows.toLocaleString("id-ID")}
                            </td>
                            <td className="py-2 pr-3 text-right font-mono font-bold text-up">
                              {item.overall_identification_rate_pct.toFixed(2)}%
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

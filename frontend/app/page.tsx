"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CandlestickChart from "@/components/CandlestickChart";
import CollapsiblePanel from "@/components/CollapsiblePanel";
import DataStatusBar from "@/components/DataStatusBar";
import Disclaimer from "@/components/Disclaimer";
import HowToRead from "@/components/HowToRead";
import { useRecentRegimes } from "@/components/MarketSummary";
import ParameterBar from "@/components/ParameterBar";
import RegimeHistoryTable from "@/components/RegimeHistoryTable";
import RegimeLegend from "@/components/RegimeLegend";
import RegimeOverview, { type RandomBand } from "@/components/RegimeOverview";
import TimeframeToggle from "@/components/TimeframeToggle";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

const pct = (v: number) => `${(v * 100).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;

function ShareBar({ title, note, rows }: { title: string; note: string; rows: { key: string; share: number }[] }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[12.5px] font-medium text-txt">{title}</span>
        <span className="text-2xs text-txtMuted">{note}</span>
      </div>
      <div className="mt-2 flex h-2.5 gap-0.5 overflow-hidden rounded-full">
        {rows.map((r) => (
          <div
            key={r.key}
            style={{ width: `${r.share * 100}%`, backgroundColor: REGIME_META[r.key as Regime]?.color ?? "#334155" }}
            title={`${REGIME_PLAIN[r.key as Regime]?.name ?? r.key}: ${(r.share * 100).toFixed(0)}%`}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {rows.map((r) => (
          <span key={r.key} className="flex items-center gap-1.5 text-[12px] text-txtDim">
            <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: REGIME_META[r.key as Regime]?.color ?? "#334155" }} />
            {REGIME_PLAIN[r.key as Regime]?.name ?? r.key}
            <span className="font-mono text-txt">{(r.share * 100).toFixed(0)}%</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { timeframe, config } = useAppConfig();
  const symbol = config?.data.symbol ?? "BTCUSDT";

  const [chartHeight, setChartHeight] = useState(520);
  useEffect(() => {
    const resize = () => setChartHeight(Math.max(380, Math.min(560, window.innerHeight - 340)));
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  // Seluruh riwayat, tidak dipotong; hasil di-cache per timeframe.
  const ohlcv = useApi(() => api.ohlcvHistory(timeframe), [timeframe]);
  // Detektor resmi untuk kedua timeframe: yang aktif untuk grafik dan kartu
  // utama, keduanya untuk strip multi-timeframe.
  const ai1h = useApi(() => api.aiRegime("1h"), []);
  const ai4h = useApi(() => api.aiRegime("4h"), []);
  const regime = timeframe === "4h" ? ai4h : ai1h;
  // Estimator klasik Hurst R/S dan DFA sebagai pembanding beserta pita acaknya.
  // 2000 titik cukup rapat untuk membaca selisih terhadap ±30 hari lalu.
  const classic = useApi(() => api.hurstDfa(timeframe, 2000), [timeframe]);

  // Chart harga hanya menunggu OHLCV; overlay regime menyusul.
  const loading = ohlcv.loading;
  const error = ohlcv.error;

  const series = regime.data?.series ?? [];
  const distribution = regime.data?.distribution ?? {};
  const recent = useRecentRegimes(series);
  const detector = regime.data?.detector;
  const band: RandomBand = classic.data?.random_band ?? null;

  const allTime = Object.entries(distribution)
    .map(([key, v]) => ({ key, share: v.share }))
    .filter((r) => r.share > 0)
    .sort((a, b) => b.share - a.share);

  return (
    <div className="mx-auto max-w-[1560px] space-y-4 px-1 pb-8 sm:px-4">
      <header className="flex flex-wrap items-end justify-between gap-3 pt-2">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-[26px] font-bold tracking-tight text-txt">{symbol.replace("USDT", "/USDT")}</h1>
            <span className="rounded-md border border-edge bg-panel px-2 py-0.5 text-[12px] font-medium text-txt">Ringkasan</span>
            <span className="rounded-md bg-surface px-2 py-0.5 text-[12px] font-medium text-txtDim">
              Identifikasi AI · {timeframe.toUpperCase()}
            </span>
          </div>
          <p className="mt-1 text-[13px] text-txtMuted">
            Sifat gerakan harga BTC/USDT menurut model identifikasi Hybrid Attention-BiLSTM.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <Link
            href="/evaluasi-identifikasi"
            className="flex items-center gap-1.5 rounded-md border border-accent/40 bg-accent/10 px-2.5 py-1 text-[12px] font-medium text-accent transition-colors hover:bg-accent/20"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Hasil Uji Identifikasi →
          </Link>
          <span data-tour="timeframe" className="flex items-center gap-2.5">
            <span className="text-[12px] text-txtMuted">Skala waktu</span>
            <TimeframeToggle />
          </span>
        </div>
      </header>

      {config?.runtime.use_mock && <Disclaimer variant="mock" />}
      <ApiState loading={loading} error={error} />

      {!loading && !error && (
        <>
          {regime.error && (
            <div className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-[12px] text-warn">
              Analisis kondisi pasar gagal dimuat ({regime.error}). Grafik harga tetap ditampilkan.
            </div>
          )}

          <div data-tour="overview">
            <RegimeOverview
              timeframe={timeframe}
              ai1h={ai1h.data}
              ai4h={ai4h.data}
              classic={classic.data?.series ?? []}
              band={band}
              candles={ohlcv.data?.candles ?? []}
            />
          </div>

          <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
            <div data-tour="chart" className="rounded-xl border border-edge bg-panel p-4 shadow-panel">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <h2 className="text-[16px] font-semibold text-txt">Harga dengan pita kondisi pasar</h2>
                <span className="text-[12px] text-txtMuted">Warna latar = kondisi saat itu · 1D–ALL mengubah rentang · gulir untuk zoom</span>
              </div>
              <CandlestickChart
                candles={ohlcv.data?.candles ?? []}
                regimes={series}
                height={chartHeight}
                symbol={symbol}
                timeframe={timeframe}
                defaultRange="3M"
                legend={<RegimeLegend compact />}
              />
            </div>
            <RegimeHistoryTable series={series} tau={detector?.abstain_tau ?? 0.75} timeframe={timeframe} />
          </section>

          <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="space-y-5 rounded-xl border border-edge bg-panel p-5 shadow-panel">
              <div>
                <h2 className="text-[15px] font-semibold text-txt">Seberapa sering tiap kondisi terjadi?</h2>
                <p className="mt-0.5 text-[12px] text-txtMuted">Bandingkan 30 hari terakhir dengan seluruh riwayat.</p>
              </div>
              {recent && <ShareBar title="30 hari terakhir" note={`${recent.switches}× berganti`} rows={recent.recentShare} />}
              {allTime.length > 0 && <ShareBar title="Seluruh riwayat" note="sejak 2019" rows={allTime} />}
            </div>
            <div className="rounded-xl border border-edge bg-panel p-5 shadow-panel">
              <h2 className="text-[15px] font-semibold text-txt">Arti tiap warna</h2>
              <div className="mt-3">
                <RegimeLegend />
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-txtMuted">
                Sengaja tidak memakai hijau/merah: kondisi pasar menggambarkan sifat gerakan, bukan arah naik/turun.
              </p>
            </div>
          </section>

          <HowToRead />

          <CollapsiblePanel title="Tentang model identifikasi" subtitle="Model AI yang menentukan kondisi pasar">
            <ParameterBar showTimeframe={false} />
            {detector && (
              <dl className="mt-3 grid gap-2 text-[12.5px] sm:grid-cols-2">
                <div className="rounded-lg bg-surface/70 px-3 py-2">
                  <dt className="text-txtMuted">Model</dt>
                  <dd className="mt-0.5 text-txt">
                    {detector.name} · ensemble {detector.ensemble_seeds.length} seed
                  </dd>
                </div>
                <div className="rounded-lg bg-surface/70 px-3 py-2">
                  <dt className="text-txtMuted">Masukan</dt>
                  <dd className="mt-0.5 text-txt">{detector.inputs}</dd>
                </div>
                <div className="rounded-lg bg-surface/70 px-3 py-2">
                  <dt className="text-txtMuted">Dilatih pada</dt>
                  <dd className="mt-0.5 text-txt">{detector.trained_on}</dd>
                </div>
                <div className="rounded-lg bg-surface/70 px-3 py-2">
                  <dt className="text-txtMuted">Identifikasi benar, partisi uji {detector.model_timeframe.toUpperCase()}</dt>
                  <dd className="mt-0.5 font-mono text-txt">
                    {detector.test_backtest.correct.toLocaleString("id-ID")}/{detector.test_backtest.n.toLocaleString("id-ID")} ({pct(detector.test_backtest.accuracy)})
                    <span className="ml-2 font-sans text-txtMuted">
                      rata-rata 3 kelas {pct(detector.test_backtest.balanced_accuracy)}
                      {detector.walk_forward_pooled ? ` · walk-forward ${pct(detector.walk_forward_pooled.accuracy)}` : ""}
                    </span>
                  </dd>
                </div>
              </dl>
            )}
            <p className="mt-3 text-[12px] leading-relaxed text-txtDim">
              Model menilai {detector?.window ?? 500} batang terakhir setiap {detector?.stride_bars ?? 4} batang dan
              mengidentifikasi regime jendela itu sendiri (h = 0, bukan prediksi). Label yang dipelajari: {detector?.label ?? "konsensus Hurst R/S–DFA-1"}
              {detector ? ` (ambang Hurst ${detector.label_thresholds.hurst.map((v) => v.toLocaleString("id-ID")).join("–")}, DFA ${detector.label_thresholds.dfa.map((v) => v.toLocaleString("id-ID")).join("–")})` : ""}.
              Riwayat sebelum batas latih adalah data latih model; angka di atas diukur pada partisi uji yang tidak dipakai melatih.
              Model paling lemah mengenali kondisi acak (random-like).
            </p>
          </CollapsiblePanel>

          <CollapsiblePanel title="Status data & catatan" subtitle="Sumber, kesegaran data, disclaimer">
            <DataStatusBar />
            <div className="mt-2">
              <Disclaimer variant="fractal" />
            </div>
          </CollapsiblePanel>
        </>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import CandlestickChart from "@/components/CandlestickChart";
import CollapsiblePanel from "@/components/CollapsiblePanel";
import DataStatusBar from "@/components/DataStatusBar";
import Disclaimer from "@/components/Disclaimer";
import ExponentGauge from "@/components/ExponentGauge";
import HowToRead from "@/components/HowToRead";
import MarketSummary, { useRecentRegimes } from "@/components/MarketSummary";
import ParameterBar from "@/components/ParameterBar";
import RegimeLegend from "@/components/RegimeLegend";
import TimeframeToggle from "@/components/TimeframeToggle";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, SEGMENT_META, type Regime } from "@/lib/regime";

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
    const resize = () => setChartHeight(Math.max(380, Math.min(600, window.innerHeight - 300)));
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  // Seluruh riwayat, tidak dipotong; hasil di-cache per timeframe.
  const ohlcv = useApi(() => api.ohlcvHistory(timeframe), [timeframe]);
  const regime = useApi(() => api.regime(timeframe), [timeframe]);
  const split = useApi(() => api.splitBoundaries(timeframe), [timeframe]);
  // Hanya untuk ambang efektif (bisa hasil kalibrasi kuantil, bukan nilai config).
  const thresholds = useApi(() => api.hurstDfa(timeframe, 100), [timeframe]);

  // Chart harga hanya menunggu OHLCV; overlay regime menyusul.
  const loading = ohlcv.loading;
  const error = ohlcv.error ?? split.error;

  const series = regime.data?.series ?? [];
  const current = regime.data?.current_regime;
  const distribution = regime.data?.distribution ?? {};
  const last = series.length ? series[series.length - 1] : null;
  const recent = useRecentRegimes(series);

  const p = thresholds.data?.parameters;
  const hLo = p?.hurst_lower ?? config?.analysis.hurst_threshold[0] ?? 0.45;
  const hHi = p?.hurst_upper ?? config?.analysis.hurst_threshold[1] ?? 0.55;
  const aLo = p?.dfa_lower ?? config?.analysis.dfa_threshold[0] ?? 0.45;
  const aHi = p?.dfa_upper ?? config?.analysis.dfa_threshold[1] ?? 0.55;

  const allTime = Object.entries(distribution)
    .map(([key, v]: [string, any]) => ({ key, share: v.share as number }))
    .sort((a, b) => b.share - a.share);

  return (
    <div className="mx-auto max-w-[1500px] space-y-4 px-1 pb-6 sm:px-3">
      <header className="flex flex-wrap items-end justify-between gap-3 pt-1">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-txt">Ringkasan pasar</h1>
          <p className="mt-0.5 text-[13px] text-txtDim">
            Sifat gerakan {symbol.replace("USDT", "/USDT")} saat ini dan apa artinya untuk strategi Anda.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-txtMuted">Skala waktu</span>
          <TimeframeToggle />
        </div>
      </header>

      <HowToRead />

      {config?.runtime.use_mock && <Disclaimer variant="mock" />}
      <ApiState loading={loading} error={error} />

      {!loading && !error && (
        <>
          {regime.error && (
            <div className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-[12px] text-warn">
              Analisis kondisi pasar gagal dimuat ({regime.error}). Grafik harga tetap ditampilkan.
            </div>
          )}

          <MarketSummary
            current={current}
            series={series}
            loading={regime.loading}
            symbol={symbol.replace("USDT", "/USDT")}
            timeframe={timeframe}
            gauges={
              <>
                <ExponentGauge
                  label="Hurst (R/S)"
                  hint="Eksponen Hurst (metode R/S). Di atas batas atas = tren berlanjut, di bawah batas bawah = cenderung berbalik."
                  value={last?.hurst}
                  lower={hLo}
                  upper={hHi}
                  loading={regime.loading}
                />
                <ExponentGauge
                  label="DFA (α)"
                  hint="Detrended Fluctuation Analysis (α). Dibaca sama seperti Hurst. Jika kedua alat ukur tidak sepakat, kondisi ditandai 'Belum Jelas'."
                  value={last?.dfa_alpha}
                  lower={aLo}
                  upper={aHi}
                  loading={regime.loading}
                />
              </>
            }
          />

          <section className="space-y-2">
            <div className="flex flex-wrap items-baseline gap-x-3 px-1">
              <h2 className="text-[15px] font-semibold text-txt">Riwayat harga &amp; kondisi pasar</h2>
              <span className="text-[12px] text-txtMuted">
                Warna latar = kondisi pasar saat itu. Tombol 1D–ALL mengubah rentang; gulir untuk zoom.
              </span>
            </div>
            <div className="overflow-hidden rounded-xl border border-edge">
              <CandlestickChart
                candles={ohlcv.data?.candles ?? []}
                regimes={series}
                segments={split.data?.segments ?? []}
                height={chartHeight}
                symbol={symbol}
                timeframe={timeframe}
                defaultRange="3M"
                legend={<RegimeLegend compact />}
              />
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="space-y-5 rounded-xl border border-edge bg-panel p-5">
              <div>
                <h2 className="text-[15px] font-semibold text-txt">Seberapa sering tiap kondisi terjadi?</h2>
                <p className="mt-0.5 text-[12px] text-txtMuted">Bandingkan 30 hari terakhir dengan seluruh riwayat.</p>
              </div>
              {recent && <ShareBar title="30 hari terakhir" note={`${recent.switches}× berganti`} rows={recent.recentShare} />}
              {allTime.length > 0 && <ShareBar title="Seluruh riwayat" note="sejak 2019" rows={allTime} />}
            </div>
            <div className="rounded-xl border border-edge bg-panel p-5">
              <h2 className="text-[15px] font-semibold text-txt">Arti tiap warna</h2>
              <div className="mt-3">
                <RegimeLegend />
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-txtMuted">
                Sengaja tidak memakai hijau/merah: kondisi pasar menggambarkan sifat gerakan, bukan arah naik/turun.
              </p>
            </div>
          </section>

          <CollapsiblePanel title="Detail teknis" subtitle="Parameter analisis dan pembagian data latih/uji">
            <ParameterBar showTimeframe={false} />
            <div className="mt-3 space-y-1.5">
              {(split.data?.segments ?? []).map((s: any) => {
                const key = s.segment.replace(/_\d+$/, "");
                const meta = SEGMENT_META[key] ?? { label: s.segment, color: "#334155" };
                const width = ((s.end_index - s.start_index) / (split.data?.n || 1)) * 100;
                return (
                  <div key={s.segment} className="flex items-center gap-2">
                    <span className="w-32 shrink-0 text-[11px] text-txtDim">{meta.label}</span>
                    <div className="h-4 flex-1 overflow-hidden rounded bg-panelAlt">
                      <div
                        className="h-full"
                        style={{ width: `${Math.max(width, 0.5)}%`, backgroundColor: meta.color.replace(/[\d.]+\)$/, "0.85)") }}
                      />
                    </div>
                    <span className="w-28 shrink-0 text-right font-mono text-2xs text-txtMuted">
                      {s.start_index}–{s.end_index}
                    </span>
                  </div>
                );
              })}
            </div>
            <p className="mt-3 text-[12px] leading-relaxed text-txtDim">
              Data diurutkan menurut waktu: bagian awal untuk melatih model, bagian akhir untuk mengujinya, seperti belajar
              dari soal lama lalu diuji dengan soal baru. Di antaranya ada jarak pengaman (purge = {config?.model.purge_gap}{" "}
              batang) agar model tidak &ldquo;mengintip&rdquo; data uji.
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

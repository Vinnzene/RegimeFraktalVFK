"use client";

import { useEffect, useState } from "react";
import CandlestickChart from "@/components/CandlestickChart";
import CollapsiblePanel from "@/components/CollapsiblePanel";
import DataStatusBar from "@/components/DataStatusBar";
import Disclaimer from "@/components/Disclaimer";
import ExponentGauge from "@/components/ExponentGauge";
import HowToRead from "@/components/HowToRead";
import MarketSummary from "@/components/MarketSummary";
import ParameterBar from "@/components/ParameterBar";
import RegimeLegend from "@/components/RegimeLegend";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, SEGMENT_META, type Regime } from "@/lib/regime";

export default function DashboardPage() {
  const { timeframe, config } = useAppConfig();

  const [chartHeight, setChartHeight] = useState(520);
  useEffect(() => {
    const resize = () => setChartHeight(Math.max(360, Math.min(620, window.innerHeight - 330)));
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

  const p = thresholds.data?.parameters;
  const hLo = p?.hurst_lower ?? config?.analysis.hurst_threshold[0] ?? 0.45;
  const hHi = p?.hurst_upper ?? config?.analysis.hurst_threshold[1] ?? 0.55;
  const aLo = p?.dfa_lower ?? config?.analysis.dfa_threshold[0] ?? 0.45;
  const aHi = p?.dfa_upper ?? config?.analysis.dfa_threshold[1] ?? 0.55;

  return (
    <div className="mx-auto max-w-[1600px] space-y-3">
      <HowToRead />
      <ParameterBar />

      {config?.runtime.use_mock && <Disclaimer variant="mock" />}

      <ApiState loading={loading} error={error} />

      {!loading && !error && (
        <>
          {regime.error && (
            <div className="rounded border border-warn/40 bg-warn/10 px-3 py-2 text-[12px] text-warn">
              Analisis kondisi pasar gagal dimuat ({regime.error}). Grafik harga tetap ditampilkan.
            </div>
          )}

          <div className="grid gap-3 xl:grid-cols-[1fr_320px]">
            <MarketSummary current={current} series={series} loading={regime.loading} />

            <div className="grid content-start gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <ExponentGauge
                label="Alat ukur 1 — Hurst"
                hint="Eksponen Hurst (metode R/S). Di atas batas atas = tren berlanjut, di bawah batas bawah = cenderung berbalik."
                value={last?.hurst}
                lower={hLo}
                upper={hHi}
                loading={regime.loading}
              />
              <ExponentGauge
                label="Alat ukur 2 — DFA"
                hint="Detrended Fluctuation Analysis (α). Dibaca sama seperti Hurst. Jika kedua alat ukur tidak sepakat, kondisi ditandai 'Belum Jelas'."
                value={last?.dfa_alpha}
                lower={aLo}
                upper={aHi}
                loading={regime.loading}
              />
            </div>
          </div>

          <div>
            <div className="mb-1.5 flex flex-wrap items-baseline gap-x-3 px-1">
              <h2 className="text-[14px] font-semibold text-txt">Riwayat harga &amp; kondisi pasar</h2>
              <span className="text-[12px] text-txtMuted">
                Warna latar = kondisi pasar pada saat itu. Gunakan tombol 1D–ALL untuk mengubah rentang,
                gulir untuk zoom.
              </span>
            </div>
            <CandlestickChart
              candles={ohlcv.data?.candles ?? []}
              regimes={series}
              segments={split.data?.segments ?? []}
              height={chartHeight}
              symbol={config?.data.symbol ?? "BTCUSDT"}
              timeframe={timeframe}
              defaultRange="3M"
              legend={<RegimeLegend compact />}
            />
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            <div className="rounded-md border border-edge bg-panel p-4 lg:col-span-1">
              <div className="text-[13px] font-semibold text-txt">Seberapa sering tiap kondisi terjadi?</div>
              <div className="mt-0.5 text-[11px] text-txtMuted">Sepanjang seluruh data historis</div>
              <div className="mt-3 space-y-2.5">
                {Object.entries(distribution)
                  .sort((a: any, b: any) => b[1].share - a[1].share)
                  .map(([key, val]: any) => (
                    <div key={key}>
                      <div className="flex justify-between text-[12px]">
                        <span className="text-txtDim">
                          {REGIME_PLAIN[key as Regime]?.name ?? key}
                        </span>
                        <span className="font-mono text-txt">{(val.share * 100).toFixed(1)}%</span>
                      </div>
                      <div className="mt-1 h-2 overflow-hidden rounded bg-panelAlt">
                        <div
                          className="h-full"
                          style={{
                            width: `${val.share * 100}%`,
                            backgroundColor: REGIME_META[key as Regime]?.color ?? "#334155",
                          }}
                        />
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            <div className="rounded-md border border-edge bg-panel p-4 lg:col-span-2">
              <div className="text-[13px] font-semibold text-txt">Arti tiap warna</div>
              <div className="mt-3">
                <RegimeLegend />
              </div>
              <p className="mt-3 text-[11px] leading-relaxed text-txtMuted">
                Warna sengaja tidak memakai hijau/merah: kondisi pasar menggambarkan sifat gerakan,
                bukan arah naik/turun.
              </p>
            </div>
          </div>

          <CollapsiblePanel
            title="Detail teknis: pembagian data latih/uji"
            subtitle="Untuk pembaca yang ingin tahu cara model diuji"
          >
            <div className="space-y-1.5">
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
                        style={{
                          width: `${Math.max(width, 0.5)}%`,
                          backgroundColor: meta.color.replace(/[\d.]+\)$/, "0.85)"),
                        }}
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
              Data diurutkan menurut waktu: bagian awal untuk melatih model, bagian akhir untuk
              mengujinya — seperti belajar dari soal lama lalu diuji dengan soal baru. Di antaranya ada
              jarak pengaman (purge = {config?.model.purge_gap} batang) agar model tidak &ldquo;mengintip&rdquo;
              data uji.
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

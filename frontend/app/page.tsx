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
import { api, type AiRegimeClass, type AiRegimeResponse } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

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

const AI_CLASSES: AiRegimeClass[] = ["persistent", "random_like", "anti_persistent"];

/** Probabilitas tiap kelas dari detektor AI untuk window terakhir. */
function ProbabilityBars({ probs }: { probs: Record<AiRegimeClass, number> | null | undefined }) {
  if (!probs) return null;
  return (
    <div className="space-y-2">
      {AI_CLASSES.map((c) => (
        <div key={c}>
          <div className="flex items-baseline justify-between text-[12px]">
            <span className="text-txtDim">{REGIME_PLAIN[c].name}</span>
            <span className="font-mono text-txt">{Math.round(probs[c] * 100)}%</span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface">
            <div className="h-full rounded-full" style={{ width: `${probs[c] * 100}%`, backgroundColor: REGIME_META[c].color }} />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Regime saat ini di setiap timeframe, berdampingan. */
function TimeframeStrip({ items }: { items: { tf: string; data: AiRegimeResponse | null; error: string | null }[] }) {
  return (
    <section className="grid gap-3 sm:grid-cols-2" aria-label="Kondisi per skala waktu">
      {items.map(({ tf, data, error }) => {
        const key = data?.current_regime ?? null;
        const color = key ? REGIME_META[key].color : "#8b949e";
        const conf = key && data?.current_probabilities ? data.current_probabilities[key] : null;
        return (
          <div key={tf} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-edge bg-panel px-4 py-3">
            <span className="rounded-md border border-edge px-2 py-0.5 font-mono text-[12px] text-txtDim">{tf.toUpperCase()}</span>
            {key ? (
              <>
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-[14px] font-semibold" style={{ color }}>
                  {REGIME_PLAIN[key].name}
                </span>
                {conf !== null && <span className="text-[12px] text-txtMuted">keyakinan {Math.round(conf * 100)}%</span>}
              </>
            ) : (
              <span className="text-[12.5px] text-txtMuted">{error ?? "Memuat…"}</span>
            )}
          </div>
        );
      })}
    </section>
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
  // Detektor resmi untuk kedua timeframe: yang aktif untuk grafik dan kartu
  // utama, keduanya untuk strip multi-timeframe.
  const ai1h = useApi(() => api.aiRegime("1h"), []);
  const ai4h = useApi(() => api.aiRegime("4h"), []);
  const regime = timeframe === "4h" ? ai4h : ai1h;
  // Estimator klasik Hurst R/S dan DFA sebagai pembanding (nilai dan ambang efektif).
  const classic = useApi(() => api.hurstDfa(timeframe, 100), [timeframe]);

  // Chart harga hanya menunggu OHLCV; overlay regime menyusul.
  const loading = ohlcv.loading;
  const error = ohlcv.error;

  const series = regime.data?.series ?? [];
  const current = regime.data?.current_regime;
  const distribution = regime.data?.distribution ?? {};
  const recent = useRecentRegimes(series);
  const classicSeries = classic.data?.series ?? [];
  const last = classicSeries.length ? classicSeries[classicSeries.length - 1] : null;
  const detector = regime.data?.detector;

  const p = classic.data?.parameters;
  const hLo = p?.hurst_lower ?? config?.analysis.hurst_threshold[0] ?? 0.45;
  const hHi = p?.hurst_upper ?? config?.analysis.hurst_threshold[1] ?? 0.55;
  const aLo = p?.dfa_lower ?? config?.analysis.dfa_threshold[0] ?? 0.45;
  const aHi = p?.dfa_upper ?? config?.analysis.dfa_threshold[1] ?? 0.55;

  const allTime = Object.entries(distribution)
    .map(([key, v]) => ({ key, share: v.share }))
    .filter((r) => r.share > 0)
    .sort((a, b) => b.share - a.share);

  return (
    <div className="mx-auto max-w-[1500px] space-y-4 px-1 pb-6 sm:px-3">
      <header className="flex flex-wrap items-end justify-between gap-3 pt-1">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-txt">Ringkasan pasar</h1>
          <p className="mt-0.5 text-[13px] text-txtDim">
            Sifat gerakan {symbol.replace("USDT", "/USDT")} menurut detektor AI dan apa artinya untuk strategi Anda.
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

          <TimeframeStrip
            items={[
              { tf: "1h", data: ai1h.data, error: ai1h.error },
              { tf: "4h", data: ai4h.data, error: ai4h.error },
            ]}
          />

          <MarketSummary
            current={current}
            series={series}
            loading={regime.loading}
            symbol={symbol.replace("USDT", "/USDT")}
            timeframe={timeframe}
            gauges={
              <>
                <ProbabilityBars probs={regime.data?.current_probabilities} />
                <div className="mt-1 border-t border-edge pt-3 text-[11.5px] text-txtMuted">Pembanding klasik (bukan penentu label)</div>
                <ExponentGauge
                  label="Hurst (R/S)"
                  hint="Eksponen Hurst (metode R/S). Di atas batas atas = tren berlanjut, di bawah batas bawah = cenderung berbalik."
                  value={last?.hurst}
                  lower={hLo}
                  upper={hHi}
                  loading={classic.loading}
                />
                <ExponentGauge
                  label="DFA (α)"
                  hint="Detrended Fluctuation Analysis (α). Dibaca sama seperti Hurst. Estimator klasik tidak andal di data berderau (Fase 1), sehingga hanya ditampilkan sebagai pembanding."
                  value={last?.dfa_alpha}
                  lower={aLo}
                  upper={aHi}
                  loading={classic.loading}
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

          <CollapsiblePanel title="Tentang detektor" subtitle="Model AI yang menentukan kondisi pasar">
            <ParameterBar showTimeframe={false} />
            {detector && (
              <dl className="mt-3 grid gap-2 text-[12.5px] sm:grid-cols-2">
                <div className="rounded-lg bg-surface/70 px-3 py-2">
                  <dt className="text-txtMuted">Model</dt>
                  <dd className="mt-0.5 text-txt">{detector.name}</dd>
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
                  <dt className="text-txtMuted">Akurasi seimbang uji sintetis (S4, deret mirip kripto)</dt>
                  <dd className="mt-0.5 font-mono text-txt">
                    {detector.test_ba_synthetic?.S4 !== undefined ? detector.test_ba_synthetic.S4.toFixed(3) : "–"}
                    <span className="ml-2 font-sans text-txtMuted">estimator klasik terbaik 0,654</span>
                  </dd>
                </div>
              </dl>
            )}
            <p className="mt-3 text-[12px] leading-relaxed text-txtDim">
              Detektor menilai {detector?.window ?? 500} batang terakhir setiap {detector?.stride_bars ?? 4} batang. Kelas
              ditentukan oleh eksponen Hurst: di bawah {detector?.class_thresholds_h[0].toLocaleString("id-ID") ?? "0,47"}{" "}
              cenderung berbalik, di atas {detector?.class_thresholds_h[1].toLocaleString("id-ID") ?? "0,53"} cenderung
              berlanjut. Model tidak pernah melihat data BTC saat dilatih, sehingga seluruh riwayat di grafik adalah data luar
              sampel. Validitas ke depan diuji pada BTC 1H; pada 4H detektor dipakai apa adanya tanpa uji tambahan.
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

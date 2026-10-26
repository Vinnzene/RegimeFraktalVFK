"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import CandlestickChart from "@/components/CandlestickChart";
import RegimeHistoryTable from "@/components/RegimeHistoryTable";
import RegimeLegend from "@/components/RegimeLegend";
import {
  bandStatus,
  Chip,
  formatDate,
  formatDuration,
  InfoCard,
  MetricCard,
  num,
  pct,
  pctConf,
  ProbabilityBars,
  runInfo,
  signed,
} from "@/components/RegimeOverview";
import { analyses, SOURCE_META, toCandles, type AnalysisResult } from "@/lib/analyses-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

/** Hasil satu analisis aset; memantau status sampai deteksi selesai. */

const LOOKBACK_POINTS = 30; // 30 titik deteksi = 120 bar

function Progress({ data }: { data: AnalysisResult | null }) {
  const p = Math.round((data?.progress ?? 0) * 100);
  return (
    <section className="rounded-xl border border-edge bg-panel p-6 shadow-panel">
      <div className="text-[14px] font-medium text-txt">
        {data?.status === "running" ? "Menjalankan detektor…" : "Menunggu giliran di antrean…"}
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface">
        <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${Math.max(5, p)}%` }} />
      </div>
      <p className="mt-2 text-[12px] text-txtMuted">Biasanya 10–60 detik, bergantung jumlah bar. Halaman ini diperbarui otomatis.</p>
    </section>
  );
}

function Result({ d }: { d: AnalysisResult }) {
  const series = d.series ?? [];
  const candles = useMemo(() => toCandles(d.candles), [d.candles]);
  const [showEvidence, setShowEvidence] = useState(false);
  const key = d.current_regime!;
  const low = Boolean(d.current_low_confidence);
  const shown: Regime = low ? "uncertain_lowconf" : key;
  const color = REGIME_META[shown].color;
  const conf = d.current_probabilities?.[key] ?? null;
  const tau = d.detector?.abstain_tau ?? 0.75;
  const band = d.random_band ?? null;
  const last = series[series.length - 1];
  const prev = series[Math.max(0, series.length - 1 - LOOKBACK_POINTS)];
  const rsStatus = bandStatus(last?.hurst, band?.hurst_rs);
  const dfaStatus = bandStatus(last?.dfa_alpha, band?.dfa_alpha);
  const outside = [rsStatus, dfaStatus].filter((s) => s?.outside).length;
  const run = runInfo(series);
  const priceChange = candles.length > 1 ? candles[candles.length - 1].close / candles[0].close - 1 : null;
  const composition = Object.entries(d.distribution ?? {}).sort((a, b) => b[1].share - a[1].share);
  const muted = "rgb(var(--c-txt-muted))";

  const classicCard = (title: string, value: number | undefined, before: number | undefined, status: ReturnType<typeof bandStatus>, hint: string) => (
    <MetricCard
      title={title}
      value={value !== undefined ? num(value) : "–"}
      status={status?.label ?? null}
      statusColor={status ? REGIME_META[status.tone].color : muted}
      foot={value !== undefined && before !== undefined ? `${signed(value - before)} vs ${LOOKBACK_POINTS * 4} bar lalu` : null}
      hint={hint}
    />
  );

  return (
    <>
      <section className="rounded-xl border border-edge bg-panel p-4 shadow-panel sm:p-5" aria-label="Kondisi aset saat ini">
        <div className="grid gap-4 xl:grid-cols-[minmax(260px,0.9fr)_2fr]">
          <div className="flex flex-col justify-center">
            <div className="text-[11px] font-medium uppercase tracking-wider text-txtDim">Kondisi pasar · {d.timeframe.toUpperCase()}</div>
            <h2 className="mt-1 text-[30px] font-bold uppercase leading-tight tracking-tight" style={{ color }}>
              {REGIME_PLAIN[shown].name}
            </h2>
            <p className="mt-1 text-[13.5px] text-txtDim">{REGIME_PLAIN[shown].summary}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {conf !== null && (
                <Chip color={low ? REGIME_META.uncertain_lowconf.color : undefined}>
                  Keyakinan {pctConf(conf, tau)}
                  {low ? " · rendah" : ""}
                </Chip>
              )}
              {band && <Chip>{outside} dari 2 di luar pita acak</Chip>}
              {priceChange !== null && (
                <Chip>
                  Harga {priceChange >= 0 ? "naik" : "turun"} {Math.abs(priceChange * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 })}% · seluruh data
                </Chip>
              )}
              {d.experimental && <Chip color={REGIME_META.anti_persistent.color}>Eksperimental</Chip>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
            <MetricCard
              title={`DETEKTOR AI ${d.timeframe.toUpperCase()}`}
              value={conf !== null ? pctConf(conf, tau) : "–"}
              status={`${REGIME_PLAIN[key].name}${low ? " · ragu" : ""}`}
              statusColor={color}
              foot={run ? `sejak ${formatDate(run.since)}` : null}
              hint={`Keyakinan kelas teratas. Di bawah ${pct(tau)} label dianggap ragu.`}
            />
            {classicCard(`HURST R/S · ${band?.window ?? 500}`, last?.hurst, prev?.hurst, rsStatus, "Pembanding klasik, dibaca terhadap pita acak.")}
            {classicCard(`DFA α · ${band?.window ?? 500}`, last?.dfa_alpha, prev?.dfa_alpha, dfaStatus, "Pembanding klasik, dibaca terhadap pita acak.")}
            <MetricCard
              title="TITIK DETEKSI"
              value={series.length.toLocaleString("id-ID")}
              status={`${pct(d.low_confidence_share ?? 0)} ragu`}
              statusColor={muted}
              foot={`tiap ${d.detector?.stride_bars ?? 4} bar`}
              hint="Jumlah jendela yang dinilai detektor pada data ini."
            />
          </div>
        </div>

        <div className="mt-3 grid gap-2.5 md:grid-cols-3">
          <InfoCard title="Berlangsung sejak">
            <div className="mt-1 text-[18px] font-semibold text-txt">{run ? formatDate(run.since) : "–"}</div>
            <div className="text-[12px] text-txtMuted">{run ? `± ${formatDuration(run.last - run.since)}` : ""}</div>
          </InfoCard>
          <InfoCard title="Pergantian kondisi">
            <div className="mt-1 text-[18px] font-semibold text-txt">{run ? `${run.switches}×` : "–"}</div>
            <div className="text-[12px] text-txtMuted">dalam 30 hari terakhir data</div>
          </InfoCard>
          <InfoCard title="Komposisi seluruh data">
            <div className="mt-1 flex flex-wrap justify-center gap-x-3 gap-y-0.5 text-[13px]">
              {composition.map(([k, v]) => (
                <span key={k} className="flex items-center gap-1 text-txtDim">
                  <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: REGIME_META[k as Regime]?.color }} />
                  {REGIME_PLAIN[k as Regime]?.name ?? k} <b className="font-mono text-txt">{pct(v.share)}</b>
                </span>
              ))}
            </div>
          </InfoCard>
        </div>

        <div className="mt-4 border-t border-edge pt-3">
          <p className="text-[13px] leading-relaxed text-txtDim">
            Detektor AI menilai {d.symbol} {d.timeframe.toUpperCase()} {REGIME_PLAIN[key].name.toLowerCase()}
            {conf !== null ? ` dengan keyakinan ${pctConf(conf, tau)}` : ""}
            {low ? `, di bawah batas ${pct(tau)} sehingga diperlakukan sebagai tidak pasti` : ""}.{" "}
            {band &&
              (outside === 0
                ? "Estimator klasik R/S dan DFA sama-sama berada di dalam pita acak."
                : `${outside} dari 2 estimator klasik berada di luar pita acak.`)}{" "}
            Kondisi menggambarkan sifat gerakan, bukan arah harga.
          </p>
          <button
            type="button"
            onClick={() => setShowEvidence((v) => !v)}
            aria-expanded={showEvidence}
            className="mt-1.5 flex items-center gap-1 text-[12.5px] font-medium text-txt hover:text-accent"
          >
            <span className={`text-[10px] transition-transform ${showEvidence ? "rotate-90" : ""}`} aria-hidden>
              ▸
            </span>
            {showEvidence ? "Sembunyikan bukti" : "Tunjukkan bukti"}
          </button>
          {showEvidence && (
            <div className="mt-3 grid gap-5 text-[12.5px] leading-relaxed text-txtDim lg:grid-cols-3">
              <ProbabilityBars title={`Probabilitas detektor · ${d.timeframe.toUpperCase()}`} data={d} />
              <div>
                <div className="mb-1.5 text-[12px] font-medium text-txt">Pita acak estimator klasik</div>
                {band ? (
                  <p>
                    Pada {band.window} bar deret tanpa memori, R/S terbaca {num(band.hurst_rs.lower)}–{num(band.hurst_rs.upper)} dan DFA{" "}
                    {num(band.dfa_alpha.lower)}–{num(band.dfa_alpha.upper)}. Nilai di dalam rentang ini tidak dapat dibedakan dari pasar acak.
                  </p>
                ) : (
                  <p>Pita acak belum tersedia.</p>
                )}
              </div>
              <div>
                <div className="mb-1.5 text-[12px] font-medium text-txt">Batas validitas</div>
                <p>
                  Detektor diuji pada data sintetis berkebenaran dasar dan divalidasi pada {d.detector?.validated_on ?? "BTC/USDT 1H"}.
                  {d.experimental
                    ? " Untuk aset dan timeframe ini belum ada validasi khusus; pada uji 19 aset lain kriteria generalisasi belum terpenuhi."
                    : ""}
                </p>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="rounded-xl border border-edge bg-panel p-4 shadow-panel">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <h2 className="text-[16px] font-semibold text-txt">Harga dengan pita kondisi pasar</h2>
            <span className="text-[12px] text-txtMuted">Warna latar = kondisi saat itu · gulir untuk zoom</span>
          </div>
          <CandlestickChart
            candles={candles}
            regimes={series}
            height={460}
            symbol={d.symbol}
            timeframe={d.timeframe}
            defaultRange="ALL"
            legend={<RegimeLegend compact />}
          />
        </div>
        <RegimeHistoryTable series={series} tau={tau} timeframe={d.timeframe} />
      </section>
    </>
  );
}

export default function AnalisisDetailPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const d = await analyses.get(params.id);
        if (stop) return;
        setData(d);
        if (d.status === "queued" || d.status === "running") timer = setTimeout(tick, 2000);
      } catch (e: any) {
        if (!stop) setError(e.message);
      }
    };
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [params.id]);

  const statusLabel = { queued: "Mengantre", running: "Diproses", done: "Selesai", failed: "Gagal" }[data?.status ?? "queued"];

  return (
    <div className="mx-auto max-w-[1560px] space-y-4 px-1 pb-8 sm:px-4">
      <header className="flex flex-wrap items-end justify-between gap-3 pt-2">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="font-mono text-[26px] font-bold tracking-tight text-txt">{data?.symbol ?? "Analisis"}</h1>
            <span className="rounded-md border border-edge bg-panel px-2 py-0.5 text-[12px] font-medium text-txt">{statusLabel}</span>
            {data && (
              <span className="rounded-md bg-surface px-2 py-0.5 text-[12px] font-medium text-txtDim">
                {SOURCE_META[data.source]?.label ?? data.source} · {data.timeframe.toUpperCase()}
              </span>
            )}
          </div>
          {data?.status === "done" && data.first_time && data.last_time && (
            <p className="mt-1 text-[13px] text-txtMuted">
              {data.n_bars?.toLocaleString("id-ID")} bar, {formatDate(data.first_time)} – {formatDate(data.last_time)} · diproses dalam{" "}
              {data.processing_seconds?.toLocaleString("id-ID")} detik
            </p>
          )}
        </div>
        <Link href="/analisis" className="rounded-lg border border-edge bg-panel px-4 py-2 text-[13px] font-medium text-txt hover:bg-surface">
          ← Analisis lain
        </Link>
      </header>

      {error && <div className="rounded-xl border border-bearish/30 bg-bearish/5 px-4 py-3 text-[13px] text-bearish">{error}</div>}
      {!error && data?.status === "failed" && (
        <div className="rounded-xl border border-bearish/30 bg-bearish/5 px-4 py-3 text-[13px] text-bearish">Analisis gagal: {data.error}</div>
      )}
      {!error && data?.experimental && data.status === "done" && (
        <p className="rounded-xl border border-warn/40 bg-warn/10 px-4 py-2.5 text-[12.5px] text-txtDim">
          <b className="text-txt">Eksperimental.</b> Detektor divalidasi pada BTC/USDT 1H; untuk {data.symbol} {data.timeframe.toUpperCase()} hasil ini
          belum divalidasi khusus.
        </p>
      )}
      {!error && (!data || data.status === "queued" || data.status === "running") && <Progress data={data} />}
      {!error && data?.status === "done" && <Result d={data} />}
    </div>
  );
}

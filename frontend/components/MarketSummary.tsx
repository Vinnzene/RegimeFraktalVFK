"use client";

import Link from "next/link";
import { useMemo } from "react";
import type { RegimePoint } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";
import { STRATEGY_PLAN, VERDICT_META } from "@/lib/strategy";

const DAY = 24 * 3600;

function formatDuration(seconds: number): string {
  const days = Math.floor(seconds / DAY);
  const hours = Math.round((seconds % DAY) / 3600);
  if (days >= 1) return hours ? `${days} hari ${hours} jam` : `${days} hari`;
  return `${Math.max(1, hours)} jam`;
}

function formatDate(t: number): string {
  return new Date(t * 1000).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

/** Statistik 30 hari terakhir dari deret regime, dipakai kartu hero dan kartu komposisi. */
export function useRecentRegimes(series: RegimePoint[]) {
  return useMemo(() => {
    if (!series.length) return null;
    const last = series[series.length - 1];
    let i = series.length - 1;
    while (i > 0 && series[i - 1].regime === last.regime) i--;
    const cutoff = last.time - 30 * DAY;
    const recent = series.filter((p) => p.time >= cutoff);
    const counts: Record<string, number> = {};
    recent.forEach((p) => (counts[p.regime] = (counts[p.regime] ?? 0) + 1));
    let switches = 0;
    for (let k = 1; k < recent.length; k++) if (recent[k].regime !== recent[k - 1].regime) switches++;
    return {
      since: series[i].time,
      lastTime: last.time,
      switches,
      recentShare: Object.entries(counts)
        .map(([key, v]) => ({ key, share: v / recent.length }))
        .sort((a, b) => b.share - a.share),
    };
  }, [series]);
}

/**
 * Kartu pertama yang dibaca: kondisi pasar sekarang menurut detektor AI, apa
 * artinya bagi pengguna (strategi beserta bukti Fase 2), dan keyakinan model.
 */
export default function MarketSummary({
  current,
  series,
  loading,
  symbol,
  timeframe,
  gauges,
  gaugesTitle = "Keyakinan detektor",
}: {
  current: string | null | undefined;
  series: RegimePoint[];
  loading: boolean;
  symbol: string;
  timeframe: string;
  gauges: React.ReactNode;
  gaugesTitle?: string;
}) {
  const info = useRecentRegimes(series);

  if (loading) {
    return (
      <div className="rounded-xl border border-edge bg-panel p-5">
        <div className="text-[13px] text-txtDim">Sedang menganalisis kondisi pasar…</div>
        <div className="mt-3 h-10 w-72 animate-pulse rounded bg-surface" />
      </div>
    );
  }

  const key = (current ?? "") as Regime;
  const plain = REGIME_PLAIN[key];
  const plan = STRATEGY_PLAN[key];
  const verdict = plan ? VERDICT_META[plan.verdict] : null;
  const color = REGIME_META[key]?.color ?? "#8b949e";

  if (!plain || !plan) {
    return <div className="rounded-xl border border-edge bg-panel p-5 text-[13px] text-txtDim">Kondisi pasar belum tersedia.</div>;
  }

  return (
    <section
      className="relative overflow-hidden rounded-xl border border-edge bg-panel"
      aria-label="Kondisi pasar saat ini"
    >
      <div className="pointer-events-none absolute -left-24 -top-24 h-64 w-64 rounded-full blur-3xl" style={{ background: `${color}22` }} />
      <div className="relative grid gap-px bg-edge lg:grid-cols-[1.15fr_1fr_300px]">
        {/* 1. Kondisi sekarang */}
        <div className="bg-panel p-5">
          <div className="flex items-center gap-2 text-[12px] text-txtDim">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 motion-reduce:hidden" style={{ background: color }} />
              <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: color }} />
            </span>
            Kondisi {symbol} saat ini · {timeframe.toUpperCase()}
          </div>
          <div className="mt-3 flex items-center gap-3">
            <span
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-2xl font-bold"
              style={{ backgroundColor: `${color}1f`, color, boxShadow: `inset 0 0 0 1px ${color}55` }}
              aria-hidden
            >
              {plain.icon}
            </span>
            <div className="min-w-0">
              <h2 className="text-[28px] font-semibold leading-none tracking-tight" style={{ color }}>
                {plain.name}
              </h2>
              <p className="mt-1.5 text-[13.5px] text-txt">{plain.summary}</p>
            </div>
          </div>
          <p className="mt-4 max-w-prose text-[13px] leading-relaxed text-txtDim">{plain.meaning}</p>
          {info && (
            <dl className="mt-4 grid grid-cols-2 gap-2 text-[12px]">
              <div className="rounded-lg bg-surface/70 px-3 py-2">
                <dt className="text-txtMuted">Berlangsung sejak</dt>
                <dd className="mt-0.5 font-medium text-txt">
                  {formatDate(info.since)} <span className="font-normal text-txtDim">(± {formatDuration(info.lastTime - info.since)})</span>
                </dd>
              </div>
              <div className="rounded-lg bg-surface/70 px-3 py-2">
                <dt className="text-txtMuted">Pergantian kondisi</dt>
                <dd className="mt-0.5 font-medium text-txt">
                  {info.switches}× <span className="font-normal text-txtDim">dalam 30 hari</span>
                </dd>
              </div>
            </dl>
          )}
        </div>

        {/* 2. Apa artinya */}
        <div className="flex flex-col bg-panel p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[12px] text-txtDim">Apa artinya untuk Anda?</span>
            {verdict && (
              <span className={`rounded-full border px-2 py-0.5 text-2xs font-medium ${verdict.className}`}>{verdict.label}</span>
            )}
          </div>
          <div className="mt-3 text-[11px] uppercase tracking-wider text-txtMuted">Strategi yang cocok</div>
          <div className={`mt-1 text-[22px] font-semibold tracking-tight ${plan.tone === "go" ? "text-txt" : "text-txtDim"}`}>
            {plan.strategy}
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-txtDim">{plan.action}</p>
          <p className="mt-3 rounded-lg bg-surface/70 px-3 py-2 text-[12px] leading-relaxed text-txtDim">
            <span className="font-medium text-txt">Bukti BTC 1H: </span>
            {plan.evidence}
          </p>
          <div className="mt-auto pt-4">
            <Link
              href="/strategi"
              className="inline-flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent/10 px-3 py-2 text-[12.5px] font-medium text-accent transition hover:bg-accent/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            >
              Lihat peta strategi lengkap <span aria-hidden>→</span>
            </Link>
          </div>
        </div>

        {/* 3. Alat ukur */}
        <div className="flex flex-col gap-3 bg-panel p-5">
          <span className="text-[12px] text-txtDim">{gaugesTitle}</span>
          {gauges}
        </div>
      </div>
      <p className="relative border-t border-edge px-5 py-2.5 text-[11px] leading-relaxed text-txtMuted">
        Kondisi menggambarkan <b className="text-txtDim">sifat gerakan</b>, bukan arah: &ldquo;Tren Berlanjut&rdquo; bisa naik
        terus atau turun terus. Bukan saran jual/beli.
      </p>
    </section>
  );
}

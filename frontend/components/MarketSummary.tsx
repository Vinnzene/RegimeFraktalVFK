"use client";

import { useMemo } from "react";
import type { RegimePoint } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

const DAY = 24 * 3600;

function formatDuration(seconds: number): string {
  const days = Math.floor(seconds / DAY);
  const hours = Math.round((seconds % DAY) / 3600);
  if (days >= 1) return hours ? `${days} hari ${hours} jam` : `${days} hari`;
  return `${Math.max(1, hours)} jam`;
}

function formatDate(t: number): string {
  return new Date(t * 1000).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * Ringkasan kondisi pasar dalam bahasa awam.
 *
 * Kartu utama yang dibaca pertama kali: nama kondisi, artinya, analogi, sejak
 * kapan berlangsung, dan komposisi 30 hari terakhir.
 */
export default function MarketSummary({
  current,
  series,
  loading,
}: {
  current: string | null | undefined;
  series: RegimePoint[];
  loading: boolean;
}) {
  const info = useMemo(() => {
    if (!series.length) return null;
    const last = series[series.length - 1];
    let i = series.length - 1;
    while (i > 0 && series[i - 1].regime === last.regime) i--;
    const since = series[i].time;

    const cutoff = last.time - 30 * DAY;
    const recent = series.filter((p) => p.time >= cutoff);
    const counts: Record<string, number> = {};
    recent.forEach((p) => (counts[p.regime] = (counts[p.regime] ?? 0) + 1));
    const recentShare = Object.entries(counts)
      .map(([k, v]) => ({ key: k, share: v / recent.length }))
      .sort((a, b) => b.share - a.share);

    let switches = 0;
    for (let k = 1; k < recent.length; k++) {
      if (recent[k].regime !== recent[k - 1].regime) switches++;
    }

    return { since, lastTime: last.time, recentShare, switches };
  }, [series]);

  if (loading) {
    return (
      <div className="rounded-md border border-edge bg-panel p-4">
        <div className="text-[13px] text-txtDim">Sedang menganalisis kondisi pasar…</div>
        <div className="mt-3 h-8 w-64 animate-pulse rounded bg-surface" />
      </div>
    );
  }

  const key = (current ?? "") as Regime;
  const plain = REGIME_PLAIN[key];
  const color = REGIME_META[key]?.color ?? "#8b949e";

  if (!plain) {
    return (
      <div className="rounded-md border border-edge bg-panel p-4 text-[13px] text-txtDim">
        Kondisi pasar belum tersedia.
      </div>
    );
  }

  return (
    <div
      className="rounded-md border bg-panel p-4"
      style={{ borderColor: `${color}66`, boxShadow: `inset 4px 0 0 ${color}` }}
    >
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <div className="text-[12px] text-txtDim">Kondisi pasar BTC saat ini</div>
          <div className="mt-1 flex items-center gap-3">
            <span
              className="flex h-10 w-10 items-center justify-center rounded-full text-xl font-bold"
              style={{ backgroundColor: `${color}26`, color }}
              aria-hidden
            >
              {plain.icon}
            </span>
            <div>
              <div className="text-2xl font-semibold leading-tight" style={{ color }}>
                {plain.name}
              </div>
              <div className="text-[13px] text-txt">{plain.summary}</div>
            </div>
          </div>

          <p className="mt-3 text-[13px] leading-relaxed text-txtDim">{plain.meaning}</p>
          <p className="mt-1 text-[12px] italic leading-relaxed text-txtMuted">{plain.analogy}</p>

          {info && (
            <div className="mt-3 flex flex-wrap gap-2 text-[12px]">
              <span className="rounded bg-surface px-2 py-1 text-txtDim">
                Berlangsung sejak <span className="text-txt">{formatDate(info.since)}</span>{" "}
                (± {formatDuration(info.lastTime - info.since)})
              </span>
              <span className="rounded bg-surface px-2 py-1 text-txtDim">
                Berganti kondisi <span className="text-txt">{info.switches}×</span> dalam 30 hari
              </span>
            </div>
          )}
        </div>

        {info && (
          <div className="rounded border border-edge bg-surface/40 p-3">
            <div className="text-[12px] font-medium text-txt">Komposisi 30 hari terakhir</div>
            <div className="mt-2 flex h-3 overflow-hidden rounded">
              {info.recentShare.map((r) => (
                <div
                  key={r.key}
                  style={{
                    width: `${r.share * 100}%`,
                    backgroundColor: REGIME_META[r.key as Regime]?.color ?? "#334155",
                  }}
                  title={`${REGIME_PLAIN[r.key as Regime]?.name ?? r.key}: ${(r.share * 100).toFixed(0)}%`}
                />
              ))}
            </div>
            <div className="mt-2 space-y-1">
              {info.recentShare.map((r) => (
                <div key={r.key} className="flex items-center gap-2 text-[12px]">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-sm"
                    style={{ backgroundColor: REGIME_META[r.key as Regime]?.color ?? "#334155" }}
                  />
                  <span className="flex-1 text-txtDim">
                    {REGIME_PLAIN[r.key as Regime]?.name ?? r.key}
                  </span>
                  <span className="font-mono text-txt">{(r.share * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <p className="mt-3 border-t border-edge pt-2 text-[11px] leading-relaxed text-txtMuted">
        Kondisi ini menggambarkan <b>sifat gerakan</b> harga, bukan arah. &ldquo;Tren
        Berlanjut&rdquo; bisa berarti naik terus atau turun terus. Informasi ini bukan saran
        jual/beli.
      </p>
    </div>
  );
}

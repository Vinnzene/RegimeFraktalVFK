"use client";

import { useMemo } from "react";
import type { AiRegimePoint } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

/**
 * Riwayat kondisi terbaru sebagai daftar periode: kapan mulai, berapa lama,
 * dan seberapa yakin detektor rata-rata selama periode itu. Titik deteksi
 * berurutan dengan label sama digabung menjadi satu periode. Label sama
 * dengan pita grafik; periode dengan keyakinan rata-rata di bawah ambang
 * ditandai "ragu".
 */

const TF_SECONDS: Record<string, number> = { "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400 };

type Segment = { regime: Regime; start: number; end: number; meanConf: number; n: number };

function segments(series: AiRegimePoint[]): Segment[] {
  const out: Segment[] = [];
  for (const p of series) {
    const regime = p.regime as Regime;
    const cur = out[out.length - 1];
    if (cur && cur.regime === regime) {
      cur.end = p.time;
      cur.meanConf += (p.confidence - cur.meanConf) / (cur.n + 1);
      cur.n += 1;
    } else {
      out.push({ regime, start: p.time, end: p.time, meanConf: p.confidence, n: 1 });
    }
  }
  return out;
}

function duration(seconds: number) {
  const h = Math.max(1, Math.round(seconds / 3600));
  if (h < 48) return `${h} jam`;
  return `${Math.round(h / 24)} hari`;
}

export default function RegimeHistoryTable({
  series,
  tau,
  timeframe,
  rows = 12,
}: {
  series: AiRegimePoint[];
  tau: number;
  timeframe: string;
  rows?: number;
}) {
  const recent = useMemo(() => segments(series).slice(-rows).reverse(), [series, rows]);
  // Satu titik deteksi mewakili 4 bar; durasi periode ditambah satu langkah itu.
  const stride = 4 * (TF_SECONDS[timeframe] ?? 3600);

  return (
    <section className="flex h-full flex-col rounded-xl border border-edge bg-panel shadow-panel">
      <div className="px-4 pb-2 pt-4">
        <h2 className="text-[16px] font-semibold text-txt">Riwayat kondisi</h2>
        <p className="mt-0.5 text-[12px] text-txtMuted">
          Periode terbaru {timeframe.toUpperCase()}, terbaru di atas. Arahkan kursor ke judul kolom untuk penjelasan.
        </p>
      </div>
      {recent.length === 0 ? (
        <div className="px-4 pb-4 text-[12.5px] text-txtMuted">Memuat…</div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <table className="w-full text-[12.5px]">
            <thead className="sticky top-0 bg-surface/80 backdrop-blur">
              <tr className="text-left text-[11.5px] text-txtDim">
                <th className="py-2 pl-4 font-medium" title="Tanggal titik deteksi pertama periode ini">Mulai</th>
                <th className="py-2 font-medium" title="Kondisi menurut detektor AI, sama dengan pita grafik; 'ragu' bila keyakinan rata-rata di bawah ambang">Kondisi</th>
                <th className="py-2 font-medium" title="Lama periode berlangsung">Lama</th>
                <th className="py-2 pr-4 text-right font-medium" title="Rata-rata keyakinan detektor selama periode">Keyakinan</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((s, i) => {
                const meta = REGIME_META[s.regime] ?? REGIME_META.uncertain_rule;
                return (
                  <tr key={s.start} className="border-t border-edge">
                    <td className="py-2 pl-4 font-mono text-[12px] text-txtDim">
                      {new Date(s.start * 1000).toLocaleDateString("id-ID", { day: "2-digit", month: "short" })}
                      {i === 0 && <span className="ml-1.5 rounded bg-accent/10 px-1 text-[10px] font-semibold text-accent">kini</span>}
                    </td>
                    <td className="py-2">
                      <span className="flex items-center gap-1.5 text-txt">
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: meta.color }} />
                        {REGIME_PLAIN[s.regime]?.name ?? s.regime}
                        {s.meanConf < tau && (
                          <span
                            className="rounded px-1 text-[10px] font-semibold text-uncertainLowconf"
                            style={{ backgroundColor: `${REGIME_META.uncertain_lowconf.color}1a` }}
                            title={`Keyakinan rata-rata di bawah ${Math.round(tau * 100)}%`}
                          >
                            ragu
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="py-2 text-txtDim">{duration(s.end - s.start + stride)}</td>
                    <td className="py-2 pr-4">
                      <div className="flex items-center justify-end gap-2">
                        <div className="hidden h-1.5 w-14 overflow-hidden rounded-full bg-surface sm:block">
                          <div className="h-full rounded-full bg-txtDim" style={{ width: `${s.meanConf * 100}%` }} />
                        </div>
                        <span className="w-8 text-right font-mono text-[12px] text-txtDim">{Math.round(s.meanConf * 100)}%</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

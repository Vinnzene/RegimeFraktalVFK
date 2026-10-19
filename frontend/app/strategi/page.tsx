"use client";

import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/PageHeader";
import ParameterBar from "@/components/ParameterBar";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api, type RegimePoint } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

/**
 * Regime → strategi.
 *
 * Menjawab pertanyaan pengguna "kondisi pasar sekarang cocok untuk strategi
 * apa?". Rekomendasi di sini adalah RANCANGAN yang akan diuji di Fase 2 pada
 * data BTC; buktinya saat ini baru simulasi sintetis, dan halaman menyatakan
 * itu terang-terangan.
 */

const MOM = REGIME_META.persistent.color;
const MR = REGIME_META.anti_persistent.color;

type Plan = { strategy: string; tool: string; action: string; tone: "go" | "wait" };

const PLAN: Record<Regime, Plan> = {
  persistent: {
    strategy: "Trend-following",
    tool: "Trend bot, breakout, MA crossover",
    action: "Ikuti arah gerakan. Masuk saat harga menembus level, keluar dengan trailing stop.",
    tone: "go",
  },
  anti_persistent: {
    strategy: "Mean-reversion",
    tool: "Grid bot, fade Bollinger/RSI",
    action: "Lawan gerakan ekstrem. Masuk di ujung range, ambil untung ke rata-rata, stop ketat.",
    tone: "go",
  },
  random_like: {
    strategy: "Tidak trading",
    tool: "Matikan bot atau posisi minimal",
    action: "Tidak ada pola yang bisa dimanfaatkan; biaya transaksi akan menggerus hasil.",
    tone: "wait",
  },
  uncertain_rule: {
    strategy: "Tunggu konfirmasi",
    tool: "Kurangi posisi",
    action: "Dua alat ukur tidak sepakat. Tunggu sampai kondisi terkonfirmasi beberapa window berturut-turut.",
    tone: "wait",
  },
  uncertain_lowconf: {
    strategy: "Tunggu konfirmasi",
    tool: "Kurangi posisi",
    action: "Model tidak cukup yakin. Tunggu sampai kondisi terkonfirmasi.",
    tone: "wait",
  },
};

const MAP_ROWS: { label: string; cells: [string, string, string] }[] = [
  { label: "Strategi", cells: ["Trend-following, breakout", "Mean-reversion, fade ekstrem", "Tidak trading / posisi minimal"] },
  { label: "Contoh alat", cells: ["Trend bot, MA crossover", "Grid bot, Bollinger/RSI", "Bot dimatikan"] },
  { label: "Entry", cells: ["Saat harga menembus level", "Saat harga di ujung range", "–"] },
  { label: "Take profit", cells: ["Trailing stop", "Target tetap ke rata-rata", "–"] },
  { label: "Stop loss", cells: ["Lebih lebar", "Ketat; gagal berbalik = regime keliru", "–"] },
  { label: "Lama posisi", cells: ["Lebih panjang", "Pendek", "–"] },
  { label: "Ukuran posisi", cells: ["Sebanding keyakinan", "Sebanding keyakinan", "Kecil atau nol"] },
];

function formatDate(t: number) {
  return new Date(t * 1000).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

function formatSpan(seconds: number) {
  const h = Math.round(seconds / 3600);
  return h >= 48 ? `${Math.round(h / 24)} hari` : `${h} jam`;
}

function currentRun(series: RegimePoint[]) {
  if (!series.length) return null;
  const last = series[series.length - 1];
  let i = series.length - 1;
  while (i > 0 && series[i - 1].regime === last.regime) i--;
  return { since: series[i].time, last: last.time };
}

/* ------------------------------------------------------------ simulasi */

type Band = { p25: number[]; median: number[]; p75: number[] };
type StratResult = { median_total_return: number; share_profitable: number; equity: Band };
type Demo = {
  design: { equity_step: number; cost_per_side: number; n_paths: number; n_bars: number };
  results: Record<string, { lag1_autocorr: number; momentum: StratResult; mean_reversion: StratResult }>;
};

const pct = (v: number) => `${v >= 0 ? "+" : "−"}${Math.abs(Math.round(v * 100))}%`;

function EquityPanel({ title, h, r, step, yTicks }: {
  title: string; h: string; r: Demo["results"][string]; step: number; yTicks: number[];
}) {
  const W = 300, H = 170, P = { l: 34, r: 46, t: 8, b: 22 };
  const all = [...r.momentum.equity.p25, ...r.momentum.equity.p75, ...r.mean_reversion.equity.p25, ...r.mean_reversion.equity.p75, ...yTicks];
  const lo = Math.log(Math.min(...all) * 0.97), hi = Math.log(Math.max(...all) * 1.03);
  const n = r.momentum.equity.median.length;
  const x = (i: number) => P.l + (i / (n - 1)) * (W - P.l - P.r);
  const y = (v: number) => P.t + (1 - (Math.log(v) - lo) / (hi - lo)) * (H - P.t - P.b);
  const line = (a: number[]) => a.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const band = (b: Band) =>
    "M" + b.p75.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("L") + "L" +
    b.p25.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).reverse().join("L") + "Z";
  const ends = [
    { v: r.momentum.equity.median[n - 1], text: pct(r.momentum.median_total_return), color: MOM },
    { v: r.mean_reversion.equity.median[n - 1], text: pct(r.mean_reversion.median_total_return), color: MR },
  ].map((e) => ({ ...e, yy: y(e.v) }));
  if (Math.abs(ends[0].yy - ends[1].yy) < 12) {
    const mid = (ends[0].yy + ends[1].yy) / 2, s = ends[0].yy <= ends[1].yy ? -1 : 1;
    ends[0].yy = mid + s * 6; ends[1].yy = mid - s * 6;
  }
  const days = ((n - 1) * step) / 24;

  return (
    <div className="stat-card min-w-0">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[12.5px] font-medium text-txt">{title}</span>
        <span className="font-mono text-2xs text-txtMuted">H = {h.replace(".", ",")}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-1 h-auto w-full" role="img"
        aria-label={`${title}: momentum ${ends[0].text}, mean-reversion ${ends[1].text}`}>
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} stroke={t === 1 ? "#5c6673" : "#252c37"} strokeDasharray={t === 1 ? "4 3" : undefined} />
            <text x={P.l - 5} y={y(t) + 3.5} textAnchor="end" fontSize="9.5" fill="#8b949e" fontFamily="ui-monospace, monospace">
              {t.toLocaleString("id-ID")}
            </text>
          </g>
        ))}
        {[0, 20, 40, 60, 80].filter((d) => d <= days).map((d) => (
          <text key={d} x={x((d * 24) / step)} y={H - 6} textAnchor="middle" fontSize="9.5" fill="#8b949e" fontFamily="ui-monospace, monospace">
            {d === 80 ? "80 hr" : d}
          </text>
        ))}
        <path d={band(r.momentum.equity)} fill={MOM} fillOpacity={0.13} />
        <path d={band(r.mean_reversion.equity)} fill={MR} fillOpacity={0.13} />
        <path d={line(r.momentum.equity.median)} fill="none" stroke={MOM} strokeWidth={2} />
        <path d={line(r.mean_reversion.equity.median)} fill="none" stroke={MR} strokeWidth={2} />
        {ends.map((e) => (
          <g key={e.color}>
            <circle cx={x(n - 1)} cy={y(e.v)} r={3.2} fill={e.color} stroke="#1b222b" strokeWidth={2} />
            <text x={W - P.r + 6} y={e.yy + 3.5} fontSize="10.5" fontWeight={600} fill="#eaecef" fontFamily="ui-monospace, monospace">
              {e.text}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function SimulationEvidence() {
  const [demo, setDemo] = useState<Demo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/regime_strategy_demo.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setDemo)
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  if (error) return <ApiState loading={false} error={`Data simulasi gagal dimuat (${error}).`} />;
  if (!demo) return <ApiState loading error={null} />;

  const step = demo.design.equity_step;
  const rows: { title: string; note: string; keys: [string, string][]; ticks: number[] }[] = [
    {
      title: "Mekanisme",
      note: "Autokorelasi lag-1 sekitar ±0,14, jauh lebih kuat dari BTC. Besarnya hasil dilebih-lebihkan.",
      keys: [["0.40", "Anti-persistent"], ["0.50", "Acak"], ["0.60", "Persistent"]],
      ticks: [0.25, 0.5, 1, 2],
    },
    {
      title: "Setara BTC",
      note: "Autokorelasi lag-1 sekitar ±0,03, sebanding dengan BTC 1H (−0,03).",
      keys: [["0.48", "Agak anti-persistent"], ["0.50", "Acak"], ["0.52", "Agak persistent"]],
      ticks: [0.5, 0.75, 1],
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11.5px] text-txtDim">
        <span className="flex items-center gap-1.5"><span className="h-[3px] w-4 rounded" style={{ background: MOM }} />Momentum</span>
        <span className="flex items-center gap-1.5"><span className="h-[3px] w-4 rounded" style={{ background: MR }} />Mean-reversion</span>
        <span className="text-txtMuted">Garis = median ekuitas {demo.design.n_paths} jalur · pita = kuartil 25–75% · skala log · garis putus = modal awal</span>
      </div>
      {rows.map((row) => (
        <div key={row.title} className="space-y-1.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4">
            <span className="text-[12.5px] font-semibold text-txt">{row.title}</span>
            <span className="text-2xs text-txtMuted">{row.note}</span>
          </div>
          <div className="grid gap-2 md:grid-cols-3">
            {row.keys.map(([k, title]) => (
              <EquityPanel key={k} title={title} h={k} r={demo.results[k]} step={step} yTicks={row.ticks} />
            ))}
          </div>
        </div>
      ))}
      <p className="text-[12px] leading-relaxed text-txtDim">
        Di kondisi setara BTC kedua strategi rugi setelah biaya ({(demo.design.cost_per_side * 100).toLocaleString("id-ID")}% per sisi),
        tetapi strategi yang salah regime ruginya beberapa kali lebih besar. Nilai praktis identifikasi regime yang paling
        jujur adalah <b className="text-txt">mengetahui strategi mana yang jangan dijalankan</b>.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------ halaman */

export default function StrategiPage() {
  const { timeframe } = useAppConfig();
  const regime = useApi(() => api.regime(timeframe), [timeframe]);

  const current = (regime.data?.current_regime ?? null) as Regime | null;
  const run = useMemo(() => currentRun(regime.data?.series ?? []), [regime.data]);
  const plan = current ? PLAN[current] : null;

  return (
    <div className="mx-auto max-w-[1400px] space-y-3">
      <PageHeader
        title="Regime → Strategi"
        description="Kondisi pasar menentukan strategi yang cocok: trend-following saat gerakan cenderung berlanjut, mean-reversion saat cenderung berbalik, dan tidak trading saat acak. Peta di halaman ini adalah rancangan yang akan diuji pada data BTC (Fase 2) dengan biaya transaksi nyata dan evaluasi walk-forward. Bukti yang tersedia sekarang baru simulasi pada data sintetis."
      />
      <ParameterBar />
      <ApiState loading={regime.loading} error={regime.error} />

      {current && plan && (
        <section className="panel grid gap-5 lg:grid-cols-[1fr_1.2fr]" style={{ borderLeft: `3px solid ${REGIME_META[current].color}` }}>
          <div className="space-y-2">
            <div className="metric-label">Kondisi pasar saat ini · {timeframe.toUpperCase()}</div>
            <div className="text-[24px] font-semibold tracking-tight" style={{ color: REGIME_META[current].color }}>
              {REGIME_PLAIN[current].name}
            </div>
            <p className="text-[13px] text-txtDim">{REGIME_PLAIN[current].summary}</p>
            {run && (
              <div className="flex flex-wrap gap-2 pt-1">
                <span className="chip">sejak {formatDate(run.since)}</span>
                <span className="chip">± {formatSpan(run.last - run.since)}</span>
              </div>
            )}
          </div>

          <div className="space-y-2 rounded-md border border-edge bg-surface/60 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="metric-label">Strategi yang cocok</div>
              <span className="rounded-full border border-warn/40 bg-warn/10 px-2 py-0.5 text-2xs font-medium text-warn">
                Rancangan · belum teruji di BTC
              </span>
            </div>
            <div className={`text-[20px] font-semibold tracking-tight ${plan.tone === "go" ? "text-txt" : "text-txtDim"}`}>
              {plan.strategy}
            </div>
            <p className="text-[13px] leading-relaxed text-txtDim">{plan.action}</p>
            <div className="text-[12px] text-txtMuted">
              Contoh alat: <span className="text-txtDim">{plan.tool}</span>
            </div>
          </div>
        </section>
      )}

      <section className="panel space-y-3">
        <div>
          <div className="panel-title">Peta keputusan</div>
          <div className="panel-sub">
            Regime tidak hanya memilih strategi, tetapi juga cara menjalankannya. Window 500 bar di 1H ≈ 3 minggu, sehingga
            horizon yang cocok intraday sampai swing.
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table min-w-[640px] font-sans">
            <thead>
              <tr>
                <th className="w-32 text-left" />
                {(["persistent", "anti_persistent", "random_like"] as Regime[]).map((k) => (
                  <th key={k} className="text-left">
                    <span className="mr-1.5 inline-block h-2 w-2 rounded-sm" style={{ background: REGIME_META[k].color }} />
                    {REGIME_PLAIN[k].name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MAP_ROWS.map((row) => (
                <tr key={row.label}>
                  <td className="py-2 font-sans text-txtMuted">{row.label}</td>
                  {row.cells.map((c, i) => (
                    <td key={i} className="py-2 text-left font-sans text-[12px] text-txtDim">{c}</td>
                  ))}
                </tr>
              ))}
              <tr>
                <td className="py-2 font-sans text-txtMuted">Saat transisi</td>
                <td colSpan={3} className="py-2 text-left font-sans text-[12px] text-txtDim">
                  Kurangi posisi sampai regime baru terkonfirmasi beberapa window berturut-turut.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel space-y-3">
        <div>
          <div className="panel-title">Bukti saat ini: simulasi pada data sintetis</div>
          <div className="panel-sub">
            Strategi yang sama dijalankan pada harga sintetis dengan eksponen Hurst yang diketahui. Data BTC sengaja belum
            dipakai agar uji Fase 2 tetap bersih.
          </div>
        </div>
        <SimulationEvidence />
      </section>
    </div>
  );
}

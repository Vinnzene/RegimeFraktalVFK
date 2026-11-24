"use client";

import Disclaimer from "@/components/Disclaimer";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import HurstDfaPanel from "@/components/HurstDfaPanel";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import RegimeLegend from "@/components/RegimeLegend";
import TransitionMatrix from "@/components/TransitionMatrix";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api, type RegimePoint } from "@/lib/api-client";
import { REGIME_META, regimeLabel, type Regime } from "@/lib/regime";

export default function RegimeExplorerPage() {
  const { timeframe, config } = useAppConfig();

  const regime = useApi(() => api.regime(timeframe), [timeframe]);
  const transition = useApi(() => api.transitionMatrix(timeframe), [timeframe]);
  const duration = useApi(() => api.regimeDuration(timeframe), [timeframe]);

  const loading = regime.loading || transition.loading || duration.loading;
  const error = regime.error ?? transition.error ?? duration.error;

  const distribution = regime.data?.distribution ?? {};
  const durationSummary = duration.data?.summary ?? {};

  const durationBars = Object.entries(durationSummary).map(([key, v]: any) => ({
    regime: regimeLabel(key),
    key,
    mean: v.mean,
    median: v.median,
    max: v.max,
    runs: v.n_runs,
  }));

  return (
    <div className="space-y-4">
      <PageHeader
        title="Regime Explorer"
        description="Karakterisasi persistensi lewat Hurst Exponent dan DFA α pada rolling window. Kategori Uncertain (rule) muncul saat kedua estimator tidak sepakat dan sengaja tidak dipaksa masuk salah satu dari tiga kategori."
      />
      <Disclaimer variant="classic" />

      <ParameterBar />
      <ApiState loading={loading} error={error} />

      {!loading && !error && (
        <>
          <Panel
            title="Hurst Exponent & DFA α"
            subtitle="Dihitung pada log-return. Pita abu-abu adalah zona Random-like."
            params={{
              input: config?.analysis.input ?? "-",
              L: config?.analysis.L ?? "-",
              stride: regime.data?.stride_bars ?? "-",
              jendela: regime.data?.original_count ?? 0,
            }}
          >
            <HurstDfaPanel
              series={regime.data?.series ?? []}
              hurstThreshold={(regime.data?.thresholds?.hurst ?? config?.analysis.hurst_threshold ?? [0.45, 0.55]) as [number, number]}
              dfaThreshold={(regime.data?.thresholds?.dfa ?? config?.analysis.dfa_threshold ?? [0.45, 0.55]) as [number, number]}
              showEr
            />
            {regime.data?.thresholds && (
              <p className="mt-2 text-2xs leading-relaxed text-txtMuted">
                Ambang kuantil 1/3–2/3 dari {regime.data.thresholds.source === "train_only" ? "partisi latih" : "seluruh riwayat"}:
                Hurst R/S {regime.data.thresholds.hurst.map((v) => v.toLocaleString("id-ID")).join("–")} (garis putus biru/oranye),
                DFA α {regime.data.thresholds.dfa.map((v) => v.toLocaleString("id-ID")).join("–")} (titik-titik kuning). Garis hijau =
                ER_q, skor kuantil Efficiency Ratio multiskala yang dipakai Trend-Aware Soft Consensus. Grafik dijarangkan menjadi{" "}
                {regime.data.series.length.toLocaleString("id-ID")} titik; statistik dihitung dari{" "}
                {regime.data.original_count.toLocaleString("id-ID")} jendela.
              </p>
            )}
            <p className="mt-2 text-2xs leading-relaxed text-txtMuted">
              Perhatikan titik di mana garis biru (Hurst) dan oranye (DFA α) berada di sisi
              berlawanan terhadap pita ambang — window seperti itulah yang dilabeli Uncertain
              (rule).
            </p>
          </Panel>

          <Panel
            title="Label per jendela"
            subtitle="Jendela terbaru, tanpa penjarangan. H, α, dan ER_q menentukan label lewat Trend-Aware Soft Consensus."
          >
            <WindowTable
              rows={[...(regime.data?.latest_windows ?? [])].reverse().slice(0, 12)}
              example={regime.data?.uncertain_example ?? null}
            />
          </Panel>

          <div className="grid gap-3 lg:grid-cols-2">
            <Panel
              title="Distribusi Regime"
              subtitle="Proporsi waktu tiap kategori sepanjang dataset"
            >
              <div className="space-y-2">
                {Object.entries(distribution).map(([key, val]: any) => (
                  <div key={key}>
                    <div className="flex justify-between text-[11px]">
                      <span className="text-txtDim">{regimeLabel(key)}</span>
                      <span className="font-mono text-txtDim">
                        {(val.share * 100).toFixed(1)}% · {val.count}
                      </span>
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
              <div className="mt-4 border-t border-edge pt-3">
                <RegimeLegend compact />
              </div>
            </Panel>

            <Panel
              title="Matriks Transisi"
              subtitle={`P(R_t+1 = j | R_t = i) — timeframe ${timeframe.toUpperCase()}`}
            >
              <TransitionMatrix
                categories={transition.data?.categories ?? []}
                matrix={transition.data?.matrix ?? []}
                counts={transition.data?.counts}
              />
              <p className="mt-2 text-2xs leading-relaxed text-txtMuted">
                Diagonal yang dominan menandakan regime cenderung bertahan dari satu jendela ke
                jendela berikutnya.
              </p>
            </Panel>
          </div>

          <Panel
            title="Durasi Regime"
            subtitle="Berapa lama tiap regime bertahan sebelum berpindah (satuan: window)"
          >
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={durationBars} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
                <CartesianGrid stroke="rgba(30,41,55,0.7)" />
                <XAxis dataKey="regime" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
                <Tooltip
                  contentStyle={{
                    background: "#0b1017",
                    border: "1px solid #1e2937",
                    fontSize: 11,
                    borderRadius: 6,
                  }}
                />
                <Bar dataKey="mean" name="Durasi rata-rata">
                  {durationBars.map((d) => (
                    <Cell key={d.key} fill={REGIME_META[d.key as Regime]?.color ?? "#334155"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1 text-left">Regime</th>
                    <th className="py-1 text-right">Jumlah run</th>
                    <th className="py-1 text-right">Rata-rata</th>
                    <th className="py-1 text-right">Median</th>
                    <th className="py-1 text-right">Maks</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-txtDim">
                  {durationBars.map((d) => (
                    <tr key={d.key} className="border-b border-edge/50">
                      <td className="py-1 font-sans" style={{ color: REGIME_META[d.key as Regime]?.color }}>
                        {d.regime}
                      </td>
                      <td className="py-1 text-right">{d.runs}</td>
                      <td className="py-1 text-right">{d.mean}</td>
                      <td className="py-1 text-right">{d.median}</td>
                      <td className="py-1 text-right">{d.max}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

function WindowTable({ rows, example }: { rows: RegimePoint[]; example: RegimePoint | null }) {
  const fmt = (v: number | null | undefined, d = 4) => (v == null ? "–" : v.toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const iso = (t: number) => new Date(t * 1000).toISOString().slice(0, 16).replace("T", " ");
  const all: (RegimePoint & { _example?: boolean })[] = [...rows];
  if (example && !rows.some((r) => r.time === example.time)) all.push({ ...example, _example: true });
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11.5px]">
        <thead className="text-txtMuted">
          <tr className="border-b border-edge">
            <th className="py-1 text-left">Bar terakhir (UTC)</th>
            <th className="py-1 text-right">Hurst R/S</th>
            <th className="py-1 text-right">DFA α</th>
            <th className="py-1 text-right">ER_q</th>
            <th className="py-1 pl-4 text-left">Label</th>
          </tr>
        </thead>
        <tbody className="font-mono text-txtDim">
          {all.map((r) => (
            <tr key={r.time} className={`border-b border-edge/50 ${r._example ? "bg-surface/70" : ""}`}>
              <td className="py-1">
                {iso(r.time)}
                {r._example && <span className="ml-2 font-sans text-2xs text-txtMuted">contoh uncertain terbaru</span>}
              </td>
              <td className="py-1 text-right">{fmt(r.hurst)}</td>
              <td className="py-1 text-right">{fmt(r.dfa_alpha)}</td>
              <td className="py-1 text-right">{fmt(r.efficiency_ratio, 3)}</td>
              <td className="py-1 pl-4 font-sans" style={{ color: REGIME_META[r.regime as Regime]?.color }}>
                {regimeLabel(r.regime)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

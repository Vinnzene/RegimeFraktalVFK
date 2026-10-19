"use client";

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
import { api } from "@/lib/api-client";
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
              n: regime.data?.series.length ?? 0,
            }}
          >
            <HurstDfaPanel
              series={regime.data?.series ?? []}
              hurstThreshold={(config?.analysis.hurst_threshold ?? [0.45, 0.55]) as [number, number]}
              dfaThreshold={(config?.analysis.dfa_threshold ?? [0.45, 0.55]) as [number, number]}
            />
            <p className="mt-2 text-2xs leading-relaxed text-txtMuted">
              Perhatikan titik di mana garis biru (Hurst) dan oranye (DFA α) berada di sisi
              berlawanan terhadap pita ambang — window seperti itulah yang dilabeli Uncertain
              (rule).
            </p>
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
                Diagonal yang dominan menandakan regime cenderung bertahan — sekaligus alasan
                Baseline Persistence pada halaman Model Comparison harus dibaca lebih dulu
                sebelum menilai angka model.
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

"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";

const COLORS = ["#3b82f6", "#f59e0b", "#10b981", "#a78bfa", "#ef4444", "#06b6d4"];

export default function SwtPage() {
  const { timeframe, config } = useAppConfig();
  const [levels, setLevels] = useState<number | undefined>(undefined);
  const [endIndex, setEndIndex] = useState<number | undefined>(undefined);

  const swt = useApi(() => api.swt(timeframe, levels, endIndex), [timeframe, levels, endIndex]);

  const components = swt.data?.components ?? {};
  const times = swt.data?.times ?? [];

  const keys = useMemo(
    () =>
      Object.keys(components).sort((a, b) => {
        if (a === "approx") return -1;
        if (b === "approx") return 1;
        return a.localeCompare(b);
      }),
    [components]
  );

  return (
    <div className="space-y-4">
      <PageHeader
        title="Dekomposisi SWT"
        description="Representasi multiskala log-return: satu komponen aproksimasi dan beberapa komponen detail. Dekomposisi dihitung ulang per window dari data ≤ t (causal), bukan sekali di seluruh deret lalu dipotong."
      />

      <ParameterBar />

      <div className="rounded border border-bullish/40 bg-bullish/10 px-3 py-2 text-[11px] leading-relaxed text-bullish">
        <span className="font-semibold">Causal: {String(swt.data?.parameters?.causal ?? "—")}. </span>
        Filter simetris pada <span className="font-mono">pywt.swt</span> membuat koefisien di
        titik t ikut menyerap sampel setelah t bila transform dijalankan pada seluruh deret.
        Di sistem ini window dipotong lebih dulu, sehingga tampilan konsisten dengan cara
        fitur model dibentuk.
      </div>

      <ApiState loading={swt.loading} error={swt.error} />

      {!swt.loading && !swt.error && (
        <>
          <Panel title="Kontrol Dekomposisi" subtitle="Parameter J dan posisi akhir window.">
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-[11px] text-txtDim">
                Level J
                <select
                  value={levels ?? config?.analysis.J ?? 4}
                  onChange={(e) => setLevels(Number(e.target.value))}
                  className="rounded border border-edge bg-panelAlt px-2 py-1 text-txtDim"
                >
                  {[1, 2, 3, 4, 5, 6].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-1 items-center gap-3 text-[11px] text-txtDim">
                Akhir window (t)
                <input
                  type="range"
                  min={600}
                  max={5900}
                  step={20}
                  value={endIndex ?? 5900}
                  onChange={(e) => setEndIndex(Number(e.target.value))}
                  className="flex-1 accent-persistent"
                />
                <span className="w-16 font-mono text-txtDim">
                  {swt.data?.parameters?.end_index ?? "—"}
                </span>
              </label>
              <span className="chip">
                J efektif: {swt.data?.parameters?.J_effective ?? "—"}
              </span>
              <span className="chip">window: {swt.data?.parameters?.window ?? "—"}</span>
            </div>
          </Panel>

          <div className="space-y-3">
            {keys.map((key, i) => {
              const data = (components[key] ?? []).map((v: number, idx: number) => ({
                idx,
                label: times[idx]
                  ? new Date(times[idx] * 1000).toISOString().slice(0, 10)
                  : String(idx),
                value: v,
              }));
              return (
                <Panel
                  key={key}
                  title={key === "approx" ? "Approximation (A_J)" : `Detail (D_${key.split("_")[1]})`}
                  subtitle={
                    key === "approx"
                      ? "Komponen tren berfrekuensi paling rendah."
                      : "Komponen fluktuasi; nomor kecil = frekuensi tinggi."
                  }
                >
                  <ResponsiveContainer width="100%" height={140}>
                    <LineChart data={data} margin={{ top: 5, right: 10, bottom: 0, left: -18 }}>
                      <CartesianGrid stroke="rgba(30,41,55,0.7)" />
                      <XAxis
                        dataKey="label"
                        tick={{ fontSize: 9, fill: "#64748b" }}
                        minTickGap={60}
                      />
                      <YAxis tick={{ fontSize: 9, fill: "#64748b" }} width={54} />
                      <Tooltip
                        contentStyle={{
                          background: "#0b1017",
                          border: "1px solid #1e2937",
                          fontSize: 11,
                          borderRadius: 6,
                        }}
                        formatter={(v: any) => [Number(v).toExponential(3), key]}
                      />
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke={COLORS[i % COLORS.length]}
                        dot={false}
                        strokeWidth={1.2}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </Panel>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

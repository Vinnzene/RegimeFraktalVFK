"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RegimePoint } from "@/lib/api-client";
import {
  AXIS_TICK,
  GRID_STROKE,
  LEGEND_STYLE,
  TOOLTIP_LABEL_STYLE,
  TOOLTIP_STYLE,
} from "@/lib/chart-theme";

/**
 * Deret Hurst & DFA α dengan pita ambang.
 *
 * Pita [lower, upper] digambar sebagai ReferenceArea supaya terlihat kenapa
 * suatu window jatuh ke kategori tertentu — dan kenapa window dengan H dan α
 * di sisi berbeda ditandai uncertain_rule.
 */
export default function HurstDfaPanel({
  series,
  hurstThreshold,
  dfaThreshold,
  height = 300,
  showEr = false,
}: {
  series: RegimePoint[];
  hurstThreshold: [number, number];
  dfaThreshold: [number, number];
  height?: number;
  showEr?: boolean;
}) {
  const data = series.map((p) => ({
    time: p.time,
    label: new Date(p.time * 1000).toISOString().slice(0, 10),
    hurst: p.hurst,
    dfa: p.dfa_alpha,
    er: p.efficiency_ratio ?? null,
    regime: p.regime,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 10, bottom: 5, left: -18 }}>
        <CartesianGrid stroke={GRID_STROKE} />
        <ReferenceArea
          y1={hurstThreshold[0]}
          y2={hurstThreshold[1]}
          fill="#94a3b8"
          fillOpacity={0.1}
        />
        <ReferenceLine y={hurstThreshold[0]} stroke="#f97316" strokeDasharray="4 3" />
        <ReferenceLine y={hurstThreshold[1]} stroke="#3b82f6" strokeDasharray="4 3" />
        <ReferenceLine y={dfaThreshold[0]} stroke="#f59e0b" strokeDasharray="1 3" />
        <ReferenceLine y={dfaThreshold[1]} stroke="#f59e0b" strokeDasharray="1 3" />
        <ReferenceLine y={0.5} stroke="#475569" strokeDasharray="2 4" />
        <XAxis dataKey="label" tick={AXIS_TICK} minTickGap={48} />
        <YAxis domain={showEr ? [0, 1] : [0.1, 1.0]} tick={AXIS_TICK} width={44} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          labelStyle={TOOLTIP_LABEL_STYLE}
          formatter={(v: any, name: string) => [
            typeof v === "number" ? v.toFixed(4) : v,
            name,
          ]}
        />
        <Legend wrapperStyle={LEGEND_STYLE} />
        <Line
          type="monotone"
          dataKey="hurst"
          name="Hurst (R/S)"
          stroke="#3b82f6"
          dot={false}
          strokeWidth={1.4}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="dfa"
          name="DFA α"
          stroke="#f59e0b"
          dot={false}
          strokeWidth={1.4}
          connectNulls
        />
        {showEr && (
          <Line
            type="monotone"
            dataKey="er"
            name="ER_q (skor kuantil efficiency ratio)"
            stroke="#10b981"
            dot={false}
            strokeWidth={1}
            strokeOpacity={0.75}
            connectNulls
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}

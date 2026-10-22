"use client";

import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import CandlestickChart from "@/components/CandlestickChart";
import Disclaimer from "@/components/Disclaimer";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";

export default function AttentionPage() {
  const { timeframe, config } = useAppConfig();
  const [seqLen, setSeqLen] = useState(120);
  const [windowId, setWindowId] = useState<number | undefined>(undefined);

  const attn = useApi(
    () => api.attention(timeframe, windowId, seqLen),
    [timeframe, windowId, seqLen]
  );

  const weights = attn.data?.attention_weights ?? [];
  const maxWeight = weights.reduce((m: number, w: any) => Math.max(m, w.weight), 0);

  const chartData = weights.map((w: any, i: number) => ({
    step: i - weights.length + 1,
    label: new Date(w.time * 1000).toISOString().slice(0, 13).replace("T", " "),
    weight: w.weight,
  }));

  return (
    <div className="space-y-4">
      <PageHeader
        title="Attention Weights"
        description="Bobot α_t yang diberikan model pada tiap timestep dalam satu window, disandingkan dengan candlestick window yang sama. Panel ini menjawab pertanyaan 'bagian mana dari sekuens yang diperhatikan model'."
      />
      <Disclaimer variant="archive" />

      <ParameterBar />
      {config?.runtime.use_mock && <Disclaimer variant="mock" />}
      <ApiState loading={attn.loading} error={attn.error} />

      {!attn.loading && !attn.error && (
        <>
          <Panel
            title="Kontrol Window"
            subtitle="Pilih panjang sekuens dan posisi window yang ingin diperiksa."
          >
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-[11px] text-txtDim">
                Panjang sekuens
                <select
                  value={seqLen}
                  onChange={(e) => setSeqLen(Number(e.target.value))}
                  className="rounded border border-edge bg-panelAlt px-2 py-1 text-txtDim"
                >
                  {[60, 120, 240].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-1 items-center gap-3 text-[11px] text-txtDim">
                Posisi window
                <input
                  type="range"
                  min={seqLen}
                  max={5000}
                  step={10}
                  value={windowId ?? 5000}
                  onChange={(e) => setWindowId(Number(e.target.value))}
                  className="flex-1 accent-persistent"
                />
                <span className="w-16 font-mono text-txtDim">
                  {attn.data?.window_id ?? "—"}
                </span>
              </label>
            </div>
          </Panel>

          <Panel
            title="Heatmap Bobot Attention"
            subtitle="Semakin terang, semakin besar kontribusi timestep tersebut terhadap konteks yang dipakai untuk klasifikasi."
            params={{ model: attn.data?.model ?? "-", seq_len: attn.data?.seq_len ?? "-" }}
          >
            <div className="flex h-10 w-full overflow-hidden rounded border border-edge">
              {weights.map((w: any, i: number) => (
                <div
                  key={i}
                  className="h-full flex-1"
                  title={`α = ${w.weight.toFixed(5)}`}
                  style={{
                    backgroundColor: `rgba(59,130,246,${0.06 + (w.weight / (maxWeight || 1)) * 0.94})`,
                  }}
                />
              ))}
            </div>
            <div className="mt-1 flex justify-between text-2xs text-txtMuted">
              <span>t − {seqLen - 1} (paling lama)</span>
              <span>t (paling baru)</span>
            </div>

            <div className="mt-4">
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: -22 }}>
                  <CartesianGrid stroke="rgba(30,41,55,0.7)" />
                  <XAxis dataKey="step" tick={{ fontSize: 10, fill: "#64748b" }} minTickGap={40} />
                  <YAxis tick={{ fontSize: 10, fill: "#64748b" }} width={52} />
                  <Tooltip
                    contentStyle={{
                      background: "#0b1017",
                      border: "1px solid #1e2937",
                      fontSize: 11,
                      borderRadius: 6,
                    }}
                    formatter={(v: any) => [Number(v).toFixed(5), "α_t"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="weight"
                    stroke="#3b82f6"
                    fill="rgba(59,130,246,0.25)"
                    strokeWidth={1.4}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel
            title="Candlestick Window yang Sama"
            subtitle="Sandingkan puncak α_t di atas dengan pergerakan harga di bawah."
          >
            <CandlestickChart
              candles={attn.data?.candles ?? []}
              height={300}
              showRegime={false}
              symbol={config?.data.symbol ?? "BTCUSDT"}
              timeframe={timeframe}
              showToolbar={false}
            />
          </Panel>
        </>
      )}
    </div>
  );
}

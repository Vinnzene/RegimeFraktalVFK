"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import BacktestDiagnostics from "@/components/BacktestDiagnostics";
import Disclaimer from "@/components/Disclaimer";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import { useAppConfig } from "@/components/ConfigContext";
import { api } from "@/lib/api-client";

export default function BacktestPage() {
  const { timeframe } = useAppConfig();
  const [source, setSource] = useState("model_prediction_at_t");
  const [modelKey, setModelKey] = useState("swt_attention_bilstm");
  const [feeBps, setFeeBps] = useState(4);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const r = await api.runBacktest({
        tf: timeframe,
        regime_source: source,
        model_key: modelKey,
        fee_bps: feeBps,
      });
      setResult(r);
    } catch (e: any) {
      setError(String(e?.message ?? e));
    } finally {
      setLoading(false);
    }
  }

  const m = result?.metrics;
  const curve = (result?.equity_curve ?? []).map((p: any) => ({
    label: new Date(p.time * 1000).toISOString().slice(0, 10),
    strategy: p.strategy,
    buy_hold: p.buy_hold,
  }));

  return (
    <div className="space-y-4">
      <PageHeader
        title="Backtest Berbasis Regime"
        description="Menguji kegunaan praktis informasi regime pada data historis. Aturan posisi ditetapkan di muka dan tidak dapat diubah pengguna, agar tidak terjadi pemilihan aturan setelah melihat hasil."
      />

      <ParameterBar />
      <Disclaimer variant="backtest" />

      <div className="rounded border border-persistent/40 bg-persistent/10 px-3 py-2 text-[11px] leading-relaxed text-txtDim">
        <span className="font-semibold">regime source: {source}. </span>
        Sinyal hanya boleh berasal dari informasi yang tersedia pada waktu t. Label ground
        truth Hurst-DFA (Y<sub>t+h</sub>) tidak disediakan sebagai sumber sinyal karena
        berasal dari window masa depan — memakainya akan membuat equity curve terlihat baik
        semata-mata karena kebocoran informasi.
      </div>

      <Panel title="Parameter Backtest" subtitle="Aturan posisi bersifat tetap, bukan pilihan.">
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-[11px] text-txtDim">
            <div className="mb-1">Sumber regime</div>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="rounded border border-edge bg-panelAlt px-2 py-1 text-txtDim"
            >
              <option value="model_prediction_at_t">Prediksi model @ t</option>
              <option value="rule_based_causal">Rule-based Hurst-DFA (window ≤ t)</option>
            </select>
          </label>
          <label className="text-[11px] text-txtDim">
            <div className="mb-1">Model</div>
            <select
              value={modelKey}
              disabled={source !== "model_prediction_at_t"}
              onChange={(e) => setModelKey(e.target.value)}
              className="rounded border border-edge bg-panelAlt px-2 py-1 text-txtDim disabled:opacity-40"
            >
              <option value="swt_attention_bilstm">SWT + Attention-BiLSTM</option>
              <option value="swt_bilstm">SWT + BiLSTM</option>
            </select>
          </label>
          <label className="text-[11px] text-txtDim">
            <div className="mb-1">Biaya transaksi (bps)</div>
            <input
              type="number"
              min={0}
              max={100}
              value={feeBps}
              onChange={(e) => setFeeBps(Number(e.target.value))}
              className="w-24 rounded border border-edge bg-panelAlt px-2 py-1 font-mono text-txtDim"
            />
          </label>
          <button
            onClick={run}
            disabled={loading}
            className="rounded bg-persistent/80 px-4 py-1.5 text-[12px] font-medium text-white transition hover:bg-persistent disabled:opacity-50"
          >
            {loading ? "Menjalankan…" : "Jalankan Backtest"}
          </button>
        </div>

        <div className="mt-4 grid gap-2 text-[11px] sm:grid-cols-3">
          {[
            ["Persistent", "ikuti arah return terakhir (trend-following)", "#3b82f6"],
            ["Anti-persistent", "lawan arah return terakhir (kontrarian)", "#f97316"],
            ["Random-like & Uncertain", "flat, tidak ambil posisi", "#94a3b8"],
          ].map(([title, body, color]) => (
            <div key={title} className="rounded border border-edge bg-panelAlt p-2">
              <div className="font-medium" style={{ color }}>
                {title}
              </div>
              <div className="mt-0.5 text-2xs text-txtMuted">{body}</div>
            </div>
          ))}
        </div>
      </Panel>

      {error && (
        <div className="rounded border border-bearish/40 bg-bearish/10 px-3 py-2 text-[11px] text-bearish">
          {error}
        </div>
      )}

      {result && (
        <>
          <Panel
            title="Equity Curve vs Buy & Hold"
            subtitle="Buy & Hold adalah pembanding wajib, bukan opsional."
            params={{ id: result.id, tf: result.timeframe, tau: result.tau }}
          >
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={curve} margin={{ top: 5, right: 10, bottom: 5, left: -18 }}>
                <CartesianGrid stroke="rgba(30,41,55,0.7)" />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#64748b" }} minTickGap={50} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} width={52} />
                <Tooltip
                  contentStyle={{
                    background: "#0b1017",
                    border: "1px solid #1e2937",
                    fontSize: 11,
                    borderRadius: 6,
                  }}
                  formatter={(v: any) => Number(v).toFixed(4)}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line
                  type="monotone"
                  dataKey="strategy"
                  name="Strategi regime"
                  stroke="#3b82f6"
                  dot={false}
                  strokeWidth={1.6}
                />
                <Line
                  type="monotone"
                  dataKey="buy_hold"
                  name="Buy & Hold"
                  stroke="#94a3b8"
                  dot={false}
                  strokeDasharray="5 3"
                  strokeWidth={1.4}
                />
              </LineChart>
            </ResponsiveContainer>
          </Panel>

          <Panel title="Metrik" subtitle={result.regime_source_note}>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {[
                ["Return kumulatif", `${(m.cumulative_return * 100).toFixed(2)}%`],
                ["Buy & Hold", `${(m.buy_hold_return * 100).toFixed(2)}%`],
                ["Max drawdown", `${(m.max_drawdown * 100).toFixed(2)}%`],
                ["B&H max drawdown", `${(m.buy_hold_max_drawdown * 100).toFixed(2)}%`],
                ["Sharpe ratio", m.sharpe_ratio.toFixed(3)],
                ["Volatilitas (thn)", m.volatility_annualized.toFixed(3)],
                ["Turnover total", m.turnover_total.toFixed(2)],
                ["Biaya transaksi", m.transaction_cost_total.toFixed(4)],
                ["Jumlah transaksi", m.n_trades],
                ["Exposure", `${(m.exposure * 100).toFixed(1)}%`],
                ["Jumlah bar", m.n_bars],
                ["Fee (bps)", m.fee_bps],
              ].map(([label, value]) => (
                <div key={label as string} className="rounded border border-edge bg-panelAlt p-2.5">
                  <div className="metric-label">{label}</div>
                  <div className="mt-0.5 font-mono text-base text-txt">{value as string}</div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
              Angka di atas belum menjelaskan penyebabnya. Panel diagnostik di bawah
              memisahkan kontribusi arah posisi, volatility drag, dan biaya transaksi,
              lalu menguji apakah hasilnya berbeda dari kebetulan.
            </p>
          </Panel>

          <BacktestDiagnostics
            timeframe={timeframe}
            regimeSource={source}
            modelKey={modelKey}
            feeBps={feeBps}
          />
        </>
      )}
    </div>
  );
}

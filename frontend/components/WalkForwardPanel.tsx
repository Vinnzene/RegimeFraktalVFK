"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import Panel from "@/components/Panel";
import { ApiState, useApi } from "@/components/useApi";
import {
  AXIS_TICK,
  GRID_STROKE,
  LEGEND_STYLE,
  TOOLTIP_STYLE,
} from "@/lib/chart-theme";
import { api } from "@/lib/api-client";
import { regimeLabel } from "@/lib/regime";

/**
 * Hasil validasi walk-forward.
 *
 * Split tunggal hanya menguji satu periode dan mudah terlihat terlalu bagus.
 * Panel ini menampilkan performa per fold beserta simpangan bakunya, sehingga
 * terlihat apakah angka agregat berasal dari performa yang merata atau dari
 * satu periode yang kebetulan mudah.
 */
export default function WalkForwardPanel({ timeframe }: { timeframe: string }) {
  const [mode, setMode] = useState<"binary" | "multiclass">("binary");
  const [labeling, setLabeling] = useState<"threshold" | "jump">("threshold");
  const [scheme, setScheme] = useState<"expanding" | "rolling">("expanding");

  const res = useApi(
    () => api.walkForward(timeframe, mode, labeling),
    [timeframe, mode, labeling]
  );

  const controls = (
    <div className="flex flex-wrap gap-1.5">
      <div className="inline-flex overflow-hidden rounded border border-edge">
        {(["binary", "multiclass"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-2 py-1 font-mono text-2xs transition ${
              mode === m ? "bg-accent/20 text-accent" : "text-txtMuted hover:bg-surface"
            }`}
          >
            {m === "binary" ? "BINER" : "3 KELAS"}
          </button>
        ))}
      </div>
      <div className="inline-flex overflow-hidden rounded border border-edge">
        {(["threshold", "jump"] as const).map((l) => (
          <button
            key={l}
            onClick={() => setLabeling(l)}
            className={`px-2 py-1 font-mono text-2xs transition ${
              labeling === l ? "bg-accent/20 text-accent" : "text-txtMuted hover:bg-surface"
            }`}
          >
            {l === "threshold" ? "AMBANG" : "JUMP"}
          </button>
        ))}
      </div>
    </div>
  );

  if (res.loading || res.error) {
    return (
      <Panel title="Validasi Walk-Forward" subtitle="Memuat…" actions={controls}>
        <ApiState loading={res.loading} error={res.error} />
      </Panel>
    );
  }

  const d = res.data;
  if (!d?.available) {
    return (
      <Panel
        title="Validasi Walk-Forward"
        subtitle="Melatih ulang model pada beberapa fold berurutan waktu."
        actions={controls}
      >
        <p className="text-[11px] text-txtMuted">
          Belum dijalankan untuk konfigurasi ini. Jalankan perintah berikut:
        </p>
        <pre className="mt-2 overflow-x-auto rounded border border-edge bg-panelAlt p-2 font-mono text-2xs text-txtDim">
          {d?.perintah}
        </pre>
      </Panel>
    );
  }

  const data = d.schemes?.[scheme];
  if (!data) return null;

  const agg = data.aggregate ?? {};
  const st = data.stability ?? {};
  const folds = data.folds ?? [];

  const chartData = folds.map((f: any) => ({
    fold: `F${f.fold}`,
    akurasi: f.accuracy,
    macroF1: f.macro_f1,
    n_train: f.n_train,
  }));

  return (
    <Panel
      title="Validasi Walk-Forward"
      subtitle="Model dilatih ulang pada tiap fold; seluruh prediksi digabung menjadi satu confusion matrix."
      params={{
        labeling: d.labeling,
        fold: data.n_splits,
        purge: `${d.purge_rows} baris`,
      }}
      actions={controls}
    >
      <div className="mb-3 inline-flex overflow-hidden rounded border border-edge">
        {(["expanding", "rolling"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setScheme(s)}
            disabled={!d.schemes?.[s]}
            className={`px-3 py-1 font-mono text-2xs transition disabled:opacity-30 ${
              scheme === s ? "bg-accent/20 text-accent" : "text-txtMuted hover:bg-surface"
            }`}
          >
            {s.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {[
          ["Akurasi agregat", agg.accuracy, true],
          ["Balanced accuracy", agg.balanced_accuracy, true],
          ["Macro F1", agg.macro_f1, true],
          ["Simpangan antar-fold", st.accuracy_std, false],
        ].map(([label, value, isGood]) => (
          <div key={label as string} className="stat-card py-2">
            <div className="metric-label">{label as string}</div>
            <div
              className={`mt-0.5 font-mono text-[17px] font-semibold tabular-nums ${
                isGood && (value as number) >= 0.8
                  ? "text-bullish"
                  : !isGood && (value as number) > 0.1
                    ? "text-warn"
                    : "text-txt"
              }`}
            >
              {((value as number) ?? 0).toFixed(4)}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4">
        <div className="mb-1.5 text-[12px] font-semibold text-txt">Performa per fold</div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
            <CartesianGrid stroke={GRID_STROKE} />
            <XAxis dataKey="fold" tick={AXIS_TICK} />
            <YAxis domain={[0, 1]} tick={AXIS_TICK} />
            <ReferenceLine
              y={agg.accuracy}
              stroke="#2ebd85"
              strokeDasharray="4 3"
              label={{ value: "agregat", fontSize: 9, fill: "#2ebd85", position: "right" }}
            />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Legend wrapperStyle={LEGEND_STYLE} />
            <Bar dataKey="akurasi" name="akurasi" fill="#4a9eff">
              {chartData.map((c: any, i: number) => (
                <Cell key={i} fill={c.akurasi >= agg.accuracy ? "#2ebd85" : "#4a9eff"} />
              ))}
            </Bar>
            <Bar dataKey="macroF1" name="macro F1" fill="#f0b90b" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <div className="mb-1.5 text-[12px] font-semibold text-txt">
            Confusion matrix agregat
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-2xs tabular-nums">
              <thead>
                <tr className="border-b border-edge text-txtMuted">
                  <th className="py-1 text-left font-medium">aktual \ prediksi</th>
                  {(agg.classes ?? []).map((c: string) => (
                    <th key={c} className="py-1 text-right font-medium">
                      {regimeLabel(c).split(" ")[0]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(agg.matrix ?? []).map((row: number[], i: number) => (
                  <tr key={i} className="border-b border-edge/50">
                    <td className="py-1 text-txtDim">{regimeLabel(agg.classes[i])}</td>
                    {row.map((v: number, j: number) => (
                      <td
                        key={j}
                        className={`py-1 text-right font-mono ${
                          i === j ? "font-semibold text-bullish" : "text-txtMuted"
                        }`}
                      >
                        {v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <div className="mb-1.5 text-[12px] font-semibold text-txt">Metrik per kelas</div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="text-left">Regime</th>
                  <th className="text-right">n</th>
                  <th className="text-right">Precision</th>
                  <th className="text-right">Recall</th>
                  <th className="text-right">F1</th>
                </tr>
              </thead>
              <tbody>
                {(agg.per_class ?? []).map((p: any) => (
                  <tr key={p.regime}>
                    <td className="font-sans text-txtDim">{regimeLabel(p.regime)}</td>
                    <td className="text-right text-txtMuted">{p.support}</td>
                    <td className="text-right">{p.precision.toFixed(3)}</td>
                    <td className="text-right">{p.recall.toFixed(3)}</td>
                    <td
                      className={`text-right font-semibold ${
                        p.f1 >= 0.8 ? "text-bullish" : p.f1 < 0.4 ? "text-bearish" : "text-txt"
                      }`}
                    >
                      {p.f1.toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
        <span className="text-txtDim">Cara membacanya: </span>
        setiap fold melatih ulang model dari awal dengan data yang tersedia hingga periode
        itu saja, lalu diuji pada periode berikutnya setelah jeda purge. Simpangan baku
        antar-fold menunjukkan kestabilan — nilai besar berarti performa sangat bergantung
        periode, sehingga angka agregat saja belum cukup untuk menyimpulkan. Skema{" "}
        <span className="text-txtDim">expanding</span> menambah data latih tiap fold,
        sedangkan <span className="text-txtDim">rolling</span> mempertahankan ukuran jendela
        tetap untuk menguji apakah data lama justru mengganggu.
      </p>
    </Panel>
  );
}

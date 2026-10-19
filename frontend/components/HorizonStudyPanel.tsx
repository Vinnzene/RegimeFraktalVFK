"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import Panel from "@/components/Panel";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";

/**
 * Sensitivitas horizon.
 *
 * Yang ditonjolkan adalah SELISIH terhadap Baseline Persistence pada horizon
 * yang sama, bukan balanced accuracy mentah. Alasannya: regime bertahan lebih
 * lama pada horizon pendek, sehingga tebakan naif pun otomatis tinggi di sana.
 * Membandingkan BA mentah antar horizon akan menyesatkan.
 */
export default function HorizonStudyPanel({ timeframe }: { timeframe: string }) {
  const study = useApi(() => api.horizonStudy(timeframe), [timeframe]);

  if (study.loading || study.error) {
    return (
      <Panel title="Sensitivitas Horizon" subtitle="Memuat…">
        <ApiState loading={study.loading} error={study.error} />
      </Panel>
    );
  }

  if (!study.data?.available) {
    return (
      <Panel
        title="Sensitivitas Horizon"
        subtitle="Menguji apakah daya prediksi menurun seiring jauhnya horizon."
      >
        <p className="text-[11px] leading-relaxed text-txtMuted">
          Studi belum dijalankan. Jalankan perintah berikut, lalu muat ulang halaman:
        </p>
        <pre className="mt-2 overflow-x-auto rounded border border-edge bg-panelAlt p-2 font-mono text-2xs text-txtDim">
          python ml/src/horizon_study.py --timeframe {timeframe}
        </pre>
      </Panel>
    );
  }

  const rows = study.data.results ?? [];
  const chartData = rows.map((r: any) => ({
    label: `${r.h_bars} bar\n${r.h_days} hari`,
    h: r.h_bars,
    lift: r.lift_over_baseline,
    ba: r.test?.balanced_accuracy,
    baseline: r.baseline?.balanced_accuracy,
  }));

  const best = rows.reduce(
    (acc: any, r: any) =>
      acc === null || (r.lift_over_baseline ?? -9) > (acc.lift_over_baseline ?? -9) ? r : acc,
    null
  );

  return (
    <Panel
      title="Sensitivitas Horizon"
      subtitle="Selisih balanced accuracy terhadap Baseline Persistence pada horizon yang sama."
      params={{
        model: study.data.model,
        horizon_diuji: rows.length,
        config_cocok: String(study.data.config_matches),
      }}
    >
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={chartData} margin={{ top: 5, right: 10, bottom: 20, left: -20 }}>
          <CartesianGrid stroke="rgba(30,41,55,0.7)" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "#64748b" }}
            interval={0}
            height={40}
          />
          <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
          <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{
              background: "#0b1017",
              border: "1px solid #1e2937",
              fontSize: 11,
              borderRadius: 6,
            }}
            formatter={(v: any, name: string) => [
              typeof v === "number" ? v.toFixed(4) : v,
              name === "lift" ? "selisih vs baseline" : name,
            ]}
          />
          <Bar dataKey="lift" name="selisih vs baseline">
            {chartData.map((d: any) => (
              <Cell key={d.h} fill={d.lift >= 0 ? "#3b82f6" : "#f97316"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead className="text-txtMuted">
            <tr className="border-b border-edge">
              <th className="py-1 text-left">Horizon</th>
              <th className="py-1 text-right">Hari</th>
              <th className="py-1 text-right">n test</th>
              <th className="py-1 text-right">BA model</th>
              <th className="py-1 text-right">BA baseline</th>
              <th className="py-1 text-right">Selisih</th>
              <th className="py-1 text-right">rata-rata max(P)</th>
            </tr>
          </thead>
          <tbody className="font-mono text-txtDim">
            {rows.map((r: any) => {
              const lift = r.lift_over_baseline ?? 0;
              return (
                <tr
                  key={r.h_bars}
                  className={`border-b border-edge/50 ${lift > 0 ? "bg-persistent/5" : ""}`}
                >
                  <td className="py-1 font-sans text-txtDim">{r.h_bars} bar</td>
                  <td className="py-1 text-right">{r.h_days}</td>
                  <td className="py-1 text-right text-txtMuted">{r.test?.n ?? "—"}</td>
                  <td className="py-1 text-right">{r.test?.balanced_accuracy ?? "—"}</td>
                  <td className="py-1 text-right text-txtMuted">
                    {r.baseline?.balanced_accuracy ?? "—"}
                  </td>
                  <td
                    className={`py-1 text-right ${lift > 0 ? "text-persistent" : "text-antiPersistent"}`}
                  >
                    {lift > 0 ? "+" : ""}
                    {lift.toFixed(4)}
                  </td>
                  <td className="py-1 text-right text-txtMuted">
                    {r.test?.mean_max_prob ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-3 space-y-1.5 text-2xs leading-relaxed text-txtMuted">
        <p>
          <span className="text-txtDim">Cara membacanya: </span>
          batang biru berarti model mengungguli tebakan naif pada horizon tersebut, oranye
          berarti tidak. Perbandingan harus lewat selisih, bukan balanced accuracy mentah —
          pada horizon pendek regime jarang berubah, sehingga baseline otomatis tinggi dan
          sulit dilampaui.
        </p>
        {best && (
          <p>
            <span className="text-txtDim">Horizon terbaik: </span>
            {best.h_bars} bar (~{best.h_days} hari) dengan selisih{" "}
            {(best.lift_over_baseline ?? 0) > 0 ? "+" : ""}
            {(best.lift_over_baseline ?? 0).toFixed(4)}.
          </p>
        )}
        <p>
          Kolom rata-rata max(P) menurun seiring bertambahnya horizon, menunjukkan model
          makin tidak yakin saat diminta melihat lebih jauh ke depan — pola yang konsisten
          dengan berkurangnya informasi yang tersedia pada horizon panjang.
        </p>
      </div>
    </Panel>
  );
}

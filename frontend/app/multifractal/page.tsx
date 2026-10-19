"use client";

import { useMemo, useState } from "react";
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
import Formula from "@/components/Formula";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";

export default function MultifractalPage() {
  const { timeframe } = useAppConfig();
  const [limit, setLimit] = useState<number>(600);

  const mf = useApi(() => api.multifractal(timeframe, limit), [timeframe, limit]);

  const series = mf.data?.series ?? [];
  const summary = mf.data?.summary ?? {};
  const crossCheck = mf.data?.cross_check;
  const params = mf.data?.parameters ?? {};

  const chartData = useMemo(() => {
    return series.map((pt: any) => ({
      time: pt.time ? new Date(pt.time * 1000).toLocaleDateString("id-ID", { month: "short", day: "numeric" }) : "",
      fullTime: pt.time ? new Date(pt.time * 1000).toLocaleString("id-ID") : "",
      hq_1: pt.hq_1 != null ? Number(pt.hq_1.toFixed(3)) : null,
      hq_2: pt.hq_2 != null ? Number(pt.hq_2.toFixed(3)) : null,
      hq_4: pt.hq_4 != null ? Number(pt.hq_4.toFixed(3)) : null,
      hq_width: pt.hq_width != null ? Number(pt.hq_width.toFixed(3)) : null,
      hurst_rs: pt.hurst_rs != null ? Number(pt.hurst_rs.toFixed(3)) : null,
    }));
  }, [series]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Spektrum Multifraktal H(q)"
        description="Analisis Generalized Hurst H(q) fungsi struktur untuk momen q ∈ {1, 2, 4} dan lebar spektrum multifraktal ΔH = H(1) - H(4). Memisahkan dinamika fluktuasi kecil yang sering dari lompatan ekstrem yang jarang."
      />

      <ParameterBar />

      <ApiState loading={mf.loading} error={mf.error} />

      {!mf.loading && !mf.error && (
        <>
          {/* Ringkasan Metrik Kunci */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded border border-edge bg-panel p-3">
              <div className="text-2xs font-medium uppercase tracking-wider text-txtDim">
                Rata-rata Lebar Spektrum (ΔH)
              </div>
              <div className="mt-1 text-xl font-bold font-mono text-txt">
                {summary.mean_width?.toFixed(3) ?? "—"}
              </div>
              <div className="mt-0.5 text-2xs text-txtMuted">Mean H(1) - H(4)</div>
            </div>

            <div className="rounded border border-edge bg-panel p-3">
              <div className="text-2xs font-medium uppercase tracking-wider text-txtDim">
                Median Lebar Spektrum
              </div>
              <div className="mt-1 text-xl font-bold font-mono text-accent">
                {summary.median_width?.toFixed(3) ?? "—"}
              </div>
              <div className="mt-0.5 text-2xs text-txtMuted">50th percentile ΔH</div>
            </div>

            <div className="rounded border border-edge bg-panel p-3">
              <div className="text-2xs font-medium uppercase tracking-wider text-txtDim">
                Maksimum ΔH Teramati
              </div>
              <div className="mt-1 text-xl font-bold font-mono text-txt">
                {summary.max_width?.toFixed(3) ?? "—"}
              </div>
              <div className="mt-0.5 text-2xs text-txtMuted">Puncak multifraktalitas</div>
            </div>

            <div className="rounded border border-edge bg-panel p-3">
              <div className="text-2xs font-medium uppercase tracking-wider text-txtDim">
                Observasi Window Finiter
              </div>
              <div className="mt-1 text-xl font-bold font-mono text-txt">
                {summary.n_finite?.toLocaleString("id-ID") ?? "—"}
              </div>
              <div className="mt-0.5 text-2xs text-txtMuted">L = {params.window ?? 500} bar per window</div>
            </div>
          </div>

          {/* Grafik Utama H(q) dan ΔH */}
          <Panel
            title="Dinamika Temporal H(q) & Spektrum Lebar ΔH"
            subtitle="H(1) mewakili fluktuasi harian kecil, H(2) setara dengan variansi skala, dan H(4) sensitif terhadap ekor tebal / lompatan harga."
            params={{
              q: "1, 2, 4",
              window: params.window ?? 500,
              estimator: params.estimator ?? "structure_function",
              titik: chartData.length,
            }}
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-4 text-txtDim">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-blue-500" /> H(1)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> H(2)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> H(4)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-pink-500" /> ΔH = H(1) - H(4)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-2xs text-txtMuted">Kepadatan Titik:</span>
                <select
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value))}
                  className="rounded border border-edge bg-panelAlt px-2 py-0.5 text-xs text-txt font-mono"
                >
                  <option value={300}>300 titik</option>
                  <option value={600}>600 titik</option>
                  <option value={1200}>1200 titik</option>
                </select>
              </div>
            </div>

            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis
                    dataKey="time"
                    stroke="#888"
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    stroke="#888"
                    domain={[0.2, 0.8]}
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#161b22",
                      borderColor: "#30363d",
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.fullTime ?? ""}
                  />
                  <Line
                    type="monotone"
                    dataKey="hq_1"
                    name="H(1)"
                    stroke="#3b82f6"
                    strokeWidth={1.5}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="hq_2"
                    name="H(2)"
                    stroke="#10b981"
                    strokeWidth={1.5}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="hq_4"
                    name="H(4)"
                    stroke="#f59e0b"
                    strokeWidth={1.5}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="hq_width"
                    name="ΔH (Lebar)"
                    stroke="#ec4899"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Catatan Intepretasi Ambang Multifraktal */}
            <div className="mt-3 rounded border border-accent/20 bg-accent/5 p-3 text-xs leading-relaxed text-txtDim">
              <span className="font-semibold text-accent">Ambang Multifraktalitas: </span>
              {summary.catatan ?? "Lebar ΔH = 0 menunjukkan proses monofraktal (misal fractional Brownian motion). Rata-rata ΔH > 0.12 membuktikan keberadaan sifat multifraktalitas non-linier pada BTC/USDT."}
            </div>
          </Panel>

          {/* Panel Cross-Check & Landasan Teori KaTeX */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Pemeriksaan Silang H(2) vs R/S */}
            <Panel
              title="Pemeriksaan Silang H(2) vs Hurst R/S"
              subtitle="Verifikasi konsistensi antar-metode estimasi fraktal independen."
            >
              {crossCheck ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3 text-center">
                    <div className="rounded border border-edge bg-panelAlt p-3">
                      <div className="text-2xs text-txtMuted">Korelasi Pearson r</div>
                      <div className="mt-1 font-mono text-lg font-bold text-bullish">
                        {crossCheck.korelasi_hq2_vs_rs > 0 ? "+" : ""}
                        {crossCheck.korelasi_hq2_vs_rs.toFixed(4)}
                      </div>
                      <div className="text-2xs text-txtMuted">N = {crossCheck.n} window</div>
                    </div>
                    <div className="rounded border border-edge bg-panelAlt p-3">
                      <div className="text-2xs text-txtMuted">Selisih Rata-rata (H(2) - R/S)</div>
                      <div className="mt-1 font-mono text-lg font-bold text-txt">
                        {crossCheck.selisih_rata_rata > 0 ? "+" : ""}
                        {crossCheck.selisih_rata_rata.toFixed(4)}
                      </div>
                      <div className="text-2xs text-txtMuted">Perbedaan sistematis</div>
                    </div>
                  </div>
                  <p className="text-xs leading-relaxed text-txtDim">
                    {crossCheck.catatan}
                  </p>
                </div>
              ) : (
                <p className="text-xs text-txtMuted">Data silang tidak cukup untuk dihitung.</p>
              )}
            </Panel>

            {/* Landasan Matematis Multifraktal */}
            <Panel
              title="Landasan Matematis: Fungsi Struktur & H(q)"
              subtitle="Formulasi teori multifraktal berdasarkan PRD & Metodologi Skripsi."
            >
              <div className="space-y-3 text-xs text-txtDim">
                <p>
                  Fungsi struktur momen ke-<Formula tex="q" block={false} /> didefinisikan sebagai ekspektasi dari selisih log-return pada skala horizon <Formula tex="\tau" block={false} />:
                </p>
                <div className="rounded bg-panelAlt px-3 py-1">
                  <Formula tex="S_q(\tau) = \mathbb{E}\left[ |X(t+\tau) - X(t)|^q \right] \sim \tau^{q \, H(q)}" />
                </div>
                <p>
                  Pada proses monofraktal ideal, <Formula tex="H(q) = H" block={false} /> konstan untuk seluruh <Formula tex="q" block={false} />. Pada BTC/USDT, dependensi kurva <Formula tex="H(q)" block={false} /> bervariasi dengan lebar spektrum:
                </p>
                <div className="rounded bg-panelAlt px-3 py-1">
                  <Formula tex="\Delta H = H(1) - H(4)" />
                </div>
                <p className="text-2xs text-txtMuted">
                  Nilai <Formula tex="\Delta H" block={false} /> dihitung secara kausal pada jendela geser <Formula tex="L = 500" block={false} /> bar dan menjadi salah satu fitur multifraktal utama dalam masukan model neural.
                </p>
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

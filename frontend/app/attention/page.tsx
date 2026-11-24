"use client";

import { useEffect, useMemo, useState } from "react";
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
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { AXIS_TICK, GRID_STROKE, TOOLTIP_LABEL_STYLE, TOOLTIP_STYLE } from "@/lib/chart-theme";
import { api, type AiRegimeClass } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN } from "@/lib/regime";

const pct = (v: number) => `${(v * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;
const num = (v: number, d = 3) => v.toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });

/** Fokus model: bobot attention alpha 32 langkah dari model identifikasi resmi (h = 0). */
export default function AttentionPage() {
  const { timeframe } = useAppConfig();
  const att = useApi(() => api.attention(timeframe), [timeframe]);
  // Hasil ablasi (perbandingan varian model) hanya ditampilkan untuk admin, seperti TopNav.
  const [admin, setAdmin] = useState(false);
  useEffect(() => {
    fetch("/api/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((r) => setAdmin(Boolean(r?.admin)))
      .catch(() => setAdmin(false));
  }, []);
  const d = att.data;

  const data = useMemo(
    () =>
      (d?.attention_weights ?? []).map((w) => ({
        step: w.step,
        label: `${w.step}`,
        weight: w.weight,
        offset: w.end_offset_bars,
        time: w.time,
      })),
    [d]
  );
  const uniform = d ? 1 / d.seq_len : 1 / 32;
  const maxStep = data.reduce((best, p) => (p.weight > best.weight ? p : best), { step: 0, weight: 0 } as any);
  const regime = d?.regime as AiRegimeClass | undefined;
  const color = regime ? REGIME_META[regime].color : "#3b82f6";
  const iso = (t: number) => new Date(t * 1000).toISOString().slice(0, 16).replace("T", " ");

  return (
    <div className="space-y-4">
      <PageHeader
        title="Fokus Model (Attention)"
        description="Bobot attention α tiap langkah sekuens statistik persistensi pada jendela terbaru, dari model identifikasi resmi Hybrid Attention-BiLSTM (h = 0), rata-rata 3 seed. Bobot menunjukkan bagian jendela yang paling banyak diberi bobot saat model merangkum sekuens; bukan bukti sebab-akibat."
      />
      <div className="rounded-lg border border-edge bg-surface/60 px-4 py-2.5 text-[12px] leading-relaxed text-txtDim">
        <b className="text-txt">Model identifikasi (h = 0).</b> Bobot di halaman ini berasal dari model yang sama dengan label di
        halaman Ringkasan: model mengidentifikasi regime jendela itu sendiri, bukan menebak regime ke depan. Model prediksi lama
        (SWT, h = 500 bar) tidak lagi dipakai.
      </div>

      <ParameterBar />
      <ApiState loading={att.loading} error={att.error} />

      {d && (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            <div className="rounded-lg border border-edge bg-panel px-4 py-3">
              <div className="metric-label">Regime jendela ini</div>
              <div className="mt-1 text-[15px] font-semibold" style={{ color }}>
                {regime ? REGIME_PLAIN[regime].name : "-"}
              </div>
              <div className="text-2xs text-txtMuted">keyakinan {pct(d.confidence)}</div>
            </div>
            <div className="rounded-lg border border-edge bg-panel px-4 py-3">
              <div className="metric-label">Bar terakhir jendela</div>
              <div className="mt-1 font-mono text-[13px] text-txt">{iso(d.window_time)} UTC</div>
              <div className="text-2xs text-txtMuted">
                jendela ke-{(d.window_index + 1).toLocaleString("id-ID")} dari {d.n_windows.toLocaleString("id-ID")}
              </div>
            </div>
            <div className="rounded-lg border border-edge bg-panel px-4 py-3">
              <div className="metric-label">Entropi ternormalisasi</div>
              <div className="mt-1 font-mono text-[15px] text-txt">{num(d.entropy_normalized)}</div>
              <div className="text-2xs text-txtMuted">1 = bobot rata sempurna</div>
            </div>
            <div className="rounded-lg border border-edge bg-panel px-4 py-3">
              <div className="metric-label">Langkah berbobot terbesar</div>
              <div className="mt-1 font-mono text-[15px] text-txt">
                {maxStep.step} · {num(maxStep.weight, 4)}
              </div>
              <div className="text-2xs text-txtMuted">rata = {num(uniform, 4)}</div>
            </div>
          </div>

          <Panel
            title="Bobot attention α per langkah"
            subtitle={`${d.seq_len} langkah × sub-jendela ${d.sub_window_bars} bar, bergeser ${d.step_bars} bar. Langkah ${d.seq_len} berakhir di bar terakhir jendela.`}
            params={{ model: "hybrid_ps_updated", h: d.horizon_bars, seed: Object.keys(d.per_seed).join("/") }}
          >
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={data} margin={{ top: 8, right: 10, bottom: 20, left: -10 }}>
                <CartesianGrid stroke={GRID_STROKE} vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={AXIS_TICK}
                  interval={1}
                  label={{ value: "langkah sekuens (1 = terlama, 32 = terbaru)", position: "insideBottom", offset: -12, fontSize: 11 }}
                />
                <YAxis tick={AXIS_TICK} width={52} tickFormatter={(v: number) => v.toFixed(3)} />
                <ReferenceLine
                  y={uniform}
                  stroke="#64748b"
                  strokeDasharray="4 3"
                  label={{ value: "rata 1/32", position: "insideTopRight", fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelStyle={TOOLTIP_LABEL_STYLE}
                  labelFormatter={(l: any) => `Langkah ${l}`}
                  formatter={(v: any, _n: any, item: any) => [
                    `${Number(v).toFixed(4)} · berakhir t${item?.payload?.offset ?? 0} bar (${iso(item?.payload?.time ?? 0)})`,
                    "α",
                  ]}
                />
                <Bar dataKey="weight" isAnimationActive={false}>
                  {data.map((p) => (
                    <Cell key={p.step} fill={color} fillOpacity={p.step === maxStep.step ? 1 : 0.55} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="mt-2 text-2xs leading-relaxed text-txtMuted">
              Pada seluruh jendela uji backtest, entropi rata-rata 0,919 (1H) dan 0,878 (4H): bobot cukup menyebar dengan
              kecenderungan lebih besar pada langkah awal jendela.{" "}
              {admin
                ? "Ablasi menunjukkan mengganti attention dengan rata-rata biasa memberi akurasi setara, jadi bobot ini lebih tepat dibaca sebagai penjelasan visual daripada sumber akurasi."
                : "Bobot ini dibaca sebagai penjelasan visual tentang bagian riwayat yang paling diperhatikan model, bukan ukuran pentingnya setiap fitur."}
            </p>
          </Panel>

          <Panel title="Probabilitas tiga kelas" subtitle="Rata-rata softmax 3 seed; jumlahnya 100%.">
            <div className="grid gap-2 sm:grid-cols-3">
              {(Object.entries(d.probabilities) as [AiRegimeClass, number][]).map(([k, v]) => (
                <div key={k} className="rounded border border-edge bg-panelAlt px-3 py-2">
                  <div className="text-[12px] text-txtDim">{REGIME_PLAIN[k].name}</div>
                  <div className="font-mono text-[15px]" style={{ color: REGIME_META[k].color }}>
                    {pct(v)}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-2 text-2xs text-txtMuted">
              Jumlah: {pct(Object.values(d.probabilities).reduce((a, b) => a + b, 0))}
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

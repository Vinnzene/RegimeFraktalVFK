"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_TICK, GRID_STROKE, LEGEND_STYLE, TOOLTIP_LABEL_STYLE, TOOLTIP_STYLE } from "@/lib/chart-theme";

/** Tahap 2: penduga wavelet sebagai penduga label ketiga (khusus admin, tanpa melatih ulang). */

type Score = { labeled_pct: number; accuracy?: number; balanced_accuracy?: number; recall?: Record<string, number>; qwk?: number };
type Estimator = Score & { spearman_true_h: number; thresholds: number[] };
type Synthetic = { scenario: string; n_eval: number; estimators: Record<string, Estimator>; combos: Record<string, Score> };
type Acc = { n: number; accuracy: number | null };
type Btc = {
  thresholds: Record<string, number[]>;
  spearman: { wavelet_vs_rs: number; wavelet_vs_dfa: number; rs_vs_dfa: number };
  test: {
    n: number;
    wavelet_agrees_with_label_pct: number;
    label_vs_wavelet_matrix: number[][];
    model_accuracy: number;
    model_when_wavelet_agrees: Acc;
    model_when_wavelet_disagrees: Acc;
    model_when_all_three_agree: Acc;
    model_otherwise: Acc;
    all_three_agree_pct: number;
  };
};
type ScaleRow = { octaves: number[]; approx_bars: number[] } & Record<string, number | number[]>;
type Payload = {
  generated_at: string;
  source: string;
  wavelet: string;
  dwt_octaves: number[];
  swt_levels: number;
  synthetic: Synthetic[];
  btc: Record<string, Btc>;
  rs_dfa_agreement: Record<string, number>;
  scale_sensitivity: ScaleRow[];
};

const COL = ["#94a3b8", "#a78bfa", "#3b82f6", "#22c55e"];
const C = { good: "#22c55e", bad: "#ef4444", main: "#3b82f6", muted: "#94a3b8", warn: "#f59e0b" };
const SCENARIO: Record<string, string> = { S1: "S1 · fGn murni", S4: "S4 · ekor gemuk + volatilitas + lonjakan", S4k: "S4k · dikalibrasi ke BTC" };
const CLS = ["Pers", "Rand", "Anti"];
const card = "rounded-xl border border-edge bg-panel p-5 shadow-panel";
const pct = (v: number | null | undefined, d = 1) =>
  v == null ? "–" : `${(100 * v).toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d })}%`;
const num = (v: number, d = 3) => v.toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });

function Toggle<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="flex rounded-lg border border-edge p-0.5 text-[12px]">
      {options.map(([k, label]) => (
        <button
          key={k}
          type="button"
          onClick={() => onChange(k)}
          className={`rounded-md px-3 py-1 font-semibold ${value === k ? "bg-txt text-panel" : "text-txtDim hover:text-txt"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function SyntheticSection({ data }: { data: Payload }) {
  const [sc, setSc] = useState(data.synthetic[0]?.scenario ?? "S1");
  const s = data.synthetic.find((x) => x.scenario === sc);
  if (!s) return null;
  const est = Object.entries(s.estimators).map(([name, e]) => ({
    name: name.replace(" (Abry-Veitch)", "").replace(" (energi per level)", ""),
    full: name,
    spearman: e.spearman_true_h,
    akurasi: 100 * (e.accuracy ?? 0),
    random: 100 * (e.recall?.random_like ?? 0),
  }));
  const combos = Object.entries(s.combos).map(([name, c]) => ({ name, berlabel: c.labeled_pct, benar: 100 * (c.accuracy ?? 0), random: 100 * (c.recall?.random_like ?? 0) }));
  return (
    <section className={card}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold text-txt">Data sintetis dengan H diketahui</h2>
        <Toggle value={sc} options={data.synthetic.map((x) => [x.scenario, x.scenario] as [string, string])} onChange={setSc} />
      </div>
      <p className="mt-1 text-[12px] text-txtMuted">
        {SCENARIO[sc] ?? sc} · {s.n_eval.toLocaleString("id-ID")} deret evaluasi · ambang tiap penduga dari kuantil 1/3 dan 2/3 separuh data kalibrasi.
      </p>
      <div className="mt-3 grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="text-[13px] font-semibold text-txtDim">Ketepatan tiap penduga terhadap kelas sebenarnya</h3>
          <div className="h-[260px]">
            <ResponsiveContainer>
              <BarChart data={est} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={GRID_STROKE} vertical={false} />
                <XAxis dataKey="name" tick={AXIS_TICK} interval={0} />
                <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={AXIS_TICK} width={40} />
                <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} formatter={(v: number, k: string) => [`${v.toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`, k]} />
                <Legend wrapperStyle={LEGEND_STYLE} />
                <ReferenceLine y={33.33} stroke={C.bad} strokeDasharray="4 4" />
                <Bar dataKey="akurasi" name="Kelas benar" fill={C.main} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="random" name="Recall random-like" fill={C.warn} radius={[3, 3, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="mt-2 w-full text-[12.5px]">
            <thead className="text-txtMuted">
              <tr className="border-b border-edge">
                <th className="py-1.5 text-left font-medium">Penduga</th>
                <th className="py-1.5 text-right font-medium">Spearman vs H</th>
                <th className="py-1.5 text-right font-medium">Kelas benar</th>
                <th className="py-1.5 text-right font-medium">QWK</th>
              </tr>
            </thead>
            <tbody className="text-txtDim">
              {Object.entries(s.estimators).map(([name, e]) => (
                <tr key={name} className="border-b border-edge/50">
                  <td className="py-1.5 text-txt">{name}</td>
                  <td className="py-1.5 text-right font-mono text-txt">{num(e.spearman_true_h)}</td>
                  <td className="py-1.5 text-right font-mono">{pct(e.accuracy)}</td>
                  <td className="py-1.5 text-right font-mono">{num(e.qwk ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h3 className="text-[13px] font-semibold text-txtDim">Aturan label: cakupan vs ketepatan</h3>
          <div className="h-[260px]">
            <ResponsiveContainer>
              <BarChart data={combos} layout="vertical" margin={{ top: 10, right: 16, bottom: 0, left: 10 }}>
                <CartesianGrid stroke={GRID_STROKE} horizontal={false} />
                <XAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v) => `${v}%`} tick={AXIS_TICK} />
                <YAxis type="category" dataKey="name" width={190} tick={{ ...AXIS_TICK, fontSize: 9 }} />
                <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} formatter={(v: number, k: string) => [`${v.toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`, k]} />
                <Legend wrapperStyle={LEGEND_STYLE} />
                <Bar dataKey="berlabel" name="Jendela berlabel" fill={C.muted} isAnimationActive={false} />
                <Bar dataKey="benar" name="Label benar" fill={C.good} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="mt-2 w-full text-[12.5px]">
            <thead className="text-txtMuted">
              <tr className="border-b border-edge">
                <th className="py-1.5 text-left font-medium">Aturan</th>
                <th className="py-1.5 text-right font-medium">Berlabel</th>
                <th className="py-1.5 text-right font-medium">Benar</th>
                <th className="py-1.5 text-right font-medium">Recall random</th>
              </tr>
            </thead>
            <tbody className="text-txtDim">
              {Object.entries(s.combos).map(([name, c]) => (
                <tr key={name} className="border-b border-edge/50">
                  <td className="py-1.5 text-txt">{name}</td>
                  <td className="py-1.5 text-right font-mono">{c.labeled_pct.toLocaleString("id-ID")}%</td>
                  <td className="py-1.5 text-right font-mono text-txt">{pct(c.accuracy)}</td>
                  <td className="py-1.5 text-right font-mono">{pct(c.recall?.random_like)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function AgreementSection({ data }: { data: Payload }) {
  const rows = Object.entries(data.rs_dfa_agreement).map(([k, v]) => ({
    k: k.replace("sintetis_", "Sintetis ").replace("btc_", "BTC ").toUpperCase().replace("SINTETIS", "Sintetis"),
    rho: v,
    btc: k.startsWith("btc"),
  }));
  return (
    <section className={card}>
      <h2 className="text-[15px] font-semibold text-txt">Seberapa sepakat R/S dan DFA?</h2>
      <p className="mt-1 text-[12px] text-txtMuted">Korelasi Spearman antara nilai R/S dan DFA pada jendela yang sama.</p>
      <div className="mt-3 h-[220px]">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis dataKey="k" tick={AXIS_TICK} />
            <YAxis domain={[0, 1]} tick={AXIS_TICK} width={36} />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} formatter={(v: number) => [num(v), "Spearman"]} />
            <Bar dataKey="rho" name="Spearman R/S vs DFA" fill={C.main} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function BtcSection({ data }: { data: Payload }) {
  const [tf, setTf] = useState<"1h" | "4h">("1h");
  const b = data.btc[tf];
  if (!b) return null;
  const t = b.test;
  const rows = [
    { k: "Semua jendela uji", n: t.n, acc: 100 * t.model_accuracy },
    { k: "Wavelet setuju", n: t.model_when_wavelet_agrees.n, acc: 100 * (t.model_when_wavelet_agrees.accuracy ?? 0) },
    { k: "Wavelet tidak setuju", n: t.model_when_wavelet_disagrees.n, acc: 100 * (t.model_when_wavelet_disagrees.accuracy ?? 0) },
    { k: "Ketiga penduga sepakat", n: t.model_when_all_three_agree.n, acc: 100 * (t.model_when_all_three_agree.accuracy ?? 0) },
    { k: "Selain itu", n: t.model_otherwise.n, acc: 100 * (t.model_otherwise.accuracy ?? 0) },
  ];
  const M = t.label_vs_wavelet_matrix;
  return (
    <section className={card}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold text-txt">BTC/USDT: wavelet terhadap label penelitian</h2>
        <Toggle value={tf} options={[["1h", "1H"], ["4h", "4H"]]} onChange={setTf} />
      </div>
      <p className="mt-1 text-[12px] text-txtMuted">
        Label penelitian dan model tidak diubah. Ambang wavelet dari kuantil data latih ({b.thresholds.wavelet.map((x) => x.toLocaleString("id-ID")).join("; ")}).
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {[
          ["Spearman wavelet vs R/S", num(b.spearman.wavelet_vs_rs)],
          ["Spearman wavelet vs DFA", num(b.spearman.wavelet_vs_dfa)],
          ["Label wavelet = label penelitian", `${t.wavelet_agrees_with_label_pct.toLocaleString("id-ID")}%`],
        ].map(([l, v]) => (
          <div key={l} className="rounded-lg border border-edge bg-surface/40 px-4 py-3">
            <div className="metric-label">{l}</div>
            <div className="mt-1 font-mono text-[20px] text-txt">{v}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="text-[13px] font-semibold text-txtDim">Akurasi model menurut kesepakatan penduga (uji)</h3>
          <div className="h-[260px]">
            <ResponsiveContainer>
              <BarChart data={rows} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={GRID_STROKE} vertical={false} />
                <XAxis dataKey="k" tick={{ ...AXIS_TICK, fontSize: 9 }} interval={0} />
                <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={AXIS_TICK} width={40} />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelStyle={TOOLTIP_LABEL_STYLE}
                  formatter={(v: number, _k: string, p: any) => [`${v.toLocaleString("id-ID", { maximumFractionDigits: 1 })}% (${p.payload.n.toLocaleString("id-ID")} jendela)`, "Akurasi"]}
                />
                <Bar dataKey="acc" name="Akurasi model" fill={C.main} radius={[3, 3, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <h3 className="text-[13px] font-semibold text-txtDim">Label penelitian (baris) vs label wavelet (kolom), jumlah jendela uji</h3>
          <table className="mt-2 w-full table-fixed border-separate border-spacing-1 text-center text-[12px]">
            <thead>
              <tr className="text-2xs text-txtMuted">
                <th className="w-[64px] text-left font-normal">label \ wavelet</th>
                {CLS.map((c) => (
                  <th key={c} className="font-medium">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {M.map((row, i) => {
                const total = row.reduce((a, b2) => a + b2, 0) || 1;
                return (
                  <tr key={i}>
                    <th className="text-left text-2xs font-medium text-txtMuted">{CLS[i]}</th>
                    {row.map((v, j) => {
                      const share = v / total;
                      const col = i === j ? C.good : C.bad;
                      return (
                        <td key={j} className="rounded-md py-2.5 font-mono" style={{ background: `${col}${Math.round(18 + share * 200).toString(16).padStart(2, "0")}` }}>
                          <div className="font-semibold text-txt">{v.toLocaleString("id-ID")}</div>
                          <div className="text-2xs text-txtDim">{pct(share, 0)}</div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function ScaleSection({ data }: { data: Payload }) {
  return (
    <section className={card}>
      <h2 className="text-[15px] font-semibold text-txt">Sensitivitas rentang oktaf wavelet</h2>
      <p className="mt-1 text-[12px] text-txtMuted">
        Konfigurasi utama oktaf {data.dwt_octaves.join("–")} ditetapkan sebelum hasil dilihat. Nilai = korelasi Spearman.
      </p>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-[12.5px]">
          <thead className="text-txtMuted">
            <tr className="border-b border-edge">
              <th className="py-1.5 text-left font-medium">Oktaf (≈ bar)</th>
              <th className="py-1.5 text-right font-medium">S1 vs H</th>
              <th className="py-1.5 text-right font-medium">S4k vs H</th>
              <th className="py-1.5 text-right font-medium">BTC 1H vs R/S</th>
              <th className="py-1.5 text-right font-medium">BTC 1H vs DFA</th>
              <th className="py-1.5 text-right font-medium">BTC 4H vs R/S</th>
              <th className="py-1.5 text-right font-medium">BTC 4H vs DFA</th>
            </tr>
          </thead>
          <tbody className="text-txtDim">
            {data.scale_sensitivity.map((r) => {
              const main = r.octaves[0] === data.dwt_octaves[0] && r.octaves[1] === data.dwt_octaves[1];
              return (
                <tr key={r.octaves.join("-")} className={`border-b border-edge/50 ${main ? "bg-accent/5" : ""}`}>
                  <td className="py-1.5 text-txt">
                    {r.octaves.join("–")} (≈ {r.approx_bars.join("–")}){main && <span className="ml-2 text-2xs text-accent">utama</span>}
                  </td>
                  {["S1_vs_true_h", "S4k_vs_true_h", "btc_1h_vs_rs", "btc_1h_vs_dfa", "btc_4h_vs_rs", "btc_4h_vs_dfa"].map((k) => (
                    <td key={k} className="py-1.5 text-right font-mono">{num(r[k] as number)}</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-2xs text-txtMuted">
        Model memakai 12 energi SWT sebagai fitur. Jika kelak model dilatih dengan label wavelet, ablasi tanpa fitur SWT wajib untuk menghindari sirkularitas.
      </p>
    </section>
  );
}

export default function WaveletPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/wavelet", { cache: "no-store" })
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.error ?? `HTTP ${r.status}`);
        setData(body);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto max-w-[1300px] space-y-4 px-1 pb-10 sm:px-4">
      <header className="pt-2">
        <h1 className="text-[24px] font-bold tracking-tight text-txt">Tahap 2 · Penduga Wavelet</h1>
        <p className="mt-1 text-[12.5px] text-txtMuted">Eksperimen tambahan tanpa melatih ulang; model dan label penelitian tidak diubah.</p>
      </header>
      {error && <p className="rounded-lg border border-bearish/30 bg-bearish/5 px-3 py-2 text-[12.5px] text-bearish">{error}</p>}
      {!data && !error && <div className={card}>Memuat…</div>}
      {data && (
        <>
          <SyntheticSection data={data} />
          <AgreementSection data={data} />
          <BtcSection data={data} />
          <ScaleSection data={data} />
          <p className="text-2xs text-txtMuted">
            {data.source}, {data.generated_at} · wavelet {data.wavelet}, DWT oktaf {data.dwt_octaves.join("–")}, SWT {data.swt_levels} level
          </p>
        </>
      )}
    </div>
  );
}

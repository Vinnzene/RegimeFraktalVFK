"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
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
import { AXIS_TICK, GRID_STROKE, LEGEND_STYLE, TOOLTIP_LABEL_STYLE, TOOLTIP_STYLE } from "@/lib/chart-theme";

/** Diagnosis overfitting/underfitting model final (khusus admin). */

type Split = {
  n: number;
  accuracy: number;
  balanced_accuracy: number;
  macro_f1: number;
  recall: Record<string, number>;
  per_seed_accuracy?: number[];
  mean_confidence?: number;
};
type TfDiag = { seeds: number[]; splits: Record<string, Split>; epochs_per_seed: number[] | null; test_matches_paper: boolean };
type Fold = { fold: number; n_train: number; n_test: number; pct: number; balanced_pct: number; mlp_pct: number };
type Payload = {
  generated_at: string;
  source: string;
  timeframes: Record<string, TfDiag>;
  learning_curve: Record<string, { folds: Fold[]; pooled_pct_ensemble: number; backtest_pct: number }>;
};

const C = { train: "#3b82f6", val: "#a78bfa", test: "#f59e0b", mlp: "#94a3b8", good: "#22c55e", bad: "#ef4444" };
const CLASS_LABEL: Record<string, string> = { persistent: "Persistent", random_like: "Random-like", anti_persistent: "Anti-persistent" };
const SPLIT_LABEL: Record<string, string> = { train: "Latih", validation: "Validasi", test: "Uji" };
const pct = (v: number, d = 1) => `${(100 * v).toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d })}%`;
const pp = (v: number) => `${v > 0 ? "+" : ""}${(100 * v).toLocaleString("id-ID", { maximumFractionDigits: 1 })} poin`;
const card = "rounded-xl border border-edge bg-panel p-5 shadow-panel";

// Aturan praktis yang dipakai untuk label diagnosis.
const OVERFIT_GAP = 0.1;
const WATCH_GAP = 0.05;
const UNDERFIT_BA = 0.75;
const CLASS_WEAK = 0.5;

function diagnose(d: TfDiag) {
  const tr = d.splits.train, te = d.splits.test;
  const gap = tr.accuracy - te.accuracy;
  const gapBa = tr.balanced_accuracy - te.balanced_accuracy;
  // Selisih terbesar dari akurasi dan balanced accuracy yang dipakai.
  const worst = Math.max(gap, gapBa);
  const over = worst > OVERFIT_GAP ? "overfit" : worst > WATCH_GAP ? "watch" : "ok";
  const under = tr.balanced_accuracy < UNDERFIT_BA;
  const weak = Object.entries(tr.recall).filter(([, v]) => v < CLASS_WEAK).map(([k]) => k);
  return { gap, gapBa, over, under, weak };
}

// Kurva ilustrasi: galat latih turun terus, galat uji berbentuk U.
const CONCEPT = Array.from({ length: 41 }, (_, i) => {
  const x = i / 40;
  return { x, latih: 0.55 * Math.exp(-3.2 * x) + 0.04, uji: 0.55 * Math.exp(-3.2 * x) + 0.1 + 0.42 * x * x * x };
});

function Concept() {
  return (
    <section className={card}>
      <h2 className="text-[15px] font-semibold text-txt">Ilustrasi konsep</h2>
      <p className="mt-1 text-[12px] text-txtMuted">Bukan data model; hanya gambaran pola galat latih dan galat uji.</p>
      <div className="mt-3 h-[240px]">
        <ResponsiveContainer>
          <ComposedChart data={CONCEPT} margin={{ top: 10, right: 16, bottom: 18, left: 0 }}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <ReferenceArea x1={0} x2={0.25} fill={C.mlp} fillOpacity={0.08} label={{ value: "Underfitting", position: "insideTop", fill: "rgb(var(--c-txt-dim))", fontSize: 11 }} />
            <ReferenceArea x1={0.25} x2={0.55} fill={C.good} fillOpacity={0.1} label={{ value: "Pas", position: "insideTop", fill: "rgb(var(--c-txt-dim))", fontSize: 11 }} />
            <ReferenceArea x1={0.55} x2={1} fill={C.bad} fillOpacity={0.08} label={{ value: "Overfitting", position: "insideTop", fill: "rgb(var(--c-txt-dim))", fontSize: 11 }} />
            <XAxis dataKey="x" type="number" domain={[0, 1]} tick={false} label={{ value: "kompleksitas model / lama pelatihan →", position: "insideBottom", offset: -6, fontSize: 11, fill: "rgb(var(--c-txt-muted))" }} />
            <YAxis tick={false} width={14} label={{ value: "galat", angle: -90, position: "insideLeft", fontSize: 11, fill: "rgb(var(--c-txt-muted))" }} />
            <Area dataKey="uji" stroke="none" fill={C.test} fillOpacity={0.06} legendType="none" tooltipType="none" isAnimationActive={false} />
            <Line dataKey="latih" name="Galat latih" stroke={C.train} strokeWidth={2.5} dot={false} isAnimationActive={false} />
            <Line dataKey="uji" name="Galat uji" stroke={C.test} strokeWidth={2.5} dot={false} isAnimationActive={false} />
            <Legend wrapperStyle={LEGEND_STYLE} verticalAlign="top" align="right" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 grid gap-2 text-[12.5px] sm:grid-cols-3">
        <div className="rounded-lg border border-edge bg-surface/40 px-3 py-2"><b className="text-txt">Underfitting</b><br /><span className="text-txtDim">latih rendah, uji juga rendah</span></div>
        <div className="rounded-lg border border-edge bg-surface/40 px-3 py-2"><b className="text-txt">Pas</b><br /><span className="text-txtDim">latih ≈ uji, keduanya baik</span></div>
        <div className="rounded-lg border border-edge bg-surface/40 px-3 py-2"><b className="text-txt">Overfitting</b><br /><span className="text-txtDim">latih tinggi, uji jauh lebih rendah</span></div>
      </div>
    </section>
  );
}

function Verdict({ d }: { d: TfDiag }) {
  const g = diagnose(d);
  const overText = { overfit: "Ada indikasi overfitting", watch: "Overfitting ringan, perlu diawasi", ok: "Tidak ada tanda overfitting" }[g.over];
  const overCol = g.over === "overfit" ? "text-bearish" : g.over === "watch" ? "text-warn" : "text-bullish";
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="rounded-lg border border-edge bg-surface/40 px-4 py-3">
        <div className="metric-label">Overfitting</div>
        <div className={`mt-1 text-[18px] font-semibold ${overCol}`}>{overText}</div>
        <div className="text-[12px] text-txtDim">
          Akurasi latih − uji: <b className="text-txt">{pp(g.gap)}</b> · balanced acc.: <b className="text-txt">{pp(g.gapBa)}</b>
        </div>
        <div className="text-2xs text-txtMuted">
          aturan: selisih terbesar &gt; {OVERFIT_GAP * 100} poin = overfitting, {WATCH_GAP * 100}–{OVERFIT_GAP * 100} poin = ringan
        </div>
      </div>
      <div className="rounded-lg border border-edge bg-surface/40 px-4 py-3">
        <div className="metric-label">Underfitting</div>
        <div className={`mt-1 text-[18px] font-semibold ${g.under ? "text-warn" : "text-bullish"}`}>
          {g.under ? "Underfitting sebagian" : "Data latih dikuasai"}
        </div>
        <div className="text-[12px] text-txtDim">
          Balanced acc. latih <b className="text-txt">{pct(d.splits.train.balanced_accuracy)}</b>
          {g.weak.length > 0 && <> · kelas lemah di data latih: <b className="text-txt">{g.weak.map((k) => CLASS_LABEL[k]).join(", ")}</b></>}
        </div>
        <div className="text-2xs text-txtMuted">aturan: balanced acc. latih &lt; {UNDERFIT_BA * 100}% atau recall kelas latih &lt; {CLASS_WEAK * 100}%</div>
      </div>
    </div>
  );
}

function SplitChart({ d }: { d: TfDiag }) {
  const rows = [
    { m: "Akurasi", ...Object.fromEntries(["train", "validation", "test"].map((k) => [k, d.splits[k].accuracy])) },
    { m: "Balanced acc.", ...Object.fromEntries(["train", "validation", "test"].map((k) => [k, d.splits[k].balanced_accuracy])) },
    { m: "Macro-F1", ...Object.fromEntries(["train", "validation", "test"].map((k) => [k, d.splits[k].macro_f1])) },
  ];
  return (
    <div className="h-[260px]">
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis dataKey="m" tick={AXIS_TICK} />
          <YAxis domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={AXIS_TICK} width={40} />
          <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} formatter={(v: number, k: string) => [pct(v), SPLIT_LABEL[k] ?? k]} />
          <Legend wrapperStyle={LEGEND_STYLE} formatter={(k: string) => SPLIT_LABEL[k] ?? k} />
          <ReferenceLine y={1 / 3} stroke={C.bad} strokeDasharray="4 4" />
          <Bar dataKey="train" fill={C.train} radius={[3, 3, 0, 0]} />
          <Bar dataKey="validation" fill={C.val} radius={[3, 3, 0, 0]} />
          <Bar dataKey="test" fill={C.test} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ClassChart({ d }: { d: TfDiag }) {
  const rows = Object.keys(CLASS_LABEL).map((c) => ({
    c: CLASS_LABEL[c],
    ...Object.fromEntries(["train", "validation", "test"].map((k) => [k, d.splits[k].recall[c]])),
  }));
  return (
    <div className="h-[260px]">
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis dataKey="c" tick={AXIS_TICK} />
          <YAxis domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={AXIS_TICK} width={40} />
          <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} formatter={(v: number, k: string) => [pct(v), SPLIT_LABEL[k] ?? k]} />
          <Legend wrapperStyle={LEGEND_STYLE} formatter={(k: string) => SPLIT_LABEL[k] ?? k} />
          <ReferenceLine y={CLASS_WEAK} stroke={C.mlp} strokeDasharray="4 4" />
          <Bar dataKey="train" fill={C.train} radius={[3, 3, 0, 0]} />
          <Bar dataKey="validation" fill={C.val} radius={[3, 3, 0, 0]} />
          <Bar dataKey="test" fill={C.test} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function LearningCurve({ lc }: { lc: Payload["learning_curve"][string] }) {
  const rows = lc.folds.map((f) => ({ ...f, label: `F${f.fold} · ${f.n_train.toLocaleString("id-ID")}` }));
  return (
    <div className="h-[280px]">
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 10, right: 44, bottom: 18, left: 0 }}>
          <CartesianGrid stroke={GRID_STROKE} />
          <XAxis dataKey="label" tick={AXIS_TICK} label={{ value: "fold · jumlah jendela latih", position: "insideBottom", offset: -8, fontSize: 11, fill: "rgb(var(--c-txt-muted))" }} />
          <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={AXIS_TICK} width={40} />
          <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} formatter={(v: number, k: string) => [`${v.toLocaleString("id-ID")}%`, k]} />
          <Legend wrapperStyle={LEGEND_STYLE} verticalAlign="top" align="right" />
          <ReferenceLine y={33.33} stroke={C.bad} strokeDasharray="4 4" label={{ value: "tebakan acak", position: "insideBottomRight", fontSize: 10, fill: C.bad }} />
          <ReferenceLine y={lc.backtest_pct} stroke={C.test} strokeDasharray="6 3" label={{ value: `backtest ${lc.backtest_pct.toLocaleString("id-ID")}%`, position: "insideTopLeft", fontSize: 10, fill: C.test }} />
          <Line dataKey="pct" name="Akurasi Hybrid" stroke={C.train} strokeWidth={2.5} dot={{ r: 4 }} isAnimationActive={false} />
          <Line dataKey="balanced_pct" name="Balanced acc. Hybrid" stroke={C.val} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
          <Line dataKey="mlp_pct" name="Akurasi MLP" stroke={C.mlp} strokeWidth={1.5} strokeDasharray="5 4" dot={{ r: 3 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function FittingPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tf, setTf] = useState<"1h" | "4h">("1h");

  useEffect(() => {
    fetch("/api/admin/fitting", { cache: "no-store" })
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.error ?? `HTTP ${r.status}`);
        setData(body);
      })
      .catch((e) => setError(e.message));
  }, []);

  const d = data?.timeframes[tf];
  const lc = data?.learning_curve[tf];
  const extra = d?.splits.train_extra_eth_bnb;
  const tableRows = useMemo(() => (d ? (["train", "validation", "test"] as const).map((k) => ({ k, s: d.splits[k] })) : []), [d]);

  return (
    <div className="mx-auto max-w-[1300px] space-y-4 px-1 pb-10 sm:px-4">
      <header className="flex flex-wrap items-end justify-between gap-3 pt-2">
        <h1 className="text-[24px] font-bold tracking-tight text-txt">Diagnosis Overfitting / Underfitting</h1>
        <div className="flex rounded-lg border border-edge p-0.5">
          {(["1h", "4h"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTf(t)}
              className={`rounded-md px-4 py-1.5 text-[13px] font-semibold ${tf === t ? "bg-txt text-panel" : "text-txtDim hover:text-txt"}`}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>
      </header>
      {error && <p className="rounded-lg border border-bearish/30 bg-bearish/5 px-3 py-2 text-[12.5px] text-bearish">{error}</p>}
      {!data && !error && <div className={card}>Memuat…</div>}

      <Concept />

      {d && lc && (
        <>
          <section className={card}>
            <h2 className="text-[15px] font-semibold text-txt">Diagnosis model final {tf.toUpperCase()}</h2>
            <div className="mt-3">
              <Verdict d={d} />
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div>
                <h3 className="text-[13px] font-semibold text-txtDim">
                  Latih vs validasi vs uji <span className="font-normal text-txtMuted">(garis merah = tebakan acak 33%)</span>
                </h3>
                <SplitChart d={d} />
              </div>
              <div>
                <h3 className="text-[13px] font-semibold text-txtDim">
                  Recall per kelas <span className="font-normal text-txtMuted">(garis abu-abu = 50%)</span>
                </h3>
                <ClassChart d={d} />
              </div>
            </div>
          </section>

          <section className={card}>
            <h2 className="text-[15px] font-semibold text-txt">Kurva belajar walk-forward {tf.toUpperCase()}</h2>
            <LearningCurve lc={lc} />
          </section>

          <section className={card}>
            <h2 className="text-[15px] font-semibold text-txt">Angka lengkap</h2>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-[12.5px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1.5 text-left font-medium">Bagian data</th>
                    <th className="py-1.5 text-right font-medium">Jendela</th>
                    <th className="py-1.5 text-right font-medium">Akurasi</th>
                    <th className="py-1.5 text-right font-medium">Balanced acc.</th>
                    <th className="py-1.5 text-right font-medium">Macro-F1</th>
                    <th className="py-1.5 text-right font-medium">Recall P / R / A</th>
                    <th className="py-1.5 text-right font-medium">Akurasi per seed</th>
                  </tr>
                </thead>
                <tbody className="text-txtDim">
                  {tableRows.map(({ k, s }) => (
                    <tr key={k} className="border-b border-edge/50">
                      <td className="py-1.5 font-semibold text-txt">{SPLIT_LABEL[k]}</td>
                      <td className="py-1.5 text-right font-mono">{s.n.toLocaleString("id-ID")}</td>
                      <td className="py-1.5 text-right font-mono text-txt">{pct(s.accuracy, 2)}</td>
                      <td className="py-1.5 text-right font-mono">{pct(s.balanced_accuracy, 2)}</td>
                      <td className="py-1.5 text-right font-mono">{s.macro_f1.toLocaleString("id-ID", { minimumFractionDigits: 3 })}</td>
                      <td className="py-1.5 text-right font-mono">
                        {Object.keys(CLASS_LABEL).map((c) => pct(s.recall[c], 0)).join(" / ")}
                      </td>
                      <td className="py-1.5 text-right font-mono">{(s.per_seed_accuracy ?? []).map((v) => pct(v, 1)).join(" · ")}</td>
                    </tr>
                  ))}
                  {extra && (
                    <tr className="border-b border-edge/50">
                      <td className="py-1.5 font-semibold text-txt">Latih tambahan ETH/BNB</td>
                      <td className="py-1.5 text-right font-mono">{extra.n.toLocaleString("id-ID")}</td>
                      <td className="py-1.5 text-right font-mono text-txt">{pct(extra.accuracy, 2)}</td>
                      <td className="py-1.5 text-right font-mono">{pct(extra.balanced_accuracy, 2)}</td>
                      <td className="py-1.5 text-right font-mono">{extra.macro_f1.toLocaleString("id-ID", { minimumFractionDigits: 3 })}</td>
                      <td className="py-1.5 text-right font-mono">{Object.keys(CLASS_LABEL).map((c) => pct(extra.recall[c], 0)).join(" / ")}</td>
                      <td className="py-1.5 text-right font-mono">–</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-2xs text-txtMuted">
              Model final (seed {d.seeds.join(", ")}, ensemble) tanpa dilatih ulang · berhenti di epoch {(d.epochs_per_seed ?? []).join(", ")} (early stopping) ·
              uji {d.test_matches_paper ? "sama dengan naskah" : "BERBEDA dari naskah"} · {data!.source}, {data!.generated_at}
            </p>
          </section>
        </>
      )}
    </div>
  );
}

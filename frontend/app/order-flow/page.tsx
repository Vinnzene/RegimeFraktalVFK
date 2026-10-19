"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
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
import { api } from "@/lib/api-client";
import { AXIS_TICK, GRID_STROKE, TOOLTIP_LABEL_STYLE, TOOLTIP_STYLE } from "@/lib/chart-theme";

const CHART_AXIS = { tick: AXIS_TICK, stroke: "#252c37" };
const CHART_GRID = { stroke: GRID_STROKE, strokeDasharray: "3 3" };
const CHART_TOOLTIP = { contentStyle: TOOLTIP_STYLE, labelStyle: TOOLTIP_LABEL_STYLE };
import { REGIME_META, REGIME_PLAIN, regimeLabel, type Regime } from "@/lib/regime";

const MAIN = ["persistent", "random_like", "anti_persistent"];
const METRICS: [string, string][] = [
  ["accuracy", "Acc"],
  ["balanced_accuracy", "BA"],
  ["macro_f1", "Macro F1"],
  ["kappa", "Kappa"],
  ["mcc", "MCC"],
];
const STAT_LABEL: Record<string, string> = {
  ofi_mean: "Rata-rata OFI",
  ofi_abs_mean: "Rata-rata |OFI|",
  ofi_sign_persist: "Kegigihan tanda OFI",
  ofi_ac1: "Autokorelasi OFI lag-1",
  ofi_ret_agree: "OFI searah return",
  cvd_norm_end: "CVD (z) akhir window",
  cvd_slope: "Kemiringan CVD / volume",
};

const fmt = (v: any, d = 4) => (typeof v === "number" ? v.toFixed(d) : "â€”");
const iso = (t: number) => new Date(t * 1000).toISOString().slice(0, 16).replace("T", " ");

function RegimeStrip({ rows, field, label }: { rows: any[]; field: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-24 shrink-0 text-right text-[11px] text-txtDim">{label}</span>
      <div className="flex h-4 flex-1 overflow-hidden rounded">
        {rows.map((r, i) => (
          <div
            key={i}
            className={r[field] === "uncertain_rule" ? "pattern-diagonal" : ""}
            style={{
              flex: 1,
              backgroundColor:
                r[field] === "uncertain_rule" ? "transparent" : REGIME_META[r[field] as Regime]?.color ?? "#252c37",
            }}
            title={`${iso(r.time)} Â· ${REGIME_PLAIN[r[field] as Regime]?.name ?? r[field]}`}
          />
        ))}
      </div>
    </div>
  );
}

export default function OrderFlowPage() {
  const { timeframe } = useAppConfig();
  const res = useApi(() => api.orderflowAblation(timeframe), [timeframe]);
  const tl = useApi(() => api.orderflowTimeline(timeframe, 600), [timeframe]);

  const ab = res.data?.ablation;
  const an = res.data?.analysis;
  const rows: any[] = tl.data?.rows ?? [];
  const models: string[] = tl.data?.models ?? [];

  const chartRows = useMemo(
    () => rows.map((r) => ({ ...r, label: iso(r.time).slice(5) })),
    [rows]
  );

  return (
    <div className="space-y-4">
      <PageHeader
        title="Order Flow (OFI & CVD)"
        description="Menguji apakah informasi order flow â€” tekanan beli vs jual â€” membantu Attention-BiLSTM mengenali regime Hurst-DFA. Model A memakai SWT saja; B menambah OFI; C menambah CVD; D menambah keduanya. Hurst dan DFA tetap hanya membentuk label, tidak pernah menjadi input."
      />
      <ParameterBar />

      <div className="rounded border border-persistent/30 bg-persistent/5 px-3 py-2 text-[12px] leading-relaxed text-txtDim">
        <b className="text-txt">OFI</b> = (volume beli âˆ’ volume jual) / total volume per candle: positif berarti
        pembeli agresif mendominasi. <b className="text-txt">CVD</b> = akumulasi selisih beliâˆ’jual, dinormalisasi
        z-score terhadap window yang sama dengan window label. Volume beli/jual berasal dari transaksi taker
        (buyer/seller-initiated), terverifikasi identik dengan agregasi aggTrades Binance.
      </div>

      <ApiState loading={res.loading} error={res.error} />

      {ab && !ab.available && (
        <div className="rounded border border-warn/40 bg-warn/10 px-3 py-2 text-[12px] text-warn">
          Hasil ablation {timeframe.toUpperCase()} belum ada. Jalankan:{" "}
          <span className="font-mono">{ab.perintah}</span>
        </div>
      )}

      {ab?.available && (
        <Panel
          title="Perbandingan Model A / B / C / D (data test)"
          subtitle={`Rata-rata Â± simpangan baku atas ${ab.seeds.length} seed. Split, purge, seed, dan hyperparameter identik; hanya input order flow yang berbeda.`}
          params={{
            n_train: ab.n.train,
            n_val: ab.n.validation,
            n_test: ab.n.test,
            purge: `${ab.purge_bars} bar`,
            window_CVD: ab.cvd_window,
          }}
        >
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="text-left">Model</th>
                  <th>OFI</th>
                  <th>CVD</th>
                  {METRICS.map(([, l]) => (
                    <th key={l} className="text-right">{l}</th>
                  ))}
                  <th className="text-right" title="Jumlah pergantian regime per 100 window pada rentang test">
                    Transisi/100
                  </th>
                  <th className="text-right" title="Porsi prediksi di bawah ambang keyakinan Ï„">Ragu (Ï„)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(ab.models).map(([k, m]: any) => (
                  <tr key={k}>
                    <td className="font-sans text-txt">
                      <b>{k}</b> <span className="text-txtMuted">{m.name}</span>
                    </td>
                    <td className="text-center">{m.ofi ? "Ya" : "â€”"}</td>
                    <td className="text-center">{m.cvd ? "Ya" : "â€”"}</td>
                    {METRICS.map(([key]) => (
                      <td key={key} className="text-right">
                        <span className="text-txt">{fmt(m.summary[key]?.mean)}</span>
                        <span className="text-txtMuted"> Â±{fmt(m.summary[key]?.std, 3)}</span>
                      </td>
                    ))}
                    <td className="text-right">{fmt(m.summary.transitions_per_100?.mean, 2)}</td>
                    <td className="text-right">
                      {((m.summary.uncertain_lowconf_share?.mean ?? 0) * 100).toFixed(1)}%
                    </td>
                  </tr>
                ))}
                <tr className="text-txtMuted">
                  <td className="font-sans" colSpan={3 + METRICS.length}>
                    Referensi Hurst-DFA (label) pada rentang test
                  </td>
                  <td className="text-right">{fmt(ab.hurst_dfa_test_range_sequence?.transitions_per_100, 2)}</td>
                  <td />
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {Object.entries(ab.comparisons_vs_A ?? {}).map(([k, list]: any) => (
              <div key={k} className="rounded border border-edge bg-surface p-3 text-[11px]">
                <div className="font-medium text-txt">Model {k} vs A</div>
                {list.map((c: any) => (
                  <div key={c.seed} className="mt-1 font-mono text-txtDim">
                    seed {c.seed}: Î”F1 {fmt(c.bootstrap_macro_f1_diff?.mean_diff, 3)} [
                    {fmt(c.bootstrap_macro_f1_diff?.ci95?.[0], 3)}, {fmt(c.bootstrap_macro_f1_diff?.ci95?.[1], 3)}]
                    Â· McNemar p={fmt(c.mcnemar?.p_value, 3)}
                  </div>
                ))}
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-txtMuted">
            Î”F1 = selisih macro F1 terhadap Model A dengan interval kepercayaan 95% dari block bootstrap. Interval
            yang memuat 0 berarti perbedaan belum dapat dibedakan dari variasi acak.
          </p>

          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {Object.entries(ab.models).map(([k, m]: any) => {
              const cm: number[][] = m.confusion_matrix_sum_seeds;
              return (
                <div key={k} className="rounded border border-edge p-2">
                  <div className="mb-1 text-[11px] font-medium text-txt">Confusion matrix â€” Model {k}</div>
                  <table className="w-full text-[10px] tabular-nums">
                    <thead>
                      <tr className="text-txtMuted">
                        <th className="text-left">aktual \ prediksi</th>
                        {ab.classes.map((c: string) => (
                          <th key={c} className="text-right">{regimeLabel(c).split(" ")[0].slice(0, 5)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {cm.map((row, i) => {
                        const tot = row.reduce((a, b) => a + b, 0) || 1;
                        return (
                          <tr key={i}>
                            <td className="text-txtDim">{regimeLabel(ab.classes[i])}</td>
                            {row.map((v, j) => (
                              <td
                                key={j}
                                className="text-right font-mono"
                                style={{ backgroundColor: `rgba(74,158,255,${(v / tot) * 0.6})` }}
                              >
                                {((v / tot) * 100).toFixed(0)}%
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              );
            })}
          </div>
        </Panel>
      )}

      <Panel
        title="Timeline gabungan (rentang test)"
        subtitle="Harga, regime Hurst-DFA (referensi), regime hasil Model Aâ€“D (rata-rata seed), OFI, dan CVD pada timestamp yang sama."
      >
        <ApiState loading={tl.loading} error={tl.error} />
        {tl.data && !tl.data.available && (
          <div className="text-[12px] text-txtMuted">
            Belum ada. Jalankan <span className="font-mono">{tl.data.perintah}</span>
          </div>
        )}
        {rows.length > 0 && (
          <div className="space-y-2">
            <div className="h-44">
              <ResponsiveContainer>
                <LineChart data={chartRows} syncId="of" margin={{ left: 50, right: 8, top: 4, bottom: 0 }}>
                  <CartesianGrid {...CHART_GRID} />
                  <XAxis dataKey="label" hide />
                  <YAxis {...CHART_AXIS} domain={["auto", "auto"]} width={60} />
                  <Tooltip {...CHART_TOOLTIP} />
                  <Line dataKey="close" name="Harga" stroke="#eaecef" dot={false} strokeWidth={1.2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-1 pl-[2px]">
              <RegimeStrip rows={rows} field="hurst_dfa_regime" label="Hurst-DFA" />
              {models.map((m) => (
                <RegimeStrip key={m} rows={rows} field={`model_${m}`} label={`Model ${m}`} />
              ))}
            </div>
            <div className="h-28">
              <ResponsiveContainer>
                <BarChart data={chartRows} syncId="of" margin={{ left: 50, right: 8, top: 4, bottom: 0 }}>
                  <CartesianGrid {...CHART_GRID} />
                  <XAxis dataKey="label" hide />
                  <YAxis {...CHART_AXIS} width={60} />
                  <Tooltip {...CHART_TOOLTIP} />
                  <ReferenceLine y={0} stroke="#5c6673" />
                  <Bar dataKey="ofi" name="OFI" isAnimationActive={false}>
                    {chartRows.map((r, i) => (
                      <Cell key={i} fill={r.ofi >= 0 ? "#2ebd85" : "#f6465d"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="h-32">
              <ResponsiveContainer>
                <LineChart data={chartRows} syncId="of" margin={{ left: 50, right: 8, top: 4, bottom: 0 }}>
                  <CartesianGrid {...CHART_GRID} />
                  <XAxis dataKey="label" {...CHART_AXIS} minTickGap={60} />
                  <YAxis {...CHART_AXIS} width={60} />
                  <Tooltip {...CHART_TOOLTIP} />
                  <ReferenceLine y={0} stroke="#5c6673" />
                  <Line dataKey="cvd_norm" name="CVD (z)" stroke="#b07cf5" dot={false} strokeWidth={1.2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="text-[11px] text-txtMuted">
              Baris berarsir = Uncertain (rule): Hurst dan DFA tidak sepakat; tidak dipakai untuk training/evaluasi
              tetapi tetap diprediksi model. OFI hijau = tekanan beli, merah = tekanan jual.
            </div>
          </div>
        )}
      </Panel>

      <Panel
        title="Regime vs distribusi OFI / CVD"
        subtitle="Statistik order flow di dalam tiap window, dikelompokkan menurut label Hurst-DFA. Tidak ada pola yang diasumsikan; semuanya dari data."
      >
        {an && !an.available && (
          <div className="text-[12px] text-txtMuted">
            Belum ada. Jalankan <span className="font-mono">{an.perintah}</span>
          </div>
        )}
        {an?.available && (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="text-left">Statistik (median)</th>
                    {MAIN.map((r) => (
                      <th key={r} className="text-right" style={{ color: REGIME_META[r as Regime].color }}>
                        {regimeLabel(r)}
                      </th>
                    ))}
                    <th className="text-right" title="Effect size Kruskal-Wallis">ÎµÂ²</th>
                    <th className="text-right" title="p-value uji permutasi blok (menjaga autokorelasi)">p (blok)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(an.tests).map((k) => {
                    const t = an.tests[k];
                    const strong = t.epsilon_squared >= 0.01 && t.p_value_block_permutation < 0.05;
                    return (
                      <tr key={k}>
                        <td className="font-sans text-txtDim">{STAT_LABEL[k] ?? k}</td>
                        {MAIN.map((r) => (
                          <td key={r} className="text-right">
                            {fmt(an.per_regime[r]?.[k]?.median)}
                          </td>
                        ))}
                        <td className={`text-right ${strong ? "text-txt" : ""}`}>{fmt(t.epsilon_squared)}</td>
                        <td className={`text-right ${strong ? "text-txt" : ""}`}>
                          {fmt(t.p_value_block_permutation, 3)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-3 h-48">
              <ResponsiveContainer>
                <BarChart
                  data={MAIN.map((r) => ({
                    regime: REGIME_PLAIN[r as Regime].name,
                    key: r,
                    pos: (an.per_regime[r]?.ofi_mean?.share_positive ?? 0) * 100,
                  }))}
                  margin={{ left: 10, right: 10, top: 10 }}
                >
                  <CartesianGrid {...CHART_GRID} />
                  <XAxis dataKey="regime" {...CHART_AXIS} />
                  <YAxis {...CHART_AXIS} unit="%" domain={[0, 100]} />
                  <Tooltip {...CHART_TOOLTIP} />
                  <ReferenceLine y={50} stroke="#5c6673" strokeDasharray="4 4" />
                  <Bar dataKey="pos" name="% window dengan OFI rata-rata > 0">
                    {MAIN.map((r) => (
                      <Cell key={r} fill={REGIME_META[r as Regime].color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-txtMuted">
              ÎµÂ² &lt; 0,01 dapat diabaikan; 0,01â€“0,06 kecil; 0,06â€“0,14 sedang. p (blok) memakai permutasi melingkar
              label sehingga autokorelasi antar-window yang tumpang tindih tetap terjaga â€” p-value uji klasik akan
              terlalu optimistis. Baris tebal = efek â‰¥ kecil dan p &lt; 0,05.
            </p>
          </>
        )}
      </Panel>
    </div>
  );
}

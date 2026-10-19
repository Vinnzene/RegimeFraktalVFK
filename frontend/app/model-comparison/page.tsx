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
import ConsistencyPanel from "@/components/ConsistencyPanel";
import HorizonStudyPanel from "@/components/HorizonStudyPanel";
import IdentificationPanel from "@/components/IdentificationPanel";
import WalkForwardPanel from "@/components/WalkForwardPanel";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import RegimeLegend from "@/components/RegimeLegend";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";
import { applyTau, REGIME_META, regimeLabel, type Regime } from "@/lib/regime";

const MODEL_ORDER = ["persistence", "rule_based", "swt_bilstm", "swt_attention_bilstm"];

export default function ModelComparisonPage() {
  const { timeframe, config } = useAppConfig();
  const [modelKey, setModelKey] = useState("swt_attention_bilstm");
  const [tau, setTau] = useState<number | null>(null);

  const compare = useApi(() => api.compare(timeframe), [timeframe]);
  const raw = useApi(() => api.rawProbabilities(timeframe, modelKey), [timeframe, modelKey]);

  const effectiveTau = tau ?? config?.model.tau ?? 0.5;

  // Slider τ menghitung ulang label langsung dari probabilitas mentah di sisi
  // frontend — tidak ada request ulang ke backend.
  const tauDistribution = useMemo(() => {
    const series = raw.data?.series ?? [];
    const counts: Record<string, number> = {};
    series.forEach((row: any) => {
      const { finalLabel } = applyTau(row.probabilities, effectiveTau);
      counts[finalLabel] = (counts[finalLabel] ?? 0) + 1;
    });
    const total = series.length || 1;
    return Object.entries(counts)
      .map(([k, v]) => ({ key: k, count: v, share: v / total }))
      .sort((a, b) => b.count - a.count);
  }, [raw.data, effectiveTau]);

  const curves = compare.data?.training_curves ?? {};
  const lossData = useMemo(() => {
    const bilstm = curves.swt_bilstm?.val_loss ?? [];
    const attn = curves.swt_attention_bilstm?.val_loss ?? [];
    const n = Math.max(bilstm.length, attn.length);
    return Array.from({ length: n }, (_, i) => ({
      epoch: i + 1,
      swt_bilstm: bilstm[i],
      swt_attention_bilstm: attn[i],
    }));
  }, [curves]);

  const models = compare.data?.models ?? {};
  // Ambil dari lapis argmax: baseline selalu memberi label tegas, jadi angka
  // inilah pembanding yang setara untuk seluruh model.
  const persistenceBA =
    models.persistence?.secondary_metrics?.argmax?.balanced_accuracy;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Model Comparison"
        description="Empat baris pembanding: Baseline Persistence (naif), Baseline 1 (rule-based), Baseline 2 (SWT+BiLSTM), dan model usulan (SWT+Attention-BiLSTM). Fokus penilaian ada pada kestabilan regime, pola transisi, dan konsistensi — bukan pada akurasi."
      />

      <ParameterBar />
      <ApiState loading={compare.loading} error={compare.error} />

      {!compare.loading && !compare.error && (
        <>
          {compare.data?.any_trained === false ? (
            <div className="rounded border border-warn/40 bg-warn/10 px-3 py-2 text-[11px] leading-relaxed text-warn">
              <span className="font-semibold">Model belum dilatih. </span>
              Artefak di <span className="font-mono">ml/artifacts/</span> belum tersedia,
              sehingga probabilitas pada halaman ini berasal dari stand-in deterministik —
              bukan hasil pembelajaran. Jalankan{" "}
              <span className="font-mono">ml/src/train.py</span> lebih dulu.
            </div>
          ) : (
            <div className="rounded border border-edge bg-surface/50 px-3 py-2 text-[11px] leading-relaxed text-txtDim">
              <span className="font-semibold text-txtDim">
                Cara membaca angka pada halaman ini.{" "}
              </span>
              Model neural tidak selalu melewati ambang τ, sehingga sebagian window tidak
              mendapat label tegas. Karena itu setiap metrik dilaporkan bersama{" "}
              <span className="text-txtDim">cakupan</span>: kolom Argmax mengukur daya
              diskriminasi tanpa ambang, kolom Setelah τ hanya menghitung window yang
              dijawab. Cakupan rendah berarti model memilih diam, bukan menjawab salah.
              <div className="mt-1.5">
                Horizon yang diuji h = {compare.data?.h_bars} bar, sekitar{" "}
                {Math.round((compare.data?.h_bars ?? 0) / 24)} hari pada timeframe 1H —
                cukup jauh ke depan, sehingga nilai yang mendekati tebakan seragam (BA ≈
                0.333) merupakan hasil yang wajar dan tetap layak dilaporkan. Seluruh angka
                diperoleh setelah fitur SWT dinormalisasi memakai statistik dari subset
                training saja, bobot kelas diseimbangkan, dan purge gap diterapkan di batas
                split.
              </div>
            </div>
          )}

          <div className="rounded border border-persistent/40 bg-persistent/10 px-3 py-2 text-[11px] leading-relaxed text-txtDim">
            <span className="font-semibold">Baca Baseline Persistence lebih dulu. </span>
            Tebakan naif &quot;regime t+h = regime t&quot; mencapai balanced accuracy{" "}
            <span className="font-mono text-txt">{persistenceBA ?? "—"}</span> pada
            kolom Argmax. Model hanya bermakna bila mengungguli angka ini secara konsisten.
            Pada deret yang regimenya bertahan lama, angka tinggi saja tidak membuktikan apa
            pun.
          </div>

          <IdentificationPanel timeframe={timeframe} />
          <WalkForwardPanel timeframe={timeframe} />
          <ConsistencyPanel timeframe={timeframe} />

          <Panel
            title="Validation Loss per Model"
            subtitle={
              compare.data?.curves_from_artifact
                ? "Kurva nyata dari metadata artefak training. Rule-based tidak punya kurva loss karena bukan model berbasis gradien."
                : "Kurva ilustratif — artefak training belum tersedia."
            }
            params={{
              h_bar: compare.data?.h_bars,
              h_window: compare.data?.h_windows,
              tau: effectiveTau.toFixed(2),
            }}
          >
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={lossData} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
                <CartesianGrid stroke="rgba(30,41,55,0.7)" />
                <XAxis dataKey="epoch" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
                <Tooltip
                  contentStyle={{
                    background: "#0b1017",
                    border: "1px solid #1e2937",
                    fontSize: 11,
                    borderRadius: 6,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line
                  type="monotone"
                  dataKey="swt_bilstm"
                  name="SWT + BiLSTM"
                  stroke="#94a3b8"
                  dot={false}
                  strokeWidth={1.5}
                />
                <Line
                  type="monotone"
                  dataKey="swt_attention_bilstm"
                  name="SWT + Attention-BiLSTM"
                  stroke="#3b82f6"
                  dot={false}
                  strokeWidth={1.5}
                />
              </LineChart>
            </ResponsiveContainer>
          </Panel>

          <div className="grid gap-3 lg:grid-cols-2">
            <Panel
              title="Stabilitas & Distribusi Regime"
              subtitle="Model yang terlalu sering berpindah regime sulit dipakai, meski akurasinya tinggi."
            >
              <div className="space-y-3">
                {MODEL_ORDER.filter((k) => models[k]).map((key) => {
                  const m = models[key];
                  return (
                    <div key={key} className="rounded border border-edge bg-panelAlt p-2.5">
                      <div className="flex items-baseline justify-between">
                        <span className="text-[11px] text-txtDim">{m.label}</span>
                        <span className="font-mono text-2xs text-txtMuted">
                          {m.n_switches} perpindahan · run rata-rata {m.mean_run_length}
                        </span>
                      </div>
                      <div className="mt-2 flex h-3 overflow-hidden rounded">
                        {Object.entries(m.distribution).map(([reg, val]: any) =>
                          val.share > 0 ? (
                            <div
                              key={reg}
                              title={`${regimeLabel(reg)}: ${(val.share * 100).toFixed(1)}%`}
                              style={{
                                width: `${val.share * 100}%`,
                                backgroundColor: REGIME_META[reg as Regime]?.color ?? "#334155",
                              }}
                            />
                          ) : null
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-3 border-t border-edge pt-3">
                <RegimeLegend compact />
              </div>
            </Panel>

            <Panel
              title="Sensitivitas τ (confidence threshold)"
              subtitle="Label dihitung ulang dari probabilitas mentah di browser — tanpa request ulang ke backend."
            >
              <div className="mb-3 flex items-center gap-3">
                <select
                  value={modelKey}
                  onChange={(e) => setModelKey(e.target.value)}
                  className="rounded border border-edge bg-panelAlt px-2 py-1 text-[11px] text-txtDim"
                >
                  <option value="swt_attention_bilstm">SWT + Attention-BiLSTM</option>
                  <option value="swt_bilstm">SWT + BiLSTM</option>
                  <option value="rule_based">Rule-based</option>
                </select>
                <span className="font-mono text-[11px] text-txtDim">
                  τ = {effectiveTau.toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min={0.34}
                max={1.0}
                step={0.01}
                value={effectiveTau}
                onChange={(e) => setTau(Number(e.target.value))}
                className="w-full accent-persistent"
              />
              <div className="mt-1 flex justify-between text-2xs text-txtMuted">
                <span>0.34 (batas bawah softmax 3 kelas)</span>
                <span>1.00 (semua jadi Uncertain)</span>
              </div>

              <div className="mt-4 space-y-2">
                {tauDistribution.map((d) => (
                  <div key={d.key}>
                    <div className="flex justify-between text-[11px]">
                      <span className="text-txtDim">{regimeLabel(d.key)}</span>
                      <span className="font-mono text-txtDim">
                        {(d.share * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="mt-1 h-2 overflow-hidden rounded bg-panelAlt">
                      <div
                        className="h-full"
                        style={{
                          width: `${d.share * 100}%`,
                          backgroundColor: REGIME_META[d.key as Regime]?.color ?? "#334155",
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
                Menaikkan τ memperbanyak Uncertain (low-conf). Ini ketidakpastian MODEL —
                berbeda dari Uncertain (rule) yang berasal dari ketidaksepakatan Hurst dan DFA
                pada DATA.
              </p>
            </Panel>
          </div>

          <Panel
            title="Metrik sekunder"
            subtitle="Bukan indikator keberhasilan utama penelitian ini. Baca kolom Cakupan lebih dulu."
          >
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1 text-left" rowSpan={2}>
                      Model
                    </th>
                    <th className="py-1 text-right" rowSpan={2}>
                      Cakupan
                    </th>
                    <th className="border-l border-edge py-1 text-center" colSpan={2}>
                      Argmax (tanpa ambang)
                    </th>
                    <th className="border-l border-edge py-1 text-center" colSpan={2}>
                      Setelah τ
                    </th>
                    <th className="border-l border-edge py-1 text-right" rowSpan={2}>
                      Asal prediksi
                    </th>
                  </tr>
                  <tr className="border-b border-edge text-2xs">
                    <th className="border-l border-edge py-1 text-right">BA</th>
                    <th className="py-1 text-right">MCC</th>
                    <th className="border-l border-edge py-1 text-right">BA</th>
                    <th className="py-1 text-right">n</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-txtDim">
                  {MODEL_ORDER.filter((k) => models[k]).map((key) => {
                    const m = models[key];
                    const s = m.secondary_metrics ?? {};
                    const argmax = s.argmax ?? {};
                    const thr = s.thresholded ?? {};
                    const isBaseline = key === "persistence";
                    const coverage = s.coverage ?? 0;
                    const lowCoverage = coverage < 0.05;
                    return (
                      <tr
                        key={key}
                        className={`border-b border-edge/50 ${isBaseline ? "bg-persistent/5" : ""}`}
                      >
                        <td className="py-1 font-sans text-txtDim">{m.label}</td>
                        <td
                          className={`py-1 text-right ${lowCoverage ? "text-warn" : ""}`}
                          title={
                            lowCoverage
                              ? "Model jarang melewati ambang τ — angka di kolom 'Setelah τ' berarti jarang menjawab, bukan sering salah."
                              : undefined
                          }
                        >
                          {(coverage * 100).toFixed(1)}%
                        </td>
                        <td className="border-l border-edge py-1 text-right">
                          {argmax.balanced_accuracy ?? "—"}
                        </td>
                        <td className="py-1 text-right">{argmax.mcc ?? "—"}</td>
                        <td className="border-l border-edge py-1 text-right text-txtMuted">
                          {thr.balanced_accuracy ?? "—"}
                        </td>
                        <td className="py-1 text-right text-txtMuted">{thr.n ?? 0}</td>
                        <td className="border-l border-edge py-1 text-right text-txtMuted">
                          {
                            {
                              trained_artifact: "model terlatih",
                              placeholder: "stand-in",
                              rule_based: "aturan Hurst-DFA",
                              baseline: "baseline naif",
                            }[m.prediction_source as string] ?? "—"
                          }
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
              <span className="text-txtDim">Cara membacanya: </span>
              kolom <span className="text-txtDim">Argmax</span> mengukur daya
              diskriminasi model tanpa memperhitungkan ambang τ, sedangkan kolom{" "}
              <span className="text-txtDim">Setelah τ</span> hanya menghitung window yang
              lolos ambang. Bila cakupan rendah, angka pada kolom kedua berarti model{" "}
              <span className="text-txtDim">jarang menjawab</span> — bukan sering salah.
              Balanced accuracy dan MCC dipakai karena kelas regime tidak seimbang. Window
              dengan ground truth Uncertain (rule) dikeluarkan karena model memang tidak
              pernah dilatih untuk kategori tersebut. Nilai acuan: tebakan seragam tiga
              kelas menghasilkan BA ≈ 0.333 dan MCC ≈ 0.
            </p>
          </Panel>

          <Panel
            title="Keyakinan Model"
            subtitle="Sebaran max(P) terhadap tebakan seragam tiga kelas (0.333)."
          >
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1 text-left">Model</th>
                    <th className="py-1 text-right">rata-rata max(P)</th>
                    <th className="py-1 text-right">persentil 90</th>
                    <th className="py-1 text-right">maksimum</th>
                    <th className="py-1 text-right">perpindahan (argmax)</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-txtDim">
                  {MODEL_ORDER.filter((k) => models[k]?.confidence).map((key) => {
                    const m = models[key];
                    const c = m.confidence;
                    return (
                      <tr key={key} className="border-b border-edge/50">
                        <td className="py-1 font-sans text-txtDim">{m.label}</td>
                        <td className="py-1 text-right">{c.mean_max_prob}</td>
                        <td className="py-1 text-right">{c.p90_max_prob}</td>
                        <td className="py-1 text-right">{c.max_max_prob}</td>
                        <td className="py-1 text-right text-txtMuted">
                          {m.argmax_switches ?? "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
              Nilai max(P) yang berkumpul di sekitar 0.333 menandakan model mendistribusikan
              probabilitas hampir merata ke tiga kelas — indikasi bahwa fitur yang tersedia
              tidak memuat cukup informasi untuk horizon ini. Kolom perpindahan dihitung dari
              argmax, sehingga tetap bermakna meski tidak ada window yang lolos ambang τ.
            </p>
          </Panel>

          <HorizonStudyPanel timeframe={timeframe} />
        </>
      )}
    </div>
  );
}

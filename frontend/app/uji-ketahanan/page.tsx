"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
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
import { AXIS_TICK, GRID_STROKE, LEGEND_STYLE, TOOLTIP_LABEL_STYLE, TOOLTIP_STYLE } from "@/lib/chart-theme";

const n = (v: number | null | undefined, d = 2) =>
  v == null ? "–" : v.toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });
const id = (v: number | null | undefined) => (v == null ? "–" : v.toLocaleString("id-ID"));
const ACCENT = "#3b82f6";
const MUTED = "#94a3b8";

function Th({ children, left = false }: { children: React.ReactNode; left?: boolean }) {
  return <th className={`py-1.5 font-medium ${left ? "text-left" : "text-right"}`}>{children}</th>;
}

function Note({ children }: { children: React.ReactNode }) {
  return <p className="mt-3 text-[12px] leading-relaxed text-txtDim">{children}</p>;
}

/**
 * Uji ketahanan metode identifikasi (h = 0): apakah hasilnya bertahan bila
 * periode diubah (walk-forward), bila parameter diubah (sensitivitas), dan
 * bila keacakan sampel diperhitungkan (Monte Carlo). Bukan uji strategi/profit.
 */
export default function RobustnessPage() {
  const { timeframe } = useAppConfig();
  const rb = useApi(() => api.robustness(), []);
  const t = rb.data?.timeframes?.[timeframe];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Uji Ketahanan Metode"
        description="Tiga cara menilai apakah metode identifikasi regime benar-benar bagus, bukan kebetulan: walk-forward (hasil bertahan di periode berbeda), sensitivitas (hasil tidak bergantung pada satu pilihan parameter), dan Monte Carlo (seberapa besar hasil bisa berubah karena keacakan sampel). Semua untuk model identifikasi Hybrid PS Attention-BiLSTM (h = 0), ensemble 3 seed. Ini bukan uji profit strategi."
      />
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ["1. Walk-forward", "Model dilatih ulang di 5 periode berurutan. Apakah hasilnya bertahan di luar satu potongan uji?"],
          ["2. Sensitivitas", "Ambang aturan label, bobot kelas, fitur, dan horizon diubah satu per satu. Apakah kesimpulan berubah?"],
          ["3. Monte Carlo", "Bootstrap blok dan permutasi ribuan kali. Seberapa lebar ketidakpastian hasil, dan apakah bisa terjadi kebetulan?"],
        ].map(([h, b]) => (
          <div key={h} className="rounded-lg border border-edge bg-panel px-4 py-3">
            <div className="text-[13px] font-semibold text-txt">{h}</div>
            <div className="mt-1 text-[12px] leading-relaxed text-txtDim">{b}</div>
          </div>
        ))}
      </div>
      <ParameterBar />
      <ApiState loading={rb.loading} error={rb.error} />
      {t && <WalkForward w={t.walk_forward} tf={timeframe} />}
      {t && <Sensitivity s={t.sensitivity} tf={timeframe} />}
      {t && <MonteCarlo m={t.monte_carlo} tf={timeframe} />}
      {rb.data && (
        <p className="text-2xs text-txtMuted">
          Sumber: ml/artifacts/robustness_tests.json (dibuat {rb.data.generated_at}) · ml/src/review_robustness.py
        </p>
      )}
    </div>
  );
}

function WalkForward({ w, tf }: { w: any; tf: string }) {
  const data = w.folds.map((f: any) => ({ fold: `Fold ${f.fold}`, hps: f.pct, mlp: f.mlp_pct }));
  const p = w.pooled;
  return (
    <Panel
      title={`1. Walk-forward · ${tf.toUpperCase()}`}
      subtitle="5 fold expanding, purge 500 bar; ambang label dikalibrasi ulang dari data latih tiap fold."
      params={{ gabungan: `${n(p.pooled_pct_ensemble)}%`, backtest: `${n(w.backtest_pct)}%` }}
    >
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 8, right: 90, bottom: 4, left: -10 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis dataKey="fold" tick={AXIS_TICK} />
          <YAxis domain={[0, 100]} tick={AXIS_TICK} unit="%" />
          <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} formatter={(v: any) => `${n(Number(v))}%`} />
          <Legend wrapperStyle={LEGEND_STYLE} />
          <ReferenceLine y={p.pooled_pct_ensemble} stroke={ACCENT} strokeDasharray="4 3" label={{ value: "gabungan", position: "right", fontSize: 10 }} />
          <ReferenceLine y={33.33} stroke={MUTED} strokeDasharray="2 4" label={{ value: "peluang 33,3%", position: "right", fontSize: 10 }} />
          <Bar dataKey="hps" name="Hybrid PS (model aplikasi)" fill={ACCENT} isAnimationActive={false} />
          <Bar dataKey="mlp" name="Structural MLP (pembanding)" fill={MUTED} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead className="text-txtMuted">
            <tr className="border-b border-edge">
              <Th left>Fold</Th>
              <Th>Jendela latih</Th>
              <Th>Jendela uji</Th>
              <Th>Benar</Th>
              <Th>% benar</Th>
              <Th>Rata-rata 3 kelas</Th>
            </tr>
          </thead>
          <tbody className="font-mono text-txtDim">
            {w.folds.map((f: any) => (
              <tr key={f.fold} className="border-b border-edge/50">
                <td className="py-1.5 font-sans">Fold {f.fold}</td>
                <td className="py-1.5 text-right">{id(f.n_train)}</td>
                <td className="py-1.5 text-right">{id(f.n_test)}</td>
                <td className="py-1.5 text-right">{id(f.correct)}</td>
                <td className="py-1.5 text-right font-semibold text-txt">{n(f.pct)}</td>
                <td className="py-1.5 text-right">{n(f.balanced_pct)}</td>
              </tr>
            ))}
            <tr className="bg-surface/70 text-txt">
              <td className="py-1.5 font-sans font-semibold">Gabungan</td>
              <td />
              <td className="py-1.5 text-right">{id(p.total_test_pooled)}</td>
              <td className="py-1.5 text-right">{id(p.total_correct_ensemble)}</td>
              <td className="py-1.5 text-right font-semibold">{n(p.pooled_pct_ensemble)}</td>
              <td className="py-1.5 text-right font-sans text-2xs text-txtMuted">
                antar-fold {n(p.fold_avg_pct)} ± {n(p.fold_std_pct)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <Note>
        Walk-forward gabungan ({n(p.pooled_pct_ensemble)}%) lebih rendah daripada backtest tunggal ({n(w.backtest_pct)}%). Angka
        walk-forward lebih mewakili kemampuan generalisasi karena mencakup lima periode pasar. Fold awal dilatih dengan data
        sedikit ({id(w.folds[0].n_train)} jendela) sehingga hasilnya paling rendah; hasil membaik saat data latih bertambah.
      </Note>
    </Panel>
  );
}

function Sensitivity({ s, tf }: { s: any; tf: string }) {
  const er = s.er_rule;
  const base = er?.rows?.[0];
  const accs = er?.rows?.map((r: any) => r.test_acc_pct) ?? [];
  return (
    <Panel
      title={`2. Sensitivitas · ${tf.toUpperCase()}`}
      subtitle="Satu parameter diubah per baris; parameter lain tetap sama dengan Bab 4."
    >
      <div className="text-[13px] font-semibold text-txt">a. Ambang aturan label Trend-Aware Soft Consensus</div>
      {er ? (
        <>
          <div className="mt-1 text-2xs text-txtMuted">
            Label dibentuk ulang, model dilatih ulang (3 seed), diuji pada partisi uji backtest
            {tf === "4h" ? "; 4H tanpa augmentasi ETH/BNB agar semua setelan sebanding" : ""}.
          </div>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead className="text-txtMuted">
                <tr className="border-b border-edge">
                  <Th left>Setelan</Th>
                  <Th>Jendela berlabel</Th>
                  <Th>Label sama dgn bawaan</Th>
                  <Th>Jendela uji</Th>
                  <Th>% benar uji</Th>
                  <Th>Selisih</Th>
                  <Th>Rata-rata 3 kelas</Th>
                  <Th>% benar validasi</Th>
                </tr>
              </thead>
              <tbody className="font-mono text-txtDim">
                {er.rows.map((r: any, i: number) => {
                  const d = r.test_acc_pct - base.test_acc_pct;
                  return (
                    <tr key={r.name} className={`border-b border-edge/50 ${i === 0 ? "bg-surface/70 text-txt" : ""}`}>
                      <td className="py-1.5 font-sans">{r.name}</td>
                      <td className="py-1.5 text-right">{n(r.labeled_pct)}%</td>
                      <td className="py-1.5 text-right">{n(r.same_label_as_default_pct)}%</td>
                      <td className="py-1.5 text-right">{id(r.n_test)}</td>
                      <td className="py-1.5 text-right font-semibold">{n(r.test_acc_pct)}</td>
                      <td className="py-1.5 text-right">{i === 0 ? "–" : `${d >= 0 ? "+" : ""}${n(d)}`}</td>
                      <td className="py-1.5 text-right">{n(r.test_ba_pct)}</td>
                      <td className="py-1.5 text-right">{n(r.val_acc_pct)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Note>
            Mengubah ambang ER ±0,05 menggeser % benar uji dalam rentang {n(Math.min(...accs))}–{n(Math.max(...accs))}% (bawaan{" "}
            {n(base.test_acc_pct)}%). Label tiap setelan juga berubah, jadi angka di atas mengukur seberapa konsisten model mengenali
            aturan label yang sedikit berbeda, bukan akurasi terhadap satu kebenaran yang sama.
          </Note>
        </>
      ) : (
        <p className="mt-1 text-[12px] text-txtMuted">Hasil sensitivitas ambang belum tersedia.</p>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div>
          <div className="text-[13px] font-semibold text-txt">b. Eksponen bobot kelas</div>
          <table className="mt-2 w-full text-[12px]">
            <thead className="text-txtMuted">
              <tr className="border-b border-edge">
                <Th left>Eksponen</Th>
                <Th>% benar validasi</Th>
                <Th>% benar uji</Th>
              </tr>
            </thead>
            <tbody className="font-mono text-txtDim">
              {s.class_weight_power.map((r: any) => (
                <tr key={r.power} className={`border-b border-edge/50 ${r.power === 0.6 ? "bg-surface/70 text-txt" : ""}`}>
                  <td className="py-1.5 font-sans">
                    {n(r.power)}
                    {r.power === 0.6 ? " (dipakai)" : ""}
                  </td>
                  <td className="py-1.5 text-right">{n(r.val_ens_acc * 100)}</td>
                  <td className="py-1.5 text-right">{n(r.test_ens_acc * 100)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <div className="text-[13px] font-semibold text-txt">c. Ablasi fitur dan arsitektur</div>
          <table className="mt-2 w-full text-[12px]">
            <thead className="text-txtMuted">
              <tr className="border-b border-edge">
                <Th left>Varian</Th>
                <Th>Backtest</Th>
                <Th>Walk-forward</Th>
              </tr>
            </thead>
            <tbody className="font-mono text-txtDim">
              {Object.entries(s.ablation).map(([k, v]: any) => (
                <tr key={k} className={`border-b border-edge/50 ${k === "normal" ? "bg-surface/70 text-txt" : ""}`}>
                  <td className="py-1.5 font-sans">{k === "normal" ? "Model lengkap" : k.replace("_", " ")}</td>
                  <td className="py-1.5 text-right">{n(v.backtest.acc_pct)}</td>
                  <td className="py-1.5 text-right">{n(v.walk_forward.acc_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {s.horizon && (
            <>
              <div className="mt-4 text-[13px] font-semibold text-txt">d. Horizon target (identifikasi vs prediksi)</div>
              {tf === "4h" && (
                <div className="mt-1 text-2xs text-txtMuted">
                  4H tanpa augmentasi ETH/BNB (label tidak dapat digeser), jadi h = 0 di sini 71,48%, bukan 74,64%.
                </div>
              )}
              <table className="mt-2 w-full text-[12px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <Th left>h (bar)</Th>
                    <Th>% benar</Th>
                    <Th>Baseline persistence</Th>
                  </tr>
                </thead>
                <tbody className="font-mono text-txtDim">
                  {s.horizon.map((r: any) => (
                    <tr key={r.h_bars} className={`border-b border-edge/50 ${r.h_bars === 0 ? "bg-surface/70 text-txt" : ""}`}>
                      <td className="py-1.5 font-sans">{r.h_bars === 0 ? "0 (identifikasi)" : r.h_bars}</td>
                      <td className="py-1.5 text-right">{n(r.acc_pct)}</td>
                      <td className="py-1.5 text-right">{r.h_bars === 0 ? "–" : n(r.baseline_acc_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
      <Note>
        Bobot kelas 0,40–0,80 menghasilkan % benar uji yang berdekatan, jadi kesimpulan tidak bergantung pada satu angka
        eksponen. Membuang fitur ER, energi SWT, atau attention hanya mengubah hasil sedikit; kontribusi utama berasal dari
        fitur statistik persistensi. Kemampuan memprediksi regime ke depan turun cepat, sehingga sistem dirancang untuk identifikasi
        (h = 0).
      </Note>
    </Panel>
  );
}

function MonteCarlo({ m, tf }: { m: any; tf: string }) {
  const bt = m.backtest;
  const wf = m.walk_forward_pooled;
  const perm = bt.permutation;
  const hist = (perm.hist?.counts ?? []).map((c: number, i: number) => ({
    x: (perm.hist.edges[i] + perm.hist.edges[i + 1]) / 2,
    label: n((perm.hist.edges[i] + perm.hist.edges[i + 1]) / 2, 1),
    count: c,
  }));
  const sur = m.surrogate;
  return (
    <Panel
      title={`3. Monte Carlo · ${tf.toUpperCase()}`}
      subtitle={`Block bootstrap 5.000× (blok ${bt.bootstrap.block_windows} jendela = 500 bar, karena jendela bertumpuk) dan permutasi geser 5.000×.`}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead className="text-txtMuted">
            <tr className="border-b border-edge">
              <Th left>Ukuran</Th>
              <Th>Backtest</Th>
              <Th>Walk-forward gabungan</Th>
            </tr>
          </thead>
          <tbody className="font-mono text-txtDim">
            <tr className="border-b border-edge/50 text-txt">
              <td className="py-1.5 font-sans">% benar</td>
              <td className="py-1.5 text-right font-semibold">{n(bt.acc_pct)}</td>
              <td className="py-1.5 text-right font-semibold">{n(wf.acc_pct)}</td>
            </tr>
            <tr className="border-b border-edge/50">
              <td className="py-1.5 font-sans">Selang kepercayaan 95% (% benar)</td>
              <td className="py-1.5 text-right">
                {n(bt.bootstrap.acc_ci95_pct[0])} – {n(bt.bootstrap.acc_ci95_pct[1])}
              </td>
              <td className="py-1.5 text-right">
                {n(wf.bootstrap.acc_ci95_pct[0])} – {n(wf.bootstrap.acc_ci95_pct[1])}
              </td>
            </tr>
            <tr className="border-b border-edge/50">
              <td className="py-1.5 font-sans">Selang kepercayaan 95% (rata-rata 3 kelas)</td>
              <td className="py-1.5 text-right">
                {n(bt.bootstrap.ba_ci95_pct[0])} – {n(bt.bootstrap.ba_ci95_pct[1])}
              </td>
              <td className="py-1.5 text-right">
                {n(wf.bootstrap.ba_ci95_pct[0])} – {n(wf.bootstrap.ba_ci95_pct[1])}
              </td>
            </tr>
            <tr className="border-b border-edge/50">
              <td className="py-1.5 font-sans">Permutasi: rata-rata nol · persentil 95</td>
              <td className="py-1.5 text-right">
                {n(perm.null_mean_pct)} · {n(perm.null_p95_pct)}
              </td>
              <td className="py-1.5 text-right">
                {n(wf.permutation.null_mean_pct)} · {n(wf.permutation.null_p95_pct)}
              </td>
            </tr>
            <tr className="border-b border-edge/50">
              <td className="py-1.5 font-sans">p-value permutasi</td>
              <td className="py-1.5 text-right">{perm.p_value < 0.001 ? "< 0,001" : n(perm.p_value, 4)}</td>
              <td className="py-1.5 text-right">{wf.permutation.p_value < 0.001 ? "< 0,001" : n(wf.permutation.p_value, 4)}</td>
            </tr>
            <tr className="border-b border-edge/50">
              <td className="py-1.5 font-sans">% benar per seed (42 / 43 / 44)</td>
              <td className="py-1.5 text-right">{bt.seed_acc_pct.map((v: number) => n(v)).join(" / ")}</td>
              <td className="py-1.5 text-right">{wf.seed_acc_pct.map((v: number) => n(v)).join(" / ")}</td>
            </tr>
            <tr>
              <td className="py-1.5 font-sans">Pembanding: kelas terbanyak · peluang</td>
              <td className="py-1.5 text-right">
                {n(bt.majority_class_pct)} · 33,33
              </td>
              <td />
            </tr>
          </tbody>
        </table>
      </div>

      <div className="mt-4 text-[13px] font-semibold text-txt">Sebaran nol permutasi (backtest) dibandingkan hasil model</div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={hist} margin={{ top: 8, right: 16, bottom: 16, left: -10 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis
            dataKey="x"
            type="number"
            domain={[Math.min(20, hist[0]?.x ?? 20), 100]}
            tick={AXIS_TICK}
            unit="%"
            label={{ value: "% benar bila label digeser acak (tanpa hubungan dengan prediksi)", position: "insideBottom", offset: -8, fontSize: 11 }}
          />
          <YAxis tick={AXIS_TICK} />
          <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} labelFormatter={(l: any) => `${n(Number(l), 1)}%`} />
          <ReferenceLine x={bt.acc_pct} stroke="#ef4444" strokeWidth={2} label={{ value: `model ${n(bt.acc_pct)}%`, position: "insideTopLeft", fontSize: 10 }} />
          <Bar dataKey="count" name="jumlah permutasi" fill={MUTED} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>

      <div className="mt-3 rounded-lg border border-edge bg-surface/60 px-3 py-2 text-[12px] leading-relaxed text-txtDim">
        <b className="text-txt">Surrogat H dan α:</b> urutan return tiap jendela diacak {id(sur.per_window_shuffle.n_shuffles)} kali pada{" "}
        {id(sur.per_window_shuffle.n_windows)} jendela. Hanya {n(sur.per_window_shuffle.pct_windows_H_reject_5pct, 1)}% (H) dan{" "}
        {n(sur.per_window_shuffle.pct_windows_alpha_reject_5pct, 1)}% (α) jendela berbeda nyata dari versi acaknya, dan{" "}
        {n(sur.both_outside_random_band_pct)}% jendela punya H dan α di luar pita acak. Label regime bersifat relatif terhadap data
        latih, bukan bukti memori jangka panjang pada tiap jendela.
      </div>
      <Note>
        Jendela bergeser {tf === "1h" ? "4" : "2"} bar dari 500 bar sehingga sangat bertumpuk; karena itu bootstrap memakai blok 500 bar
        dan permutasi menggeser label minimal 500 bar. Dengan cara ini pun, hasil model jauh di atas sebaran nol (p &lt; 0,001), tetapi
        selang kepercayaannya cukup lebar, terutama untuk 4H.
      </Note>
    </Panel>
  );
}

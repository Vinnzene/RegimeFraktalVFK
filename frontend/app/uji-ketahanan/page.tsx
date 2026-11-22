"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
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
import { ApiState } from "@/components/useApi";
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
/**
 * Halaman ini terkunci per akun: pengguna meminta akses, admin menyetujui di
 * /admin/akses. Data hanya dikirim rute /api/robustness untuk admin, akun yang
 * disetujui, atau bila pemilik membuka untuk semua (UJI_KETAHANAN_TERBUKA=1).
 */
type AccessResponse = {
  access: "pending" | "approved" | "rejected" | null;
  requested_at: number | null;
  admin: boolean;
  open: boolean;
  data: any | null;
};

export default function RobustnessPage() {
  const [res, setRes] = useState<AccessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/robustness", { cache: "no-store" });
      const body = await r.json();
      if (!r.ok) throw new Error(body.error ?? `HTTP ${r.status}`);
      setRes(body);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const request = async (note: string) => {
    const r = await fetch("/api/robustness", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note }) });
    if (!r.ok) setError("Permintaan gagal dikirim.");
    await load();
  };

  if (error) return <ApiState loading={false} error={error} />;
  if (!res) return <ApiState loading error={null} />;
  if (!res.open || !res.data) return <Locked res={res} onRequest={request} />;
  return <RobustnessContent data={res.data} admin={res.admin} />;
}

function LockIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <rect x="4" y="10" width="16" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function Locked({ res, onRequest }: { res: AccessResponse; onRequest: (note: string) => Promise<void> }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    await onRequest(note);
    setBusy(false);
  };
  return (
    <section className="mx-auto mt-6 max-w-[640px] rounded-xl border border-edge bg-panel p-6 text-center shadow-panel">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-surface text-txtDim">
        <LockIcon />
      </div>
      <h1 className="mt-3 text-[18px] font-semibold text-txt">Uji Ketahanan Metode terkunci</h1>
      <p className="mt-1.5 text-[13px] leading-relaxed text-txtDim">
        Halaman ini hanya dibuka untuk akun yang disetujui pemilik aplikasi.
      </p>

      {res.access === "pending" ? (
        <p className="mt-4 rounded-lg border border-warn/40 bg-warn/10 px-4 py-3 text-[13px] text-txt">
          Permintaan terkirim
          {res.requested_at
            ? ` pada ${new Date(res.requested_at * 1000).toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}`
            : ""}
          . Menunggu persetujuan pemilik.
        </p>
      ) : (
        <div className="mt-4 text-left">
          {res.access === "rejected" && (
            <p className="mb-3 rounded-lg border border-bearish/30 bg-bearish/5 px-3 py-2 text-[12.5px] text-bearish">
              Permintaan sebelumnya tidak disetujui. Anda dapat mengajukan lagi.
            </p>
          )}
          <label className="block text-[12px] font-medium text-txtDim" htmlFor="alasan">
            Alasan (opsional)
          </label>
          <textarea
            id="alasan"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={300}
            rows={3}
            placeholder="Mis. dosen pembimbing atau penguji."
            className="mt-1 w-full rounded-lg border border-edge bg-panel px-3 py-2 text-[13px] text-txt outline-none focus:border-accent"
          />
          <button
            type="button"
            onClick={submit}
            disabled={busy}
            className="mt-3 w-full rounded-lg bg-txt px-5 py-2.5 text-[14px] font-semibold text-panel transition hover:opacity-90 disabled:opacity-40"
          >
            {busy ? "Mengirim…" : "Minta akses"}
          </button>
        </div>
      )}
    </section>
  );
}

function RobustnessContent({ data, admin }: { data: any; admin: boolean }) {
  const { timeframe } = useAppConfig();
  const rb = { data };
  const t = rb.data?.timeframes?.[timeframe];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Uji Ketahanan Metode"
        description="Empat cara menilai apakah metode identifikasi regime benar-benar bagus dan berguna: walk-forward (hasil bertahan di periode berbeda), sensitivitas (hasil tidak bergantung pada satu pilihan parameter), Monte Carlo (seberapa besar hasil bisa berubah karena keacakan sampel), dan pembanding indikator klasik ADX/Choppiness (apa bedanya dengan alat gratis yang sudah ada). Semua untuk model identifikasi Hybrid PS Attention-BiLSTM (h = 0), ensemble 3 seed. Ini bukan uji profit strategi."
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["1. Walk-forward", "Model dilatih ulang di 5 periode berurutan. Apakah hasilnya bertahan di luar satu potongan uji?"],
          ["2. Sensitivitas", "Ambang aturan label, bobot kelas, fitur, dan horizon diubah satu per satu. Apakah kesimpulan berubah?"],
          ["3. Monte Carlo", "Bootstrap blok dan permutasi ribuan kali. Seberapa lebar ketidakpastian hasil, dan apakah bisa terjadi kebetulan?"],
          ["4. Indikator klasik", "Dibandingkan ADX dan Choppiness Index. Apakah labelnya berbeda, dan apakah lebih berguna untuk aturan trend following?"],
        ].map(([h, b]) => (
          <div key={h} className="rounded-lg border border-edge bg-panel px-4 py-3">
            <div className="text-[13px] font-semibold text-txt">{h}</div>
            <div className="mt-1 text-[12px] leading-relaxed text-txtDim">{b}</div>
          </div>
        ))}
      </div>
      {admin && (
        <p className="text-[12px] text-txtMuted">
          Halaman ini terkunci untuk akun lain.{" "}
          <Link href="/admin/akses?fitur=robustness" className="font-medium text-txtDim underline hover:text-txt">
            Kelola akses →
          </Link>
        </p>
      )}
      <ParameterBar />
      {t && <WalkForward w={t.walk_forward} tf={timeframe} />}
      {t && <Sensitivity s={t.sensitivity} tf={timeframe} />}
      {t && <MonteCarlo m={t.monte_carlo} tf={timeframe} />}
      {t?.vs_indicators && <VsIndicators v={t.vs_indicators} rules={rb.data.vs_indicators_rules} tf={timeframe} />}
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

const ROWS: [string, string][] = [
  ["RFraktal_model", "RFraktal (prediksi model): persistent − anti-persistent"],
  ["ADX14", "ADX(14): trending − ranging"],
  ["CHOP14", "Choppiness(14): trending − choppy"],
  ["CHOP500", "Choppiness(500): trending − choppy"],
];

function Spread({ x }: { x: any }) {
  if (!x) return <span>–</span>;
  const sig = x.ci95_pp[0] > 0 || x.ci95_pp[1] < 0;
  const color = !sig ? "text-txtDim" : x.spread_pp > 0 ? "text-bullish" : "text-bearish";
  return (
    <span className={color}>
      {x.spread_pp > 0 ? "+" : ""}
      {n(x.spread_pp)} <span className="text-2xs text-txtMuted">[{n(x.ci95_pp[0])}; {n(x.ci95_pp[1])}]</span>
      {sig ? " *" : ""}
    </span>
  );
}

function VsIndicators({ v, rules, tf }: { v: any; rules: any; tf: string }) {
  const a = v.association;
  const sm = v.momentum_scale_matched ?? {};
  return (
    <Panel
      title={`4. Pembanding indikator klasik · ${tf.toUpperCase()}`}
      subtitle="ADX dan Choppiness Index tersedia gratis di platform trading. Apa bedanya, dan mana yang lebih berguna?"
    >
      <div className="text-[13px] font-semibold text-txt">a. Apakah labelnya sama?</div>
      <div className="mt-1 text-2xs text-txtMuted">
        Cramér&apos;s V pada jendela uji: 0 = tidak terkait, 1 = identik. ADX: {rules?.adx_rule}. Choppiness: {rules?.chop_rule}.
      </div>
      <table className="mt-2 w-full text-[12px]">
        <thead className="text-txtMuted">
          <tr className="border-b border-edge">
            <Th left>Pasangan</Th>
            <Th>Label acuan</Th>
            <Th>Prediksi model</Th>
          </tr>
        </thead>
        <tbody className="font-mono text-txtDim">
          {[
            ["ADX(14)", "ADX14"],
            ["Choppiness(14)", "CHOP14"],
            ["Choppiness(500), skala sama", "CHOP500"],
          ].map(([label, k]) => (
            <tr key={k} className="border-b border-edge/50">
              <td className="py-1.5 font-sans">RFraktal vs {label}</td>
              <td className="py-1.5 text-right">{n(a[`label_acuan_vs_${k}`], 3)}</td>
              <td className="py-1.5 text-right">{n(a[`prediksi_model_vs_${k}`], 3)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-5 text-[13px] font-semibold text-txt">b. Apakah lebih berguna untuk trend following?</div>
      <div className="mt-1 text-2xs text-txtMuted">
        Aturan: arah harga beberapa bar terakhir dipakai menebak arah h bar berikutnya. Angka = selisih ketepatan (poin persen) antara
        kelompok &quot;tren&quot; dan kelompok &quot;berbalik/sideways&quot; menurut tiap alat. Positif = alat berhasil memisahkan pasar yang
        cocok untuk trend following. [SK 95% block bootstrap]; * = signifikan; hijau positif, merah negatif.
      </div>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead className="text-txtMuted">
            <tr className="border-b border-edge">
              <Th left>Alat</Th>
              {Object.keys(v.momentum_short).map((h) => (
                <Th key={h}>lookback {rules?.lookback_bars} · h {h}</Th>
              ))}
              {Object.keys(sm).map((k) => {
                const [lb, h] = k.slice(2).split("_h");
                return <Th key={k}>lookback {lb} · h {h}</Th>;
              })}
            </tr>
          </thead>
          <tbody className="font-mono">
            {ROWS.map(([k, label]) => (
              <tr key={k} className="border-b border-edge/50">
                <td className="py-1.5 font-sans text-txtDim">{label}</td>
                {Object.values(v.momentum_short).map((m: any, i) => (
                  <td key={i} className="py-1.5 text-right">
                    <Spread x={m[k]} />
                  </td>
                ))}
                {Object.values(sm).map((m: any, i) => (
                  <td key={`s${i}`} className="py-1.5 text-right">
                    <Spread x={k === "RFraktal_model" ? m.model : m[k]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Note>
        Label RFraktal hampir tidak terkait dengan ADX(14) dan Choppiness(14): RFraktal membaca sifat memori pada 500 bar, ADX membaca
        kekuatan gerak sekitar 14 bar. Pada horizon pendek, label persistent tidak membuat trend following lebih tepat, bahkan lebih buruk.
        Pada skala panjang di 4H arahnya sesuai teori, tetapi belum signifikan karena periode uji hanya ±1 tahun. Belum ada bukti bahwa
        RFraktal lebih berguna daripada ADX untuk memilih strategi; nilai praktisnya adalah konteks sifat pasar skala panjang beserta
        tingkat keyakinan.
      </Note>
    </Panel>
  );
}

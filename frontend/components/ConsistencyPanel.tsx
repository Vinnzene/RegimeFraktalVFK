"use client";

import { useState } from "react";
import Panel from "@/components/Panel";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";
import { regimeLabel } from "@/lib/regime";

/**
 * Konsistensi identifikasi model terhadap karakteristik Hurst-DFA.
 *
 * Menjawab rumusan masalah penelitian secara langsung. Disusun berlapis karena
 * akurasi saja dapat menyembunyikan model yang benar secara agregat tetapi
 * kehilangan sifat persistensi — justru sifat yang menjadi inti penelitian.
 */
export default function ConsistencyPanel({ timeframe }: { timeframe: string }) {
  const [mode, setMode] = useState<"multiclass" | "binary">("multiclass");
  const res = useApi(() => api.consistency(timeframe, mode), [timeframe, mode]);

  const modeToggle = (
    <div className="inline-flex overflow-hidden rounded border border-edge">
      {(["multiclass", "binary"] as const).map((m) => (
        <button
          key={m}
          onClick={() => setMode(m)}
          className={`px-2.5 py-1 font-mono text-2xs transition ${
            mode === m ? "bg-accent/20 text-accent" : "text-txtMuted hover:bg-surface"
          }`}
        >
          {m === "binary" ? "BINER" : "3 KELAS"}
        </button>
      ))}
    </div>
  );

  if (res.loading || res.error) {
    return (
      <Panel title="Konsistensi terhadap Hurst-DFA" subtitle="Memuat…" actions={modeToggle}>
        <ApiState loading={res.loading} error={res.error} />
      </Panel>
    );
  }

  const d = res.data;
  if (!d?.available) {
    return (
      <Panel
        title="Konsistensi terhadap Hurst-DFA"
        subtitle="Seberapa sesuai identifikasi model dengan karakteristik statistik."
        actions={modeToggle}
      >
        <p className="text-[11px] text-txtMuted">{d?.reason ?? "Belum tersedia."}</p>
        {d?.perintah && (
          <pre className="mt-2 overflow-x-auto rounded border border-edge bg-panelAlt p-2 font-mono text-2xs text-txtDim">
            {d.perintah}
          </pre>
        )}
      </Panel>
    );
  }

  const ag = d.agreement ?? {};
  const cf = d.confusion ?? {};
  const dist = d.distribution ?? {};
  const temp = d.temporal ?? {};
  const ea = d.exponent_alignment ?? {};
  const tr = d.transitions ?? {};

  return (
    <Panel
      title="Konsistensi terhadap Hurst-DFA"
      subtitle="Diukur pada rentang test — data yang tidak pernah dilihat model saat pelatihan."
      params={{ mode: d.mode, model: d.model, n: ag.n ?? 0 }}
      actions={modeToggle}
    >
      {/* Ringkasan empat lapis */}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <div className="stat-card py-2">
          <div className="metric-label">Kesepakatan window</div>
          <div className="mt-0.5 font-mono text-[17px] font-semibold tabular-nums text-txt">
            {((ag.agreement_rate ?? 0) * 100).toFixed(2)}%
          </div>
          <div className="mt-0.5 text-2xs text-txtMuted">
            {ag.n_agree} dari {ag.n} window
          </div>
        </div>

        <div className="stat-card py-2">
          <div className="metric-label">Cohen&apos;s Kappa</div>
          <div
            className={`mt-0.5 font-mono text-[17px] font-semibold tabular-nums ${
              (ag.cohen_kappa ?? 0) >= 0.61 ? "text-bullish" : "text-txt"
            }`}
          >
            {(ag.cohen_kappa ?? 0).toFixed(4)}
          </div>
          <div className="mt-0.5 text-2xs text-txtMuted">
            {ag.kappa_interpretation} · melebihi kebetulan
          </div>
        </div>

        <div className="stat-card py-2">
          <div className="metric-label">Selisih Hurst</div>
          <div
            className={`mt-0.5 font-mono text-[17px] font-semibold tabular-nums ${
              (ea.mean_abs_gap_hurst ?? 1) < 0.02 ? "text-bullish" : "text-txt"
            }`}
          >
            {(ea.mean_abs_gap_hurst ?? 0).toFixed(4)}
          </div>
          <div className="mt-0.5 text-2xs text-txtMuted">rata-rata absolut per kategori</div>
        </div>

        <div className="stat-card py-2">
          <div className="metric-label">Urutan eksponen</div>
          <div
            className={`mt-0.5 font-sans text-[15px] font-semibold ${
              ea.ordering_preserved ? "text-bullish" : "text-bearish"
            }`}
          >
            {ea.ordering_preserved ? "Terjaga" : "Tidak terjaga"}
          </div>
          <div className="mt-0.5 text-2xs text-txtMuted">Persistent &gt; Anti-persistent</div>
        </div>
      </div>

      {/* Matriks konfusi + metrik per kelas */}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <div className="mb-1.5 text-[12px] font-semibold text-txt">Matriks konfusi</div>
          <p className="mb-2 text-2xs text-txtMuted">
            Baris = regime Hurst-DFA, kolom = prediksi model.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-2xs tabular-nums">
              <thead>
                <tr className="border-b border-edge text-txtMuted">
                  <th className="py-1 text-left font-medium">referensi \ model</th>
                  {(cf.classes ?? []).map((c: string) => (
                    <th key={c} className="py-1 text-right font-medium">
                      {regimeLabel(c).split(" ")[0]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(cf.matrix ?? []).map((row: number[], i: number) => (
                  <tr key={i} className="border-b border-edge/50">
                    <td className="py-1 text-txtDim">{regimeLabel(cf.classes[i])}</td>
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
          <div className="mb-1.5 flex items-baseline gap-2">
            <span className="text-[12px] font-semibold text-txt">Metrik per kelas</span>
            <span className="font-mono text-2xs text-txtMuted">
              macro F1 = {(cf.macro_f1 ?? 0).toFixed(4)}
            </span>
          </div>
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
                {(cf.per_class ?? []).map((p: any) => (
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

      {/* Lapis 4 — bukti terkuat */}
      <div className="mt-4">
        <div className="mb-1.5 text-[12px] font-semibold text-txt">
          Kesesuaian nilai eksponen
        </div>
        <p className="mb-2 text-2xs leading-relaxed text-txtMuted">
          Rata-rata Hurst dan DFA pada window yang <span className="text-txtDim">diprediksi</span>{" "}
          model, dibandingkan dengan kategori Hurst-DFA sebenarnya. Selisih kecil berarti
          model menangkap karakteristik statistiknya, bukan sekadar mencocokkan label.
        </p>
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th className="text-left">Regime</th>
                <th className="text-right">n model</th>
                <th className="text-right">Hurst (model)</th>
                <th className="text-right">Hurst (Hurst-DFA)</th>
                <th className="text-right">Selisih</th>
                <th className="text-right">α (model)</th>
                <th className="text-right">α (Hurst-DFA)</th>
              </tr>
            </thead>
            <tbody>
              {(ea.per_regime ?? []).map((r: any) => {
                const gap = Math.abs(r.hurst_model - r.hurst_truth);
                return (
                  <tr key={r.regime}>
                    <td className="font-sans text-txtDim">{regimeLabel(r.regime)}</td>
                    <td className="text-right text-txtMuted">{r.n_model}</td>
                    <td className="text-right text-txt">{r.hurst_model.toFixed(4)}</td>
                    <td className="text-right text-txtMuted">{r.hurst_truth.toFixed(4)}</td>
                    <td
                      className={`text-right ${gap < 0.02 ? "text-bullish" : "text-warn"}`}
                    >
                      {gap.toFixed(4)}
                    </td>
                    <td className="text-right text-txt">{r.dfa_model.toFixed(4)}</td>
                    <td className="text-right text-txtMuted">{r.dfa_truth.toFixed(4)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Lapis 2 dan 3 */}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <div className="mb-1.5 text-[12px] font-semibold text-txt">Distribusi kategori</div>
          <div className="space-y-1.5">
            {(dist.per_regime ?? []).map((r: any) => (
              <div key={r.regime} className="flex items-center gap-2 text-[11px]">
                <span className="w-32 shrink-0 text-txtDim">{regimeLabel(r.regime)}</span>
                <span className="font-mono tabular-nums text-txtMuted">
                  {(r.share_truth * 100).toFixed(1)}%
                </span>
                <span className="text-txtMuted">→</span>
                <span className="font-mono tabular-nums text-txt">
                  {(r.share_model * 100).toFixed(1)}%
                </span>
                <span
                  className={`ml-auto font-mono text-2xs ${
                    Math.abs(r.diff_pp) < 5 ? "text-txtMuted" : "text-warn"
                  }`}
                >
                  {r.diff_pp > 0 ? "+" : ""}
                  {r.diff_pp.toFixed(1)} pp
                </span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-1.5 text-[12px] font-semibold text-txt">Struktur temporal</div>
          <div className="space-y-1.5 text-[11px]">
            <div className="flex items-center gap-2">
              <span className="w-32 shrink-0 text-txtDim">Durasi rata-rata</span>
              <span className="font-mono tabular-nums text-txtMuted">
                {temp.mean_duration_truth}
              </span>
              <span className="text-txtMuted">→</span>
              <span className="font-mono tabular-nums text-txt">
                {temp.mean_duration_model}
              </span>
              <span className="ml-auto text-2xs text-txtMuted">window</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-32 shrink-0 text-txtDim">Perpindahan</span>
              <span className="font-mono tabular-nums text-txtMuted">
                {temp.switches_truth}
              </span>
              <span className="text-txtMuted">→</span>
              <span className="font-mono tabular-nums text-txt">{temp.switches_model}</span>
            </div>
            {(temp.persistence ?? []).map((p: any) => (
              <div key={p.regime} className="flex items-center gap-2">
                <span className="w-32 shrink-0 text-txtDim">
                  P(bertahan) {regimeLabel(p.regime)}
                </span>
                <span className="font-mono tabular-nums text-txtMuted">
                  {p.stay_truth.toFixed(3)}
                </span>
                <span className="text-txtMuted">→</span>
                <span className="font-mono tabular-nums text-txt">
                  {p.stay_model.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Titik transisi */}
      {tr.n_transitions_truth > 0 && (
        <div className="mt-4">
          <div className="mb-1.5 text-[12px] font-semibold text-txt">
            Ketepatan titik transisi
          </div>
          <p className="mb-2 text-2xs leading-relaxed text-txtMuted">
            Bukan hanya label per window, tetapi seberapa tepat model menangkap{" "}
            <span className="text-txtDim">waktu</span> pergantian regime. Toleransi{" "}
            {tr.tolerance_windows} window karena window tumpang tindih membuat pergeseran
            satu-dua langkah wajar terjadi.
          </p>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {[
              ["Transisi referensi", tr.n_transitions_truth],
              ["Transisi model", tr.n_transitions_model],
              ["Terdeteksi", `${((tr.detection_rate ?? 0) * 100).toFixed(1)}%`],
              ["False alarm", `${((tr.false_alarm_rate ?? 0) * 100).toFixed(1)}%`],
            ].map(([label, value]) => (
              <div key={label as string} className="stat-card py-2">
                <div className="metric-label">{label as string}</div>
                <div className="mt-0.5 font-mono text-[15px] tabular-nums text-txt">
                  {value as string}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
        Kolom kiri tiap pasangan adalah nilai Hurst-DFA, kolom kanan nilai model. Durasi
        model yang lebih pendek dan false alarm yang tinggi menandakan model berpindah
        regime lebih sering daripada aturan Hurst-DFA. Perbedaan ini wajar dilaporkan:
        Hurst-DFA memakai window tumpang tindih yang otomatis melicinkan label, sedangkan
        model memutuskan tiap window secara mandiri tanpa mengetahui label tetangganya.
      </p>
    </Panel>
  );
}

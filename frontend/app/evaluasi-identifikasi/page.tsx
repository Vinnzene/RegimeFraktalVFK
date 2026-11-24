"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN } from "@/lib/regime";

const CLASSES = ["persistent", "random_like", "anti_persistent"] as const;
/** Urutan lima model untuk admin. Pengguna biasa hanya melihat model aplikasi (hybrid_ps). */
const MODEL_ORDER = ["swt_bilstm", "swt_attention_bilstm", "structural_mlp", "hybrid_swt", "hybrid_ps"];
const APP_MODEL = "hybrid_ps";
const APP_MODEL_NAME = "Hybrid Attention-BiLSTM";
const id = (v: number) => v.toLocaleString("id-ID");
const pc = (v: number) => `${v.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;

type Cls = { total: number; correct: number; pct: number };

function ClassCells({ per }: { per: Record<string, Cls> }) {
  return (
    <>
      {CLASSES.map((c) => (
        <td key={c} className="py-1.5 text-right">
          {id(per[c].correct)}/{id(per[c].total)} <span className="text-txtMuted">({pc(per[c].pct)})</span>
        </td>
      ))}
    </>
  );
}

function ClassHeads() {
  return (
    <>
      {CLASSES.map((c) => (
        <th key={c} className="py-1.5 text-right font-medium" style={{ color: REGIME_META[c].color }}>
          {REGIME_PLAIN[c].name}
        </th>
      ))}
    </>
  );
}

/**
 * Hasil uji identifikasi (h = 0), dibaca apa adanya dari updated_eval_summary.json.
 *
 * Pengguna biasa hanya melihat model aplikasi (Hybrid Attention-BiLSTM); perbandingan
 * dengan model lain hanya ditampilkan untuk admin. Angka tidak diubah.
 */
export default function EvaluationPage() {
  const { timeframe } = useAppConfig();
  const ev = useApi(() => api.evaluation(), []);
  const d = ev.data?.timeframes?.[timeframe];

  // Status admin dibaca sama seperti TopNav; bawaan false sampai respons datang.
  const [admin, setAdmin] = useState(false);
  useEffect(() => {
    fetch("/api/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((r) => setAdmin(Boolean(r?.admin)))
      .catch(() => setAdmin(false));
  }, []);
  const models = admin ? MODEL_ORDER : [APP_MODEL];
  const modelName = (label: string) => (admin ? label : APP_MODEL_NAME);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Hasil Uji Identifikasi"
        description={
          admin
            ? "Jumlah dan persentase jendela yang diidentifikasi benar oleh tiap model pada partisi uji historical backtesting dan pada 5-fold expanding purged walk-forward. Label acuan: Trend-Aware Soft Consensus Hurst R/S–DFA-1, ambang kuantil data latih. Ensemble = rata-rata softmax 3 seed (42, 43, 44). Angka dibaca langsung dari ml/artifacts/updated_eval_summary.json."
            : "Jumlah dan persentase jendela yang diidentifikasi benar oleh model identifikasi Hybrid Attention-BiLSTM pada partisi uji historical backtesting dan pada 5-fold expanding purged walk-forward. Label acuan: Trend-Aware Soft Consensus Hurst R/S–DFA-1, ambang kuantil data latih. Ensemble = rata-rata softmax 3 seed (42, 43, 44)."
        }
      />
      {admin && (
        <p className="text-[12px] text-txtMuted">Perbandingan model hanya terlihat oleh admin.</p>
      )}
      <ParameterBar />
      <ApiState loading={ev.loading} error={ev.error} />

      {d && (
        <>
          <Panel
            title={`Historical backtesting · ${timeframe.toUpperCase()}`}
            subtitle={`Partisi uji ${id(d.partitions.test.definitive)} jendela berlabel (split 70/15/15, purge ${d.purge_rows} baris = 500 bar, stride ${d.stride_bars} bar).`}
            params={{ sumber: "updated_eval_summary.json", h: 0 }}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1.5 text-left font-medium">Model</th>
                    <th className="py-1.5 text-right font-medium">Benar</th>
                    <th className="py-1.5 text-right font-medium">% benar</th>
                    <th className="py-1.5 text-right font-medium">Rata-rata 3 kelas</th>
                    <ClassHeads />
                  </tr>
                </thead>
                <tbody className="font-mono text-txtDim">
                  {models.map((k) => {
                    const m = d.backtest[k];
                    const main = admin && k === APP_MODEL;
                    return (
                      <tr key={k} className={`border-b border-edge/50 ${main ? "bg-surface/70 text-txt" : ""}`}>
                        <td className="py-1.5 font-sans">{modelName(m.label)}</td>
                        <td className="py-1.5 text-right">
                          {id(m.correct)}/{id(m.total)}
                        </td>
                        <td className="py-1.5 text-right font-semibold">{pc(m.pct)}</td>
                        <td className="py-1.5 text-right">{pc(m.balanced_pct)}</td>
                        <ClassCells per={m.per_class} />
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel
            title={`5-fold expanding purged walk-forward · ${timeframe.toUpperCase()}`}
            subtitle={
              admin
                ? "Model dilatih ulang tiap fold; ambang label dikalibrasi ulang dari data latih fold itu. Baris tebal = Hybrid Attention-BiLSTM (model aplikasi)."
                : "Model dilatih ulang tiap fold; ambang label dikalibrasi ulang dari data latih fold itu."
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1.5 text-left font-medium">Fold</th>
                    <th className="py-1.5 text-right font-medium">Latih</th>
                    <th className="py-1.5 text-right font-medium">Uji</th>
                    <th className="py-1.5 text-right font-medium">Hybrid Attention-BiLSTM benar</th>
                    <th className="py-1.5 text-right font-medium">% benar</th>
                    <ClassHeads />
                  </tr>
                </thead>
                <tbody className="font-mono text-txtDim">
                  {d.walk_forward.folds.map((f: any) => {
                    const m = f.models.hybrid_ps;
                    return (
                      <tr key={f.fold} className="border-b border-edge/50">
                        <td className="py-1.5 font-sans">Fold {f.fold}</td>
                        <td className="py-1.5 text-right">{id(f.n_train)}</td>
                        <td className="py-1.5 text-right">{id(f.n_test)}</td>
                        <td className="py-1.5 text-right">
                          {id(m.correct)}/{id(m.total)}
                        </td>
                        <td className="py-1.5 text-right font-semibold">{pc(m.pct)}</td>
                        <ClassCells per={m.per_class} />
                      </tr>
                    );
                  })}
                  <tr className="bg-surface/70 text-txt">
                    <td className="py-1.5 font-sans font-semibold">Gabungan</td>
                    <td />
                    <td className="py-1.5 text-right">{id(d.walk_forward.summary.hybrid_ps.total_test_pooled)}</td>
                    <td className="py-1.5 text-right">
                      {id(d.walk_forward.summary.hybrid_ps.total_correct_ensemble)}/{id(d.walk_forward.summary.hybrid_ps.total_test_pooled)}
                    </td>
                    <td className="py-1.5 text-right font-semibold">{pc(d.walk_forward.summary.hybrid_ps.pooled_pct_ensemble)}</td>
                    <td colSpan={3} className="py-1.5 text-right font-sans text-2xs text-txtMuted">
                      rata-rata antar-fold {pc(d.walk_forward.summary.hybrid_ps.fold_avg_pct)} ± {pc(d.walk_forward.summary.hybrid_ps.fold_std_pct)} (rata-rata 3 seed)
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="mt-4 overflow-x-auto">
              <div className="mb-1 text-[12px] font-medium text-txt">
                {admin ? "Gabungan 5 fold, semua model (ensemble)" : "Gabungan 5 fold (ensemble 3 seed)"}
              </div>
              <table className="w-full text-[12px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1.5 text-left font-medium">Model</th>
                    <th className="py-1.5 text-right font-medium">Benar</th>
                    <th className="py-1.5 text-right font-medium">% benar</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-txtDim">
                  {models.map((k) => {
                    const s = d.walk_forward.summary[k];
                    return (
                      <tr key={k} className={`border-b border-edge/50 ${k === APP_MODEL ? "text-txt" : ""}`}>
                        <td className="py-1.5 font-sans">{modelName(s.label)}</td>
                        <td className="py-1.5 text-right">
                          {id(s.total_correct_ensemble)}/{id(s.total_test_pooled)}
                        </td>
                        <td className="py-1.5 text-right font-semibold">{pc(s.pooled_pct_ensemble)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

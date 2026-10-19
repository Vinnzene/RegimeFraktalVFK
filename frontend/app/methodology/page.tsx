"use client";

import Disclaimer from "@/components/Disclaimer";
import Formula from "@/components/Formula";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import RegimeLegend from "@/components/RegimeLegend";
import ResearchFramework from "@/components/ResearchFramework";
import WalkForwardDiagram from "@/components/WalkForwardDiagram";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";

export default function MethodologyPage() {
  const meth = useApi(() => api.methodology(), []);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Metodologi"
        description="Definisi, rumus, dan kriteria yang dipakai sistem ini. Halaman ini ditujukan untuk audiens sidang, termasuk yang belum terbiasa dengan analisis fraktal."
      />

      <ParameterBar showTimeframe={false} />
      <Disclaimer variant="fractal" />
      <ApiState loading={meth.loading} error={meth.error} />

      <Panel
        title="Kerangka Penelitian"
        subtitle="Setiap solusi dibaca sebagai jawaban atas masalah tepat di atasnya."
      >
        <ResearchFramework />
      </Panel>

      {!meth.loading && !meth.error && (
        <>
          <div className="grid gap-3 lg:grid-cols-2">
            {(meth.data?.sections ?? []).map((s: any) => (
              <Panel key={s.id} title={s.title}>
                <div className="rounded border border-edge bg-panelAlt px-3 py-1">
                  <Formula tex={s.formula} />
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-txtDim">{s.body}</p>
              </Panel>
            ))}
          </div>

          <Panel
            title="Empat Kategori Regime"
            subtitle="Dua di antaranya adalah bentuk ketidakpastian dengan asal yang berbeda."
          >
            <RegimeLegend />
            <p className="mt-3 text-[11px] leading-relaxed text-txtDim">
              Pemisahan ini penting saat sidang: Uncertain (rule) menyatakan bahwa DATA-nya
              ambigu — Hurst dan DFA memberi kesimpulan berbeda pada window yang sama.
              Uncertain (low-conf) menyatakan bahwa MODEL-nya ragu — probabilitas tertinggi
              masih di bawah ambang τ. Menggabungkan keduanya akan menyembunyikan perbedaan
              antara keterbatasan data dan keterbatasan model.
            </p>
          </Panel>

          <Panel
            title="Walk-Forward Testing"
            subtitle="Jendela training bergeser maju bertahap; purge gap memisahkan train dari test."
          >
            <WalkForwardDiagram />
            <p className="mt-3 text-[11px] leading-relaxed text-txtDim">
              Split utama bersifat time-based tanpa shuffle (train → validation → test
              berurutan). Walk-forward dipakai sebagai pemeriksaan tambahan: apakah keunggulan
              model bertahan ketika periode training dan test digeser maju, atau hanya berlaku
              pada satu potongan waktu tertentu.
            </p>
          </Panel>

          <Panel
            title="Alur Pemrosesan"
            subtitle="Urutan yang dijalankan sistem, dari harga mentah hingga label regime."
          >
            <ol className="space-y-2 text-[11px] leading-relaxed text-txtDim">
              {[
                "Harga penutupan diubah menjadi log-return. Harga level tidak dipakai karena bersifat non-stasioner (unit root) sehingga estimasi Hurst akan selalu mendekati 1.",
                "Rolling window sepanjang L dibentuk. Window pada titik t hanya memuat data sampai t.",
                "Hurst (R/S) dan DFA α dihitung untuk tiap window.",
                "Label ground truth ditetapkan dari pasangan (H, α). Bila keduanya tidak sepakat, window ditandai Uncertain (rule).",
                "SWT dihitung ulang per window secara causal untuk membentuk fitur multiskala.",
                "Attention-BiLSTM memetakan fitur pada t ke regime pada t+h — bukan ke regime window yang sama, agar tugasnya prediktif dan bukan sekadar meniru rumus Hurst-DFA.",
                "Output softmax 3 kelas dilewatkan ambang τ; bila probabilitas tertinggi di bawah τ, label menjadi Uncertain (low-conf).",
              ].map((step, i) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-edge font-mono text-2xs text-txtMuted">
                    {i + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </Panel>
        </>
      )}
    </div>
  );
}

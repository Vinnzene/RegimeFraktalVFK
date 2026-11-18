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
              Uncertain (rule) hanya muncul pada label klasik Hurst-DFA: R/S dan DFA memberi
              kesimpulan berbeda pada window yang sama (47,4% window BTC 1H). Uncertain
              (low-conf) muncul pada model identifikasi AI: probabilitas tertinggi di bawah ambang τ = 0,75.
              Pada set validasi, jendela dengan keyakinan ≥ 0,75 (25% di 1H, 49% di 4H) teridentifikasi
              benar 85,7% (1H) dan 94,8% (4H). Label tetap argmax; τ hanya penanda. Keduanya dipisah
              karena yang satu keterbatasan data, yang lain keterbatasan model.
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
            subtitle="Urutan yang dijalankan model identifikasi sistem, dari harga mentah hingga label regime."
          >
            <ol className="space-y-2 text-[11px] leading-relaxed text-txtDim">
              {[
                "Harga penutupan diubah menjadi log-return. Harga level tidak dipakai karena bersifat non-stasioner (unit root) sehingga estimasi Hurst akan selalu mendekati 1. Candle yang belum tutup dibuang.",
                "Rolling window 500 bar dibentuk setiap 4 bar (1H) atau 2 bar (4H). Window pada titik t hanya memuat data sampai t; tugasnya identifikasi kondisi saat ini (h = 0), bukan prediksi.",
                "Fitur dihitung tanpa penskalaan ulang: sekuens statistik persistensi 32 × 14 (variance ratio, autokorelasi, volatilitas, efficiency ratio per sub-window) dan 56 fitur (50 struktural termasuk 12 rasio energi SWT db4 4 level causal, + 6 multifraktal), lalu distandarkan dengan statistik partisi latih.",
                "Ensemble 3 seed Hybrid PS Attention-BiLSTM mengeluarkan probabilitas tiga kelas. Model dilatih pada partisi latih BTC (70%) untuk mengenali label Trend-Aware Soft Consensus Hurst R/S–DFA-1 dengan ambang kuantil train-only.",
                "Bila probabilitas tertinggi di bawah τ = 0,75, kondisi ditandai keyakinan rendah (Uncertain low-conf).",
                "Hurst R/S dan DFA α dihitung untuk setiap window; konsensusnya adalah label yang dipelajari model dan ditampilkan di halaman Hurst-DFA Klasik.",
                "Pergantian regime diumumkan (dashboard dan Telegram) bila 3 window berturut-turut berlabel sama.",
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

"use client";

import Disclaimer from "@/components/Disclaimer";
import { useMemo } from "react";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import RegimeLegend from "@/components/RegimeLegend";
import TransitionMatrix from "@/components/TransitionMatrix";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";
import { REGIME_META, regimeLabel, type Regime } from "@/lib/regime";

/**
 * Timeline regime sebagai pita horizontal — memudahkan perbandingan 1H vs 4H.
 *
 * Titik berurutan dengan regime sama digabung menjadi satu elemen. Satu div per
 * window akan menghasilkan ~1375 node per kolom (2750 untuk dua kolom); setelah
 * dikompresi biasanya tinggal puluhan.
 */
function RegimeTimeline({ series }: { series: any[] }) {
  const runs = useMemo(() => {
    const out: { regime: string; length: number; start: number; end: number }[] = [];
    series.forEach((p) => {
      const last = out[out.length - 1];
      if (last && last.regime === p.regime) {
        last.length += 1;
        last.end = p.time;
      } else {
        out.push({ regime: p.regime, length: 1, start: p.time, end: p.time });
      }
    });
    return out;
  }, [series]);

  if (runs.length === 0) return null;

  const iso = (t: number) => new Date(t * 1000).toISOString().slice(0, 10);

  return (
    <div className="flex h-8 w-full overflow-hidden rounded border border-edge">
      {runs.map((r, i) => (
        <div
          key={i}
          className="h-full"
          style={{
            flexGrow: r.length,
            flexBasis: 0,
            backgroundColor: REGIME_META[r.regime as Regime]?.color ?? "#334155",
          }}
          title={`${iso(r.start)} – ${iso(r.end)} · ${regimeLabel(r.regime)} (${r.length} window)`}
        />
      ))}
    </div>
  );
}

function TimeframeColumn({ tf }: { tf: string }) {
  const regime = useApi(() => api.regime(tf), [tf]);
  const duration = useApi(() => api.regimeDuration(tf), [tf]);
  const transition = useApi(() => api.transitionMatrix(tf), [tf]);

  const loading = regime.loading || duration.loading || transition.loading;
  const error = regime.error ?? duration.error ?? transition.error;

  const series = regime.data?.series ?? [];
  const switches = series.reduce(
    (acc: number, p: any, i: number) => (i > 0 && series[i - 1].regime !== p.regime ? acc + 1 : acc),
    0
  );
  const summary = duration.data?.summary ?? {};
  const meanAll =
    Object.values(summary).reduce((a: number, v: any) => a + (v.mean ?? 0), 0) /
    (Object.keys(summary).length || 1);

  return (
    <div className="space-y-3">
      <Panel
        title={`Timeframe ${tf.toUpperCase()}`}
        subtitle={`Regime aktif: ${regimeLabel(regime.data?.current_regime ?? "-")}`}
        params={{ window: series.length, perpindahan: switches }}
      >
        <ApiState loading={loading} error={error} />
        {!loading && !error && (
          <>
            <RegimeTimeline series={series} />
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded border border-edge bg-panelAlt p-2">
                <div className="metric-label">Durasi rata-rata</div>
                <div className="font-mono text-lg text-txt">{meanAll.toFixed(1)}</div>
                <div className="text-2xs text-txtMuted">window</div>
              </div>
              <div className="rounded border border-edge bg-panelAlt p-2">
                <div className="metric-label">Frekuensi pindah</div>
                <div className="font-mono text-lg text-txt">
                  {series.length ? ((switches / series.length) * 100).toFixed(1) : "0"}%
                </div>
                <div className="text-2xs text-txtMuted">per window</div>
              </div>
            </div>
            <div className="mt-3 space-y-1.5">
              {Object.entries(regime.data?.distribution ?? {}).map(([key, val]: any) => (
                <div key={key} className="flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-sm"
                    style={{ backgroundColor: REGIME_META[key as Regime]?.color }}
                  />
                  <span className="flex-1 text-[11px] text-txtDim">{regimeLabel(key)}</span>
                  <span className="font-mono text-[11px] text-txtDim">
                    {(val.share * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </Panel>

      <Panel title={`Matriks Transisi ${tf.toUpperCase()}`} subtitle="P(R_t+1 = j | R_t = i)">
        {!loading && !error && (
          <TransitionMatrix
            categories={transition.data?.categories ?? []}
            matrix={transition.data?.matrix ?? []}
            counts={transition.data?.counts}
          />
        )}
      </Panel>
    </div>
  );
}

export default function TimeframeComparisonPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Perbandingan 1H vs 4H"
        description="Apakah karakteristik regime berubah mengikuti skala waktu pengamatan. Perhatikan bahwa 4H memakai seperempat jumlah sampel 1H untuk rentang kalender yang sama, sehingga sebagian perbedaan bisa berasal dari ukuran sampel, bukan dari sifat skalanya."
      />
      <Disclaimer variant="classic" />

      <ParameterBar showTimeframe={false} />

      <div className="rounded border border-warn/40 bg-warn/10 px-3 py-2 text-[11px] leading-relaxed text-warn/90">
        <span className="font-semibold">Kontrol interpretasi. </span>
        Estimasi Hurst pada 4H lebih bising karena jumlah bar lebih sedikit. Saat menyimpulkan
        &quot;regime berbeda antar timeframe&quot;, bandingkan pada jumlah bar yang setara,
        bukan pada rentang kalender yang setara.
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <TimeframeColumn tf="1h" />
        <TimeframeColumn tf="4h" />
      </div>

      <Panel title="Legenda" subtitle="Kategori yang sama dipakai di kedua timeframe.">
        <RegimeLegend />
      </Panel>
    </div>
  );
}

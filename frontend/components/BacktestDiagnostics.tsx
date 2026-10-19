"use client";

import Panel from "@/components/Panel";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";
import { regimeLabel } from "@/lib/regime";

/**
 * Diagnostik backtest.
 *
 * Equity curve yang menurun tidak menjelaskan penyebabnya. Panel ini memisahkan
 * tiga sumber kerugian yang mungkin — arah posisi, volatility drag, biaya —
 * lalu menguji apakah hasilnya berbeda dari kebetulan dan apakah asumsi arah
 * pada aturan Bab 3 benar-benar berlaku.
 */
export default function BacktestDiagnostics({
  timeframe,
  regimeSource,
  modelKey,
  feeBps,
}: {
  timeframe: string;
  regimeSource: string;
  modelKey: string;
  feeBps: number;
}) {
  const diag = useApi(
    () => api.backtestDiagnostics(timeframe, regimeSource, modelKey, feeBps),
    [timeframe, regimeSource, modelKey, feeBps]
  );

  if (diag.loading || diag.error) {
    return (
      <Panel title="Diagnostik" subtitle="Menghitung bukti pendukung…">
        <ApiState loading={diag.loading} error={diag.error} />
      </Panel>
    );
  }

  const d = diag.data;
  if (!d?.available) return null;

  const dec = d.decomposition ?? {};
  const rb = d.random_benchmark ?? {};
  const dir = d.direction ?? {};
  const stab = d.stability ?? [];

  const components = [
    { label: "Arah posisi (edge)", value: dec.edge_component },
    { label: "Volatility drag", value: dec.drag_component },
    { label: "Biaya transaksi", value: dec.cost_component },
  ];
  const maxAbs = Math.max(...components.map((c) => Math.abs(c.value ?? 0)), 0.01);

  const verdictTone =
    rb.percentile_of_strategy < 5
      ? "border-antiPersistent/50 bg-antiPersistent/10 text-antiPersistent"
      : rb.percentile_of_strategy > 95
        ? "border-persistent/50 bg-persistent/10 text-persistent"
        : "border-edge bg-surface/50 text-txtDim";

  return (
    <>
      <Panel
        title="Dari mana kerugiannya berasal?"
        subtitle="Log-equity kumulatif dipisah menjadi tiga sumber. Nilai negatif memperkecil modal."
        params={{ sumber: d.regime_source, fee_bps: d.fee_bps }}
      >
        <div className="space-y-2">
          {components.map((c) => {
            const v = c.value ?? 0;
            const width = (Math.abs(v) / maxAbs) * 100;
            return (
              <div key={c.label}>
                <div className="flex justify-between text-[11px]">
                  <span className="text-txtDim">{c.label}</span>
                  <span className="font-mono text-txtDim">{v.toFixed(4)}</span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded bg-panelAlt">
                  <div
                    className="h-full"
                    style={{
                      width: `${width}%`,
                      backgroundColor: v < 0 ? "#f97316" : "#3b82f6",
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
          <span className="text-txtDim">Edge</span> adalah kontribusi arah posisi;{" "}
          <span className="text-txtDim">drag</span> adalah penalti volatilitas yang melekat
          pada pertumbuhan majemuk dan tidak dapat dihindari strategi mana pun;{" "}
          <span className="text-txtDim">biaya</span> adalah ongkos transaksi. Bila edge
          bernilai negatif besar, kerugian berasal dari arah posisi yang keliru — bukan
          sekadar tergerus biaya.
        </p>
      </Panel>

      <Panel
        title="Apakah hasilnya berbeda dari kebetulan?"
        subtitle={`Dibandingkan dengan ${rb.n_simulations} simulasi posisi acak ber-exposure identik (${rb.exposure}).`}
      >
        <div className={`rounded border px-3 py-2 text-[11px] leading-relaxed ${verdictTone}`}>
          <span className="font-semibold">
            Strategi berada di persentil {rb.percentile_of_strategy} — {rb.verdict}.
          </span>
          {rb.percentile_of_strategy < 5 && (
            <div className="mt-1">
              Kalah konsisten dari tebakan acak bukan pertanda sinyal kosong. Sinyal yang
              benar-benar tanpa informasi akan mendarat di sekitar persentil 50. Nilai yang
              sangat rendah justru menunjukkan arah posisi terbalik secara sistematis —
              artinya ada informasi, hanya dipakai dengan tanda yang keliru.
            </div>
          )}
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          {[
            ["Strategi", rb.strategy_return],
            ["Median acak", rb.random_median],
            ["Persentil 5", rb.random_p5],
            ["Persentil 95", rb.random_p95],
          ].map(([label, value]) => (
            <div key={label as string} className="rounded border border-edge bg-panelAlt p-2">
              <div className="metric-label">{label as string}</div>
              <div
                className={`mt-0.5 font-mono text-sm ${
                  (value as number) < 0 ? "text-antiPersistent" : "text-persistent"
                }`}
              >
                {(((value as number) ?? 0) * 100).toFixed(1)}%
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel
        title="Apakah asumsi arah pada aturan berlaku?"
        subtitle={`Autokorelasi lag-1 return antar-window: ${dir.lag1_autocorrelation}`}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead className="text-txtMuted">
              <tr className="border-b border-edge">
                <th className="py-1 text-left">Regime</th>
                <th className="py-1 text-right">n</th>
                <th className="py-1 text-right">P(arah berlanjut)</th>
                <th className="py-1 text-left">Diasumsikan aturan</th>
                <th className="py-1 text-center">Berlaku?</th>
              </tr>
            </thead>
            <tbody className="font-mono text-txtDim">
              {(dir.per_regime ?? []).map((p: any) => (
                <tr key={p.regime} className="border-b border-edge/50">
                  <td className="py-1 font-sans text-txtDim">{regimeLabel(p.regime)}</td>
                  <td className="py-1 text-right">{p.n}</td>
                  <td
                    className={`py-1 text-right ${
                      p.p_same_direction < 0.5 ? "text-antiPersistent" : "text-persistent"
                    }`}
                  >
                    {p.p_same_direction.toFixed(4)}
                  </td>
                  <td className="py-1 font-sans text-txtMuted">{p.assumed_by_rule}</td>
                  <td className="py-1 text-center">
                    {p.assumption_holds === null ? (
                      <span className="text-txtMuted">—</span>
                    ) : p.assumption_holds ? (
                      <span className="text-persistent">ya</span>
                    ) : (
                      <span className="text-antiPersistent">tidak</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
          Nilai 0.5 berarti arah return berikutnya tidak dapat ditebak sama sekali. Aturan
          pada Bab 3 mengandaikan regime Persistent membuat arah berlanjut (P &gt; 0.5).
          Perlu dicatat bahwa Hurst Exponent mengukur persistensi struktur skala dan
          volatilitas — bukan tanda return. Tabel ini menguji apakah penerjemahan dari
          persistensi menjadi prediksi arah dapat dipertahankan pada data BTC/USDT.
        </p>
      </Panel>

      <Panel
        title="Apakah polanya stabil?"
        subtitle="Hasil yang hanya muncul di satu segmen adalah kebetulan, bukan temuan."
      >
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead className="text-txtMuted">
              <tr className="border-b border-edge">
                <th className="py-1 text-left">Segmen</th>
                <th className="py-1 text-right">n window</th>
                <th className="py-1 text-right">Return kumulatif</th>
                <th className="py-1 text-right">Hit rate</th>
                <th className="py-1 text-right">Exposure</th>
              </tr>
            </thead>
            <tbody className="font-mono text-txtDim">
              {stab.map((s: any) => (
                <tr key={s.segment} className="border-b border-edge/50">
                  <td className="py-1 font-sans text-txtDim">{s.segment}</td>
                  <td className="py-1 text-right text-txtMuted">{s.n}</td>
                  <td
                    className={`py-1 text-right ${
                      s.cumulative_return < 0 ? "text-antiPersistent" : "text-persistent"
                    }`}
                  >
                    {(s.cumulative_return * 100).toFixed(2)}%
                  </td>
                  <td className="py-1 text-right">{s.hit_rate?.toFixed(3) ?? "—"}</td>
                  <td className="py-1 text-right text-txtMuted">{s.exposure}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
          Hit rate di sekitar 0.50 menandakan arah posisi praktis setara lemparan koin.
          Perhatikan pula apakah tanda return kumulatif konsisten di ketiga segmen — bila
          berbeda-beda, pola tersebut tidak dapat diandalkan terlepas dari besar angkanya.
        </p>
      </Panel>
    </>
  );
}

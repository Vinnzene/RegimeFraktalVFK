"use client";

import Panel from "@/components/Panel";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";
import { regimeLabel } from "@/lib/regime";

/**
 * Hasil tugas IDENTIFIKASI regime.
 *
 * Dipisahkan dari panel perbandingan model karena menjawab pertanyaan berbeda:
 * "window ini regimenya apa" — bukan "regimenya nanti apa". Judul penelitian
 * menyebut identifikasi, sehingga angka di sini yang paling dekat dengan
 * rumusan masalahnya.
 */
export default function IdentificationPanel({ timeframe }: { timeframe: string }) {
  const res = useApi(() => api.identification(timeframe), [timeframe]);

  if (res.loading || res.error) {
    return (
      <Panel title="Identifikasi Regime" subtitle="Memuat…">
        <ApiState loading={res.loading} error={res.error} />
      </Panel>
    );
  }

  if (!res.data?.available) {
    return (
      <Panel
        title="Identifikasi Regime"
        subtitle="Mengenali regime window saat ini dari struktur deret."
      >
        <p className="text-[11px] leading-relaxed text-txtMuted">
          Belum dilatih. Jalankan perintah berikut, lalu muat ulang halaman:
        </p>
        <pre className="mt-2 overflow-x-auto rounded border border-edge bg-panelAlt p-2 font-mono text-2xs text-txtDim">
          {res.data?.perintah ?? "python ml/src/train_identification.py"}
        </pre>
      </Panel>
    );
  }

  const modes = res.data.modes ?? {};
  // Sorotan memakai tugas utama skripsi (tiga kelas) dan balanced accuracy.
  // Mode biner lebih mudah dan akurasi biasa menggelembung pada kelas timpang,
  // jadi keduanya tidak dipakai sebagai angka utama.
  const best = Object.values(modes)
    .flatMap((m: any) => m.models ?? [])
    .filter((m: any) => (m.classes?.length ?? 3) === 3)
    .reduce(
      (acc: any, m: any) =>
        acc === null || (m.test?.balanced_accuracy ?? 0) > (acc.test?.balanced_accuracy ?? 0) ? m : acc,
      null
    );
  const anyStale = Object.values(modes)
    .flatMap((m: any) => m.models ?? [])
    .some((m: any) => m.config_matches === false);

  return (
    <Panel
      title="Identifikasi Regime"
      subtitle="Mengenali regime window yang sedang diamati (h = 0), bukan memprediksi ke depan."
      params={{ tf: timeframe }}
    >
      {best && (
        <div className="mb-3 rounded border border-accent/40 bg-accent/10 px-3 py-2 text-[11px] leading-relaxed text-txtDim">
          <span className="font-semibold text-accent">
            Balanced accuracy tertinggi {((best.test?.balanced_accuracy ?? 0) * 100).toFixed(1)}%
          </span>{" "}
          pada tugas tiga kelas, model{" "}
          {best.model === "hybrid_attention_bilstm"
            ? "SWT + Attention-BiLSTM + fitur struktural"
            : "MLP fitur struktural"}
          . Tebakan acak = 33,3%.
        </div>
      )}

      {anyStale && (
        <div className="mb-3 rounded border border-warn/40 bg-warn/10 px-3 py-2 text-[11px] leading-relaxed text-warn">
          Sebagian artefak dilatih dengan konfigurasi lama (ditandai &ldquo;config berbeda&rdquo;). Angkanya tetap
          ditampilkan sebagai arsip; hasil evaluasi terbaru ada di laporan Bab 4.
        </div>
      )}

      {Object.entries(modes).map(([mode, payload]: [string, any]) => (
        <div key={mode} className="mb-4 last:mb-0">
          <div className="mb-2 flex items-baseline gap-2">
            <span className="text-[12px] font-semibold text-txt">
              {mode === "binary" ? "Mode biner" : "Mode tiga kelas"}
            </span>
            <span className="text-2xs text-txtMuted">
              {(payload.models?.[0]?.classes ?? []).map(regimeLabel).join(" · ")}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="text-left">Model</th>
                  <th className="text-right">n train</th>
                  <th className="text-right">n test</th>
                  <th className="text-right">Akurasi</th>
                  <th className="text-right">BA</th>
                  <th className="text-right">MCC</th>
                </tr>
              </thead>
              <tbody>
                {(payload.models ?? []).map((m: any) => {
                  const acc = m.test?.accuracy ?? 0;
                  return (
                    <tr key={m.model}>
                      <td className="font-sans text-txtDim">
                        {m.model === "hybrid_attention_bilstm"
                          ? "SWT + Attention-BiLSTM + struktural"
                          : "MLP fitur struktural"}
                        {!m.config_matches && (
                          <span className="ml-2 text-2xs text-warn">config berbeda</span>
                        )}
                      </td>
                      <td className="text-right text-txtMuted">{m.n_train}</td>
                      <td className="text-right text-txtMuted">{m.n_test}</td>
                      <td
                        className={`text-right font-semibold ${
                          acc >= 0.88 ? "text-bullish" : "text-txtDim"
                        }`}
                      >
                        {(acc * 100).toFixed(2)}%
                      </td>
                      <td className="text-right">
                        {((m.test?.balanced_accuracy ?? 0) * 100).toFixed(2)}%
                      </td>
                      <td className="text-right text-txtMuted">
                        {(m.test?.mcc ?? 0).toFixed(3)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Recall per kelas menjelaskan di mana model kuat dan di mana lemah. */}
          {payload.models?.[0]?.test?.per_class && (
            <div className="mt-2 flex flex-wrap gap-3">
              {Object.entries(
                payload.models.find((m: any) => m.model === "hybrid_attention_bilstm")
                  ?.test?.per_class ?? payload.models[0].test.per_class
              ).map(([cls, v]: [string, any]) => (
                <div key={cls} className="flex items-center gap-1.5 text-2xs">
                  <span className="text-txtMuted">{regimeLabel(cls)}</span>
                  <span
                    className={`font-mono ${
                      v.recall >= 0.8 ? "text-bullish" : v.recall < 0.3 ? "text-bearish" : "text-txtDim"
                    }`}
                  >
                    {(v.recall * 100).toFixed(1)}%
                  </span>
                  <span className="text-txtMuted">(n={v.n})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
        <span className="text-txtDim">Catatan metodologis: </span>
        Hurst dan DFA sengaja tidak dipakai sebagai fitur. Label regime dibentuk dari
        keduanya lewat aturan ambang, sehingga memberikannya sebagai input akan membuat
        model sekadar menghafal aturan if-else — label sirkular, dan angka akurasinya tidak
        membuktikan apa pun. Fitur yang dipakai adalah variance ratio (Lo &amp; MacKinlay),
        autokorelasi multi-lag, dan rasio energi antar-skala SWT: berkaitan dengan
        persistensi secara teoretis, tetapi dihitung dengan cara yang berbeda.
      </p>
      <p className="mt-1.5 text-2xs leading-relaxed text-txtMuted">
        Mode biner mengeluarkan kategori Random-like karena batasnya kabur secara definisi —
        ia dinyatakan sebagai &quot;tidak persisten dan tidak anti-persisten&quot;, sehingga
        berada tepat di perbatasan dua kelas lainnya.
      </p>
    </Panel>
  );
}

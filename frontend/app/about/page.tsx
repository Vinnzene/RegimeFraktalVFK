"use client";

import DataStatusBar from "@/components/DataStatusBar";
import Disclaimer from "@/components/Disclaimer";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ParameterBar from "@/components/ParameterBar";
import { useAppConfig } from "@/components/ConfigContext";
import { ApiState, useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";

export default function AboutPage() {
  const { config, configHash } = useAppConfig();
  const status = useApi(() => api.dataStatus(), []);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Tentang Penelitian"
        description="Identifikasi Regime Fraktal Dinamis BTC/USDT Multi-Timeframe menggunakan SWT dan Attention-BiLSTM berbasis Hurst-DFA."
      />

      <ParameterBar showTimeframe={false} />
      <DataStatusBar />

      <Panel
        title="Sumber Data"
        subtitle="Asal data historis yang dipakai seluruh analisis di dashboard ini."
      >
        <ApiState loading={status.loading} error={status.error} />
        {!status.loading && !status.error && status.data && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1 text-left">Timeframe</th>
                    <th className="py-1 text-right">Jumlah bar</th>
                    <th className="py-1 text-right">Bar pertama</th>
                    <th className="py-1 text-right">Bar terakhir</th>
                    <th className="py-1 text-right">Sumber</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-txtDim">
                  {status.data.timeframes.map((t: any) => (
                    <tr key={t.timeframe} className="border-b border-edge/50">
                      <td className="py-1 font-sans text-txtDim">
                        {t.timeframe.toUpperCase()}
                      </td>
                      <td className="py-1 text-right">{t.rows?.toLocaleString() ?? "—"}</td>
                      <td className="py-1 text-right">
                        {t.first_time
                          ? new Date(t.first_time * 1000).toISOString().slice(0, 10)
                          : "—"}
                      </td>
                      <td className="py-1 text-right">
                        {t.last_time
                          ? new Date(t.last_time * 1000).toISOString().slice(0, 16).replace("T", " ")
                          : "—"}
                      </td>
                      <td className="py-1 text-right text-txtMuted">{t.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-txtDim">
              Data diambil dari{" "}
              <span className="font-mono text-txtDim">data-api.binance.vision</span>, mirror
              data pasar resmi Binance, sepanjang {status.data.years} tahun terakhir. Bar yang
              belum tutup selalu dibuang sebelum analisis: nilai penutupnya masih berubah,
              sehingga menyertakannya membuat Hurst dan label regime pada window terakhir
              berubah setiap kali data disegarkan.
            </p>
          </>
        )}
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Latar Belakang">
          <p className="text-[11px] leading-relaxed text-txtDim">
            Penelitian ini tidak memprediksi harga. Yang diidentifikasi adalah{" "}
            <span className="text-txt">regime karakteristik</span> deret waktu BTC/USDT:
            apakah pergerakan pada suatu periode cenderung berlanjut (persistent), menyerupai
            random walk (random-like), atau cenderung berbalik arah (anti-persistent).
            Karakterisasi dilakukan dengan Hurst Exponent dan Detrended Fluctuation Analysis
            pada rolling window, direpresentasikan multiskala lewat Stationary Wavelet
            Transform, lalu dipelajari polanya oleh Attention-BiLSTM.
          </p>
        </Panel>

        <Panel title="Tujuan">
          <ul className="space-y-1.5 text-[11px] leading-relaxed text-txtDim">
            {[
              "Mengkarakterisasi regime fraktal BTC/USDT berdasarkan Hurst-DFA.",
              "Menguji apakah SWT + Attention-BiLSTM dapat mengidentifikasi regime periode berikutnya.",
              "Membandingkan hasil pada timeframe 1H dan 4H.",
              "Menilai kegunaan praktis informasi regime lewat backtesting eksploratif.",
            ].map((t, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-persistent">•</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Batasan Penelitian">
          <ul className="space-y-1.5 text-[11px] leading-relaxed text-txtDim">
            {[
              "Output utama bukan prediksi harga.",
              "Faktor eksternal (berita, sentimen, makroekonomi, fundamental) tidak dipakai.",
              "Tidak ada eksekusi order otomatis ke exchange.",
              "Accuracy / precision / recall / F1 bukan indikator keberhasilan utama.",
              "Data terbatas pada BTC/USDT.",
              "Backtest bersifat eksploratif, bukan jaminan profit.",
            ].map((t, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-antiPersistent">•</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Yang Masih Terbuka">
          <ul className="space-y-1.5 text-[11px] leading-relaxed text-txtDim">
            {[
              "Angka pasti ukuran rolling window L untuk 1H dan 4H.",
              "Angka pasti level dekomposisi SWT (J).",
              "Detail arsitektur numerik Attention-BiLSTM (unit, layer, dropout).",
              "Nilai horizon h final setelah uji sensitivitas.",
            ].map((t, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-txtMuted">◦</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
            Seluruh butir di atas bersifat numerik. Nilainya dibaca dari{" "}
            <span className="font-mono">config.yaml</span> sehingga dapat diisi tanpa mengubah
            struktur sistem.
          </p>
        </Panel>
      </div>

      <Panel title="Konfigurasi Aktif" subtitle="Jejak reproducibility untuk keperluan akademik.">
        <pre className="overflow-x-auto rounded border border-edge bg-panelAlt p-3 font-mono text-2xs leading-relaxed text-txtDim">
          {JSON.stringify(config, null, 2)}
        </pre>
        <div className="mt-2 break-all text-2xs text-txtMuted">
          config_hash (SHA-256): <span className="font-mono text-txtDim">{configHash}</span>
        </div>
      </Panel>

      <Disclaimer variant="fractal" />
      <Disclaimer variant="backtest" />
    </div>
  );
}

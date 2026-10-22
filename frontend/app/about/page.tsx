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
            Regime didefinisikan oleh eksponen Hurst. Estimator klasik Hurst R/S dan DFA
            ternyata sering tidak sepakat dan kurang akurat pada data kripto, sehingga
            identifikasi dilakukan oleh Attention-BiLSTM yang dilatih pada deret sintetis
            dengan nilai Hurst yang diketahui, memakai fitur persistensi dan energi multiskala
            Stationary Wavelet Transform.
          </p>
        </Panel>

        <Panel title="Tujuan">
          <ul className="space-y-1.5 text-[11px] leading-relaxed text-txtDim">
            {[
              "Mengukur konsistensi dan akurasi estimator Hurst-DFA klasik pada BTC/USDT.",
              "Menguji peran SWT dan sekuens statistik persistensi sebagai representasi.",
              "Membangun Attention-BiLSTM yang mengidentifikasi regime saat ini dan membandingkannya dengan estimator klasik.",
              "Membandingkan identifikasi pada timeframe 1H dan 4H.",
              "Menguji generalisasi ke aset lain dan kegunaannya untuk memilih strategi setelah biaya.",
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
              "Identifikasi kondisi saat ini, bukan prediksi harga atau prediksi regime.",
              "Hanya data harga OHLCV; berita, sentimen, dan fundamental tidak dipakai.",
              "Tidak ada eksekusi order otomatis ke exchange.",
              "Objek utama BTC/USDT 1H dan 4H; 19 aset lain hanya untuk uji generalisasi tanpa latih ulang.",
              "Deteksi pergantian regime butuh waktu (median ±300 bar) karena window 500 bar.",
              "Hasil uji strategi bukan jaminan profit.",
            ].map((t, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-antiPersistent">•</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Temuan Utama">
          <ul className="space-y-1.5 text-[11px] leading-relaxed text-txtDim">
            {[
              "R/S dan DFA hanya sepakat pada 52,6% window BTC 1H.",
              "Attention-BiLSTM latih-sintetis lebih akurat dari Hurst-DFA klasik terbaik: 0,813 vs 0,654.",
              "Koefisien SWT mentah gagal (BA 0,38); energi SWT dan attention tidak terbukti menambah akurasi.",
              "Menggabungkan timeframe lebih tepat (+0,03) tetapi lebih lambat mendeteksi pergantian (+39%).",
              "Pemilihan strategi berbasis regime tidak menambah Sharpe setelah biaya; kegunaannya sebagai filter \"jangan trading\".",
            ].map((t, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-txtMuted">◦</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
            Setiap uji dipraregistrasi (hipotesis dikunci sebelum hasil dilihat); rincian di
            folder <span className="font-mono">docs/</span> dan <span className="font-mono">ml/artifacts/</span>.
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

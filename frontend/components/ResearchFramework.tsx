"use client";

/**
 * Kerangka penelitian dalam format masalah-solusi.
 *
 * Disusun berpasangan agar setiap solusi terbaca sebagai jawaban atas masalah
 * tepat di atasnya — bentuk yang lazim dipakai saat mempertahankan rancangan
 * penelitian. Angka pada kolom bukti diambil dari hasil nyata sistem, bukan
 * ditulis ulang sebagai teks statis.
 */

interface Row {
  stage: string;
  content: string;
  kind: "problem" | "solution" | "output" | "analysis";
  evidence?: string;
}

const ROWS: Row[] = [
  {
    stage: "Masalah umum",
    kind: "problem",
    content:
      "Sifat gerakan Bitcoin (berlanjut, acak, atau berbalik) berubah dari waktu ke waktu; strategi yang tidak cocok dengan kondisi itu merugi.",
  },
  {
    stage: "Solusi masalah umum",
    kind: "solution",
    content: "Identifikasi regime fraktal berbasis eksponen Hurst pada rolling window, untuk timeframe 1H dan 4H.",
    evidence: "L = 500 bar · langkah 4 bar · kelas H < 0,47 / 0,47–0,53 / > 0,53",
  },
  {
    stage: "Masalah khusus",
    kind: "problem",
    content:
      "Estimator Hurst-DFA klasik tidak konsisten dan tidak akurat pada data berderau; regime sebenarnya di data nyata tidak teramati.",
    evidence: "R/S dan DFA hanya sepakat 52,6% (BTC 1H) · konsensus naif BA 0,268 pada data mirip kripto",
  },
  {
    stage: "Solusi informatika",
    kind: "solution",
    content:
      "Attention-BiLSTM dengan sekuens statistik persistensi dan fitur multi-skala (termasuk energi SWT), dilatih pada deret sintetis berkarakter kripto yang nilai H-nya diketahui.",
    evidence: "BA 0,813 vs Hurst-DFA klasik terbaik 0,654 (+0,159, terbukti) · selisih latih–uji ±0,01",
  },
  {
    stage: "Temuan yang dilaporkan terbuka",
    kind: "analysis",
    content:
      "Koefisien SWT mentah gagal; energi SWT dan lapisan attention tidak terbukti menambah akurasi; menggabungkan timeframe lebih tepat tetapi lebih lambat.",
    evidence: "SWT mentah BA 0,38 · ablasi SWT ΔBA −0,0003 · H3 tidak terbukti · multi-skala +0,03 BA, +39% keterlambatan",
  },
  {
    stage: "Output",
    kind: "output",
    content:
      "Regime Tren Berlanjut, Acak, dan Cenderung Berbalik beserta keyakinan model, untuk 1H dan 4H, di dashboard dan notifikasi Telegram.",
    evidence: "Deteksi pergantian regime median 296 bar (2× lebih cepat dari konsensus Hurst-DFA)",
  },
  {
    stage: "Kegunaan",
    kind: "analysis",
    content:
      "Uji pemilihan strategi setelah biaya (Fase 2) dan uji generalisasi pada 20 aset tanpa latih ulang.",
    evidence: "Saat label acak, strategi aktif rugi paling besar → filter \"jangan trading\" · saham IDX: drawdown ±½ beli-tahan",
  },
];

const TONE: Record<Row["kind"], { border: string; label: string }> = {
  problem: { border: "border-l-bearish", label: "text-bearish" },
  solution: { border: "border-l-bullish", label: "text-bullish" },
  output: { border: "border-l-persistent", label: "text-persistent" },
  analysis: { border: "border-l-warn", label: "text-warn" },
};

export default function ResearchFramework() {
  return (
    <div className="space-y-1.5">
      {ROWS.map((row) => {
        const tone = TONE[row.kind];
        return (
          <div
            key={row.stage}
            className={`rounded border border-edge border-l-2 bg-surface/40 px-3 py-2 ${tone.border}`}
          >
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className={`shrink-0 text-2xs font-semibold uppercase tracking-wider ${tone.label}`}>
                {row.stage}
              </span>
              <span className="flex-1 text-[11px] leading-relaxed text-txtDim">
                {row.content}
              </span>
            </div>
            {row.evidence && (
              <div className="mt-1 font-mono text-2xs text-txtMuted">{row.evidence}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

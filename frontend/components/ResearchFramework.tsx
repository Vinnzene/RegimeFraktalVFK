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
      "Karakteristik pola Bitcoin berubah dari waktu ke waktu dan berbeda pada skala waktu.",
  },
  {
    stage: "Solusi masalah umum",
    kind: "solution",
    content: "Karakterisasi dinamis menggunakan Hurst-DFA dengan rolling window.",
    evidence: "L = 500 bar · stride 4 bar · 16.736 window pada 1H",
  },
  {
    stage: "Masalah informatika",
    kind: "problem",
    content:
      "Data sequence bersifat kompleks, temporal, dan multiskala sehingga sulit dikenali secara otomatis.",
  },
  {
    stage: "Solusi informatika",
    kind: "solution",
    content:
      "SWT untuk representasi multiskala dan Attention-BiLSTM untuk pembelajaran temporal.",
    evidence: "SWT J = 4 level, dihitung causal per window",
  },
  {
    stage: "Masalah khusus",
    kind: "problem",
    content:
      "Hasil model harus dikaitkan dengan regime yang memiliki dasar karakteristik statistik dan tidak boleh mengalami leakage.",
  },
  {
    stage: "Solusi masalah khusus",
    kind: "solution",
    content:
      "Hurst-DFA membentuk target regime; input hanya berasal dari data historis sampai waktu t.",
    evidence: "SWT causal · purge gap L + h di batas split · scaler dari subset training",
  },
  {
    stage: "Output",
    kind: "output",
    content:
      "Regime Persistent, Random-like, Anti-persistent, ditambah Uncertain saat Hurst dan DFA tidak sepakat.",
    evidence: "Identifikasi biner 90,2% · tiga kelas 69,0%",
  },
  {
    stage: "Analisis",
    kind: "analysis",
    content: "Dinamika regime, durasi, perpindahan regime, serta perbandingan 1H dan 4H.",
    evidence: "P(bertahan) 0,76–0,79 versus 0,19–0,20 bila label acak",
  },
  {
    stage: "Evaluasi tambahan",
    kind: "analysis",
    content:
      "Backtesting eksploratif beserta diagnostik penyebab, bukan sekadar equity curve.",
    evidence: "Dekomposisi edge/drag/biaya · uji lawan posisi acak",
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

"use client";

/**
 * Disclaimer wajib tampil di UI (bukan hanya di dokumen).
 *  - variant "backtest"  : hasil eksploratif, bukan jaminan profit
 *  - variant "fractal"   : istilah "regime fraktal" dipakai operasional,
 *                          bukan klaim matematis ketat (Bab 2.1.3)
 *  - variant "mock"      : data masih sintetis
 */
export default function Disclaimer({
  variant,
  className = "",
}: {
  variant: "backtest" | "fractal" | "mock";
  className?: string;
}) {
  const content = {
    backtest: {
      tone: "border-warn/40 bg-warn/10 text-warn",
      title: "Backtest bersifat eksploratif",
      body: "Modul ini hanya menguji kegunaan praktis informasi regime pada data historis. BUKAN jaminan profit dan BUKAN rekomendasi trading.",
    },
    fractal: {
      tone: "border-edge bg-surface/50 text-txtMuted",
      title: "Catatan istilah",
      body: 'Istilah "regime fraktal" dipakai secara operasional untuk merujuk karakteristik persistensi hasil estimasi Hurst-DFA. Ini bukan klaim bahwa deret harga bersifat fraktal secara matematis ketat (lihat Bab 2.1.3 dan Maraun et al., 2004).',
    },
    mock: {
      tone: "border-uncertainLowconf/40 bg-uncertainLowconf/10 text-uncertainLowconf",
      title: "Data sintetis (use_mock = true)",
      body: "Angka pada halaman ini berasal dari generator mock. Sumber data historis resmi (exchange dan rentang tanggal) masih open question di skripsi.",
    },
  }[variant];

  return (
    <div
      className={`rounded border px-3 py-2 text-[11px] leading-relaxed ${content.tone} ${className}`}
    >
      <span className="font-semibold">{content.title}. </span>
      {content.body}
    </div>
  );
}

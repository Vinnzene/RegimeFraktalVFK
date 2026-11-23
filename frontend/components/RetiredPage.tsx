import Link from "next/link";

/**
 * Pengganti halaman yang memakai model prediksi lama (SWT, h = 500 bar).
 *
 * Sistem kini hanya melakukan IDENTIFIKASI regime (h = 0) dengan model Hybrid Attention-BiLSTM
 * yang dilaporkan di Bab 4. Halaman lama memakai model lain dengan target
 * berbeda, sehingga angkanya tidak boleh tampil berdampingan seolah satu sistem.
 * Kodenya disimpan di `app/_arsip_prediksi/` (folder privat, tidak dirutekan).
 */
export default function RetiredPage({ title, reason }: { title: string; reason: string }) {
  return (
    <div className="mx-auto max-w-2xl py-10">
      <h1 className="font-sans text-[15px] font-semibold tracking-tight text-txt">{title}</h1>
      <div className="mt-3 rounded-lg border border-edge bg-surface/60 px-4 py-3 text-[12.5px] leading-relaxed text-txtDim">
        <p>
          Halaman ini dinonaktifkan. {reason} Sistem sekarang hanya melakukan <b className="text-txt">identifikasi</b> regime
          (h = 0) dengan model Hybrid Attention-BiLSTM yang dievaluasi di Bab 4.
        </p>
        <p className="mt-2">
          Lihat kondisi pasar terkini di{" "}
          <Link href="/" className="text-accent underline-offset-2 hover:underline">
            Ringkasan
          </Link>{" "}
          atau label Hurst–DFA di{" "}
          <Link href="/regime-explorer" className="text-accent underline-offset-2 hover:underline">
            Hurst-DFA Klasik
          </Link>
          .
        </p>
      </div>
    </div>
  );
}

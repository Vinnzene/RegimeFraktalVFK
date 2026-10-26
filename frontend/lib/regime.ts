/**
 * Palet & label regime — satu sumber untuk seluruh halaman.
 *
 * Dua jenis Uncertain sengaja dibedakan secara visual:
 *  - uncertain_rule    : hatching diagonal (Hurst & DFA tidak sepakat -> soal DATA)
 *  - uncertain_lowconf : hatching titik    (max(P) < tau            -> soal MODEL)
 *
 * Warna dipilih bernada tengah agar terbaca di tema terang maupun gelap.
 * Hijau dan merah TIDAK dipakai di sini meski tema memakainya untuk candle.
 * Regime menyatakan sifat persistensi, bukan arah harga: Persistent tidak
 * berarti naik. Memakai warna arah akan membuat pembaca menyamakan keduanya.
 */

export type Regime =
  | "persistent"
  | "random_like"
  | "anti_persistent"
  | "uncertain_rule"
  | "uncertain_lowconf";

export const REGIME_ORDER: Regime[] = [
  "persistent",
  "random_like",
  "anti_persistent",
  "uncertain_rule",
  "uncertain_lowconf",
];

export const REGIME_META: Record<
  Regime,
  { label: string; color: string; pattern: "solid" | "diagonal" | "dots"; note: string }
> = {
  persistent: {
    label: "Persistent",
    color: "#3b82f6",
    pattern: "solid",
    note: "H & α di atas ambang atas — gerakan cenderung berlanjut",
  },
  random_like: {
    label: "Random-like",
    color: "#808896",
    pattern: "solid",
    note: "H & α di dalam pita ambang — menyerupai random walk",
  },
  anti_persistent: {
    label: "Anti-persistent",
    color: "#d4a20a",
    pattern: "solid",
    note: "H & α di bawah ambang bawah — cenderung berbalik arah",
  },
  uncertain_rule: {
    label: "Uncertain (rule)",
    color: "#64748b",
    pattern: "diagonal",
    note: "Hurst & DFA tidak konsisten — ketidakpastian pada DATA",
  },
  uncertain_lowconf: {
    label: "Uncertain (low-conf)",
    color: "#a371f7",
    pattern: "dots",
    note: "max(P) < τ — ketidakpastian pada MODEL",
  },
};

/**
 * Bahasa awam untuk tiap regime. Istilah teknis tetap dipakai di halaman
 * analisis; versi ini untuk ringkasan yang dibaca orang tanpa latar statistik.
 */
export const REGIME_PLAIN: Record<
  Regime,
  { name: string; icon: string; summary: string; meaning: string; analogy: string }
> = {
  persistent: {
    name: "Tren Berlanjut",
    icon: "➜",
    summary: "Gerakan harga cenderung meneruskan arah sebelumnya.",
    meaning:
      "Kalau harga sedang naik, kecenderungannya terus naik; kalau sedang turun, cenderung terus turun. Pasar sedang punya 'momentum'.",
    analogy: "Seperti bola yang menggelinding di turunan — sekali bergerak, susah berhenti.",
  },
  random_like: {
    name: "Acak / Tanpa Pola",
    icon: "≈",
    summary: "Gerakan harga sulit ditebak, mirip lempar koin.",
    meaning:
      "Arah sebelumnya tidak banyak memberi petunjuk tentang arah berikutnya. Pasar sedang tidak punya pola yang jelas.",
    analogy: "Seperti lempar koin — hasil sebelumnya tidak memengaruhi hasil berikutnya.",
  },
  anti_persistent: {
    name: "Cenderung Berbalik",
    icon: "⇄",
    summary: "Gerakan harga cenderung berbalik arah (naik-turun bergantian).",
    meaning:
      "Setelah naik, harga cenderung turun lagi, dan sebaliknya. Pasar bergerak bolak-balik dalam kisaran tertentu (sideways).",
    analogy: "Seperti pegas — ditarik ke satu arah, lalu memantul balik.",
  },
  uncertain_rule: {
    name: "Belum Jelas",
    icon: "?",
    summary: "Dua alat ukur memberi jawaban berbeda.",
    meaning:
      "Dua metode pengukur (Hurst dan DFA) tidak sepakat, jadi sistem memilih tidak memaksakan kesimpulan.",
    analogy: "Seperti dua termometer yang menunjukkan angka berbeda — lebih aman menunggu.",
  },
  uncertain_lowconf: {
    name: "Model Ragu",
    icon: "?",
    summary: "Model tidak cukup yakin untuk memilih satu kondisi.",
    meaning:
      "Keyakinan model di bawah batas minimum, sehingga hasilnya ditandai ragu alih-alih ditebak.",
    analogy: "Seperti prakiraan cuaca 'mungkin hujan, mungkin tidak'.",
  },
};

export function regimePlain(regime: string): string {
  return REGIME_PLAIN[regime as Regime]?.name ?? regime;
}

export function regimeColor(regime: string): string {
  return REGIME_META[regime as Regime]?.color ?? "#252c37";
}

export function regimeLabel(regime: string): string {
  return REGIME_META[regime as Regime]?.label ?? regime;
}

/** Hitung ulang label dari probabilitas mentah — dipakai saat slider τ digeser. */
export function applyTau(
  probabilities: Record<string, number>,
  tau: number
): { finalLabel: Regime; argmax: string; maxProb: number } {
  const entries = Object.entries(probabilities);
  if (entries.length === 0) {
    return { finalLabel: "uncertain_lowconf", argmax: "", maxProb: 0 };
  }
  const [argmax, maxProb] = entries.reduce((a, b) => (b[1] > a[1] ? b : a));
  return {
    finalLabel: maxProb >= tau ? (argmax as Regime) : "uncertain_lowconf",
    argmax,
    maxProb,
  };
}

export const SEGMENT_META: Record<string, { label: string; color: string }> = {
  train: { label: "Training", color: "rgba(74,158,255,0.12)" },
  purge: { label: "Purge gap (L + h)", color: "rgba(246,70,93,0.20)" },
  validation: { label: "Validation", color: "rgba(240,185,11,0.14)" },
  test: { label: "Test", color: "rgba(46,189,133,0.12)" },
};

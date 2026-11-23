/**
 * Kuesioner System Usability Scale (SUS; Brooke, 1996) RFraktal: instrumen, skor, rekap, CSV.
 *
 * Satu sumber untuk halaman responden, rute API, halaman Rekap SUS, dan unit test.
 * Modul ini sengaja tanpa impor agar dapat diuji langsung dengan `node --test`.
 *
 * Alur: persetujuan + profil → mencoba aplikasi (minimal 3 halaman) → 10 butir SUS → saran.
 */

export const SUS_VERSION = "sus-v1";

/** Teks 10 butir SUS (terjemahan Bahasa Indonesia). Butir ganjil positif, genap negatif. */
export const SUS_ITEMS: string[] = [
  "Saya rasa saya akan sering menggunakan sistem ini.",
  "Saya merasa sistem ini terlalu rumit untuk digunakan.",
  "Saya merasa sistem ini mudah digunakan.",
  "Saya rasa saya membutuhkan bantuan orang teknis untuk dapat menggunakan sistem ini.",
  "Saya merasa fitur-fitur pada sistem ini terintegrasi dengan baik.",
  "Saya merasa ada terlalu banyak ketidakkonsistenan pada sistem ini.",
  "Saya rasa kebanyakan orang akan cepat belajar menggunakan sistem ini.",
  "Saya merasa sistem ini sangat merepotkan untuk digunakan.",
  "Saya merasa sangat percaya diri saat menggunakan sistem ini.",
  "Saya perlu mempelajari banyak hal sebelum dapat menggunakan sistem ini.",
];

export const SUS_SCALE = [
  { value: 1, label: "Sangat tidak setuju" },
  { value: 2, label: "Tidak setuju" },
  { value: 3, label: "Netral" },
  { value: 4, label: "Setuju" },
  { value: 5, label: "Sangat setuju" },
] as const;

export const ROLE_OPTIONS = ["Trader ritel", "Investor kripto", "Analis / peneliti pasar", "Mahasiswa / akademisi", "Lainnya"];

/** Batas isian profil. */
export const EXPERIENCE_MAX_MONTHS = 600;
export const AGE_MIN = 15;
export const AGE_MAX = 100;

/** Halaman yang wajib dibuka sebelum kuesioner (responden boleh mencoba halaman lain). */
export const EXPLORE_PAGES = [
  { key: "ringkasan", href: "/", label: "Ringkasan", hint: "Kondisi pasar 1H & 4H, grafik harga berpita kondisi, riwayat kondisi." },
  { key: "evaluasi", href: "/evaluasi-identifikasi", label: "Hasil Uji Identifikasi", hint: "Berapa persen identifikasi model yang benar, per kelas dan per tahap." },
  { key: "fokus", href: "/attention", label: "Fokus Model", hint: "Bagian riwayat harga yang paling diperhatikan model." },
] as const;

export const CONSENT_TEXT = [
  "Kuesioner ini bagian dari penelitian skripsi tentang aplikasi identifikasi regime fraktal BTC/USDT (RFraktal).",
  "Anda akan mencoba aplikasi secara bebas (minimal tiga halaman), lalu mengisi 10 pernyataan System Usability Scale (SUS). Perkiraan waktu 10–15 menit. Tidak ada jawaban benar atau salah; yang dinilai adalah aplikasinya, bukan Anda.",
  "Yang disimpan: kode responden (mis. R01), peran, lama pengalaman trading/analisis kripto, usia (opsional), halaman yang dibuka dari daftar, jawaban kuesioner, saran, dan waktu pengisian. Nama dan email akun tidak disimpan bersama jawaban; akun hanya dipakai agar satu orang mengisi satu kali.",
  "Jawaban tidak dapat diubah setelah dikirim. Partisipasi bersifat sukarela dan Anda dapat berhenti kapan saja sebelum mengirim.",
];

// ---------------------------------------------------------------- tipe data

export type SusStatus = "explore" | "questionnaire" | "done";

export type SusProfile = { role: string; experience_months: number; age: number | null };

export type SusResponse = {
  version: string;
  uid: string;
  code: string;
  status: SusStatus;
  consent_at: number;
  profile: SusProfile;
  /** Halaman dari daftar EXPLORE_PAGES yang dibuka responden, beserta waktu pertama dibuka. */
  visited: Record<string, number>;
  explore_done_at: number | null;
  answers: number[];
  score: number | null;
  feedback: string;
  submitted_at: number | null;
  demo: boolean;
};

/** Bentuk untuk klien, rekap, dan ekspor: tanpa uid. */
export type PublicSus = Omit<SusResponse, "uid">;

// ---------------------------------------------------------------- skor

export class SusInputError extends Error {}

/** Pastikan tepat 10 jawaban bilangan bulat 1–5; selain itu ditolak. */
export function validateAnswers(answers: unknown): number[] {
  if (!Array.isArray(answers) || answers.length !== 10) throw new SusInputError("Semua 10 butir SUS wajib dijawab.");
  const out = answers.map((v) => (typeof v === "string" && v.trim() !== "" ? Number(v) : v));
  if (out.some((v) => typeof v !== "number" || !Number.isInteger(v) || v < 1 || v > 5)) {
    throw new SusInputError("Setiap butir SUS harus bernilai bilangan bulat 1–5.");
  }
  return out as number[];
}

/** SUS = 2,5 × [Σ(butir ganjil − 1) + Σ(5 − butir genap)], 0–100. Jawaban tidak lengkap ditolak. */
export function susScore(answers: unknown): number {
  const a = validateAnswers(answers);
  const sum = a.reduce((acc, v, i) => acc + (i % 2 === 0 ? v - 1 : 5 - v), 0);
  return sum * 2.5;
}

/**
 * Skala kata sifat Bangor, Kortum & Miller (2009). Rata-rata SUS tiap kata sifat:
 * Worst Imaginable 12,5 · Awful 20,3 · Poor 35,7 · OK 50,9 · Good 71,4 · Excellent 85,5 ·
 * Best Imaginable 90,9. Skor dikelompokkan ke kata sifat terdekat (batas = titik tengah
 * antar-rata-rata).
 */
export const BANGOR_ADJECTIVES = [
  { label: "Worst Imaginable", mean: 12.5, upper: 16.4 },
  { label: "Awful", mean: 20.3, upper: 28.0 },
  { label: "Poor", mean: 35.7, upper: 43.3 },
  { label: "OK", mean: 50.9, upper: 61.15 },
  { label: "Good", mean: 71.4, upper: 78.45 },
  { label: "Excellent", mean: 85.5, upper: 88.2 },
  { label: "Best Imaginable", mean: 90.9, upper: Infinity },
] as const;

export function bangorAdjective(score: number): string {
  return BANGOR_ADJECTIVES.find((a) => score < a.upper)!.label;
}

/** Rentang penerimaan Bangor dkk.: < 50 tidak dapat diterima, 50–70 marginal, > 70 dapat diterima. */
export function acceptability(score: number): string {
  if (score > 70) return "Acceptable";
  if (score >= 50) return "Marginal";
  return "Not Acceptable";
}

export const SUS_BENCHMARK = 68;

// ---------------------------------------------------------------- rekap

const median = (xs: number[]): number | null => {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

export type ItemRecap = {
  item: number;
  text: string;
  polarity: "positif" | "negatif";
  mean: number;
  /** Sumbangan ke skor (0–4): ganjil = rata-rata − 1, genap = 5 − rata-rata. Terkecil = butir terlemah. */
  contribution: number;
};

export type SusSummary = {
  n: number;
  in_progress: number;
  mean: number | null;
  sd: number | null;
  min: number | null;
  max: number | null;
  median: number | null;
  adjective: string | null;
  acceptability: string | null;
  at_or_above_68: number;
  items: ItemRecap[];
  weakest_item: number | null;
};

/** Rekap seluruh responden yang sudah mengirim (status done). Skor selalu dihitung ulang. */
export function summarize(responses: PublicSus[]): SusSummary {
  const done = responses.filter((r) => r.status === "done");
  const scores = done.map((r) => susScore(r.answers));
  const n = scores.length;
  const mean = n ? scores.reduce((a, b) => a + b, 0) / n : null;
  const sd = n > 1 && mean !== null ? Math.sqrt(scores.reduce((a, v) => a + (v - mean) ** 2, 0) / (n - 1)) : null;
  const items: ItemRecap[] = SUS_ITEMS.map((text, i) => {
    const m = n ? done.reduce((a, r) => a + r.answers[i], 0) / n : 0;
    return { item: i + 1, text, polarity: i % 2 === 0 ? "positif" : "negatif", mean: m, contribution: i % 2 === 0 ? m - 1 : 5 - m };
  });
  // Butir terlemah = sumbangan terkecil (seri → nomor terkecil); tidak ada bila semua butir sama.
  const spread = n ? Math.max(...items.map((it) => it.contribution)) - Math.min(...items.map((it) => it.contribution)) : 0;
  const weakest = n && spread > 1e-12 ? items.reduce((w, it) => (it.contribution < w.contribution ? it : w), items[0]).item : null;
  return {
    n,
    in_progress: responses.length - n,
    mean,
    sd,
    min: n ? Math.min(...scores) : null,
    max: n ? Math.max(...scores) : null,
    median: median(scores),
    adjective: mean === null ? null : bangorAdjective(mean),
    acceptability: mean === null ? null : acceptability(mean),
    at_or_above_68: scores.filter((s) => s >= SUS_BENCHMARK).length,
    items,
    weakest_item: weakest,
  };
}

export const CSV_HEAD = [
  "kode", "status", "versi_instrumen", "waktu_persetujuan_utc", "waktu_selesai_mencoba_utc", "waktu_kirim_utc",
  "peran", "pengalaman_bulan", "usia", "halaman_dibuka",
  ...SUS_ITEMS.map((_, i) => `SUS${i + 1}`),
  "skor_sus", "saran",
];

/** CSV satu baris per responden yang sudah mengirim, tanpa nama, email, maupun uid. */
export function toCsv(responses: PublicSus[]): string {
  const iso = (t: number | null) => (t ? new Date(t * 1000).toISOString() : "");
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const rows = responses
    .filter((r) => r.status === "done")
    .sort((a, b) => a.code.localeCompare(b.code))
    .map((r) => [
      r.code, r.status, r.version, iso(r.consent_at), iso(r.explore_done_at), iso(r.submitted_at),
      r.profile.role, r.profile.experience_months, r.profile.age ?? "",
      EXPLORE_PAGES.filter((p) => r.visited[p.key]).map((p) => p.key).join("|"),
      ...r.answers,
      susScore(r.answers), r.feedback ?? "",
    ]);
  return [CSV_HEAD, ...rows].map((row) => row.map(esc).join(",")).join("\n") + "\n";
}

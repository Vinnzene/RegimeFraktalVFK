/**
 * Instrumen dan perhitungan skor User Acceptance Testing (UAT) RFraktal.
 *
 * Dipakai bersama oleh halaman responden, route API, dan halaman rekap admin, supaya
 * butir kuesioner dan rumus skor hanya punya satu sumber.
 *
 * Alur: persetujuan + profil → 5 tugas terpandu (jawaban dicek otomatis terhadap isi
 * sistem saat itu, waktu tercatat, tiap tugas dinilai kemudahannya/SEQ) → 8 butir
 * kelayakan Likert (Tabel 3.12) → System Usability Scale (Brooke, 1996) → saran.
 */

export const UAT_VERSION = "uat-v1";

export type ProfileField = { key: string; label: string; options: string[] };

export const PROFILE_FIELDS: ProfileField[] = [
  { key: "role", label: "Peran utama", options: ["Trader ritel", "Analis / peneliti pasar", "Mahasiswa / akademisi", "Pengembang perangkat lunak", "Lainnya"] },
  { key: "experience", label: "Pengalaman trading atau analisis kripto", options: ["Belum pernah", "< 1 tahun", "1–3 tahun", "> 3 tahun"] },
  { key: "timeframe", label: "Timeframe yang paling sering dipakai", options: ["< 1 jam", "1 jam (1H)", "4 jam (4H)", "Harian atau lebih", "Tidak trading"] },
  { key: "hurst_familiarity", label: "Pengenalan terhadap Hurst Exponent / DFA sebelumnya", options: ["Belum pernah dengar", "Pernah dengar", "Paham dasar", "Pernah memakai"] },
];

export type TaskChoice = { value: string; label: string };
export type UatTask = {
  id: string;
  title: string;
  /** Halaman yang perlu dibuka responden. */
  href: string;
  instruction: string;
  question: string;
  kind: "choice" | "number";
  choices?: TaskChoice[];
  /** Untuk jawaban angka: selisih yang masih dianggap benar. */
  tolerance?: number;
  unit?: string;
};

const REGIME_CHOICES: TaskChoice[] = [
  { value: "persistent", label: "Tren Berlanjut (persistent)" },
  { value: "random_like", label: "Acak / Tanpa Pola (random-like)" },
  { value: "anti_persistent", label: "Cenderung Berbalik (anti-persistent)" },
];

export const TASKS: UatTask[] = [
  {
    id: "T1",
    title: "Membaca kondisi pasar 1H",
    href: "/",
    instruction: "Buka halaman Ringkasan dengan skala waktu 1H. Perhatikan kartu Kondisi Pasar di bagian atas.",
    question: "Apa kondisi pasar BTC/USDT 1H saat ini menurut model identifikasi?",
    kind: "choice",
    choices: REGIME_CHOICES,
  },
  {
    id: "T2",
    title: "Membandingkan 1H dan 4H",
    href: "/",
    instruction: "Masih di halaman Ringkasan, bandingkan kartu Identifikasi AI 1H dan Identifikasi AI 4H.",
    question: "Apakah kondisi pasar 1H dan 4H saat ini sama?",
    kind: "choice",
    choices: [
      { value: "same", label: "Sama" },
      { value: "different", label: "Berbeda" },
    ],
  },
  {
    id: "T3",
    title: "Membaca label per jendela",
    href: "/regime-explorer",
    instruction: "Buka menu Riset → Hurst-DFA Klasik (skala 1H). Cari tabel 'Label per jendela'.",
    question: "Apa label jendela paling atas (terbaru) pada tabel tersebut?",
    kind: "choice",
    choices: [...REGIME_CHOICES, { value: "uncertain_rule", label: "Uncertain (rule) / tidak sepakat" }],
  },
  {
    id: "T4",
    title: "Membaca hasil uji ketahanan",
    href: "/uji-ketahanan",
    instruction: "Buka menu Riset → Uji Ketahanan Metode (skala 1H). Lihat bagian 1. Walk-forward.",
    question: "Berapa persen benar walk-forward gabungan pada 1H?",
    kind: "number",
    tolerance: 0.5,
    unit: "%",
  },
  {
    id: "T5",
    title: "Membaca fokus model (attention)",
    href: "/attention",
    instruction: "Buka menu Riset → Fokus Model (skala 1H). Lihat grafik bobot attention per langkah.",
    question: "Langkah ke berapa yang memiliki bobot attention terbesar?",
    kind: "number",
    tolerance: 0,
  },
];

/** Skala Single Ease Question (Sauro & Dumas, 2009): 1 = sangat sulit, 7 = sangat mudah. */
export const SEQ_SCALE = [1, 2, 3, 4, 5, 6, 7] as const;

export type LikertItem = { code: string; aspect: string; statement: string };

/**
 * Butir kelayakan (Tabel 3.12 naskah). UAT-02 dan UAT-05 disesuaikan dengan fitur
 * aplikasi yang sebenarnya; Tabel 3.12 perlu diperbarui agar sama.
 */
export const LIKERT_ITEMS: LikertItem[] = [
  { code: "UAT-01", aspect: "Kemudahan antarmuka", statement: "Tampilan antarmuka (dashboard) aplikasi RFraktal mudah dipahami, terstruktur dengan jelas, dan nyaman dioperasikan." },
  { code: "UAT-02", aspect: "Pemilihan kerangka waktu", statement: "Fitur pemilihan kerangka waktu (1H dan 4H) dan perpindahan antarhalaman berfungsi dengan lancar." },
  { code: "UAT-03", aspect: "Kejelasan informasi konsensus Hurst-DFA", statement: "Sistem menyajikan nilai Hurst Exponent (R/S), DFA-1, skor efisiensi arah (ER_q), dan label konsensus secara jelas dan transparan." },
  { code: "UAT-04", aspect: "Visualisasi SWT", statement: "Grafik dekomposisi Stationary Wavelet Transform (SWT) 4 level mudah dibaca untuk memahami struktur multiskala pasar." },
  { code: "UAT-05", aspect: "Tampilan identifikasi regime", statement: "Pewarnaan latar regime pada grafik harga mudah dibaca dan membantu saya melihat kapan pasar cenderung berlanjut, berbalik, atau acak." },
  { code: "UAT-06", aspect: "Bobot atensi dan probabilitas", statement: "Probabilitas tiga kelas dan grafik bobot attention membantu saya memahami dasar hasil identifikasi model." },
  { code: "UAT-07", aspect: "Perbandingan 1H dan 4H", statement: "Fitur perbandingan regime 1H dan 4H memberikan wawasan yang berguna dalam membaca konteks pasar lintas skala waktu." },
  { code: "UAT-08", aspect: "Hasil pengujian identifikasi", statement: "Halaman hasil uji (Hasil Uji Identifikasi dan Uji Ketahanan Metode) menampilkan jumlah dan persentase identifikasi yang benar secara jelas." },
];

export const LIKERT_SCALE = [
  { value: 1, short: "STS", label: "Sangat Tidak Setuju" },
  { value: 2, short: "TS", label: "Tidak Setuju" },
  { value: 3, short: "CS", label: "Cukup Setuju" },
  { value: 4, short: "S", label: "Setuju" },
  { value: 5, short: "SS", label: "Sangat Setuju" },
] as const;

/** System Usability Scale (Brooke, 1996), terjemahan Bahasa Indonesia. Butir ganjil positif, genap negatif. */
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

export const CONSENT_TEXT = [
  "Pengujian ini adalah bagian dari penelitian skripsi tentang aplikasi identifikasi regime fraktal BTC/USDT (RFraktal).",
  "Anda akan mengerjakan 5 tugas singkat di aplikasi, lalu mengisi kuesioner (±10–15 menit). Tidak ada jawaban benar atau salah tentang pendapat Anda; yang dinilai adalah aplikasinya, bukan Anda.",
  "Yang disimpan: kode responden (mis. R01), profil singkat, jawaban dan waktu pengerjaan tugas, jawaban kuesioner, dan waktu pengisian. Email akun hanya dipakai untuk memastikan satu akun mengisi satu kali dan tidak ikut diekspor.",
  "Jawaban tidak dapat diubah setelah dikirim. Partisipasi bersifat sukarela dan Anda dapat berhenti kapan saja sebelum mengirim.",
];

// ---------------------------------------------------------------- tipe data jawaban

export type TaskResult = {
  started_at: number | null;
  answered_at: number | null;
  seconds: number | null;
  answer: string | null;
  /** Jawaban yang benar menurut sistem saat tugas dimulai dan saat dijawab. */
  expected: string[];
  correct: boolean | null;
  seq: number | null;
};

export type UatStatus = "tasks" | "questionnaire" | "done";

export type UatResponse = {
  version: string;
  uid: string;
  code: string;
  status: UatStatus;
  consent_at: number;
  profile: Record<string, string>;
  tasks: Record<string, TaskResult>;
  likert: Record<string, number>;
  sus: number[];
  feedback: string;
  submitted_at: number | null;
  app: { config_hash: string | null };
  demo: boolean;
};

/** Bentuk yang dikirim ke klien/ekspor: tanpa uid dan email. */
export type PublicResponse = Omit<UatResponse, "uid">;

// ---------------------------------------------------------------- skor

/** Skor SUS satu responden (0–100): (Σ(ganjil − 1) + Σ(5 − genap)) × 2,5. */
export function susScore(answers: number[]): number | null {
  if (answers.length !== 10 || answers.some((v) => !(v >= 1 && v <= 5))) return null;
  const sum = answers.reduce((acc, v, i) => acc + (i % 2 === 0 ? v - 1 : 5 - v), 0);
  return sum * 2.5;
}

/**
 * Interpretasi SUS dengan skala nilai berkurva Sauro & Lewis (2016), disederhanakan ke
 * huruf utama; rata-rata industri ±68 (Sauro, 2011).
 */
export function susGrade(score: number): string {
  if (score >= 80.8) return "A (sangat baik)";
  if (score >= 72.6) return "B (baik)";
  if (score >= 62.7) return "C (rata-rata)";
  if (score >= 51.7) return "D (di bawah rata-rata)";
  return "F (buruk)";
}

/** Kategori kelayakan P_UAT (Tabel 3.11 naskah). */
export function uatCategory(pct: number): string {
  if (pct >= 81) return "Sangat Layak";
  if (pct >= 61) return "Layak";
  if (pct >= 41) return "Cukup Layak";
  if (pct >= 21) return "Kurang Layak";
  return "Tidak Layak";
}

export type ItemRecap = {
  code: string;
  aspect: string;
  counts: Record<"SS" | "S" | "CS" | "TS" | "STS", number>;
  score: number;
  max: number;
  pct: number;
};

export type UatSummary = {
  n: number;
  likert: { items: ItemRecap[]; total_score: number; total_max: number; pct: number; category: string };
  sus: { scores: { code: string; score: number }[]; mean: number | null; sd: number | null; median: number | null; grade: string | null };
  tasks: { id: string; title: string; n: number; correct: number; success_pct: number; median_seconds: number | null; mean_seq: number | null }[];
  profile: Record<string, Record<string, number>>;
};

const median = (xs: number[]) => {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

/** Rekap seluruh responden yang sudah mengirim (status done). */
export function summarize(responses: PublicResponse[]): UatSummary {
  const done = responses.filter((r) => r.status === "done");
  const n = done.length;
  const items: ItemRecap[] = LIKERT_ITEMS.map((it) => {
    const counts = { SS: 0, S: 0, CS: 0, TS: 0, STS: 0 };
    let score = 0;
    for (const r of done) {
      const v = r.likert[it.code];
      if (!v) continue;
      score += v;
      counts[LIKERT_SCALE[v - 1].short as keyof typeof counts] += 1;
    }
    const max = n * 5;
    return { code: it.code, aspect: it.aspect, counts, score, max, pct: max ? (100 * score) / max : 0 };
  });
  const total_score = items.reduce((a, b) => a + b.score, 0);
  const total_max = items.reduce((a, b) => a + b.max, 0);
  const pct = total_max ? (100 * total_score) / total_max : 0;

  const susScores = done
    .map((r) => ({ code: r.code, score: susScore(r.sus) }))
    .filter((x): x is { code: string; score: number } => x.score !== null);
  const vals = susScores.map((s) => s.score);
  const mean = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  const sd = vals.length > 1 && mean !== null ? Math.sqrt(vals.reduce((a, v) => a + (v - mean) ** 2, 0) / (vals.length - 1)) : null;

  const tasks = TASKS.map((t) => {
    const rs = done.map((r) => r.tasks[t.id]).filter(Boolean);
    const correct = rs.filter((x) => x.correct).length;
    const secs = rs.map((x) => x.seconds).filter((x): x is number => x !== null);
    const seqs = rs.map((x) => x.seq).filter((x): x is number => x !== null);
    return {
      id: t.id,
      title: t.title,
      n: rs.length,
      correct,
      success_pct: rs.length ? (100 * correct) / rs.length : 0,
      median_seconds: median(secs),
      mean_seq: seqs.length ? seqs.reduce((a, b) => a + b, 0) / seqs.length : null,
    };
  });

  const profile: Record<string, Record<string, number>> = {};
  for (const f of PROFILE_FIELDS) {
    profile[f.key] = Object.fromEntries(f.options.map((o) => [o, 0]));
    for (const r of done) {
      const v = r.profile[f.key];
      if (v) profile[f.key][v] = (profile[f.key][v] ?? 0) + 1;
    }
  }

  return {
    n,
    likert: { items, total_score, total_max, pct, category: uatCategory(pct) },
    sus: { scores: susScores, mean, sd, median: median(vals), grade: mean === null ? null : susGrade(mean) },
    tasks,
    profile,
  };
}

/** CSV satu baris per responden (tanpa email/uid), untuk lampiran naskah. */
export function toCsv(responses: PublicResponse[]): string {
  const head = [
    "kode", "status", "versi_instrumen", "waktu_persetujuan_utc", "waktu_kirim_utc", "config_hash",
    ...PROFILE_FIELDS.map((f) => `profil_${f.key}`),
    ...TASKS.flatMap((t) => [`${t.id}_jawaban`, `${t.id}_jawaban_sistem`, `${t.id}_benar`, `${t.id}_detik`, `${t.id}_seq`]),
    ...LIKERT_ITEMS.map((i) => i.code),
    ...SUS_ITEMS.map((_, i) => `SUS${i + 1}`),
    "skor_sus",
    "saran",
  ];
  const iso = (t: number | null) => (t ? new Date(t * 1000).toISOString() : "");
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const rows = responses.map((r) => [
    r.code, r.status, r.version, iso(r.consent_at), iso(r.submitted_at), r.app?.config_hash ?? "",
    ...PROFILE_FIELDS.map((f) => r.profile[f.key] ?? ""),
    ...TASKS.flatMap((t) => {
      const x = r.tasks[t.id];
      return [x?.answer ?? "", (x?.expected ?? []).join("|"), x?.correct === null || x?.correct === undefined ? "" : x.correct ? 1 : 0, x?.seconds ?? "", x?.seq ?? ""];
    }),
    ...LIKERT_ITEMS.map((i) => r.likert[i.code] ?? ""),
    ...SUS_ITEMS.map((_, i) => r.sus[i] ?? ""),
    susScore(r.sus) ?? "",
    r.feedback ?? "",
  ]);
  return [head, ...rows].map((row) => row.map(esc).join(",")).join("\n") + "\n";
}

/** Cocokkan jawaban tugas dengan nilai yang diharapkan sistem. */
export function isCorrect(task: UatTask, answer: string, expected: string[]): boolean {
  if (task.kind === "choice") return expected.includes(answer);
  const a = Number(String(answer).replace(",", "."));
  if (!Number.isFinite(a)) return false;
  return expected.some((e) => Math.abs(Number(e) - a) <= (task.tolerance ?? 0) + 1e-9);
}

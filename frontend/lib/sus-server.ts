import { adminDb } from "@/lib/firebase-admin";
import type { SessionUser } from "@/lib/session";
import { isAdmin } from "@/lib/setup-access";
import {
  AGE_MAX,
  AGE_MIN,
  EXPERIENCE_MAX_MONTHS,
  EXPLORE_PAGES,
  ROLE_OPTIONS,
  SUS_VERSION,
  SusInputError,
  susScore,
  validateAnswers,
  type PublicSus,
  type SusResponse,
} from "@/lib/sus";

/** Penyimpanan Kuesioner SUS di sisi server Next.js. */

const now = () => Math.floor(Date.now() / 1000);

type Memory = { responses: Map<string, SusResponse>; counter: number };
const memory: Memory = ((globalThis as any).__susMemory ??= { responses: new Map(), counter: 0 });

function db(user: SessionUser) {
  return user.demo ? null : adminDb();
}

export class SusError extends Error {
  constructor(message: string, public status = 400) {
    super(message);
  }
}

export function inviteCode(): string {
  return (process.env.SUS_INVITE_CODE ?? process.env.UAT_INVITE_CODE ?? "").trim();
}

/** Rekap: admin (ADMIN_EMAILS) membaca Firestore. */
export function canAdminSus(user: SessionUser): boolean {
  return isAdmin(user) || user.demo;
}

export function susOpen(user: SessionUser): boolean {
  return user.demo || inviteCode().length > 0;
}

function checkInvite(user: SessionUser, code: string): boolean {
  const expected = inviteCode();
  if (!expected) return user.demo;
  return code.trim().toUpperCase() === expected.toUpperCase();
}

export function toPublic(r: SusResponse): PublicSus {
  const { uid: _uid, ...rest } = r; // eslint-disable-line @typescript-eslint/no-unused-vars
  return rest;
}

export async function getResponse(user: SessionUser): Promise<SusResponse | null> {
  const d = db(user);
  if (!d) return memory.responses.get(user.uid) ?? null;
  const snap = await d.collection("sus_responses").doc(user.uid).get();
  return snap.exists ? (snap.data() as SusResponse) : null;
}

async function save(user: SessionUser, r: SusResponse): Promise<void> {
  const d = db(user);
  if (!d) {
    memory.responses.set(user.uid, r);
    return;
  }
  await d.collection("sus_responses").doc(user.uid).set(r);
}

async function nextCode(user: SessionUser): Promise<string> {
  const d = db(user);
  if (!d) {
    memory.counter += 1;
    return `D${String(memory.counter).padStart(2, "0")}`; // kode demo dibedakan dari responden sungguhan
  }
  const ref = d.collection("sus_meta").doc("counter");
  const n = await d.runTransaction(async (tx) => {
    const cur = Number((await tx.get(ref)).data()?.next ?? 1);
    tx.set(ref, { next: cur + 1 });
    return cur;
  });
  return `R${String(n).padStart(2, "0")}`;
}

function intIn(v: unknown, lo: number, hi: number): number | null {
  const n = typeof v === "string" && v.trim() !== "" ? Number(v) : v;
  return typeof n === "number" && Number.isInteger(n) && n >= lo && n <= hi ? n : null;
}

/** Persetujuan + profil. */
export async function start(user: SessionUser, body: any): Promise<SusResponse> {
  if (!susOpen(user)) throw new SusError("Kuesioner SUS belum dibuka.", 403);
  const existing = await getResponse(user);
  if (existing) return existing;
  if (!checkInvite(user, String(body?.invite ?? ""))) throw new SusError("Kode undangan tidak sesuai.", 403);
  if (body?.consent !== true) throw new SusError("Persetujuan diperlukan untuk mengisi kuesioner.");
  const role = String(body?.profile?.role ?? "");
  if (!ROLE_OPTIONS.includes(role)) throw new SusError("Peran utama belum dipilih.");
  const experience = intIn(body?.profile?.experience_months, 0, EXPERIENCE_MAX_MONTHS);
  if (experience === null) throw new SusError(`Pengalaman diisi dalam bulan, bilangan bulat 0–${EXPERIENCE_MAX_MONTHS}.`);
  const rawAge = body?.profile?.age;
  const age = rawAge === null || rawAge === undefined || rawAge === "" ? null : intIn(rawAge, AGE_MIN, AGE_MAX);
  if (age === null && !(rawAge === null || rawAge === undefined || rawAge === "")) {
    throw new SusError(`Usia diisi bilangan bulat ${AGE_MIN}–${AGE_MAX}, atau dikosongkan.`);
  }
  const r: SusResponse = {
    version: SUS_VERSION,
    uid: user.uid,
    code: await nextCode(user),
    status: "explore",
    consent_at: now(),
    profile: { role, experience_months: experience, age },
    visited: {},
    explore_done_at: null,
    answers: [],
    score: null,
    feedback: "",
    submitted_at: null,
    demo: user.demo,
  };
  await save(user, r);
  return r;
}

function requireStatus(r: SusResponse | null, status: SusResponse["status"]): SusResponse {
  if (!r) throw new SusError("Anda belum memulai kuesioner.", 409);
  if (r.status !== status) {
    throw new SusError(r.status === "done" ? "Kuesioner sudah dikirim dan tidak dapat diubah." : "Langkah ini belum dapat dikerjakan.", 409);
  }
  return r;
}

/** Catat halaman dari daftar yang dibuka responden (waktu pertama dibuka). */
export async function visit(user: SessionUser, page: string): Promise<SusResponse> {
  const r = requireStatus(await getResponse(user), "explore");
  if (!EXPLORE_PAGES.some((p) => p.key === page)) throw new SusError("Halaman tidak dikenal.");
  if (!r.visited[page]) {
    r.visited = { ...r.visited, [page]: now() };
    await save(user, r);
  }
  return r;
}

/** "Saya sudah mencoba, lanjut ke kuesioner": ketiga halaman wajib sudah dibuka. */
export async function exploreDone(user: SessionUser): Promise<SusResponse> {
  const r = requireStatus(await getResponse(user), "explore");
  const missing = EXPLORE_PAGES.filter((p) => !r.visited[p.key]).map((p) => p.label);
  if (missing.length) throw new SusError(`Buka dulu halaman: ${missing.join(", ")}.`);
  r.status = "questionnaire";
  r.explore_done_at = now();
  await save(user, r);
  return r;
}

export async function submit(user: SessionUser, body: any): Promise<SusResponse> {
  const r = requireStatus(await getResponse(user), "questionnaire");
  let answers: number[];
  try {
    answers = validateAnswers(body?.answers);
  } catch (e) {
    if (e instanceof SusInputError) throw new SusError(e.message);
    throw e;
  }
  r.answers = answers;
  r.score = susScore(answers);
  r.feedback = String(body?.feedback ?? "").slice(0, 2000);
  r.status = "done";
  r.submitted_at = now();
  await save(user, r);
  return r;
}

/** Sesi demo lokal boleh mengulang (data hanya di memori). */
export async function resetDemo(user: SessionUser): Promise<void> {
  if (!user.demo) throw new SusError("Hanya sesi demo yang dapat mengulang.", 403);
  memory.responses.delete(user.uid);
}

/** Semua jawaban untuk rekap admin, tanpa uid. */
export async function listResponses(admin: SessionUser): Promise<PublicSus[]> {
  const d = db(admin);
  const raw: SusResponse[] = d
    ? (await d.collection("sus_responses").get()).docs.map((x) => x.data() as SusResponse)
    : Array.from(memory.responses.values());
  return raw.map(toPublic).sort((a, b) => a.code.localeCompare(b.code));
}

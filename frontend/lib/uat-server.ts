import { adminDb } from "@/lib/firebase-admin";
import type { SessionUser } from "@/lib/session";
import { isAdmin } from "@/lib/setup-access";
import {
  LIKERT_ITEMS,
  PROFILE_FIELDS,
  TASKS,
  UAT_VERSION,
  isCorrect,
  type PublicResponse,
  type UatResponse,
} from "@/lib/uat";

/**
 * Penyimpanan UAT di sisi server Next.js.
 *
 * Firestore: uat_responses/{uid} (satu dokumen per akun) dan uat_meta/counter (nomor
 * kode responden R01, R02, ...). Sesi demo lokal memakai memori proses agar uji coba di
 * laptop tidak tercampur dengan data responden sungguhan.
 *
 * Akses dibuka dengan kode undangan `UAT_INVITE_CODE` (env). Tanpa kode, UAT tertutup
 * untuk akun biasa; sesi demo lokal boleh mencoba tanpa kode.
 */

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
const now = () => Math.floor(Date.now() / 1000);

type Memory = { responses: Map<string, UatResponse>; counter: number };
const memory: Memory = ((globalThis as any).__uatMemory ??= { responses: new Map(), counter: 0 });

function db(user: SessionUser) {
  return user.demo ? null : adminDb();
}

export function inviteCode(): string {
  return (process.env.UAT_INVITE_CODE ?? "").trim();
}

/** Admin UAT: email di ADMIN_EMAILS, atau sesi demo lokal (hanya melihat data demo di memori). */
export function canAdminUat(user: SessionUser): boolean {
  return isAdmin(user) || user.demo;
}

export function uatOpen(user: SessionUser): boolean {
  return user.demo || inviteCode().length > 0;
}

export function checkInvite(user: SessionUser, code: string): boolean {
  const expected = inviteCode();
  if (!expected) return user.demo;
  return code.trim().toUpperCase() === expected.toUpperCase();
}

/** Untuk rekap/ekspor admin: tanpa uid dan email. */
export function toPublic(r: UatResponse): PublicResponse {
  const { uid: _uid, email: _email, ...rest } = r as UatResponse & { email?: string | null }; // eslint-disable-line @typescript-eslint/no-unused-vars
  return rest;
}

/** Untuk responden: tanpa uid/email dan tanpa kunci jawaban (expected/correct). */
export function toClient(r: UatResponse) {
  const pub = toPublic(r);
  const tasks = Object.fromEntries(
    Object.entries(pub.tasks).map(([k, t]) => [k, { started_at: t.started_at, answered_at: t.answered_at, answer: t.answer, seq: t.seq }]),
  );
  return { ...pub, tasks };
}

export async function getResponse(user: SessionUser): Promise<UatResponse | null> {
  const d = db(user);
  if (!d) return memory.responses.get(user.uid) ?? null;
  const snap = await d.collection("uat_responses").doc(user.uid).get();
  return snap.exists ? (snap.data() as UatResponse) : null;
}

async function save(user: SessionUser, r: UatResponse): Promise<void> {
  const d = db(user);
  if (!d) {
    memory.responses.set(user.uid, r);
    return;
  }
  await d.collection("uat_responses").doc(user.uid).set({ ...r, email: user.email ?? null });
}

async function nextCode(user: SessionUser): Promise<string> {
  const d = db(user);
  if (!d) {
    memory.counter += 1;
    return `D${String(memory.counter).padStart(2, "0")}`; // kode demo dibedakan dari responden sungguhan
  }
  const ref = d.collection("uat_meta").doc("counter");
  const n = await d.runTransaction(async (tx) => {
    const cur = Number((await tx.get(ref)).data()?.next ?? 1);
    tx.set(ref, { next: cur + 1 });
    return cur;
  });
  return `R${String(n).padStart(2, "0")}`;
}

async function getJson(path: string): Promise<any> {
  const res = await fetch(`${BACKEND}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} HTTP ${res.status}`);
  return res.json();
}

async function configHash(): Promise<string | null> {
  try {
    return (await getJson("/api/v1/meta/config")).config_hash ?? null;
  } catch {
    return null;
  }
}

/** Jawaban yang benar menurut sistem saat ini untuk satu tugas. */
export async function expectedAnswer(taskId: string): Promise<string | null> {
  try {
    switch (taskId) {
      case "T1":
        return (await getJson("/api/v1/analysis/ai-regime?tf=1h&limit=100")).current_regime ?? null;
      case "T2": {
        const [a, b] = await Promise.all([
          getJson("/api/v1/analysis/ai-regime?tf=1h&limit=100"),
          getJson("/api/v1/analysis/ai-regime?tf=4h&limit=100"),
        ]);
        return a.current_regime && b.current_regime ? (a.current_regime === b.current_regime ? "same" : "different") : null;
      }
      case "T3": {
        const r = await getJson("/api/v1/analysis/regime?tf=1h&limit=100");
        return r.latest_windows?.length ? r.latest_windows[r.latest_windows.length - 1].regime : null;
      }
      case "T4": {
        const r = await getJson("/api/v1/model/robustness");
        const v = r.timeframes?.["1h"]?.walk_forward?.pooled?.pooled_pct_ensemble;
        return typeof v === "number" ? String(v) : null;
      }
      case "T5": {
        const r = await getJson("/api/v1/analysis/attention?tf=1h");
        const w: { step: number; weight: number }[] = r.attention_weights ?? [];
        if (!w.length) return null;
        return String(w.reduce((best, x) => (x.weight > best.weight ? x : best), w[0]).step);
      }
    }
  } catch {
    return null;
  }
  return null;
}

export class UatError extends Error {
  constructor(message: string, public status = 400) {
    super(message);
  }
}

export async function start(user: SessionUser, body: any): Promise<UatResponse> {
  if (!uatOpen(user)) throw new UatError("UAT belum dibuka.", 403);
  if (!checkInvite(user, String(body?.invite ?? ""))) throw new UatError("Kode undangan tidak sesuai.", 403);
  if (body?.consent !== true) throw new UatError("Persetujuan diperlukan untuk mengikuti UAT.");
  const existing = await getResponse(user);
  if (existing) return existing;
  const profile: Record<string, string> = {};
  for (const f of PROFILE_FIELDS) {
    const v = String(body?.profile?.[f.key] ?? "");
    if (!f.options.includes(v)) throw new UatError(`Isian "${f.label}" belum dipilih.`);
    profile[f.key] = v;
  }
  const r: UatResponse = {
    version: UAT_VERSION,
    uid: user.uid,
    code: await nextCode(user),
    status: "tasks",
    consent_at: now(),
    profile,
    tasks: Object.fromEntries(
      TASKS.map((t) => [t.id, { started_at: null, answered_at: null, seconds: null, answer: null, expected: [], correct: null, seq: null }]),
    ),
    likert: {},
    sus: [],
    feedback: "",
    submitted_at: null,
    app: { config_hash: await configHash() },
    demo: user.demo,
  };
  await save(user, r);
  return r;
}

function requireStatus(r: UatResponse | null, status: UatResponse["status"]): UatResponse {
  if (!r) throw new UatError("Anda belum memulai UAT.", 409);
  if (r.status !== status) throw new UatError(r.status === "done" ? "UAT sudah dikirim dan tidak dapat diubah." : "Langkah ini belum dapat dikerjakan.", 409);
  return r;
}

export async function taskStart(user: SessionUser, taskId: string): Promise<UatResponse> {
  const r = requireStatus(await getResponse(user), "tasks");
  const t = r.tasks[taskId];
  if (!t) throw new UatError("Tugas tidak dikenal.");
  if (t.started_at === null) {
    const exp = await expectedAnswer(taskId);
    t.started_at = now();
    t.expected = exp === null ? [] : [exp];
    await save(user, r);
  }
  return r;
}

export async function taskAnswer(user: SessionUser, taskId: string, answer: string, seq: number): Promise<UatResponse> {
  const r = requireStatus(await getResponse(user), "tasks");
  const task = TASKS.find((t) => t.id === taskId);
  const t = r.tasks[taskId];
  if (!task || !t) throw new UatError("Tugas tidak dikenal.");
  if (t.answered_at !== null) throw new UatError("Tugas ini sudah dijawab.", 409);
  if (t.started_at === null) throw new UatError("Tugas belum dimulai.", 409);
  const a = String(answer ?? "").trim();
  if (!a) throw new UatError("Jawaban belum diisi.");
  if (task.kind === "choice" && !task.choices?.some((c) => c.value === a)) throw new UatError("Pilihan jawaban tidak valid.");
  if (task.kind === "number" && !Number.isFinite(Number(a.replace(",", ".")))) throw new UatError("Jawaban harus berupa angka.");
  if (!(Number.isInteger(seq) && seq >= 1 && seq <= 7)) throw new UatError("Nilai kemudahan tugas (1–7) belum dipilih.");

  // Isi sistem dapat berubah saat candle baru tutup: jawaban dianggap benar bila cocok
  // dengan nilai saat tugas dimulai atau saat dijawab.
  const latest = await expectedAnswer(taskId);
  const expected = Array.from(new Set([...t.expected, ...(latest === null ? [] : [latest])]));
  t.answered_at = now();
  t.seconds = t.answered_at - t.started_at;
  t.answer = a;
  t.expected = expected;
  t.correct = expected.length ? isCorrect(task, a, expected) : null;
  t.seq = seq;
  if (TASKS.every((x) => r.tasks[x.id].answered_at !== null)) r.status = "questionnaire";
  await save(user, r);
  return r;
}

export async function submitQuestionnaire(user: SessionUser, body: any): Promise<UatResponse> {
  const r = requireStatus(await getResponse(user), "questionnaire");
  const likert: Record<string, number> = {};
  for (const it of LIKERT_ITEMS) {
    const v = Number(body?.likert?.[it.code]);
    if (!(Number.isInteger(v) && v >= 1 && v <= 5)) throw new UatError(`Butir ${it.code} belum dijawab.`);
    likert[it.code] = v;
  }
  const sus = Array.isArray(body?.sus) ? body.sus.map(Number) : [];
  if (sus.length !== 10 || sus.some((v: number) => !(Number.isInteger(v) && v >= 1 && v <= 5))) {
    throw new UatError("Semua 10 butir SUS wajib dijawab.");
  }
  r.likert = likert;
  r.sus = sus;
  r.feedback = String(body?.feedback ?? "").slice(0, 2000);
  r.status = "done";
  r.submitted_at = now();
  await save(user, r);
  return r;
}

/** Sesi demo lokal boleh mengulang (data hanya di memori). */
export async function resetDemo(user: SessionUser): Promise<void> {
  if (!user.demo) throw new UatError("Hanya sesi demo yang dapat mengulang.", 403);
  memory.responses.delete(user.uid);
}

/** Semua jawaban untuk rekap admin. Admin sungguhan membaca Firestore; sesi demo membaca memori. */
export async function listResponses(admin: SessionUser): Promise<PublicResponse[]> {
  const d = db(admin);
  const raw: UatResponse[] = d
    ? (await d.collection("uat_responses").get()).docs.map((x) => x.data() as UatResponse)
    : Array.from(memory.responses.values());
  return raw.map(toPublic).sort((a, b) => a.code.localeCompare(b.code));
}

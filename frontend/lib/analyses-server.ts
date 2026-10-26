import { FieldValue } from "firebase-admin/firestore";
import { adminDb } from "@/lib/firebase-admin";
import type { SessionUser } from "@/lib/session";

/**
 * Analisis aset di sisi server Next.js: kuota harian, riwayat per pengguna, dan
 * panggilan ke endpoint internal backend.
 *
 * Kuota dan riwayat disimpan di Firestore (users/{uid}/analyses dan
 * analysis_quota/{uid}). Sesi demo lokal memakai memori proses agar pengujian
 * di laptop tidak menulis ke Firestore produksi.
 */

export const DAILY_LIMIT = 10;
const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

export type AnalysisRecord = {
  id: string;
  source: string;
  symbol: string;
  timeframe: string;
  bars: number;
  created_at: number;
  status: "queued" | "running" | "done" | "failed";
  current_regime?: string | null;
  confidence?: number | null;
  low_confidence?: boolean | null;
  error?: string | null;
};

/** Tanggal kalender WIB; kuota direset pukul 00.00 WIB. */
function today(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Jakarta" }).format(new Date());
}

type MemoryStore = { quota: Map<string, { date: string; count: number }>; records: Map<string, AnalysisRecord[]> };
const memory: MemoryStore = ((globalThis as any).__analysisMemory ??= { quota: new Map(), records: new Map() });

function db(user: SessionUser) {
  return user.demo ? null : adminDb();
}

export async function quotaUsed(user: SessionUser): Promise<number> {
  const d = db(user);
  if (!d) {
    const q = memory.quota.get(user.uid);
    return q && q.date === today() ? q.count : 0;
  }
  const snap = await d.collection("analysis_quota").doc(user.uid).get();
  const data = snap.data();
  return data && data.date === today() ? Number(data.count) || 0 : 0;
}

/** Tambah pemakaian bila masih di bawah batas; false bila kuota habis. */
export async function consumeQuota(user: SessionUser): Promise<boolean> {
  const d = db(user);
  const date = today();
  if (!d) {
    const q = memory.quota.get(user.uid);
    const count = q && q.date === date ? q.count : 0;
    if (count >= DAILY_LIMIT) return false;
    memory.quota.set(user.uid, { date, count: count + 1 });
    return true;
  }
  const ref = d.collection("analysis_quota").doc(user.uid);
  return d.runTransaction(async (tx) => {
    const data = (await tx.get(ref)).data();
    const count = data && data.date === date ? Number(data.count) || 0 : 0;
    if (count >= DAILY_LIMIT) return false;
    tx.set(ref, { date, count: count + 1, updated_at: FieldValue.serverTimestamp() });
    return true;
  });
}

export async function refundQuota(user: SessionUser): Promise<void> {
  const d = db(user);
  const date = today();
  if (!d) {
    const q = memory.quota.get(user.uid);
    if (q && q.date === date && q.count > 0) q.count -= 1;
    return;
  }
  const ref = d.collection("analysis_quota").doc(user.uid);
  await d.runTransaction(async (tx) => {
    const data = (await tx.get(ref)).data();
    if (data && data.date === date && Number(data.count) > 0) tx.update(ref, { count: Number(data.count) - 1 });
  });
}

export async function saveRecord(user: SessionUser, rec: AnalysisRecord): Promise<void> {
  const d = db(user);
  if (!d) {
    const list = memory.records.get(user.uid) ?? [];
    const i = list.findIndex((r) => r.id === rec.id);
    if (i >= 0) list[i] = rec;
    else list.unshift(rec);
    memory.records.set(user.uid, list.slice(0, 50));
    return;
  }
  await d.collection("users").doc(user.uid).collection("analyses").doc(rec.id).set(rec, { merge: true });
}

export async function getRecord(user: SessionUser, id: string): Promise<AnalysisRecord | null> {
  const d = db(user);
  if (!d) return (memory.records.get(user.uid) ?? []).find((r) => r.id === id) ?? null;
  const snap = await d.collection("users").doc(user.uid).collection("analyses").doc(id).get();
  return snap.exists ? (snap.data() as AnalysisRecord) : null;
}

export async function listRecords(user: SessionUser): Promise<AnalysisRecord[]> {
  const d = db(user);
  if (!d) return memory.records.get(user.uid) ?? [];
  const snap = await d
    .collection("users")
    .doc(user.uid)
    .collection("analyses")
    .orderBy("created_at", "desc")
    .limit(50)
    .get();
  return snap.docs.map((doc) => doc.data() as AnalysisRecord);
}

/** Panggil endpoint internal backend (tidak dapat dijangkau dari luar lewat Caddy). */
export async function backend(path: string, init?: RequestInit): Promise<Response> {
  const token = process.env.ANALYSIS_INTERNAL_TOKEN?.trim();
  return fetch(`${BACKEND}/internal/analyses${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Internal-Token": token } : {}),
      ...(init?.headers ?? {}),
    },
  });
}

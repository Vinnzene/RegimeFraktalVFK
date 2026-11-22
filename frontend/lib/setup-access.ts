import { FieldValue } from "firebase-admin/firestore";
import { adminDb } from "@/lib/firebase-admin";
import type { SessionUser } from "@/lib/session";

/**
 * Akses fitur terkunci (Panduan Setup, Uji Ketahanan Metode): pengguna meminta,
 * admin menyetujui.
 *
 * Status disimpan di Firestore `setup_access/{uid}` atau `robustness_access/{uid}`. Admin ditentukan oleh
 * variabel lingkungan ADMIN_EMAILS (dipisah koma). Sesi demo lokal memakai
 * memori proses agar pengujian di laptop tidak menulis ke Firestore produksi.
 */

export type AccessStatus = "pending" | "approved" | "rejected";

export type AccessRecord = {
  uid: string;
  email: string | null;
  name: string | null;
  status: AccessStatus;
  note: string | null;
  requested_at: number;
  decided_at: number | null;
  decided_by: string | null;
};

/** Fitur yang aksesnya diatur admin; masing-masing punya koleksi Firestore sendiri. */
export type AccessFeature = "setup" | "robustness";

export const FEATURES: Record<AccessFeature, { label: string; collection: string; path: string }> = {
  setup: { label: "Panduan Setup", collection: "setup_access", path: "/setup" },
  robustness: { label: "Uji Ketahanan Metode", collection: "robustness_access", path: "/uji-ketahanan" },
};

export const isFeature = (v: unknown): v is AccessFeature => typeof v === "string" && v in FEATURES;

const memories: Record<AccessFeature, Map<string, AccessRecord>> = ((globalThis as any).__accessStores ??= {
  setup: new Map(),
  robustness: new Map(),
});

export function adminEmails(): string[] {
  return (process.env.ADMIN_EMAILS ?? "")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
}

export function isAdmin(user: SessionUser): boolean {
  return Boolean(user.email) && adminEmails().includes(user.email!.toLowerCase());
}

function db(user?: SessionUser) {
  return user?.demo ? null : adminDb();
}

export async function getAccess(user: SessionUser, feature: AccessFeature = "setup"): Promise<AccessRecord | null> {
  const d = db(user);
  if (!d) return memories[feature].get(user.uid) ?? null;
  const snap = await d.collection(FEATURES[feature].collection).doc(user.uid).get();
  return snap.exists ? (snap.data() as AccessRecord) : null;
}

/** Admin selalu punya akses; pengguna lain hanya bila disetujui. */
export async function hasAccess(user: SessionUser, feature: AccessFeature = "setup"): Promise<boolean> {
  if (isAdmin(user)) return true;
  return (await getAccess(user, feature))?.status === "approved";
}

export async function requestAccess(user: SessionUser, note: string | null, feature: AccessFeature = "setup"): Promise<AccessRecord> {
  const rec: AccessRecord = {
    uid: user.uid,
    email: user.email,
    name: user.name,
    status: "pending",
    note: note ? note.slice(0, 300) : null,
    requested_at: Math.floor(Date.now() / 1000),
    decided_at: null,
    decided_by: null,
  };
  const d = db(user);
  if (!d) memories[feature].set(user.uid, rec);
  else await d.collection(FEATURES[feature].collection).doc(user.uid).set({ ...rec, updated_at: FieldValue.serverTimestamp() });
  return rec;
}

export async function listAccess(admin: SessionUser, feature: AccessFeature = "setup"): Promise<AccessRecord[]> {
  const d = db(admin);
  if (!d) return [...memories[feature].values()].sort((a, b) => b.requested_at - a.requested_at);
  const snap = await d.collection(FEATURES[feature].collection).orderBy("requested_at", "desc").limit(200).get();
  return snap.docs.map((doc) => doc.data() as AccessRecord);
}

export async function decide(
  admin: SessionUser,
  uid: string,
  status: AccessStatus,
  feature: AccessFeature = "setup",
): Promise<AccessRecord | null> {
  const patch = { status, decided_at: Math.floor(Date.now() / 1000), decided_by: admin.email };
  const d = db(admin);
  if (!d) {
    const rec = memories[feature].get(uid);
    if (!rec) return null;
    Object.assign(rec, patch);
    return rec;
  }
  const ref = d.collection(FEATURES[feature].collection).doc(uid);
  const snap = await ref.get();
  if (!snap.exists) return null;
  await ref.update({ ...patch, updated_at: FieldValue.serverTimestamp() });
  return { ...(snap.data() as AccessRecord), ...patch };
}

/** Kirim pesan Telegram ke chat yang tertaut pada akun-akun tertentu; gagal diam-diam. */
export async function notifyTelegram(target: { uids?: string[]; emails?: string[] }, html: string): Promise<void> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const d = adminDb();
  if (!token || !d) return;
  try {
    const chats = new Set<number>();
    for (const uid of target.uids ?? []) {
      const id = (await d.collection("users").doc(uid).get()).data()?.telegram?.chat_id;
      if (id) chats.add(id);
    }
    for (const email of target.emails ?? []) {
      const snap = await d.collection("users").where("email", "==", email).limit(3).get();
      snap.docs.forEach((doc) => doc.data()?.telegram?.chat_id && chats.add(doc.data().telegram.chat_id));
    }
    await Promise.all(
      [...chats].map((chat_id) =>
        fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id, text: html, parse_mode: "HTML", disable_web_page_preview: true }),
        }).catch(() => undefined),
      ),
    );
  } catch {
    /* notifikasi pelengkap; tidak boleh menggagalkan permintaan */
  }
}

export const escapeHtml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

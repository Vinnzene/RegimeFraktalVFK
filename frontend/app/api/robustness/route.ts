import { NextResponse } from "next/server";
import { adminEmails, escapeHtml, getAccess, isAdmin, notifyTelegram, requestAccess } from "@/lib/setup-access";
import { requireUser } from "@/lib/server-user";

export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
const FEATURE = "robustness" as const;

/** Saklar pemilik UJI_KETAHANAN_TERBUKA=1 di backend/.env: buka untuk semua akun. */
async function openForAll(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND}/api/v1/model/robustness/status`, { cache: "no-store" });
    return res.ok && Boolean((await res.json())?.terbuka);
  } catch {
    return false;
  }
}

/**
 * Status akses Uji Ketahanan Metode, dan datanya hanya untuk admin, akun yang
 * disetujui admin, atau bila pemilik membuka halaman untuk semua.
 * `?status=1` hanya mengembalikan status (dipakai menu navigasi).
 */
export async function GET(req: Request) {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const admin = isAdmin(user);
  const [access, all] = await Promise.all([getAccess(user, FEATURE), openForAll()]);
  const open = admin || all || access?.status === "approved";
  const state = {
    access: admin || all ? "approved" : access?.status ?? null,
    requested_at: access?.requested_at ?? null,
    admin,
    open,
  };
  if (!open || new URL(req.url).searchParams.has("status")) return NextResponse.json({ ...state, data: null });

  const token = process.env.ANALYSIS_INTERNAL_TOKEN?.trim();
  const res = await fetch(`${BACKEND}/internal/robustness`, {
    cache: "no-store",
    headers: token ? { "X-Internal-Token": token } : {},
  }).catch(() => null);
  if (!res) return NextResponse.json({ error: "Backend tidak dapat dihubungi." }, { status: 502 });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) return NextResponse.json({ error: body?.detail ?? `HTTP ${res.status}` }, { status: res.status });
  return NextResponse.json({ ...state, data: body });
}

/** Minta akses; admin diberi tahu lewat Telegram bila akunnya tertaut. */
export async function POST(req: Request) {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const current = await getAccess(user, FEATURE);
  if (isAdmin(user) || current?.status === "approved") return NextResponse.json({ access: "approved" });
  if (current?.status === "pending") return NextResponse.json({ access: "pending", requested_at: current.requested_at });

  const body = await req.json().catch(() => ({}));
  const note = typeof body?.note === "string" ? body.note.trim() || null : null;
  const rec = await requestAccess(user, note, FEATURE);
  const who = escapeHtml(user.name ?? user.email ?? user.uid);
  await notifyTelegram(
    { emails: adminEmails() },
    `<b>Permintaan akses Uji Ketahanan Metode</b>\n${who}${user.email ? ` (${escapeHtml(user.email)})` : ""}` +
      (note ? `\nAlasan: ${escapeHtml(note)}` : "") +
      `\n\nSetujui di ${escapeHtml(process.env.DASHBOARD_URL ?? "")}/admin/akses?fitur=robustness`,
  );
  return NextResponse.json({ access: rec.status, requested_at: rec.requested_at });
}

import { NextResponse } from "next/server";
import { adminEmails, escapeHtml, getAccess, isAdmin, notifyTelegram, requestAccess } from "@/lib/setup-access";
import { GUIDE_NOTES, SETUP_GUIDE } from "@/lib/setup-guide";
import { requireUser } from "@/lib/server-user";

export const dynamic = "force-dynamic";

/** Isi Panduan Setup hanya untuk akun yang disetujui (atau admin); lainnya menerima status akses. */
export async function GET() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const admin = isAdmin(user);
  const access = await getAccess(user);
  const approved = admin || access?.status === "approved";
  return NextResponse.json({
    access: admin ? "approved" : access?.status ?? null,
    requested_at: access?.requested_at ?? null,
    admin,
    guide: approved ? SETUP_GUIDE : null,
    notes: approved ? GUIDE_NOTES : null,
  });
}

/** Minta akses; admin diberi tahu lewat Telegram bila akunnya tertaut. */
export async function POST(req: Request) {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const current = await getAccess(user);
  if (isAdmin(user) || current?.status === "approved") return NextResponse.json({ access: "approved" });
  if (current?.status === "pending") return NextResponse.json({ access: "pending", requested_at: current.requested_at });

  const body = await req.json().catch(() => ({}));
  const note = typeof body?.note === "string" ? body.note.trim() || null : null;
  const rec = await requestAccess(user, note);
  const who = escapeHtml(user.name ?? user.email ?? user.uid);
  await notifyTelegram(
    { emails: adminEmails() },
    `<b>Permintaan akses Panduan Setup</b>\n${who}${user.email ? ` (${escapeHtml(user.email)})` : ""}` +
      (note ? `\nAlasan: ${escapeHtml(note)}` : "") +
      `\n\nSetujui di ${escapeHtml(process.env.DASHBOARD_URL ?? "")}/admin/akses`,
  );
  return NextResponse.json({ access: rec.status, requested_at: rec.requested_at });
}

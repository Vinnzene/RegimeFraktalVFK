import { NextResponse } from "next/server";
import { decide, isAdmin, listAccess, notifyTelegram, type AccessStatus } from "@/lib/setup-access";
import { requireUser } from "@/lib/server-user";

export const dynamic = "force-dynamic";

async function requireAdmin() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  if (!isAdmin(user)) return NextResponse.json({ error: "Hanya admin." }, { status: 403 });
  return user;
}

/** Daftar permintaan akses Panduan Setup. */
export async function GET() {
  const admin = await requireAdmin();
  if (admin instanceof NextResponse) return admin;
  return NextResponse.json({ items: await listAccess(admin) });
}

const ACTIONS: Record<string, AccessStatus> = { approve: "approved", reject: "rejected", revoke: "rejected" };

/** Setujui, tolak, atau cabut akses satu akun. */
export async function POST(req: Request) {
  const admin = await requireAdmin();
  if (admin instanceof NextResponse) return admin;
  const body = await req.json().catch(() => null);
  const status = ACTIONS[body?.action];
  if (!body?.uid || !status) return NextResponse.json({ error: "Permintaan tidak valid." }, { status: 400 });

  const rec = await decide(admin, String(body.uid), status);
  if (!rec) return NextResponse.json({ error: "Permintaan tidak ditemukan." }, { status: 404 });
  await notifyTelegram(
    { uids: [rec.uid] },
    status === "approved"
      ? "<b>Akses Panduan Setup disetujui.</b>\nBuka menu Strategi → Panduan Setup di dashboard."
      : "<b>Akses Panduan Setup tidak diberikan.</b>\nHubungi admin bila ada pertanyaan.",
  );
  return NextResponse.json({ item: rec });
}

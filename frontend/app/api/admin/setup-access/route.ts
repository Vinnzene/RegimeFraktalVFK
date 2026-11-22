import { NextResponse } from "next/server";
import { decide, FEATURES, isAdmin, isFeature, listAccess, notifyTelegram, type AccessFeature, type AccessStatus } from "@/lib/setup-access";
import { requireUser } from "@/lib/server-user";

export const dynamic = "force-dynamic";

async function requireAdmin() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  if (!isAdmin(user)) return NextResponse.json({ error: "Hanya admin." }, { status: 403 });
  return user;
}

/** `fitur` = setup (Panduan Setup, bawaan) atau robustness (Uji Ketahanan Metode). */
const featureOf = (v: unknown): AccessFeature | null => (v == null || v === "" ? "setup" : isFeature(v) ? v : null);

/** Daftar permintaan akses satu fitur. */
export async function GET(req: Request) {
  const admin = await requireAdmin();
  if (admin instanceof NextResponse) return admin;
  const feature = featureOf(new URL(req.url).searchParams.get("fitur"));
  if (!feature) return NextResponse.json({ error: "Fitur tidak dikenal." }, { status: 400 });
  return NextResponse.json({ feature, items: await listAccess(admin, feature) });
}

const ACTIONS: Record<string, AccessStatus> = { approve: "approved", reject: "rejected", revoke: "rejected" };

const MENU: Record<AccessFeature, string> = {
  setup: "Strategi → Panduan Setup",
  robustness: "Riset → Uji Ketahanan Metode",
};

/** Setujui, tolak, atau cabut akses satu akun pada satu fitur. */
export async function POST(req: Request) {
  const admin = await requireAdmin();
  if (admin instanceof NextResponse) return admin;
  const body = await req.json().catch(() => null);
  const status = ACTIONS[body?.action];
  const feature = featureOf(body?.fitur);
  if (!body?.uid || !status || !feature) return NextResponse.json({ error: "Permintaan tidak valid." }, { status: 400 });

  const rec = await decide(admin, String(body.uid), status, feature);
  if (!rec) return NextResponse.json({ error: "Permintaan tidak ditemukan." }, { status: 404 });
  const label = FEATURES[feature].label;
  await notifyTelegram(
    { uids: [rec.uid] },
    status === "approved"
      ? `<b>Akses ${label} disetujui.</b>\nBuka menu ${MENU[feature]} di dashboard.`
      : `<b>Akses ${label} tidak diberikan.</b>\nHubungi admin bila ada pertanyaan.`,
  );
  return NextResponse.json({ item: rec });
}

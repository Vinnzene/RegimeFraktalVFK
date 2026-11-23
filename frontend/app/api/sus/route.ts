import { NextResponse } from "next/server";
import { requireUser } from "@/lib/server-user";
import { SusError, canAdminSus, exploreDone, getResponse, inviteCode, resetDemo, start, submit, susOpen, toPublic, visit } from "@/lib/sus-server";

export const dynamic = "force-dynamic";

/** Status Kuesioner SUS akun yang sedang login. */
export async function GET() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const r = await getResponse(user);
  return NextResponse.json({
    open: susOpen(user),
    invite_required: inviteCode().length > 0,
    demo: user.demo,
    admin: canAdminSus(user),
    response: r ? toPublic(r) : null,
  });
}

/** Aksi responden: start, visit, explore_done, submit, reset (demo). */
export async function POST(req: Request) {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const body = await req.json().catch(() => null);
  try {
    let r;
    switch (body?.action) {
      case "start":
        r = await start(user, body);
        break;
      case "visit":
        r = await visit(user, String(body.page ?? ""));
        break;
      case "explore_done":
        r = await exploreDone(user);
        break;
      case "submit":
        r = await submit(user, body);
        break;
      case "reset":
        await resetDemo(user);
        return NextResponse.json({ response: null });
      default:
        return NextResponse.json({ error: "Aksi tidak dikenal." }, { status: 400 });
    }
    return NextResponse.json({ response: toPublic(r) });
  } catch (e) {
    if (e instanceof SusError) return NextResponse.json({ error: e.message }, { status: e.status });
    return NextResponse.json({ error: "Server kuesioner gagal memproses permintaan." }, { status: 500 });
  }
}

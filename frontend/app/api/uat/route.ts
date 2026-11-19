import { NextResponse } from "next/server";
import { requireUser } from "@/lib/server-user";
import {
  UatError,
  canAdminUat,
  getResponse,
  inviteCode,
  resetDemo,
  start,
  submitQuestionnaire,
  taskAnswer,
  taskStart,
  toClient,
  uatOpen,
} from "@/lib/uat-server";

export const dynamic = "force-dynamic";

/** Status UAT akun yang sedang login. */
export async function GET() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const r = await getResponse(user);
  return NextResponse.json({
    open: uatOpen(user),
    invite_required: inviteCode().length > 0,
    demo: user.demo,
    admin: canAdminUat(user),
    response: r ? toClient(r) : null,
  });
}

/** Aksi responden: start, task_start, task_answer, questionnaire, reset (demo). */
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
      case "task_start":
        r = await taskStart(user, String(body.task));
        break;
      case "task_answer":
        r = await taskAnswer(user, String(body.task), String(body.answer ?? ""), Number(body.seq));
        break;
      case "questionnaire":
        r = await submitQuestionnaire(user, body);
        break;
      case "reset":
        await resetDemo(user);
        return NextResponse.json({ response: null });
      default:
        return NextResponse.json({ error: "Aksi tidak dikenal." }, { status: 400 });
    }
    return NextResponse.json({ response: toClient(r) });
  } catch (e) {
    if (e instanceof UatError) return NextResponse.json({ error: e.message }, { status: e.status });
    return NextResponse.json({ error: "Server UAT gagal memproses permintaan." }, { status: 500 });
  }
}

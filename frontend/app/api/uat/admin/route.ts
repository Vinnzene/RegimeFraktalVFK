import { NextResponse } from "next/server";
import { requireUser } from "@/lib/server-user";
import { UatError, canAdminUat, clearDemo, listResponsesForAdmin, seedDemo } from "@/lib/uat-server";
import { summarize } from "@/lib/uat";

export const dynamic = "force-dynamic";

/**
 * Rekap UAT untuk admin: skor kelayakan per butir, SUS, keberhasilan tugas, dan jawaban
 * tiap responden beserta akunnya. Akun hanya tampil di sini, tidak ikut ekspor CSV.
 */
export async function GET() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  if (!canAdminUat(user)) return NextResponse.json({ error: "Hanya admin." }, { status: 403 });
  const responses = await listResponsesForAdmin(user);
  return NextResponse.json({
    source: user.demo ? "memori sesi demo lokal (bukan data responden)" : "Firestore uat_responses",
    demo: user.demo,
    summary: summarize(responses),
    responses,
  });
}

/** Sesi demo lokal saja: isi atau hapus jawaban contoh di memori untuk mencoba tampilan. */
export async function POST(req: Request) {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  if (!canAdminUat(user)) return NextResponse.json({ error: "Hanya admin." }, { status: 403 });
  const body = await req.json().catch(() => null);
  try {
    if (body?.action === "seed_demo") seedDemo(user);
    else if (body?.action === "clear_demo") clearDemo(user);
    else return NextResponse.json({ error: "Aksi tidak dikenal." }, { status: 400 });
  } catch (e) {
    if (e instanceof UatError) return NextResponse.json({ error: e.message }, { status: e.status });
    throw e;
  }
  return NextResponse.json({ ok: true });
}

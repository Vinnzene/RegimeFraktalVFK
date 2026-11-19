import { NextResponse } from "next/server";
import { requireUser } from "@/lib/server-user";
import { canAdminUat, listResponses } from "@/lib/uat-server";
import { summarize } from "@/lib/uat";

export const dynamic = "force-dynamic";

/** Rekap UAT untuk admin: skor kelayakan per butir, SUS, keberhasilan tugas, dan daftar responden. */
export async function GET() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  if (!canAdminUat(user)) return NextResponse.json({ error: "Hanya admin." }, { status: 403 });
  const responses = await listResponses(user);
  return NextResponse.json({
    source: user.demo ? "memori sesi demo lokal (bukan data responden)" : "Firestore uat_responses",
    summary: summarize(responses),
    responses,
  });
}

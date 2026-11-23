import { NextResponse } from "next/server";
import { requireUser } from "@/lib/server-user";
import { canAdminSus, listResponses } from "@/lib/sus-server";
import { summarize } from "@/lib/sus";

export const dynamic = "force-dynamic";

/** Rekap SUS untuk admin: ringkasan, rata-rata per butir, dan jawaban per responden (tanpa nama/email). */
export async function GET() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  if (!canAdminSus(user)) return NextResponse.json({ error: "Hanya admin." }, { status: 403 });
  const responses = await listResponses(user);
  return NextResponse.json({
    source: user.demo ? "memori sesi demo lokal (bukan data responden)" : "Firestore sus_responses",
    demo: user.demo,
    summary: summarize(responses),
    responses,
  });
}

import { NextResponse } from "next/server";
import { requireUser } from "@/lib/server-user";
import { canAdminUat, listResponses } from "@/lib/uat-server";
import { toCsv } from "@/lib/uat";

export const dynamic = "force-dynamic";

/** Ekspor CSV jawaban per responden (tanpa email) untuk lampiran naskah. */
export async function GET() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  if (!canAdminUat(user)) return NextResponse.json({ error: "Hanya admin." }, { status: 403 });
  const csv = toCsv(await listResponses(user));
  const stamp = new Date().toISOString().slice(0, 10);
  return new NextResponse("\uFEFF" + csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="uat_rfraktal_${user.demo ? "demo_" : ""}${stamp}.csv"`,
      "Cache-Control": "no-store",
    },
  });
}

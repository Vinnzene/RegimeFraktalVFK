import { NextResponse } from "next/server";
import { isAdmin } from "@/lib/setup-access";
import { requireUser } from "@/lib/server-user";

export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/** Diagnosis overfitting/underfitting model final, khusus admin. */
export async function GET() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  if (!isAdmin(user)) return NextResponse.json({ error: "Hanya admin." }, { status: 403 });

  const token = process.env.ANALYSIS_INTERNAL_TOKEN?.trim();
  const res = await fetch(`${BACKEND}/internal/fitting`, {
    cache: "no-store",
    headers: token ? { "X-Internal-Token": token } : {},
  }).catch(() => null);
  if (!res) return NextResponse.json({ error: "Backend tidak dapat dihubungi." }, { status: 502 });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) return NextResponse.json({ error: body?.detail ?? `HTTP ${res.status}` }, { status: res.status });
  return NextResponse.json(body);
}

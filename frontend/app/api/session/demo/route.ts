import { NextResponse, type NextRequest } from "next/server";
import { DEMO_COOKIE, SESSION_MAX_AGE, demoAllowed, signDemoSession } from "@/lib/session";

/** Sesi demo untuk sidang tanpa internet. Hanya dari localhost dengan DEMO_LOGIN=true. */
export async function POST(req: NextRequest) {
  if (!demoAllowed(req.headers.get("host"))) {
    return NextResponse.json({ error: "Mode demo tidak tersedia di alamat ini." }, { status: 403 });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(DEMO_COOKIE, await signDemoSession(), {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
  return res;
}

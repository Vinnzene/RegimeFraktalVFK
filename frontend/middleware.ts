import { NextResponse, type NextRequest } from "next/server";
import { readSession } from "@/lib/session";

/**
 * Semua halaman dan API wajib login, kecuali halaman login, endpoint pembuat
 * sesi, dan berkas statis. Halaman diarahkan ke /login; API menjawab 401.
 */
export async function middleware(req: NextRequest) {
  const user = await readSession(req.cookies, req.headers.get("host"));
  if (user) return NextResponse.next();

  if (req.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "Belum login" }, { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = `?callbackUrl=${encodeURIComponent(req.nextUrl.pathname + req.nextUrl.search)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!login|api/session|_next/static|_next/image|favicon.ico|icon.svg|data/|reports/).*)"],
};

import { NextResponse, type NextRequest } from "next/server";
import { readSession } from "@/lib/session";

/**
 * Semua halaman dan API wajib login, kecuali landing page (/welcome), halaman
 * login, endpoint pembuat sesi, dan berkas statis. Halaman diarahkan ke /login; API menjawab 401.
 */
export async function middleware(req: NextRequest) {
  const user = await readSession(req.cookies, req.headers.get("host"));
  if (user) return NextResponse.next();

  if (req.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "Belum login" }, { status: 401 });
  }
  // Pengunjung baru di alamat utama melihat landing page, bukan langsung login.
  if (req.nextUrl.pathname === "/") {
    const landing = req.nextUrl.clone();
    landing.pathname = "/welcome";
    landing.search = "";
    return NextResponse.redirect(landing);
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = `?callbackUrl=${encodeURIComponent(req.nextUrl.pathname + req.nextUrl.search)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!login|welcome|landing/|api/session|_next/static|_next/image|favicon.ico|icon.svg|data/|reports/).*)"],
};

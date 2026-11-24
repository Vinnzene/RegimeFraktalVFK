import { NextResponse, type NextRequest } from "next/server";
import { readSession } from "@/lib/session";

/**
 * Semua halaman dan API wajib login, kecuali landing page (/welcome), halaman
 * login, endpoint pembuat sesi, dan berkas statis. Halaman diarahkan ke /login; API menjawab 401.
 * Halaman pada ADMIN_ONLY hanya dapat dibuka akun yang emailnya ada di ADMIN_EMAILS.
 */
/**
 * Hanya untuk admin: fitur tambahan di luar ruang lingkup skripsi (Walk-Forward multi-aset,
 * Analisis Aset, Analisa Teknikal, Order Flow Live, grup Strategi) serta grup Riset,
 * Arsip Fase 0, dan Tentang. Pengguna biasa hanya membuka Ringkasan, grup Identifikasi,
 * dan Kuesioner SUS.
 */
const ADMIN_ONLY = [
  "/walk-forward-evaluation",
  "/analisis",
  "/analisa-teknikal",
  "/orderflow-live",
  "/strategi",
  "/setup",
  "/notifikasi",
  "/uji-ketahanan",
  "/multifractal",
  "/order-flow",
  "/methodology",
  "/about",
];

function isAdminEmail(email: string | null): boolean {
  const list = (process.env.ADMIN_EMAILS ?? "")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
  return Boolean(email) && list.includes(email!.toLowerCase());
}

export async function middleware(req: NextRequest) {
  const user = await readSession(req.cookies, req.headers.get("host"));
  if (user) {
    const path = req.nextUrl.pathname;
    const adminOnly = ADMIN_ONLY.some((p) => path === p || path.startsWith(`${p}/`));
    if (adminOnly && !isAdminEmail(user.email)) {
      // Pengguna biasa diarahkan ke Ringkasan; menu ini memang tidak ditampilkan untuknya.
      const home = req.nextUrl.clone();
      home.pathname = "/";
      home.search = "";
      return NextResponse.redirect(home);
    }
    return NextResponse.next();
  }

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

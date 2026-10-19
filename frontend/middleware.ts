import { withAuth } from "next-auth/middleware";

/**
 * Semua halaman wajib login, kecuali halaman login sendiri, endpoint auth,
 * dan berkas statis. Pengunjung yang belum login diarahkan ke /login.
 */
export default withAuth({
  pages: { signIn: "/login" },
});

export const config = {
  matcher: ["/((?!login|api/auth|_next/static|_next/image|favicon.ico|icon.svg|data/|reports/).*)"],
};

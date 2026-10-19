import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";

/**
 * Autentikasi dashboard.
 *
 * - Google: siapa pun dengan akun Google boleh masuk. Login dipakai sebagai
 *   identitas, bukan pembatas akses.
 * - Mode demo: cadangan saat sidang tanpa internet. Hanya aktif bila
 *   DEMO_LOGIN=true DAN aplikasi berjalan di localhost, supaya tidak bisa
 *   dinyalakan tanpa sengaja di server publik.
 */

export const googleConfigured = Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);

const baseUrl = process.env.NEXTAUTH_URL ?? "http://localhost:3000";
const runsLocally = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/.test(baseUrl);
export const demoLoginEnabled = process.env.DEMO_LOGIN === "true" && runsLocally;

const providers: NextAuthOptions["providers"] = [];

if (googleConfigured) {
  providers.push(
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID as string,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
    })
  );
}

if (demoLoginEnabled) {
  providers.push(
    CredentialsProvider({
      id: "demo",
      name: "Mode demo",
      credentials: {},
      async authorize() {
        return { id: "demo", name: "Mode Demo", email: "demo@localhost" };
      },
    })
  );
}

export const authOptions: NextAuthOptions = {
  providers,
  secret: process.env.NEXTAUTH_SECRET,
  session: { strategy: "jwt", maxAge: 7 * 24 * 60 * 60 },
  pages: { signIn: "/login", error: "/login" },
};

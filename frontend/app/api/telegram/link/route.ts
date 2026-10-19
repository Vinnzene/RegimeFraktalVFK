import { randomBytes } from "node:crypto";
import { Timestamp } from "firebase-admin/firestore";
import { NextResponse } from "next/server";
import { adminDb } from "@/lib/firebase-admin";
import { requireUser } from "@/lib/server-user";

const TOKEN_MINUTES = 15;

/**
 * Buat kode sekali pakai dan tautan t.me/<bot>?start=<kode>.
 * Bot (backend) menukar kode ini dengan chat ID pengguna.
 */
export async function POST() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const db = adminDb();
  const bot = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME?.replace(/^@/, "");
  if (!db || !bot) {
    return NextResponse.json({ error: "Notifikasi Telegram belum dikonfigurasi di server." }, { status: 503 });
  }

  // base64url: karakter yang diizinkan parameter start Telegram (maks 64).
  const token = randomBytes(18).toString("base64url");
  const expires = new Date(Date.now() + TOKEN_MINUTES * 60 * 1000);
  await db.collection("link_tokens").doc(token).set({
    uid: user.uid,
    email: user.email,
    created_at: Timestamp.now(),
    expires_at: Timestamp.fromDate(expires),
  });
  return NextResponse.json({ url: `https://t.me/${bot}?start=${token}`, expires_at: expires.toISOString() });
}

import { NextResponse } from "next/server";
import { adminDb } from "@/lib/firebase-admin";
import { requireUser } from "@/lib/server-user";
import { isAdmin } from "@/lib/setup-access";

export type TelegramStatus = {
  chat_id: number;
  username: string | null;
  first_name: string | null;
  enabled: boolean;
  timeframes: string[];
  linked_at: string | null;
};

export type MeResponse = {
  user: { uid: string; email: string | null; name: string | null; picture: string | null; demo: boolean };
  telegram: TelegramStatus | null;
  firestore: boolean;
  bot_username: string | null;
  /** Email akun ada di ADMIN_EMAILS: boleh mengelola akses Panduan Setup. */
  admin: boolean;
};

/** Profil pengguna + status langganan Telegram. */
export async function GET() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;

  const db = adminDb();
  let telegram: TelegramStatus | null = null;
  if (db) {
    try {
      const snap = await db.collection("users").doc(user.uid).get();
      const tg = snap.data()?.telegram;
      if (tg?.chat_id) {
        telegram = {
          chat_id: tg.chat_id,
          username: tg.username ?? null,
          first_name: tg.first_name ?? null,
          enabled: Boolean(tg.enabled),
          timeframes: tg.timeframes ?? ["1h"],
          linked_at: tg.linked_at?.toDate?.().toISOString?.() ?? null,
        };
      }
    } catch {
      // Firestore tak terjangkau (mis. offline): profil tetap dikembalikan.
    }
  }

  const body: MeResponse = {
    user,
    telegram,
    firestore: Boolean(db),
    bot_username: process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME?.replace(/^@/, "") || null,
    admin: isAdmin(user),
  };
  return NextResponse.json(body);
}

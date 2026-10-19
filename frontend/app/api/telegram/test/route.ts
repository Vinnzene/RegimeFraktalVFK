import { NextResponse } from "next/server";
import { adminDb } from "@/lib/firebase-admin";
import { requireUser } from "@/lib/server-user";

/** Kirim pesan uji ke chat Telegram pengguna ini. */
export async function POST() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const db = adminDb();
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!db || !token) {
    return NextResponse.json({ error: "Notifikasi Telegram belum dikonfigurasi di server." }, { status: 503 });
  }
  const chatId = (await db.collection("users").doc(user.uid).get()).data()?.telegram?.chat_id;
  if (!chatId) return NextResponse.json({ error: "Telegram belum terhubung." }, { status: 409 });

  const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      parse_mode: "HTML",
      text: "<b>Pesan uji</b>\nNotifikasi regime BTC/USDT sudah tersambung ke chat ini.",
    }),
  }).catch(() => null);
  const data = res ? await res.json().catch(() => null) : null;
  if (!data?.ok) {
    const reason = data?.description ?? "Telegram tidak dapat dihubungi";
    return NextResponse.json({ error: `Pesan uji gagal: ${reason}.` }, { status: 502 });
  }
  return NextResponse.json({ ok: true });
}

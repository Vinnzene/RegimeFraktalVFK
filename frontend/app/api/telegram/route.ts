import { FieldValue } from "firebase-admin/firestore";
import { NextResponse, type NextRequest } from "next/server";
import { adminDb } from "@/lib/firebase-admin";
import { TIMEFRAMES, requireUser } from "@/lib/server-user";

function db503() {
  return NextResponse.json({ error: "Firestore belum dikonfigurasi di server." }, { status: 503 });
}

/** Ubah pengaturan langganan: aktif/nonaktif dan timeframe. */
export async function PATCH(req: NextRequest) {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const db = adminDb();
  if (!db) return db503();

  const body = await req.json().catch(() => ({}));
  const update: Record<string, unknown> = {};
  if (typeof body.enabled === "boolean") update["telegram.enabled"] = body.enabled;
  if (Array.isArray(body.timeframes)) {
    const tfs = TIMEFRAMES.filter((t) => body.timeframes.includes(t));
    if (!tfs.length) return NextResponse.json({ error: "Pilih minimal satu timeframe." }, { status: 400 });
    update["telegram.timeframes"] = tfs;
  }
  if (!Object.keys(update).length) return NextResponse.json({ error: "Tidak ada perubahan." }, { status: 400 });

  const ref = db.collection("users").doc(user.uid);
  const snap = await ref.get();
  if (!snap.data()?.telegram?.chat_id) {
    return NextResponse.json({ error: "Telegram belum terhubung." }, { status: 409 });
  }
  await ref.update(update);
  return NextResponse.json({ ok: true });
}

/** Putuskan tautan Telegram dari akun ini. */
export async function DELETE() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const db = adminDb();
  if (!db) return db503();
  await db.collection("users").doc(user.uid).set({ telegram: FieldValue.delete() }, { merge: true });
  return NextResponse.json({ ok: true });
}

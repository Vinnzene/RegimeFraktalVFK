import { FieldValue } from "firebase-admin/firestore";
import { NextResponse, type NextRequest } from "next/server";
import { adminAuth, adminDb } from "@/lib/firebase-admin";
import { DEMO_COOKIE, SESSION_COOKIE, SESSION_MAX_AGE } from "@/lib/session";

/** Tukar ID token Google (dari popup Firebase) menjadi cookie sesi server. */
export async function POST(req: NextRequest) {
  const auth = adminAuth();
  if (!auth) {
    return NextResponse.json(
      { error: "Server belum dikonfigurasi: kunci service account Firebase tidak ditemukan." },
      { status: 503 }
    );
  }
  const { idToken } = await req.json().catch(() => ({ idToken: null }));
  if (typeof idToken !== "string") return NextResponse.json({ error: "idToken wajib diisi" }, { status: 400 });

  let decoded;
  try {
    decoded = await auth.verifyIdToken(idToken);
  } catch {
    return NextResponse.json({ error: "Token Google tidak sah. Coba masuk lagi." }, { status: 401 });
  }
  // Token harus baru (5 menit) agar cookie tidak dibuat dari token curian lama.
  if (Date.now() / 1000 - decoded.auth_time > 5 * 60) {
    return NextResponse.json({ error: "Sesi login kedaluwarsa. Coba masuk lagi." }, { status: 401 });
  }
  const sessionCookie = await auth.createSessionCookie(idToken, { expiresIn: SESSION_MAX_AGE * 1000 });

  const db = adminDb();
  if (db) {
    const ref = db.collection("users").doc(decoded.uid);
    const snap = await ref.get();
    await ref.set(
      {
        email: decoded.email ?? null,
        name: decoded.name ?? null,
        photo: decoded.picture ?? null,
        last_login: FieldValue.serverTimestamp(),
        ...(snap.exists ? {} : { created_at: FieldValue.serverTimestamp() }),
      },
      { merge: true }
    );
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, sessionCookie, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
  return res;
}

/** Keluar: hapus cookie sesi Google maupun demo. */
export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, "", { path: "/", maxAge: 0 });
  res.cookies.set(DEMO_COOKIE, "", { path: "/", maxAge: 0 });
  return res;
}

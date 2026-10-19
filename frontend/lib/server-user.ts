import { cookies, headers } from "next/headers";
import { NextResponse } from "next/server";
import { readSession, type SessionUser } from "@/lib/session";

/** Pengguna yang sedang login untuk route handler / server component. */
export async function currentUser(): Promise<SessionUser | null> {
  return readSession(cookies(), headers().get("host"));
}

/** Untuk route API: pengguna, atau respons 401 siap dikembalikan. */
export async function requireUser(): Promise<SessionUser | NextResponse> {
  const user = await currentUser();
  return user ?? NextResponse.json({ error: "Belum login" }, { status: 401 });
}

export const TIMEFRAMES = ["1h", "4h"] as const;

import { SignJWT, importX509, jwtVerify, decodeProtectedHeader, type KeyLike } from "jose";

/**
 * Verifikasi sesi yang bisa dipakai di middleware (edge) maupun route handler.
 *
 * - Sesi Google: cookie sesi Firebase (dibuat lewat Admin SDK) diverifikasi
 *   dengan kunci publik Google, tanpa Admin SDK, supaya jalan di edge.
 * - Sesi demo: JWT HS256 yang ditandatangani SESSION_SECRET. Hanya dibuat
 *   bila DEMO_LOGIN=true dan permintaan datang dari localhost.
 */

export const SESSION_COOKIE = "__session";
export const DEMO_COOKIE = "demo_session";
export const SESSION_MAX_AGE = 5 * 24 * 60 * 60; // detik

export type SessionUser = {
  uid: string;
  email: string | null;
  name: string | null;
  picture: string | null;
  demo: boolean;
};

const KEYS_URL = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/publicKeys";
let keyCache: { keys: Record<string, KeyLike>; expires: number } | null = null;

async function googleKey(kid: string): Promise<KeyLike | null> {
  if (!keyCache || Date.now() > keyCache.expires || !keyCache.keys[kid]) {
    const res = await fetch(KEYS_URL);
    if (!res.ok) return null;
    const pems: Record<string, string> = await res.json();
    const maxAge = Number(/max-age=(\d+)/.exec(res.headers.get("cache-control") ?? "")?.[1] ?? 3600);
    const keys: Record<string, KeyLike> = {};
    for (const [id, pem] of Object.entries(pems)) keys[id] = await importX509(pem, "RS256");
    keyCache = { keys, expires: Date.now() + maxAge * 1000 };
  }
  return keyCache.keys[kid] ?? null;
}

export async function verifyFirebaseSession(cookie: string): Promise<SessionUser | null> {
  const projectId = process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID;
  if (!projectId || !cookie) return null;
  try {
    const { kid } = decodeProtectedHeader(cookie);
    const key = kid ? await googleKey(kid) : null;
    if (!key) return null;
    const { payload } = await jwtVerify(cookie, key, {
      issuer: `https://session.firebase.google.com/${projectId}`,
      audience: projectId,
    });
    if (!payload.sub) return null;
    return {
      uid: payload.sub,
      email: (payload.email as string) ?? null,
      name: (payload.name as string) ?? null,
      picture: (payload.picture as string) ?? null,
      demo: false,
    };
  } catch {
    return null;
  }
}

function demoSecret(): Uint8Array | null {
  const s = process.env.SESSION_SECRET;
  return s ? new TextEncoder().encode(s) : null;
}

export function isLocalHost(host: string | null): boolean {
  return /^(localhost|127\.0\.0\.1)(:\d+)?$/.test(host ?? "");
}

export function demoAllowed(host: string | null): boolean {
  return process.env.DEMO_LOGIN === "true" && Boolean(demoSecret()) && isLocalHost(host);
}

export async function signDemoSession(): Promise<string> {
  const secret = demoSecret();
  if (!secret) throw new Error("SESSION_SECRET belum diisi");
  return new SignJWT({ name: "Mode Demo", email: "demo@localhost" })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject("demo")
    .setIssuedAt()
    .setExpirationTime(`${SESSION_MAX_AGE}s`)
    .sign(secret);
}

export async function verifyDemoSession(cookie: string, host: string | null): Promise<SessionUser | null> {
  const secret = demoSecret();
  if (!secret || !cookie || !demoAllowed(host)) return null;
  try {
    await jwtVerify(cookie, secret, { algorithms: ["HS256"] });
    return { uid: "demo", email: "demo@localhost", name: "Mode Demo", picture: null, demo: true };
  } catch {
    return null;
  }
}

type CookieReader = { get(name: string): { value: string } | undefined };

export async function readSession(cookies: CookieReader, host: string | null): Promise<SessionUser | null> {
  const google = cookies.get(SESSION_COOKIE)?.value;
  if (google) {
    const user = await verifyFirebaseSession(google);
    if (user) return user;
  }
  const demo = cookies.get(DEMO_COOKIE)?.value;
  return demo ? verifyDemoSession(demo, host) : null;
}

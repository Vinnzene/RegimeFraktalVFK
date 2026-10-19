import { readFileSync } from "node:fs";
import path from "node:path";
import { cert, getApps, initializeApp, type App, type ServiceAccount } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";

/**
 * Firebase Admin untuk server Next.js (route handler, bukan middleware).
 *
 * Kredensial dibaca dari FIREBASE_SERVICE_ACCOUNT_JSON (isi JSON, untuk hosting)
 * atau FIREBASE_SERVICE_ACCOUNT (path; relatif terhadap root project).
 */

function loadServiceAccount(): ServiceAccount | null {
  const inline = process.env.FIREBASE_SERVICE_ACCOUNT_JSON?.trim();
  if (inline) return JSON.parse(inline);
  const raw = process.env.FIREBASE_SERVICE_ACCOUNT?.trim();
  if (!raw) return null;
  const file = path.isAbsolute(raw) ? raw : path.resolve(process.cwd(), "..", raw);
  try {
    return JSON.parse(readFileSync(file, "utf-8"));
  } catch {
    return null;
  }
}

let app: App | null | undefined;

export function adminApp(): App | null {
  if (app !== undefined) return app;
  const existing = getApps()[0];
  if (existing) return (app = existing);
  const sa = loadServiceAccount();
  app = sa ? initializeApp({ credential: cert(sa) }) : null;
  return app;
}

export function adminAuth() {
  const a = adminApp();
  return a ? getAuth(a) : null;
}

export function adminDb() {
  const a = adminApp();
  return a ? getFirestore(a) : null;
}

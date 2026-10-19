"use client";

import { getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut } from "firebase/auth";

/** Firebase di browser, hanya untuk popup login Google. Data dibaca lewat API server. */

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export const firebaseConfigured = Boolean(config.apiKey && config.authDomain && config.projectId);

function app(): FirebaseApp {
  return getApps()[0] ?? initializeApp(config);
}

/** Login Google lewat popup, lalu tukar ID token menjadi cookie sesi server. */
export async function signInWithGoogle(): Promise<void> {
  const auth = getAuth(app());
  const cred = await signInWithPopup(auth, new GoogleAuthProvider());
  const idToken = await cred.user.getIdToken();
  const res = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken }),
  });
  // Sesi dipegang cookie server; status login di browser tidak diperlukan lagi.
  await signOut(auth).catch(() => undefined);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `Gagal membuat sesi (HTTP ${res.status})`);
  }
}

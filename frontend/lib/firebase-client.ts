"use client";

import { getApps, initializeApp, type FirebaseApp } from "firebase/app";
import {
  GoogleAuthProvider,
  createUserWithEmailAndPassword,
  getAuth,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
  type User,
} from "firebase/auth";

/** Firebase di browser, hanya untuk proses login. Data dibaca lewat API server. */

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

/** Tukar ID token menjadi cookie sesi server, lalu lepas status login di browser. */
async function exchange(user: User, remember: boolean): Promise<void> {
  const idToken = await user.getIdToken();
  const res = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken, remember }),
  });
  await signOut(getAuth(app())).catch(() => undefined);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `Gagal membuat sesi (HTTP ${res.status})`);
  }
}

export async function signInWithGoogle(remember = true): Promise<void> {
  const cred = await signInWithPopup(getAuth(app()), new GoogleAuthProvider());
  await exchange(cred.user, remember);
}

export async function signInWithEmail(email: string, password: string, remember: boolean): Promise<void> {
  const cred = await signInWithEmailAndPassword(getAuth(app()), email, password);
  await exchange(cred.user, remember);
}

export async function registerWithEmail(name: string, email: string, password: string, remember: boolean): Promise<void> {
  const cred = await createUserWithEmailAndPassword(getAuth(app()), email, password);
  if (name.trim()) await updateProfile(cred.user, { displayName: name.trim() });
  // Token baru agar nama ikut masuk ke cookie sesi.
  await cred.user.getIdToken(true);
  await exchange(cred.user, remember);
}

export async function resetPassword(email: string): Promise<void> {
  await sendPasswordResetEmail(getAuth(app()), email);
}

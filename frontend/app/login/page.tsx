import { headers } from "next/headers";
import { redirect } from "next/navigation";
import LoginPanel from "@/components/LoginPanel";
import { adminApp } from "@/lib/firebase-admin";
import { demoAllowed } from "@/lib/session";
import { currentUser } from "@/lib/server-user";

export const metadata = { title: "Masuk — RFraktal" };

export default async function LoginPage({ searchParams }: { searchParams: { callbackUrl?: string } }) {
  const callbackUrl = searchParams.callbackUrl?.startsWith("/") ? searchParams.callbackUrl : "/";
  if (await currentUser()) redirect(callbackUrl);

  const googleReady = Boolean(
    process.env.NEXT_PUBLIC_FIREBASE_API_KEY && process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID && adminApp()
  );

  return (
    <LoginPanel
      callbackUrl={callbackUrl}
      googleConfigured={googleReady}
      demoEnabled={demoAllowed(headers().get("host"))}
    />
  );
}

import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import LoginPanel from "@/components/LoginPanel";
import { authOptions, demoLoginEnabled, googleConfigured } from "@/lib/auth";

export const metadata = { title: "Masuk — regimefraktalVFK" };

const ERRORS: Record<string, string> = {
  OAuthSignin: "Gagal menghubungi Google. Periksa koneksi internet lalu coba lagi.",
  OAuthCallback: "Google menolak permintaan masuk. Coba lagi, atau pakai akun Google lain.",
  OAuthAccountNotLinked: "Akun ini sudah terhubung dengan cara masuk lain.",
  AccessDenied: "Akses ditolak.",
  Configuration: "Login belum dikonfigurasi di server. Lihat frontend/.env.example.",
  CredentialsSignin: "Mode demo tidak dapat dipakai saat ini.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: { callbackUrl?: string; error?: string };
}) {
  const session = await getServerSession(authOptions);
  const callbackUrl = searchParams.callbackUrl?.startsWith("/") ? searchParams.callbackUrl : "/";
  if (session) redirect(callbackUrl);

  const error = searchParams.error ? ERRORS[searchParams.error] ?? "Masuk gagal. Coba lagi." : null;

  return (
    <LoginPanel
      callbackUrl={callbackUrl}
      error={error}
      googleConfigured={googleConfigured}
      demoEnabled={demoLoginEnabled}
    />
  );
}

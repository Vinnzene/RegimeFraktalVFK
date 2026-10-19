"use client";

import { useEffect, useState } from "react";
import BrandMark from "@/components/login/BrandMark";
import HeroChart from "@/components/login/HeroChart";
import ParticleWave from "@/components/login/ParticleWave";
import { api } from "@/lib/api-client";
import { registerWithEmail, resetPassword, signInWithEmail, signInWithGoogle } from "@/lib/firebase-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

const ERRORS: Record<string, string> = {
  "auth/popup-closed-by-user": "Jendela login ditutup sebelum selesai.",
  "auth/cancelled-popup-request": "Jendela login ditutup sebelum selesai.",
  "auth/popup-blocked": "Browser memblokir jendela login. Izinkan pop-up untuk situs ini lalu coba lagi.",
  "auth/network-request-failed": "Tidak bisa menghubungi server login. Periksa koneksi internet, atau pakai mode demo.",
  "auth/unauthorized-domain": "Domain ini belum diizinkan di Firebase (Authentication > Settings > Authorized domains).",
  "auth/invalid-credential": "Email atau password salah.",
  "auth/wrong-password": "Email atau password salah.",
  "auth/user-not-found": "Email atau password salah.",
  "auth/invalid-email": "Format email tidak valid.",
  "auth/email-already-in-use": "Email ini sudah terdaftar. Silakan masuk.",
  "auth/weak-password": "Password minimal 6 karakter.",
  "auth/too-many-requests": "Terlalu banyak percobaan. Tunggu beberapa menit lalu coba lagi.",
  "auth/operation-not-allowed": "Login email belum diaktifkan di Firebase (Authentication > Sign-in method > Email/Password).",
  "auth/missing-email": "Isi email terlebih dahulu.",
};

type Mode = "signin" | "register" | "reset";
type Stats = { price: number; changePct: number; regime: Regime | null };

function MailIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <rect x="2.5" y="4.5" width="15" height="11" rx="2" />
      <path d="m3 5.5 7 5 7-5" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <rect x="4" y="9" width="12" height="8" rx="2" />
      <path d="M7 9V6.5a3 3 0 0 1 6 0V9" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <circle cx="10" cy="7" r="3.2" />
      <path d="M3.8 17c.9-3 3.4-4.6 6.2-4.6s5.3 1.6 6.2 4.6" />
    </svg>
  );
}

function EyeIcon({ off }: { off: boolean }) {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M1.8 10S5 4.5 10 4.5 18.2 10 18.2 10 15 15.5 10 15.5 1.8 10 1.8 10Z" />
      <circle cx="10" cy="10" r="2.5" />
      {off && <path d="m3 3 14 14" />}
    </svg>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="h-[18px] w-[18px]" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

function Field({ id, label, icon, children }: { id: string; label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="group relative">
      <label htmlFor={id} className="sr-only">{label}</label>
      <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#9a948d] transition-colors group-focus-within:text-[#ff8a3d]">
        {icon}
      </span>
      {children}
    </div>
  );
}

const inputClass =
  "h-11 w-full rounded-lg border border-white/10 bg-black/35 pl-10 pr-10 text-[14px] text-[#f3efe9] placeholder:text-[#8d867e] outline-none transition focus:border-[#ff8a3d]/80 focus:bg-black/45 focus:shadow-[0_0_0_3px_rgba(255,122,26,0.18)] disabled:opacity-50";

function useMarketStats() {
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [o, g] = await Promise.all([api.ohlcv("1h", 25), api.regime("1h").catch(() => null)]);
        const c = o.candles;
        if (!alive || c.length < 2) return;
        const last = c[c.length - 1];
        const ref = c[Math.max(0, c.length - 25)];
        setStats({
          price: last.close,
          changePct: ref.close ? ((last.close - ref.close) / ref.close) * 100 : 0,
          regime: (g?.current_regime as Regime) ?? null,
        });
      } catch {
        // Backend mati: statistik disembunyikan, login tetap berfungsi.
      }
    })();
    return () => {
      alive = false;
    };
  }, []);
  return stats;
}

export default function LoginPanel({
  callbackUrl,
  googleConfigured,
  demoEnabled,
}: {
  callbackUrl: string;
  googleConfigured: boolean;
  demoEnabled: boolean;
}) {
  const [mode, setMode] = useState<Mode>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [remember, setRemember] = useState(true);
  const [pending, setPending] = useState<"email" | "google" | "demo" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const stats = useMarketStats();
  const ready = googleConfigured;

  const run = async (kind: "email" | "google" | "demo", fn: () => Promise<void>, redirect = true) => {
    setPending(kind);
    setError(null);
    setNotice(null);
    try {
      await fn();
      if (redirect) window.location.href = callbackUrl;
      else setPending(null);
    } catch (e) {
      const code = (e as { code?: string }).code;
      setError((code && ERRORS[code]) || (e as Error).message || "Masuk gagal. Coba lagi.");
      setPending(null);
    }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === "reset") {
      void run("email", async () => {
        await resetPassword(email.trim());
        setNotice("Tautan reset password sudah dikirim. Cek kotak masuk email Anda.");
        setMode("signin");
      }, false);
    } else if (mode === "register") {
      void run("email", () => registerWithEmail(name, email.trim(), password, remember));
    } else {
      void run("email", () => signInWithEmail(email.trim(), password, remember));
    }
  };

  const demo = () =>
    run("demo", async () => {
      const res = await fetch("/api/session/demo", { method: "POST" });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error ?? "Mode demo gagal.");
    });

  const title = { signin: "Selamat datang kembali", register: "Buat akun", reset: "Reset password" }[mode];
  const subtitle = {
    signin: "Masuk untuk membuka dashboard",
    register: "Daftar untuk mulai memantau regime pasar",
    reset: "Kami kirim tautan reset ke email Anda",
  }[mode];
  const cta = { signin: "Masuk", register: "Buat akun", reset: "Kirim tautan reset" }[mode];
  const up = (stats?.changePct ?? 0) >= 0;

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0a0b0d] font-sans text-[#f3efe9]">
      {/* Cahaya latar */}
      <div className="pointer-events-none absolute -left-40 bottom-[-12rem] h-[34rem] w-[34rem] rounded-full bg-[#ff6a00]/20 blur-[120px]" />
      <div className="pointer-events-none absolute right-[-10rem] top-[-10rem] h-[30rem] w-[30rem] rounded-full bg-[#ff7a1a]/15 blur-[120px]" />

      <div className="relative grid min-h-screen lg:grid-cols-2">
        {/* Kiri: identitas + ilustrasi */}
        <section className="relative hidden flex-col justify-between px-12 py-10 lg:flex xl:px-16">
          <div className="flex items-center gap-3">
            <BrandMark size={38} />
            <span className="text-[19px] font-semibold tracking-[0.04em]">
              regimefraktal<span className="text-[#ff8a3d]">VFK</span>
            </span>
          </div>

          <HeroChart />

          <div className="space-y-6">
            <div className="space-y-3">
              <h1 className="max-w-xl text-balance text-[40px] font-medium leading-[1.1] tracking-tight xl:text-[44px]">
                Kenali <span className="font-bold">sifat pasar</span> sebelum memilih strategi.
              </h1>
              <p className="max-w-lg text-[17px] leading-relaxed text-[#b9b2aa]">
                Identifikasi regime persistensi untuk kripto, emas, dan saham Indonesia, dari sistem yang tidak dilatih
                pada satu aset saja.
              </p>
            </div>

            <dl className="flex flex-wrap items-stretch gap-x-6 gap-y-3 text-[12px]">
              <div className="min-w-[9rem]">
                <dt className="text-[#8d867e]">BTC/USDT</dt>
                <dd className="mt-0.5 flex items-center gap-2">
                  <span className="font-mono text-[14px] font-semibold tabular-nums">
                    {stats ? stats.price.toLocaleString("en-US", { maximumFractionDigits: 2 }) : "–"}
                  </span>
                  {stats && (
                    <span className={`rounded px-1.5 py-0.5 font-mono text-[11px] ${up ? "bg-emerald-500/15 text-emerald-400" : "bg-[#ff6a00]/15 text-[#ff8a3d]"}`}>
                      {up ? "▲" : "▼"} {Math.abs(stats.changePct).toFixed(2)}%
                    </span>
                  )}
                </dd>
              </div>
              <div className="border-l border-white/10 pl-6">
                <dt className="text-[#8d867e]">Regime BTC 1H</dt>
                <dd className="mt-0.5 flex items-center gap-2 text-[14px] font-semibold">
                  {stats?.regime ? (
                    <>
                      <span className="h-2 w-2 rounded-full" style={{ background: REGIME_META[stats.regime].color }} />
                      {REGIME_PLAIN[stats.regime].name}
                    </>
                  ) : (
                    "–"
                  )}
                </dd>
              </div>
              <div className="border-l border-white/10 pl-6">
                <dt className="text-[#8d867e]">Aset dipantau</dt>
                <dd className="mt-0.5 text-[14px] font-semibold">
                  20 <span className="font-normal text-[#8d867e]">· kripto, emas, IDX</span>
                </dd>
              </div>
            </dl>
          </div>
        </section>

        {/* Kanan: kartu login */}
        <section className="relative flex items-center justify-center px-4 py-10 sm:px-8">
          <ParticleWave className="pointer-events-none absolute inset-0 h-full w-full opacity-80" />

          <div className="relative w-full max-w-[420px] rounded-2xl border border-[#ff8a3d]/45 bg-white/[0.06] p-7 shadow-[0_0_0_1px_rgba(255,138,61,0.08),0_0_60px_-10px_rgba(255,106,0,0.45),0_30px_80px_-20px_rgba(0,0,0,0.8)] backdrop-blur-xl sm:p-9">
            <div className="flex flex-col items-center text-center">
              <BrandMark size={64} />
              <div className="mt-2 text-[20px] font-semibold tracking-[0.04em]">
                regimefraktal<span className="text-[#ff8a3d]">VFK</span>
              </div>
              <h2 className="mt-5 text-[26px] font-medium tracking-tight">{title}</h2>
              <p className="mt-1 text-[13px] text-[#b9b2aa]">{subtitle}</p>
            </div>

            {!ready && (
              <p className="mt-5 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[12px] leading-relaxed text-amber-300">
                Login belum dikonfigurasi. Isi konfigurasi Firebase di <code className="font-mono">frontend/.env.local</code>{" "}
                (panduan di README bagian Login).
              </p>
            )}

            <form onSubmit={submit} className="mt-6 space-y-3.5" noValidate>
              {mode === "register" && (
                <Field id="login-name" label="Nama" icon={<UserIcon />}>
                  <input
                    id="login-name"
                    type="text"
                    autoComplete="name"
                    placeholder="Nama"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    disabled={!ready || pending !== null}
                    className={inputClass}
                  />
                </Field>
              )}
              <Field id="login-email" label="Email" icon={<MailIcon />}>
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  placeholder="Alamat email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={!ready || pending !== null}
                  className={inputClass}
                />
              </Field>
              {mode !== "reset" && (
                <Field id="login-password" label="Password" icon={<LockIcon />}>
                  <input
                    id="login-password"
                    type={showPw ? "text" : "password"}
                    autoComplete={mode === "register" ? "new-password" : "current-password"}
                    placeholder="Password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={!ready || pending !== null}
                    className={inputClass}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    aria-label={showPw ? "Sembunyikan password" : "Tampilkan password"}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-[#9a948d] transition hover:text-[#f3efe9] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#ff8a3d]"
                  >
                    <EyeIcon off={showPw} />
                  </button>
                </Field>
              )}

              {mode !== "reset" && (
                <div className="flex items-center justify-between text-[12.5px]">
                  <label htmlFor="login-remember" className="flex cursor-pointer items-center gap-2 text-[#cfc8bf]">
                    <input
                      id="login-remember"
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                      className="h-4 w-4 rounded border-white/20 bg-black/40 accent-[#ff7a1a]"
                    />
                    Ingat saya
                  </label>
                  {mode === "signin" && (
                    <button type="button" onClick={() => { setMode("reset"); setError(null); }} className="text-[#ff8a3d] transition hover:text-[#ffb27a]">
                      Lupa password?
                    </button>
                  )}
                </div>
              )}

              {error && (
                <p role="alert" className="rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-[12.5px] text-red-300">{error}</p>
              )}
              {notice && (
                <p role="status" className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-[12.5px] text-emerald-300">{notice}</p>
              )}

              <button
                type="submit"
                disabled={!ready || pending !== null}
                className="h-11 w-full rounded-lg bg-gradient-to-b from-[#ff8a3d] to-[#e2551b] text-[14px] font-semibold text-white shadow-[0_8px_30px_-6px_rgba(255,106,0,0.6)] transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#ff8a3d] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {pending === "email" ? "Memproses…" : cta}
              </button>
            </form>

            {mode === "reset" ? (
              <button type="button" onClick={() => { setMode("signin"); setError(null); }} className="mt-4 w-full text-center text-[12.5px] text-[#b9b2aa] transition hover:text-[#f3efe9]">
                ← Kembali ke halaman masuk
              </button>
            ) : (
              <>
                <div className="my-5 text-center text-[12px] text-[#8d867e]">
                  <div>– ATAU –</div>
                  <div className="mt-1 flex items-center gap-3">
                    <span className="h-px flex-1 bg-white/10" />
                    atau lanjut dengan
                    <span className="h-px flex-1 bg-white/10" />
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => void run("google", () => signInWithGoogle(remember))}
                  disabled={!ready || pending !== null}
                  className="flex h-11 w-full items-center justify-center gap-3 rounded-lg border border-white/12 bg-white/[0.08] text-[14px] font-medium text-[#f3efe9] transition hover:bg-white/[0.12] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#ff8a3d] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <GoogleMark />
                  {pending === "google" ? "Mengalihkan ke Google…" : "Lanjut dengan Google"}
                </button>

                <p className="mt-5 text-center text-[12.5px] text-[#b9b2aa]">
                  {mode === "signin" ? "Belum punya akun? " : "Sudah punya akun? "}
                  <button
                    type="button"
                    onClick={() => { setMode(mode === "signin" ? "register" : "signin"); setError(null); }}
                    className="font-medium text-[#ff8a3d] transition hover:text-[#ffb27a]"
                  >
                    {mode === "signin" ? "Buat akun" : "Masuk"}
                  </button>
                </p>
              </>
            )}

            {demoEnabled && (
              <div className="mt-5 border-t border-white/10 pt-4 text-center">
                <button
                  type="button"
                  onClick={() => void demo()}
                  disabled={pending !== null}
                  className="text-[12.5px] text-[#b9b2aa] underline decoration-white/20 underline-offset-4 transition hover:text-[#f3efe9] disabled:opacity-50"
                >
                  {pending === "demo" ? "Membuka…" : "Masuk mode demo (tanpa internet)"}
                </button>
              </div>
            )}
          </div>
        </section>
      </div>

      <p className="pointer-events-none absolute bottom-3 left-0 right-0 text-center text-[11px] text-[#6f6962] lg:left-auto lg:right-6 lg:text-right">
        Penelitian skripsi, bukan saran investasi.
      </p>
    </div>
  );
}

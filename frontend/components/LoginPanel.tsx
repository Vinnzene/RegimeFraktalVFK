"use client";

import { useState } from "react";
import { signInWithGoogle } from "@/lib/firebase-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

const ROWS: { regime: Regime; strategy: string }[] = [
  { regime: "persistent", strategy: "Trend-following" },
  { regime: "anti_persistent", strategy: "Mean-reversion" },
  { regime: "random_like", strategy: "Tidak trading" },
];

/** Garis harga kecil yang dibangkitkan deterministik untuk tiap regime. */
function Glyph({ regime }: { regime: Regime }) {
  const n = 48;
  const phi = regime === "persistent" ? 0.85 : regime === "anti_persistent" ? -0.75 : 0;
  let seed = regime.length * 9301 + 49297;
  const rnd = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280 - 0.5;
  };
  let y = 0;
  let e = 0;
  const pts: number[] = [];
  for (let i = 0; i < n; i++) {
    e = phi * e + rnd();
    y += e;
    pts.push(y);
  }
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const d = pts
    .map((v, i) => `${i ? "L" : "M"}${((i / (n - 1)) * 88 + 2).toFixed(1)},${(26 - ((v - lo) / (hi - lo || 1)) * 22).toFixed(1)}`)
    .join("");
  return (
    <svg viewBox="0 0 92 30" className="h-8 w-24 shrink-0" aria-hidden="true">
      <path d={d} fill="none" stroke={REGIME_META[regime].color} strokeWidth="1.6" strokeLinejoin="round" />
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

const POPUP_ERRORS: Record<string, string> = {
  "auth/popup-closed-by-user": "Jendela login ditutup sebelum selesai.",
  "auth/cancelled-popup-request": "Jendela login ditutup sebelum selesai.",
  "auth/popup-blocked": "Browser memblokir jendela login. Izinkan pop-up untuk situs ini lalu coba lagi.",
  "auth/network-request-failed": "Tidak bisa menghubungi Google. Periksa koneksi internet, atau pakai mode demo.",
  "auth/unauthorized-domain": "Domain ini belum diizinkan di Firebase (Authentication > Settings > Authorized domains).",
};

export default function LoginPanel({
  callbackUrl,
  googleConfigured,
  demoEnabled,
}: {
  callbackUrl: string;
  googleConfigured: boolean;
  demoEnabled: boolean;
}) {
  const [pending, setPending] = useState<"google" | "demo" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const go = async (provider: "google" | "demo") => {
    setPending(provider);
    setError(null);
    try {
      if (provider === "google") {
        await signInWithGoogle();
      } else {
        const res = await fetch("/api/session/demo", { method: "POST" });
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error ?? "Mode demo gagal.");
      }
      window.location.href = callbackUrl;
    } catch (e) {
      const code = (e as { code?: string }).code;
      setError((code && POPUP_ERRORS[code]) || (e as Error).message || "Masuk gagal. Coba lagi.");
      setPending(null);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-panelAlt px-4 py-10">
      <div className="grid w-full max-w-4xl overflow-hidden rounded-lg border border-edge bg-panel shadow-pop md:grid-cols-[1.15fr_1fr]">
        <section className="flex flex-col gap-7 border-b border-edge p-7 md:border-b-0 md:border-r md:p-9">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-accent font-mono text-sm font-bold text-panelAlt">
              R
            </span>
            <span className="text-[14px] font-semibold tracking-tight text-txt">
              regimefraktal<span className="text-accent">VFK</span>
            </span>
          </div>

          <div className="space-y-2.5">
            <h1 className="text-balance text-[26px] font-semibold leading-tight tracking-tight text-txt">
              Kenali sifat pasar sebelum memilih strategi
            </h1>
            <p className="max-w-md text-[13px] leading-relaxed text-txtDim">
              Dashboard ini mengukur apakah gerakan BTC/USDT sedang cenderung berlanjut, berbalik, atau acak, lalu
              memetakan kondisi itu ke strategi yang cocok.
            </p>
          </div>

          <ul className="grid gap-2.5">
            {ROWS.map(({ regime, strategy }) => (
              <li key={regime} className="flex items-center gap-3 rounded-md border border-edge bg-surface/50 px-3 py-2">
                <Glyph regime={regime} />
                <div className="min-w-0">
                  <div className="text-[13px] font-medium text-txt">{REGIME_PLAIN[regime].name}</div>
                  <div className="text-2xs text-txtMuted">
                    Strategi yang diuji: <span className="text-txtDim">{strategy}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <p className="mt-auto text-2xs leading-relaxed text-txtMuted">
            Penelitian skripsi, bukan saran investasi. Data historis Binance BTC/USDT 2019–2026.
          </p>
        </section>

        <section className="flex flex-col justify-center gap-5 p-7 md:p-9">
          <div className="space-y-1">
            <h2 className="text-[18px] font-semibold tracking-tight text-txt">Masuk</h2>
            <p className="text-[12.5px] text-txtDim">Gunakan akun Google untuk membuka dashboard.</p>
          </div>

          {error && (
            <div role="alert" className="rounded-md border border-bearish/40 bg-bearish/10 px-3 py-2 text-[12px] text-bearish">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={() => void go("google")}
            disabled={!googleConfigured || pending !== null}
            className="flex h-11 w-full items-center justify-center gap-3 rounded-md border border-[#dadce0] bg-white text-[14px] font-medium text-[#1f1f1f] transition hover:bg-[#f7f8f8] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60"
          >
            <GoogleMark />
            {pending === "google" ? "Mengalihkan ke Google…" : "Masuk dengan Google"}
          </button>

          {!googleConfigured && (
            <p className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-[11.5px] leading-relaxed text-warn">
              Login Google belum dikonfigurasi. Isi konfigurasi Firebase (<code className="font-mono">NEXT_PUBLIC_FIREBASE_*</code>)
              dan kunci service account di <code className="font-mono">frontend/.env.local</code>, lalu jalankan ulang
              frontend. Panduan ada di README bagian Login.
            </p>
          )}

          {demoEnabled && (
            <>
              <div className="flex items-center gap-3 text-2xs uppercase tracking-wider text-txtMuted">
                <span className="h-px flex-1 bg-edge" />
                atau
                <span className="h-px flex-1 bg-edge" />
              </div>
              <button
                type="button"
                onClick={() => void go("demo")}
                disabled={pending !== null}
                className="h-10 w-full rounded-md border border-edge bg-surface text-[13px] font-medium text-txt transition hover:border-edgeBright focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60"
              >
                {pending === "demo" ? "Membuka…" : "Masuk mode demo"}
              </button>
              <p className="text-2xs leading-relaxed text-txtMuted">
                Mode demo hanya tersedia saat dashboard dijalankan di laptop ini (localhost), untuk sidang tanpa
                internet.
              </p>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

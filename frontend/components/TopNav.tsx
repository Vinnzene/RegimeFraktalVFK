"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import UserMenu from "@/components/UserMenu";
import { startTour } from "@/components/GuidedTour";
import BrandMark from "@/components/login/BrandMark";

/**
 * Navigasi horizontal di header, dikelompokkan menurut pertanyaan pengguna.
 *
 * Semua akun melihat grup Pasar, Identifikasi, dan Strategi. Grup atau menu bertanda
 * adminOnly (Riset termasuk Walk-Forward multi-aset, Arsip Fase 0, Tentang) hanya tampil
 * untuk admin dan juga ditolak middleware (ADMIN_ONLY) bagi akun lain. Seluruh lebar layar tetap tersedia untuk
 * chart karena navigasi ada di header, bukan sidebar.
 */

/** adminOnly pada item: menu hanya tampil untuk admin, walaupun grupnya umum. */
type NavItem = { href: string; label: string; hint: string; locked?: boolean; adminOnly?: boolean };
/** adminOnly: grup hanya tampil untuk akun admin (email di ADMIN_EMAILS). */
type NavGroup = { label: string; items: NavItem[]; adminOnly?: boolean };

const GROUPS: NavGroup[] = [
  {
    label: "Pasar",
    items: [
      { href: "/", label: "Ringkasan", hint: "Kondisi pasar 1H & 4H menurut model identifikasi AI + grafik harga" },
      { href: "/analisis", label: "Analisis Aset", hint: "Identifikasi regime untuk pair/ticker apa pun (Binance, Yahoo) · 10 per hari" },
      { href: "/analisa-teknikal", label: "Analisa Teknikal", hint: "Tarik garis, fibonacci, dan indikator (TradingView)" },
      { href: "/orderflow-live", label: "Order Flow Live", hint: "Heatmap order book, footprint, delta & CVD (kripto)" },
    ],
  },
  {
    label: "Identifikasi",
    items: [
      { href: "/evaluasi-identifikasi", label: "Hasil Uji Identifikasi", hint: "Persentase identifikasi benar per kelas (backtest) dan per tahap walk-forward, BTC/USDT 1H & 4H" },
      { href: "/regime-explorer", label: "Hurst-DFA Klasik", hint: "Pembanding: label konsensus R/S–DFA, perpindahan & durasi" },
      { href: "/timeframe-comparison", label: "Hurst-DFA 1H vs 4H", hint: "Pembanding klasik pada dua skala waktu" },
      { href: "/swt", label: "Wavelet", hint: "Dekomposisi multiskala SWT" },
      { href: "/attention", label: "Fokus Model", hint: "Bobot attention 32 langkah model identifikasi (h = 0)" },
    ],
  },
  {
    label: "Strategi",
    items: [
      { href: "/strategi", label: "Regime → Strategi", hint: "Strategi per kondisi beserta hasil uji Fase 2" },
      { href: "/setup", label: "Panduan Setup", hint: "Setup yang cocok dan dihindari per kondisi pasar · perlu persetujuan admin" },
      { href: "/notifikasi", label: "Notifikasi Telegram", hint: "Pesan otomatis saat regime berganti" },
    ],
  },
  {
    label: "Riset",
    adminOnly: true,
    items: [
      { href: "/uji-ketahanan", label: "Uji Ketahanan Metode", hint: "Walk-forward, sensitivitas parameter, dan Monte Carlo (bootstrap & permutasi)" },
      { href: "/walk-forward-evaluation", label: "Walk-Forward Multi-Aset", hint: "Bukti identifikasi regime berjalan 2019→2026 (12 aset, h=0)" },
      { href: "/multifractal", label: "Multifraktal", hint: "Spektrum H(q) momen q=1,2,4 dan lebar ΔH" },
    ],
  },
  {
    label: "Arsip Fase 0",
    adminOnly: true,
    items: [
      { href: "/order-flow", label: "Order Flow (riset)", hint: "Arsip: ablation OFI & CVD (Model A–D)" },
    ],
  },
  {
    label: "Tentang",
    adminOnly: true,
    items: [
      { href: "/methodology", label: "Metodologi", hint: "Alur identifikasi, rumus & definisi" },
      { href: "/about", label: "Tentang", hint: "Latar belakang, batasan & temuan utama" },
    ],
  },
];

const isActive = (pathname: string, href: string) => pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));

/** Menu yang terkunci per akun sampai pemilik menyetujui (lihat /api/robustness). */
const LOCKED_HREF = "/uji-ketahanan";
const LockBadge = () => (
  <span className="rounded border border-edge px-1 py-px text-[10px] font-medium text-txtMuted">Terkunci</span>
);

export default function TopNav() {
  const pathname = usePathname();
  const [ujiTerbuka, setUjiTerbuka] = useState(false);
  const [admin, setAdmin] = useState(false);

  useEffect(() => {
    fetch("/api/robustness?status=1", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((r) => setUjiTerbuka(Boolean(r?.open)))
      .catch(() => setUjiTerbuka(false));
    // Grup Riset, Arsip Fase 0, dan Tentang hanya untuk akun admin.
    fetch("/api/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((r) => setAdmin(Boolean(r?.admin)))
      .catch(() => setAdmin(false));
  }, []);

  const groups = GROUPS.filter((g) => !g.adminOnly || admin).map((g) => ({
    ...g,
    items: g.items
      .filter((i) => !i.adminOnly || admin)
      .map((i) =>
        i.href === LOCKED_HREF && !ujiTerbuka ? { ...i, locked: true, hint: "Terkunci · buka halaman untuk meminta akses ke pemilik" } : i,
      ),
  }));
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navRef = useRef<HTMLDivElement>(null);

  // Tutup semua menu saat pindah halaman atau klik di luar navigasi.
  useEffect(() => {
    setOpenGroup(null);
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node)) {
        setOpenGroup(null);
        setMobileOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpenGroup(null);
        setMobileOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  return (
    <div ref={navRef} className="flex h-12 shrink-0 items-center gap-1 border-b border-edge bg-panel px-3">
      <Link href="/" className="mr-4 flex shrink-0 items-center gap-2">
        <BrandMark size={26} />
        <span className="hidden font-sans text-[13px] font-semibold tracking-tight text-txt sm:inline">
          R<span className="text-accent">Fraktal</span>
        </span>
      </Link>

      {/* Menu berkelompok untuk layar lebar. */}
      <nav className="hidden flex-1 items-center gap-0.5 lg:flex" aria-label="Navigasi utama">
        {groups.map((group) => {
          const groupActive = group.items.some((i) => isActive(pathname, i.href));
          const open = openGroup === group.label;
          return (
            <div key={group.label} className="relative" data-tour={`nav-${group.label.toLowerCase().replace(/\s+/g, "-")}`}>
              <button
                type="button"
                aria-expanded={open}
                aria-haspopup="true"
                onClick={() => setOpenGroup(open ? null : group.label)}
                className={`relative flex items-center gap-1 rounded-md px-3 py-1.5 text-[12.5px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${groupActive || open ? "text-txt" : "text-txtDim hover:bg-surface/60 hover:text-txt"
                  } ${open ? "bg-surface" : ""}`}
              >
                {group.label}
                <span className={`text-[9px] text-txtMuted transition-transform ${open ? "rotate-180" : ""}`}>▼</span>
                {groupActive && <span className="absolute inset-x-3 -bottom-[9px] h-0.5 rounded-t bg-accent" />}
              </button>

              {open && (
                <div className="absolute left-0 top-full z-50 mt-2 w-72 rounded-md border border-edge bg-panel p-1.5 shadow-pop">
                  {group.items.map((item) => {
                    const active = isActive(pathname, item.href);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={`block rounded px-3 py-2 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${active ? "bg-surface" : "hover:bg-surface/70"
                          }`}
                      >
                        <div className={`flex items-center gap-2 text-[12.5px] font-medium ${active ? "text-accent" : "text-txt"}`}>
                          {item.label}
                          {item.locked && <LockBadge />}
                        </div>
                        <div className="mt-0.5 text-2xs leading-snug text-txtMuted">{item.hint}</div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        <Link
          href="/evaluasi-identifikasi"
          className={`ml-2 flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[12px] font-medium transition-colors ${
            isActive(pathname, "/evaluasi-identifikasi")
              ? "border-accent bg-accent/15 text-accent"
              : "border-edge bg-surface/50 text-txt hover:border-accent/60 hover:text-accent"
          }`}
          title="Persentase identifikasi benar: historical backtesting dan 5-fold walk-forward, BTC/USDT 1H & 4H"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Hasil Uji Identifikasi
        </Link>
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          aria-expanded={mobileOpen}
          data-tour="nav-mobile"
          onClick={() => setMobileOpen((v) => !v)}
          className="rounded-md border border-edge px-2.5 py-1 text-[12px] text-txtDim transition-colors hover:border-edgeBright hover:text-txt lg:hidden"
        >
          Menu
        </button>
        <button
          type="button"
          data-tour="help"
          onClick={startTour}
          title="Tampilkan panduan penggunaan"
          className="flex items-center gap-1.5 rounded-md border border-edge px-2 py-1 text-[12px] text-txtDim transition-colors hover:border-edgeBright hover:text-txt"
        >
          <span className="flex h-4 w-4 items-center justify-center rounded-full border border-current text-[10px] font-semibold leading-none">?</span>
          <span className="hidden sm:inline">Panduan</span>
        </button>
        <ThemeToggle />
        <span data-tour="user" className="inline-flex">
          <UserMenu />
        </span>
      </div>

      {mobileOpen && (
        <div className="absolute left-0 right-0 top-12 z-50 max-h-[75vh] overflow-y-auto border-b border-edge bg-panel p-3 shadow-pop lg:hidden">
          <div className="grid gap-4 sm:grid-cols-2">
            {groups.map((group) => (
              <div key={group.label}>
                <div className="metric-label mb-1.5 px-2">{group.label}</div>
                <div className="grid gap-0.5">
                  {group.items.map((item) => {
                    const active = isActive(pathname, item.href);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={`rounded px-2 py-1.5 transition-colors ${active ? "bg-surface" : "hover:bg-surface/60"}`}
                      >
                        <div className={`flex items-center gap-2 text-[12.5px] font-medium ${active ? "text-accent" : "text-txt"}`}>
                          {item.label}
                          {item.locked && <LockBadge />}
                        </div>
                        <div className="text-2xs text-txtMuted">{item.hint}</div>
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

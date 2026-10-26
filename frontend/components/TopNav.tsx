"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import UserMenu from "@/components/UserMenu";
import BrandMark from "@/components/login/BrandMark";

/**
 * Navigasi horizontal di header, dikelompokkan menurut pertanyaan pengguna.
 *
 * Dua belas menu sejajar membuat pengunjung tidak tahu harus mulai dari mana.
 * Kelompok mengikuti alur cerita dashboard: kondisi pasar sekarang, strategi
 * yang cocok, bukti riset di baliknya, lalu metodologi. Seluruh lebar layar
 * tetap tersedia untuk chart karena navigasi ada di header, bukan sidebar.
 */

type NavItem = { href: string; label: string; hint: string };
type NavGroup = { label: string; items: NavItem[] };

const GROUPS: NavGroup[] = [
  {
    label: "Pasar",
    items: [
      { href: "/", label: "Ringkasan", hint: "Kondisi pasar 1H & 4H menurut detektor AI + grafik harga" },
      { href: "/analisis", label: "Analisis Aset", hint: "Detektor regime untuk pair/ticker apa pun (Binance, Yahoo) · 10 per hari" },
      { href: "/analisa-teknikal", label: "Analisa Teknikal", hint: "Tarik garis, fibonacci, dan indikator (TradingView)" },
      { href: "/orderflow-live", label: "Order Flow Live", hint: "Heatmap order book, footprint, delta & CVD (kripto)" },
    ],
  },
  {
    label: "Strategi",
    items: [
      { href: "/strategi", label: "Regime → Strategi", hint: "Strategi per kondisi beserta hasil uji Fase 2" },
      { href: "/notifikasi", label: "Notifikasi Telegram", hint: "Pesan otomatis saat regime berganti" },
    ],
  },
  {
    label: "Riset",
    items: [
      { href: "/regime-explorer", label: "Hurst-DFA Klasik", hint: "Pembanding: label konsensus R/S–DFA, perpindahan & durasi" },
      { href: "/timeframe-comparison", label: "Hurst-DFA 1H vs 4H", hint: "Pembanding klasik pada dua skala waktu" },
      { href: "/multifractal", label: "Multifraktal", hint: "Spektrum H(q) momen q=1,2,4 dan lebar ΔH" },
      { href: "/swt", label: "Wavelet", hint: "Dekomposisi multiskala SWT" },
    ],
  },
  {
    label: "Arsip Fase 0",
    items: [
      { href: "/model-comparison", label: "Perbandingan Model", hint: "Arsip: model lama berlabel Hurst-DFA" },
      { href: "/attention", label: "Fokus Model", hint: "Arsip: bobot attention model SWT lama" },
      { href: "/backtest", label: "Uji Strategi (lama)", hint: "Arsip: backtest eksploratif sebelum Fase 2" },
      { href: "/walk-forward-evaluation", label: "Setup Engine", hint: "Arsip: simulasi setup engine, digantikan Fase 2" },
      { href: "/order-flow", label: "Order Flow (riset)", hint: "Arsip: ablation OFI & CVD (Model A–D)" },
    ],
  },
  {
    label: "Tentang",
    items: [
      { href: "/methodology", label: "Metodologi", hint: "Alur detektor, rumus & definisi" },
      { href: "/about", label: "Tentang", hint: "Latar belakang, batasan & temuan utama" },
    ],
  },
];

const isActive = (pathname: string, href: string) => pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));

export default function TopNav() {
  const pathname = usePathname();
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
          regimefraktal<span className="text-accent">VFK</span>
        </span>
      </Link>

      {/* Menu berkelompok untuk layar lebar. */}
      <nav className="hidden flex-1 items-center gap-0.5 lg:flex" aria-label="Navigasi utama">
        {GROUPS.map((group) => {
          const groupActive = group.items.some((i) => isActive(pathname, i.href));
          const open = openGroup === group.label;
          return (
            <div key={group.label} className="relative">
              <button
                type="button"
                aria-expanded={open}
                aria-haspopup="true"
                onClick={() => setOpenGroup(open ? null : group.label)}
                className={`relative flex items-center gap-1 rounded-md px-3 py-1.5 text-[12.5px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                  groupActive || open ? "text-txt" : "text-txtDim hover:bg-surface/60 hover:text-txt"
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
                        className={`block rounded px-3 py-2 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                          active ? "bg-surface" : "hover:bg-surface/70"
                        }`}
                      >
                        <div className={`flex items-center gap-2 text-[12.5px] font-medium ${active ? "text-accent" : "text-txt"}`}>
                          {item.label}
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
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen((v) => !v)}
          className="rounded-md border border-edge px-2.5 py-1 text-[12px] text-txtDim transition-colors hover:border-edgeBright hover:text-txt lg:hidden"
        >
          Menu
        </button>
        <ThemeToggle />
        <UserMenu />
      </div>

      {mobileOpen && (
        <div className="absolute left-0 right-0 top-12 z-50 max-h-[75vh] overflow-y-auto border-b border-edge bg-panel p-3 shadow-pop lg:hidden">
          <div className="grid gap-4 sm:grid-cols-2">
            {GROUPS.map((group) => (
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
                        <div className={`text-[12.5px] font-medium ${active ? "text-accent" : "text-txt"}`}>{item.label}</div>
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

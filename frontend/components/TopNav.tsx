"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

/**
 * Navigasi horizontal di header.
 *
 * Menggantikan sidebar agar seluruh lebar layar tersedia untuk chart — penting
 * saat demo di proyektor, di mana ruang horizontal jauh lebih berharga daripada
 * daftar menu yang selalu terlihat.
 *
 * Label dibuat ringkas karena ruang mendatar terbatas; keterangan panjang
 * dipindahkan ke atribut title.
 */

const NAV = [
  { href: "/", label: "Ringkasan", hint: "Kondisi pasar saat ini + grafik harga" },
  { href: "/regime-explorer", label: "Detail Kondisi", hint: "Hurst, DFA, perpindahan & durasi kondisi" },
  { href: "/multifractal", label: "Multifraktal", hint: "Spektrum H(q) momen q=1,2,4 dan lebar ΔH" },
  { href: "/model-comparison", label: "Perbandingan Model", hint: "Model usulan vs pembanding" },
  { href: "/order-flow", label: "Order Flow", hint: "Ablation OFI & CVD (Model A–D)" },
  { href: "/swt", label: "Wavelet", hint: "Dekomposisi multiskala SWT" },
  { href: "/attention", label: "Fokus Model", hint: "Bagian data yang diperhatikan model (attention)" },
  { href: "/timeframe-comparison", label: "1H vs 4H", hint: "Perbandingan skala waktu" },
  { href: "/walk-forward-evaluation", label: "Walk-Forward", hint: "Evaluasi walk-forward out-of-sample" },
  { href: "/backtest", label: "Uji Strategi", hint: "Backtest eksploratif vs Buy & Hold" },
  { href: "/methodology", label: "Metodologi", hint: "Rumus & definisi" },
  { href: "/about", label: "Tentang", hint: "Latar belakang & batasan" },
];

export default function TopNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <div className="flex h-11 shrink-0 items-center gap-1 border-b border-edge bg-panel px-3">
      <Link href="/" className="mr-3 flex shrink-0 items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded bg-accent font-mono text-xs font-bold text-panelAlt">
          R
        </span>
        <span className="hidden font-sans text-[13px] font-semibold tracking-tight text-txt sm:inline">
          regimefraktal<span className="text-accent">VFK</span>
        </span>
      </Link>

      {/* Menu mendatar untuk layar lebar. */}
      <nav className="hidden flex-1 items-center gap-0.5 overflow-x-auto xl:flex">
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.hint}
              className={`relative whitespace-nowrap rounded px-2.5 py-1.5 text-[12px] font-medium transition-colors ${
                active ? "text-txt" : "text-txtDim hover:bg-surface/60 hover:text-txt"
              }`}
            >
              {item.label}
              {active && (
                <span className="absolute inset-x-2 -bottom-[9px] h-0.5 rounded-t bg-accent" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Tombol menu untuk layar sempit. */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="ml-auto rounded border border-edge px-2 py-1 text-[11px] text-txtDim xl:hidden"
      >
        Menu
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-11 z-50 border-b border-edge bg-panel p-2 shadow-pop xl:hidden">
          <div className="grid grid-cols-2 gap-1 sm:grid-cols-3">
            {NAV.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={`rounded px-3 py-2 text-[12px] transition-colors ${
                    active ? "bg-surface text-txt" : "text-txtDim hover:bg-surface/60"
                  }`}
                >
                  <div className="font-medium">{item.label}</div>
                  <div className="mt-0.5 text-2xs text-txtMuted">{item.hint}</div>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

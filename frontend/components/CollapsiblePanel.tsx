"use client";

import { useState } from "react";
import { useAppConfig } from "@/components/ConfigContext";

/**
 * Panel yang dapat dilipat.
 *
 * Dipakai untuk konten pendukung di bawah chart. Saat tertutup, chart memperoleh
 * hampir seluruh tinggi layar; saat dibuka, detailnya tetap tersedia tanpa
 * berpindah halaman.
 */
export default function CollapsiblePanel({
  title,
  subtitle,
  params,
  defaultOpen = false,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  params?: Record<string, string | number>;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const { shortHash } = useAppConfig();

  return (
    <section className={`rounded-md border border-edge bg-panel shadow-panel ${className}`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left transition-colors hover:bg-surface/40"
      >
        <span
          className={`text-txtMuted transition-transform ${open ? "rotate-90" : ""}`}
          aria-hidden
        >
          ▸
        </span>
        <span className="panel-title">{title}</span>
        {subtitle && !open && (
          <span className="truncate text-2xs text-txtMuted">— {subtitle}</span>
        )}
        {params && open && (
          <span className="ml-auto flex flex-wrap gap-1.5">
            {Object.entries(params).map(([k, v]) => (
              <span key={k} className="chip">
                {k}=<span className="text-txt">{String(v)}</span>
              </span>
            ))}
          </span>
        )}
      </button>

      {open && (
        <div className="border-t border-edge px-4 pb-3 pt-3">
          {subtitle && <p className="panel-sub mb-3">{subtitle}</p>}
          {children}
          <div className="mt-3 border-t border-edge pt-2 text-2xs text-txtMuted">
            config_hash <span className="font-mono">{shortHash || "…"}</span>
          </div>
        </div>
      )}
    </section>
  );
}

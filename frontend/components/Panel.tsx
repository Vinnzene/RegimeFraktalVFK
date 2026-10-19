"use client";

import { useAppConfig } from "@/components/ConfigContext";

/**
 * Pembungkus panel standar.
 *
 * Setiap panel menampilkan config_hash di footer. Tujuannya: angka mana pun
 * yang muncul di sidang bisa ditelusuri ke konfigurasi yang menghasilkannya.
 */
export default function Panel({
  title,
  subtitle,
  params,
  actions,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  params?: Record<string, string | number>;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const { shortHash } = useAppConfig();
  return (
    <section className={`panel flex flex-col ${className}`}>
      <header className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="panel-title">{title}</h2>
          {subtitle && <p className="panel-sub">{subtitle}</p>}
          {params && Object.keys(params).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {Object.entries(params).map(([k, v]) => (
                <span key={k} className="chip">
                  {k}=<span className="text-txt">{String(v)}</span>
                </span>
              ))}
            </div>
          )}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </header>

      <div className="flex-1">{children}</div>

      <footer className="mt-3 border-t border-edge pt-2 text-2xs text-txtMuted">
        config_hash <span className="font-mono">{shortHash || "…"}</span>
      </footer>
    </section>
  );
}

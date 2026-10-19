"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { signOutEverywhere, useUser } from "@/components/UserContext";

/** Avatar pengguna yang sedang login, dengan pintasan notifikasi dan tombol keluar. */
export default function UserMenu() {
  const { me } = useUser();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  if (!me) return <span className="h-7 w-7 rounded-full bg-surface" aria-hidden="true" />;

  const { name, email, picture, demo } = me.user;
  const initial = (name ?? email ?? "?").trim().charAt(0).toUpperCase();
  const tg = me.telegram;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-label={`Akun ${name ?? email ?? ""}`}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full border border-edge py-0.5 pl-0.5 pr-2.5 transition-colors hover:border-edgeBright focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
      >
        {picture ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={picture} alt="" className="h-6 w-6 rounded-full" referrerPolicy="no-referrer" />
        ) : (
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-surface font-mono text-[11px] font-semibold text-txt">
            {initial}
          </span>
        )}
        <span className="hidden max-w-[10rem] truncate text-[12px] text-txtDim md:inline">{name ?? email}</span>
        {demo && <span className="chip hidden md:inline">demo</span>}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-64 rounded-md border border-edge bg-panel p-1.5 shadow-pop">
          <div className="border-b border-edge px-3 pb-2.5 pt-1.5">
            <div className="truncate text-[13px] font-medium text-txt">{name ?? "Pengguna"}</div>
            {email && <div className="truncate text-2xs text-txtMuted">{email}</div>}
            {demo && <div className="mt-1.5 text-2xs leading-snug text-warn">Mode demo lokal, tanpa akun Google.</div>}
          </div>
          <Link
            href="/notifikasi"
            onClick={() => setOpen(false)}
            className="mt-1 flex items-center justify-between rounded px-3 py-2 text-[12.5px] text-txtDim transition-colors hover:bg-surface hover:text-txt"
          >
            Notifikasi Telegram
            <span className={`text-2xs ${tg?.enabled ? "text-bullish" : "text-txtMuted"}`}>
              {tg ? (tg.enabled ? "aktif" : "jeda") : "belum"}
            </span>
          </Link>
          <button
            type="button"
            onClick={() => void signOutEverywhere()}
            className="w-full rounded px-3 py-2 text-left text-[12.5px] text-txtDim transition-colors hover:bg-surface hover:text-txt"
          >
            Keluar
          </button>
        </div>
      )}
    </div>
  );
}

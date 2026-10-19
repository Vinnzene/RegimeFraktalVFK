/**
 * Judul halaman ringkas.
 *
 * Deskripsi panjang disembunyikan di balik tombol agar tidak memakan ruang
 * vertikal yang dibutuhkan chart. Teksnya tetap tersedia — penting untuk
 * penjelasan saat sidang — hanya tidak selalu tampil.
 */
"use client";

import { useState } from "react";

export default function PageHeader({
  title,
  description,
  right,
}: {
  title: string;
  description: string;
  right?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-2">
      <div className="flex items-center gap-3">
        <h1 className="font-sans text-[15px] font-semibold tracking-tight text-txt">{title}</h1>
        <button
          onClick={() => setOpen((v) => !v)}
          className="rounded border border-edge px-1.5 py-0.5 text-2xs text-txtMuted transition hover:border-edgeBright hover:text-txtDim"
          title="Tampilkan keterangan halaman"
        >
          {open ? "sembunyikan" : "info"}
        </button>
        {right && <div className="ml-auto">{right}</div>}
      </div>

      {open && (
        <p className="mt-2 max-w-4xl rounded border border-edge bg-surface/40 px-3 py-2 text-[11px] leading-relaxed text-txtDim">
          {description}
        </p>
      )}
    </div>
  );
}

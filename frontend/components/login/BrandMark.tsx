"use client";

import { useId } from "react";

/** Logo regimefraktalVFK: segitiga bersegi (puncak = regime, sisi = tiga kelas). */
export default function BrandMark({ size = 40, className = "" }: { size?: number; className?: string }) {
  // ID gradien unik per instans: bila dua logo memakai ID sama dan yang pertama
  // tersembunyi (display:none), gradien logo kedua ikut tidak tergambar.
  const uid = useId().replace(/:/g, "");
  const edge = `bm-edge-${uid}`;
  const face = `bm-face-${uid}`;
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={edge} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffb469" />
          <stop offset="1" stopColor="#e2551b" />
        </linearGradient>
        <linearGradient id={face} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ff8a3d" stopOpacity="0.55" />
          <stop offset="1" stopColor="#7a2a0c" stopOpacity="0.15" />
        </linearGradient>
      </defs>
      <path d="M24 3 L45 43 H3 Z" fill={`url(#${face})`} stroke={`url(#${edge})`} strokeWidth="2.2" strokeLinejoin="round" />
      <path d="M24 3 L24 30 M24 30 L11 43 M24 30 L37 43 M15.5 26 H32.5" stroke={`url(#${edge})`} strokeWidth="1.4" strokeLinecap="round" opacity="0.85" />
      <path d="M24 13 L31 26 H17 Z" fill="#ff8a3d" opacity="0.35" />
    </svg>
  );
}

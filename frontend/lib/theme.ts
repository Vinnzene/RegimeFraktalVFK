"use client";

import { useEffect, useState } from "react";
import { THEME_KEY } from "@/lib/theme-script";

/**
 * Tema terang/gelap. Pilihan disimpan per peramban (localStorage) dan dipasang
 * sebagai atribut data-theme pada <html>; skrip di layout.tsx memasangnya
 * sebelum halaman dilukis agar tidak berkedip.
 */

export type Theme = "light" | "dark";

export function currentTheme(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function setTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* mode privat: tema tetap berlaku untuk sesi ini */
  }
}

/** Tema aktif; ikut berubah saat tombol tema ditekan di mana pun. */
export function useTheme(): Theme {
  const [theme, set] = useState<Theme>("light");
  useEffect(() => {
    set(currentTheme());
    const obs = new MutationObserver(() => set(currentTheme()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);
  return theme;
}

/**
 * Warna token tema sebagai rgba(r, g, b, a), untuk pustaka canvas yang tidak
 * memahami var(). Format berkoma dipakai karena lightweight-charts menolak
 * sintaks rgb() berpemisah spasi.
 */
export function themeColor(token: string, alpha = 1): string {
  if (typeof document === "undefined") return "rgba(0, 0, 0, 1)";
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--c-${token}`).trim();
  const [r, g, b] = v.split(/\s+/).map(Number);
  return `rgba(${r || 0}, ${g || 0}, ${b || 0}, ${alpha})`;
}

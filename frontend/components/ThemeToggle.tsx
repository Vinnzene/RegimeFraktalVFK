"use client";

import { setTheme, useTheme } from "@/lib/theme";

/** Tombol bulan/matahari untuk berpindah tema terang dan gelap. */
export default function ThemeToggle() {
  const theme = useTheme();
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? "light" : "dark")}
      aria-label={dark ? "Ganti ke tema terang" : "Ganti ke tema gelap"}
      title={dark ? "Tema terang" : "Tema gelap"}
      className="flex h-8 w-8 items-center justify-center rounded-md text-txtDim transition-colors hover:bg-surface hover:text-txt focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
    >
      {dark ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
      )}
    </button>
  );
}

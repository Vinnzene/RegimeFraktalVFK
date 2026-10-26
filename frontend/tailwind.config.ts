import type { Config } from "tailwindcss";

/**
 * Dua tema berbagi nama warna yang sama: terang (bawaan, putih bersih dengan
 * garis tipis) dan gelap (terminal data kripto). Nilainya ada di globals.css;
 * aksen merek oranye dan hijau-merah khusus untuk arah harga.
 *
 * Catatan penting soal warna regime: hijau/merah SENGAJA tidak dipakai untuk
 * kategori regime. Persistent bukan berarti naik dan anti-persistent bukan
 * berarti turun — keduanya menyatakan sifat persistensi, bukan arah. Memakai
 * hijau/merah di sana akan membuat penonton menyamakannya dengan candle.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Semua warna dibaca dari variabel CSS (globals.css) supaya tema terang
        // dan gelap berbagi nama kelas yang sama. Format "r g b" memungkinkan
        // modifier opasitas Tailwind seperti bg-surface/70.
        // Lapisan latar, dari paling dalam ke paling depan.
        panelAlt: "rgb(var(--c-panel-alt) / <alpha-value>)",
        panel: "rgb(var(--c-panel) / <alpha-value>)",
        surface: "rgb(var(--c-surface) / <alpha-value>)",
        edge: "rgb(var(--c-edge) / <alpha-value>)",
        edgeBright: "rgb(var(--c-edge-bright) / <alpha-value>)",

        // Teks
        txt: "rgb(var(--c-txt) / <alpha-value>)",
        txtDim: "rgb(var(--c-txt-dim) / <alpha-value>)",
        txtMuted: "rgb(var(--c-txt-muted) / <alpha-value>)",

        // Arah harga
        bullish: "rgb(var(--c-bullish) / <alpha-value>)",
        bearish: "rgb(var(--c-bearish) / <alpha-value>)",
        // Aksen merek (navigasi, pilihan aktif). Bukan penanda naik/turun.
        accent: "rgb(var(--c-accent) / <alpha-value>)",
        warn: "rgb(var(--c-warn) / <alpha-value>)",

        // Kategori regime — biru/emas/ungu, bukan hijau/merah.
        persistent: "rgb(var(--c-persistent) / <alpha-value>)",
        randomLike: "rgb(var(--c-random-like) / <alpha-value>)",
        antiPersistent: "rgb(var(--c-anti-persistent) / <alpha-value>)",
        uncertainRule: "rgb(var(--c-uncertain-rule) / <alpha-value>)",
        uncertainLowconf: "rgb(var(--c-uncertain-lowconf) / <alpha-value>)",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      fontSize: {
        "2xs": ["10px", "14px"],
      },
      boxShadow: {
        panel: "var(--shadow-panel)",
        pop: "var(--shadow-pop)",
      },
    },
  },
  plugins: [],
};

export default config;

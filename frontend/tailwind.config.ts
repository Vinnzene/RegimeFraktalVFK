import type { Config } from "tailwindcss";

/** Dua tema berbagi nama warna yang sama: terang. */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Semua warna dibaca dari variabel CSS (globals.css) supaya tema terang.
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

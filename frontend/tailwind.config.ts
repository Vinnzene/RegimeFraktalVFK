import type { Config } from "tailwindcss";

/**
 * Palet bergaya terminal data kripto: latar nyaris hitam, permukaan berlapis,
 * dan aksen hijau-merah yang tegas untuk arah harga.
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
        // Lapisan latar, dari paling dalam ke paling depan.
        panelAlt: "#0b0e11",
        panel: "#151a21",
        surface: "#1b222b",
        edge: "#252c37",
        edgeBright: "#323b48",

        // Teks
        txt: "#eaecef",
        txtDim: "#8b949e",
        txtMuted: "#5c6673",

        // Arah harga
        bullish: "#2ebd85",
        bearish: "#f6465d",
        accent: "#2ebd85",
        warn: "#f0b90b",

        // Kategori regime — biru/emas/ungu, bukan hijau/merah.
        persistent: "#4a9eff",
        randomLike: "#8b949e",
        antiPersistent: "#f0b90b",
        uncertainRule: "#5c6673",
        uncertainLowconf: "#b07cf5",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      fontSize: {
        "2xs": ["10px", "14px"],
      },
      boxShadow: {
        panel: "0 1px 2px rgba(0,0,0,0.4)",
        pop: "0 8px 24px rgba(0,0,0,0.55)",
      },
    },
  },
  plugins: [],
};

export default config;

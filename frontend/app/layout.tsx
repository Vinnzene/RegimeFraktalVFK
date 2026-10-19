import type { Metadata } from "next";
import "./globals.css";
import "katex/dist/katex.min.css";
import AppChrome from "@/components/AppChrome";

export const metadata: Metadata = {
  title: "regimefraktalVFK — Identifikasi Regime Fraktal BTC/USDT",
  description:
    "Dashboard riset identifikasi regime persistensi BTC/USDT dan pemilihan strategi trading berbasis regime.",
};

/**
 * Tata letak dua baris header, tanpa sidebar.
 *
 * Navigasi dipindah ke header agar lebar penuh layar tersedia untuk chart.
 * Saat demo di proyektor, ruang mendatar lebih berharga daripada daftar menu
 * yang selalu terlihat.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";
import "katex/dist/katex.min.css";
import AppChrome from "@/components/AppChrome";
import { THEME_INIT_SCRIPT } from "@/lib/theme-script";

export const metadata: Metadata = {
  title: "rfraktal — Identifikasi Regime Fraktal BTC/USDT",
  description:
    "Dashboard riset identifikasi regime persistensi BTC/USDT dan pemilihan strategi trading berbasis regime.",
};

/** Tata letak dua baris header, tanpa sidebar. */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}

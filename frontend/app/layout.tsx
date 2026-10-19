import type { Metadata } from "next";
import "./globals.css";
import "katex/dist/katex.min.css";
import TopBar from "@/components/TopBar";
import TopNav from "@/components/TopNav";
import { ConfigProvider } from "@/components/ConfigContext";

export const metadata: Metadata = {
  title: "regimefraktalVFK — Identifikasi Regime Fraktal BTC/USDT",
  description:
    "Dashboard riset identifikasi regime fraktal dinamis BTC/USDT multi-timeframe (Hurst-DFA + SWT + Attention-BiLSTM).",
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
        <ConfigProvider>
          <div className="flex h-screen flex-col overflow-hidden">
            <div className="relative shrink-0">
              <TopNav />
              <TopBar />
            </div>
            <main className="flex-1 overflow-y-auto p-3">{children}</main>
          </div>
        </ConfigProvider>
      </body>
    </html>
  );
}

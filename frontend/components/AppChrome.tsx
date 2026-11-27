"use client";

import { usePathname } from "next/navigation";
import { ConfigProvider } from "@/components/ConfigContext";
import GuidedTour from "@/components/GuidedTour";
import TopBar from "@/components/TopBar";
import TopNav from "@/components/TopNav";
import { UserProvider } from "@/components/UserContext";

/** Kerangka aplikasi: pengguna, config, dan dua baris header. */
export default function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/login" || pathname === "/welcome") return <>{children}</>;
  // Halaman chart penuh: tanpa bar ticker BTC dan tanpa padding, agar chart mengisi layar.
  const fullBleed = pathname === "/analisa-teknikal";

  return (
    <UserProvider>
      <ConfigProvider>
        <div className="flex h-screen flex-col overflow-hidden">
          <div className="relative z-40 shrink-0">
            <TopNav />
            {!fullBleed && <TopBar />}
          </div>
          <main className={fullBleed ? "min-h-0 flex-1 overflow-hidden" : "flex-1 overflow-y-auto p-3"}>{children}</main>
        </div>
        <GuidedTour />
      </ConfigProvider>
    </UserProvider>
  );
}

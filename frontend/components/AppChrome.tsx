"use client";

import { usePathname } from "next/navigation";
import { ConfigProvider } from "@/components/ConfigContext";
import TopBar from "@/components/TopBar";
import TopNav from "@/components/TopNav";
import { UserProvider } from "@/components/UserContext";

/**
 * Kerangka aplikasi: pengguna, config, dan dua baris header.
 *
 * Halaman login tampil tanpa header karena pengunjung belum masuk dan data
 * pasar belum perlu dimuat.
 */
export default function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/login") return <>{children}</>;

  return (
    <UserProvider>
      <ConfigProvider>
        <div className="flex h-screen flex-col overflow-hidden">
          <div className="relative z-40 shrink-0">
            <TopNav />
            <TopBar />
          </div>
          <main className="flex-1 overflow-y-auto p-3">{children}</main>
        </div>
      </ConfigProvider>
    </UserProvider>
  );
}

"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { MeResponse } from "@/app/api/me/route";

type Ctx = { me: MeResponse | null; loading: boolean; reload: () => Promise<MeResponse | null> };

const UserCtx = createContext<Ctx>({ me: null, loading: true, reload: async () => null });

/** Profil pengguna yang sedang login dan status Telegram-nya, dibaca dari /api/me. */
export function UserProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      const res = await fetch("/api/me", { cache: "no-store" });
      const data: MeResponse | null = res.ok ? await res.json() : null;
      setMe(data);
      return data;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return <UserCtx.Provider value={{ me, loading, reload }}>{children}</UserCtx.Provider>;
}

export const useUser = () => useContext(UserCtx);

export async function signOutEverywhere() {
  await fetch("/api/session", { method: "DELETE" }).catch(() => undefined);
  window.location.href = "/login";
}

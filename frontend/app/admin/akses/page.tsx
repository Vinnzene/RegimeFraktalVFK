"use client";

import { useCallback, useEffect, useState } from "react";
import type { AccessRecord } from "@/lib/setup-access";

/** Admin: setujui, tolak, atau cabut akses Panduan Setup. */

const STATUS: Record<AccessRecord["status"], { label: string; className: string }> = {
  pending: { label: "Menunggu", className: "border-warn/40 bg-warn/10 text-warn" },
  approved: { label: "Disetujui", className: "border-bullish/40 bg-bullish/10 text-bullish" },
  rejected: { label: "Ditolak", className: "border-edge bg-surface text-txtDim" },
};

const when = (t: number | null) =>
  t ? new Date(t * 1000).toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "–";

export default function AdminAksesPage() {
  const [items, setItems] = useState<AccessRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await fetch("/api/admin/setup-access", { cache: "no-store" });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) return setError(body.error ?? `HTTP ${res.status}`);
    setItems(body.items);
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const act = async (uid: string, action: "approve" | "reject" | "revoke") => {
    setBusy(uid);
    const res = await fetch("/api/admin/setup-access", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid, action }),
    });
    if (!res.ok) setError((await res.json().catch(() => ({}))).error ?? "Gagal menyimpan.");
    setBusy(null);
    await load();
  };

  const pending = items?.filter((i) => i.status === "pending").length ?? 0;

  return (
    <div className="mx-auto max-w-[1100px] space-y-4 px-1 pb-8 sm:px-4">
      <header className="pt-2">
        <h1 className="text-[26px] font-bold tracking-tight text-txt">Akses Panduan Setup</h1>
        <p className="mt-1 text-[13px] text-txtMuted">
          {items ? `${pending} permintaan menunggu · ${items.length} total` : "Memuat…"} · Pengguna diberi tahu lewat Telegram bila akunnya tertaut.
        </p>
      </header>

      {error && <div className="rounded-lg border border-bearish/30 bg-bearish/5 px-4 py-2.5 text-[13px] text-bearish">{error}</div>}

      {items && (
        <section className="overflow-x-auto rounded-xl border border-edge bg-panel shadow-panel">
          {items.length === 0 ? (
            <p className="px-5 py-6 text-[13px] text-txtMuted">Belum ada permintaan.</p>
          ) : (
            <table className="w-full text-[13px]">
              <thead className="bg-surface/70 text-left text-[12px] text-txtDim">
                <tr>
                  <th className="py-2 pl-5 font-medium">Pengguna</th>
                  <th className="py-2 font-medium">Alasan</th>
                  <th className="py-2 font-medium">Diminta</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2 pr-5 text-right font-medium">Tindakan</th>
                </tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.uid} className="border-t border-edge align-top">
                    <td className="py-3 pl-5">
                      <div className="font-medium text-txt">{i.name ?? "–"}</div>
                      <div className="text-[12px] text-txtMuted">{i.email ?? i.uid}</div>
                    </td>
                    <td className="max-w-[280px] py-3 pr-3 text-[12.5px] text-txtDim">{i.note ?? "–"}</td>
                    <td className="py-3 text-[12px] text-txtMuted">{when(i.requested_at)}</td>
                    <td className="py-3">
                      <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${STATUS[i.status].className}`}>{STATUS[i.status].label}</span>
                      {i.decided_at && <div className="mt-1 text-[11px] text-txtMuted">{when(i.decided_at)}</div>}
                    </td>
                    <td className="py-3 pr-5">
                      <div className="flex justify-end gap-2">
                        {i.status !== "approved" && (
                          <button
                            type="button"
                            disabled={busy === i.uid}
                            onClick={() => act(i.uid, "approve")}
                            className="rounded-md bg-txt px-3 py-1.5 text-[12px] font-semibold text-panel hover:opacity-90 disabled:opacity-40"
                          >
                            Setujui
                          </button>
                        )}
                        {i.status === "pending" && (
                          <button
                            type="button"
                            disabled={busy === i.uid}
                            onClick={() => act(i.uid, "reject")}
                            className="rounded-md border border-edge px-3 py-1.5 text-[12px] font-medium text-txtDim hover:text-txt disabled:opacity-40"
                          >
                            Tolak
                          </button>
                        )}
                        {i.status === "approved" && (
                          <button
                            type="button"
                            disabled={busy === i.uid}
                            onClick={() => act(i.uid, "revoke")}
                            className="rounded-md border border-bearish/40 px-3 py-1.5 text-[12px] font-medium text-bearish hover:bg-bearish/5 disabled:opacity-40"
                          >
                            Cabut
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  );
}

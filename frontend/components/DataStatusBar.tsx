"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api-client";

/**
 * Indikator sumber & kesegaran data.
 *
 * Dua hal yang wajib terlihat saat sidang:
 *  1. Datanya asli (Binance) atau sintetis (mock) — jangan sampai ambigu.
 *  2. Bar terakhir sudah tutup. Candle berjalan sengaja dibuang, jadi jeda
 *     satu bar dari waktu sekarang itu normal, bukan tanda data basi.
 */

interface TimeframeStatus {
  timeframe: string;
  available: boolean;
  source: string;
  rows: number | null;
  first_time: number | null;
  last_time: number | null;
  age_seconds: number | null;
  stale: boolean;
  is_mock: boolean;
}

interface StatusPayload {
  is_mock: boolean;
  provider: string;
  years: number;
  drop_open_bar: boolean;
  timeframes: TimeframeStatus[];
  scheduler: {
    running: boolean;
    refresh_minutes: number;
    last_run: { at: number } | null;
  };
}

function formatAge(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${seconds} detik lalu`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} menit lalu`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;
  return `${Math.floor(hours / 24)} hari lalu`;
}

function formatDate(unix: number | null): string {
  if (!unix) return "—";
  return new Date(unix * 1000).toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

export default function DataStatusBar() {
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await api.dataStatus());
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 60_000);
    return () => clearInterval(timer);
  }, [load]);

  async function handleRefresh() {
    setRefreshing(true);
    setMessage(null);
    try {
      const res = await api.refreshData(false);
      const added = (res.refreshed ?? []).reduce(
        (acc: number, r: any) => acc + (r.rows_added ?? 0),
        0
      );
      setMessage(
        res.errors?.length
          ? `Sebagian gagal: ${res.errors[0].error?.slice(0, 110)}`
          : `Data diperbarui — ${added} bar baru.`
      );
      await load();
      // Panel lain membaca data turunan; muat ulang agar angkanya sinkron.
      if (!res.errors?.length && added > 0) {
        setTimeout(() => window.location.reload(), 900);
      }
    } catch (e: any) {
      setMessage(String(e?.message ?? e).slice(0, 160));
    } finally {
      setRefreshing(false);
    }
  }

  if (!status) return null;

  const isMock = status.is_mock;
  const anyStale = status.timeframes.some((t) => t.stale);

  const tone = isMock
    ? "border-uncertainLowconf/40 bg-uncertainLowconf/10 text-uncertainLowconf"
    : anyStale
      ? "border-warn/40 bg-warn/10 text-warn"
      : "border-bullish/40 bg-bullish/10 text-bullish";

  return (
    <div className={`rounded border px-3 py-2 ${tone}`}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="flex items-center gap-1.5 text-[11px] font-semibold">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              isMock ? "bg-uncertainLowconf" : anyStale ? "bg-warn" : "bg-bullish"
            }`}
          />
          {isMock ? "Data sintetis (mock)" : `Data live — ${status.provider}`}
        </span>

        {status.timeframes.map((t) => (
          <span key={t.timeframe} className="font-mono text-2xs opacity-90">
            {t.timeframe.toUpperCase()}: {t.rows?.toLocaleString() ?? "—"} bar · terakhir{" "}
            {formatDate(t.last_time)} ({formatAge(t.age_seconds)})
          </span>
        ))}

        <span className="text-2xs opacity-70">
          {status.scheduler.running
            ? `auto-refresh tiap ${status.scheduler.refresh_minutes} menit`
            : "auto-refresh nonaktif"}
        </span>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="ml-auto rounded border border-current/40 px-2.5 py-1 text-[11px] transition hover:bg-white/5 disabled:opacity-50"
        >
          {refreshing ? "Menarik data…" : "Refresh sekarang"}
        </button>
      </div>

      {!isMock && (
        <div className="mt-1.5 text-2xs opacity-70">
          Bar yang belum tutup sengaja dibuang, sehingga jeda satu bar dari waktu
          sekarang adalah perilaku normal — bukan tanda data tertinggal.
        </div>
      )}

      {message && <div className="mt-1.5 text-2xs opacity-90">{message}</div>}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import SymbolSearch, { type SymbolItem } from "@/components/SymbolSearch";
import { analyses, SOURCE_META, type AnalysisRecord, type AnalysisSource } from "@/lib/analyses-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

/**
 * Analisis Aset: jalankan detektor regime pada pair atau ticker apa pun dari
 * Binance atau Yahoo Finance, dibatasi 10 analisis per hari per akun.
 */

const BARS = [1000, 2000, 3000, 5000];

function StatusBadge({ r }: { r: AnalysisRecord }) {
  if (r.status === "done" && r.current_regime) {
    const key: Regime = r.low_confidence ? "uncertain_lowconf" : r.current_regime;
    const color = REGIME_META[key].color;
    return (
      <span className="inline-flex items-center gap-1.5 text-txt">
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
        {REGIME_PLAIN[key].name}
        {r.confidence !== null && r.confidence !== undefined && (
          <span className="font-mono text-[12px] text-txtMuted">{Math.round(r.confidence * 100)}%</span>
        )}
      </span>
    );
  }
  if (r.status === "failed") return <span className="text-bearish">Gagal</span>;
  return <span className="text-txtMuted">Diproses…</span>;
}

export default function AnalisisPage() {
  const router = useRouter();
  const [source, setSource] = useState<AnalysisSource>("binance");
  const [picked, setPicked] = useState<SymbolItem | null>(null);
  const [timeframe, setTimeframe] = useState("1h");
  const [bars, setBars] = useState(2000);
  const [items, setItems] = useState<AnalysisRecord[] | null>(null);
  const [quota, setQuota] = useState<{ used: number; limit: number; remaining: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    analyses
      .list()
      .then((d) => {
        setItems(d.items);
        setQuota(d.quota);
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const meta = SOURCE_META[source];
  const pickSource = (s: AnalysisSource) => {
    setSource(s);
    setPicked(null);
    if (!SOURCE_META[s].timeframes.includes(timeframe)) setTimeframe(SOURCE_META[s].timeframes.includes("1d") ? "1d" : SOURCE_META[s].timeframes[0]);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!picked) return setError("Pilih simbol dari daftar terlebih dahulu.");
    setBusy(true);
    setError(null);
    try {
      const job = await analyses.create({ source, symbol: picked.symbol, timeframe, bars });
      router.push(`/analisis/${job.id}`);
    } catch (err: any) {
      setError(err.message);
      setBusy(false);
      load();
    }
  };

  const exhausted = quota !== null && quota.remaining <= 0;

  return (
    <div className="mx-auto max-w-[1200px] space-y-4 px-1 pb-8 sm:px-4">
      <header className="pt-2">
        <h1 className="text-[26px] font-bold tracking-tight text-txt">Analisis Aset</h1>
        <p className="mt-1 text-[13px] text-txtMuted">
          Jalankan detektor regime fraktal pada pair kripto (Binance) atau saham, indeks, emas, dan forex (Yahoo Finance).
        </p>
      </header>

      <form onSubmit={submit} className="rounded-xl border border-edge bg-panel p-5 shadow-panel">
        <div className="grid gap-4 md:grid-cols-[auto_1fr_auto_auto_auto] md:items-end">
          <div className="block" role="group" aria-label="Sumber data">
            <span className="mb-1 block text-[12px] font-medium text-txtDim">Sumber data</span>
            <div className="inline-flex gap-0.5 rounded-lg border border-edge bg-surface p-0.5">
              {(Object.keys(SOURCE_META) as AnalysisSource[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => pickSource(s)}
                  aria-pressed={source === s}
                  className={`rounded-md px-3 py-1.5 text-[13px] font-medium transition ${source === s ? "bg-txt text-panel shadow-panel" : "text-txtDim hover:text-txt"}`}
                >
                  {SOURCE_META[s].label}
                </button>
              ))}
            </div>
          </div>
          <div className="block">
            <span className="mb-1 block text-[12px] font-medium text-txtDim">Simbol (ketik untuk mencari, lalu pilih)</span>
            <SymbolSearch source={source} value={picked} onChange={setPicked} />
          </div>
          <label className="block">
            <span className="mb-1 block text-[12px] font-medium text-txtDim">Timeframe</span>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="rounded-lg border border-edge bg-panel px-3 py-2 text-[14px] text-txt outline-none focus:border-accent"
            >
              {meta.timeframes.map((tf) => (
                <option key={tf} value={tf}>
                  {tf.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-[12px] font-medium text-txtDim">Jumlah bar</span>
            <select
              value={bars}
              onChange={(e) => setBars(Number(e.target.value))}
              className="rounded-lg border border-edge bg-panel px-3 py-2 text-[14px] text-txt outline-none focus:border-accent"
            >
              {BARS.map((b) => (
                <option key={b} value={b}>
                  {b.toLocaleString("id-ID")}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={busy || exhausted}
            className="rounded-lg bg-txt px-5 py-2 text-[14px] font-semibold text-panel transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Mengambil data…" : "Analisis"}
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-txtMuted">
          <span className="ml-auto">
            {quota ? (
              <>
                Kuota hari ini: <b className="text-txt">{quota.remaining}</b> dari {quota.limit} tersisa · direset 00.00 WIB
              </>
            ) : (
              "Memuat kuota…"
            )}
          </span>
        </div>
        {source === "yahoo" && (
          <p className="mt-2 text-[12px] text-txtMuted">Data 1H dari Yahoo Finance hanya tersedia sekitar 2 tahun terakhir; untuk saham, 1D lebih lengkap.</p>
        )}
        {error && <p className="mt-3 rounded-lg border border-bearish/30 bg-bearish/5 px-3 py-2 text-[12.5px] text-bearish">{error}</p>}
      </form>

      <p className="rounded-xl border border-warn/40 bg-warn/10 px-4 py-2.5 text-[12.5px] leading-relaxed text-txtDim">
        <b className="text-txt">Eksperimental untuk aset selain BTC/USDT 1H.</b> Detektor diuji pada data sintetis dan divalidasi pada BTC
        1H; pada uji 19 aset lain, kriteria generalisasi belum terpenuhi. Gunakan hasil untuk aset lain sebagai gambaran, bukan kepastian.
      </p>

      <section className="rounded-xl border border-edge bg-panel shadow-panel">
        <div className="px-5 pb-2 pt-4">
          <h2 className="text-[16px] font-semibold text-txt">Riwayat analisis</h2>
        </div>
        {items === null ? (
          <div className="px-5 pb-5 text-[13px] text-txtMuted">Memuat…</div>
        ) : items.length === 0 ? (
          <div className="px-5 pb-5 text-[13px] text-txtMuted">Belum ada analisis. Mulai dengan memasukkan simbol di atas.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="bg-surface/70 text-left text-[12px] text-txtDim">
                <tr>
                  <th className="py-2 pl-5 font-medium">Simbol</th>
                  <th className="py-2 font-medium">Sumber</th>
                  <th className="py-2 font-medium">TF</th>
                  <th className="py-2 font-medium">Kondisi terakhir</th>
                  <th className="py-2 pr-5 text-right font-medium">Dibuat</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} className="border-t border-edge transition hover:bg-surface/50">
                    <td className="py-2.5 pl-5">
                      <Link href={`/analisis/${r.id}`} className="font-mono font-semibold text-txt hover:text-accent">
                        {r.symbol}
                      </Link>
                    </td>
                    <td className="py-2.5 text-txtDim">{SOURCE_META[r.source]?.label ?? r.source}</td>
                    <td className="py-2.5 font-mono text-txtDim">{r.timeframe.toUpperCase()}</td>
                    <td className="py-2.5">
                      <StatusBadge r={r} />
                    </td>
                    <td className="py-2.5 pr-5 text-right text-[12px] text-txtMuted">
                      {new Date(r.created_at * 1000).toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

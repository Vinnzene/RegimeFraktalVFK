"use client";

import { useCallback, useEffect, useState } from "react";
import { BANGOR_ADJECTIVES, SUS_BENCHMARK, SUS_ITEMS, susScore, type PublicSus, type SusSummary } from "@/lib/sus";

/**
 * Rekap SUS untuk admin: ringkasan skor, rata-rata per butir (butir terlemah), dan jawaban
 * per responden. Tanpa nama dan email; ekspor CSV juga anonim.
 */

type Payload = { source: string; demo: boolean; summary: SusSummary; responses: PublicSus[] };

const n = (v: number | null | undefined, d = 1) =>
  v == null ? "–" : v.toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });
const when = (t: number | null) =>
  t ? new Date(t * 1000).toLocaleString("id-ID", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "–";
const card = "rounded-xl border border-edge bg-panel p-5 shadow-panel";
const th = "py-1.5 px-1.5 font-medium text-right";

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border border-edge bg-surface/40 px-4 py-3">
      <div className="metric-label">{label}</div>
      <div className="mt-1 font-mono text-[20px] text-txt">{value}</div>
      {note && <div className="text-2xs text-txtMuted">{note}</div>}
    </div>
  );
}

export default function RekapSusPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/sus/admin", { cache: "no-store" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setData(body);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const s = data?.summary;
  const done = (data?.responses ?? []).filter((r) => r.status === "done");

  return (
    <div className="mx-auto max-w-[1300px] space-y-4 px-1 pb-10 sm:px-4">
      <header className="flex flex-wrap items-end justify-between gap-3 pt-2">
        <div>
          <h1 className="text-[24px] font-bold tracking-tight text-txt">Rekap SUS</h1>
          <p className="mt-1 text-[13px] text-txtMuted">
            System Usability Scale (Brooke, 1996), dihitung langsung dari jawaban yang dikirim responden. Sumber: {data?.source ?? "…"}.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void load()} className="rounded-lg border border-edge px-3 py-2 text-[12.5px] text-txtDim hover:text-txt">
            Muat ulang
          </button>
          <a href="/api/sus/admin/export" className="rounded-lg bg-txt px-4 py-2 text-[13px] font-semibold text-panel hover:opacity-90">
            Ekspor CSV (tanpa nama/email)
          </a>
        </div>
      </header>
      {error && <p className="rounded-lg border border-bearish/30 bg-bearish/5 px-3 py-2 text-[12.5px] text-bearish">{error}</p>}
      {!data && !error && <div className={card}>Memuat…</div>}

      {s && (
        <section className={card}>
          <h2 className="text-[15px] font-semibold text-txt">Ringkasan</h2>
          {s.n === 0 ? (
            <p className="mt-2 text-[13px] text-txtMuted">
              Belum ada responden yang mengirim jawaban.{s.in_progress > 0 ? ` ${s.in_progress} akun sudah memulai tetapi belum mengirim.` : ""}
            </p>
          ) : (
            <>
              <div className="mt-3 grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
                <Stat label="Jumlah responden" value={String(s.n)} note={s.in_progress ? `${s.in_progress} belum selesai (tidak dihitung)` : "semua selesai"} />
                <Stat label="Rata-rata" value={n(s.mean, 2)} note={`SD ${n(s.sd, 2)} (n − 1)`} />
                <Stat label="Median" value={n(s.median, 2)} note={`min ${n(s.min, 1)} · maks ${n(s.max, 1)}`} />
                <Stat label="Skala kata sifat (Bangor, 2009)" value={s.adjective ?? "–"} note={`rentang penerimaan: ${s.acceptability ?? "–"}`} />
                <Stat label={`Skor ≥ ${SUS_BENCHMARK}`} value={`${s.at_or_above_68} dari ${s.n}`} note={`${n((100 * s.at_or_above_68) / s.n, 0)}% responden`} />
              </div>
              <p className="mt-3 text-2xs leading-relaxed text-txtMuted">
                Skor = 2,5 × [Σ(butir ganjil − 1) + Σ(5 − butir genap)]. Kata sifat dipilih dari rata-rata kelompok terdekat Bangor dkk. (2009):{" "}
                {BANGOR_ADJECTIVES.map((a) => `${a.label} ${n(a.mean, 1)}`).join(" · ")}. Rentang penerimaan: &lt; 50 Not Acceptable, 50–70 Marginal,
                &gt; 70 Acceptable. Acuan rata-rata {SUS_BENCHMARK}.
              </p>
            </>
          )}
        </section>
      )}

      {s && s.n > 0 && (
        <section className={card}>
          <h2 className="text-[15px] font-semibold text-txt">Rata-rata tiap butir</h2>
          <p className="mt-1 text-2xs text-txtMuted">
            Sumbangan ke skor (0–4): butir ganjil = rata-rata − 1, butir genap = 5 − rata-rata. Sumbangan terkecil = butir terlemah (tidak ditandai bila semua butir sama).
          </p>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead className="text-txtMuted">
                <tr className="border-b border-edge">
                  <th className="py-1.5 text-left font-medium">Butir</th>
                  <th className="py-1.5 text-left font-medium">Pernyataan</th>
                  <th className={th}>Arah</th>
                  <th className={th}>Rata-rata (1–5)</th>
                  <th className="w-[200px] py-1.5 pl-4 text-left font-medium">Sumbangan (0–4)</th>
                </tr>
              </thead>
              <tbody className="text-txtDim">
                {s.items.map((it) => {
                  const weakest = it.item === s.weakest_item;
                  return (
                    <tr key={it.item} className={`border-b border-edge/50 ${weakest ? "bg-warn/10" : ""}`}>
                      <td className="py-1.5 font-mono">{it.item}</td>
                      <td className="py-1.5 pr-3">
                        {it.text}
                        {weakest && <span className="ml-2 rounded border border-warn/40 px-1.5 text-2xs font-semibold text-warn">terlemah</span>}
                      </td>
                      <td className="py-1.5 text-right">{it.polarity}</td>
                      <td className="py-1.5 text-right font-mono text-txt">{n(it.mean, 2)}</td>
                      <td className="py-1.5 pl-4">
                        <div className="flex items-center gap-2">
                          <div className="h-2 flex-1 rounded bg-surface">
                            <div className="h-2 rounded bg-accent/70" style={{ width: `${(100 * it.contribution) / 4}%` }} />
                          </div>
                          <span className="w-10 text-right font-mono text-txt">{n(it.contribution, 2)}</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {data && (
        <section className={card}>
          <h2 className="text-[15px] font-semibold text-txt">Jawaban per responden</h2>
          {done.length === 0 ? (
            <p className="mt-2 text-[13px] text-txtMuted">Belum ada jawaban yang dikirim.</p>
          ) : (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1.5 text-left font-medium">Kode</th>
                    <th className="py-1.5 text-left font-medium">Peran</th>
                    <th className={th}>Pengalaman (bulan)</th>
                    {SUS_ITEMS.map((_, i) => (
                      <th key={i} className={th}>
                        {i + 1}
                      </th>
                    ))}
                    <th className={th}>Skor SUS</th>
                    <th className="py-1.5 pl-3 text-left font-medium">Waktu pengisian</th>
                  </tr>
                </thead>
                <tbody className="text-txtDim">
                  {done.map((r) => (
                    <tr key={r.code} className="border-b border-edge/50">
                      <td className="py-1.5 font-mono">{r.code}</td>
                      <td className="py-1.5">{r.profile.role}</td>
                      <td className="py-1.5 text-right font-mono">{r.profile.experience_months}</td>
                      {r.answers.map((v, i) => (
                        <td key={i} className="py-1.5 text-right font-mono">
                          {v}
                        </td>
                      ))}
                      <td className="py-1.5 text-right font-mono font-semibold text-txt">{n(susScore(r.answers), 1)}</td>
                      <td className="py-1.5 pl-3">{when(r.submitted_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-2 text-2xs text-txtMuted">
            Nama dan email tidak disimpan bersama jawaban. Kolom 1–10 = butir SUS (1 sangat tidak setuju … 5 sangat setuju). Waktu pengisian = saat
            jawaban dikirim (waktu lokal perangkat ini; CSV memakai UTC). Usia (opsional) dan saran ada di CSV.
          </p>
        </section>
      )}
    </div>
  );
}

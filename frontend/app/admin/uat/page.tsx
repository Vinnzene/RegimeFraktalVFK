"use client";

import { useEffect, useState } from "react";
import { PROFILE_FIELDS, SUS_ITEMS, type PublicResponse, type UatSummary } from "@/lib/uat";

const n = (v: number | null | undefined, d = 2) =>
  v == null ? "–" : v.toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });
const when = (t: number | null) =>
  t ? new Date(t * 1000).toLocaleString("id-ID", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "–";
const card = "rounded-xl border border-edge bg-panel p-5 shadow-panel";
const th = "py-1.5 font-medium text-right";

/** Admin: rekap UAT dari jawaban responden yang tersimpan, beserta ekspor CSV. */
export default function AdminUatPage() {
  const [data, setData] = useState<{ source: string; summary: UatSummary; responses: PublicResponse[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/uat/admin", { cache: "no-store" })
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
        setData(body);
      })
      .catch((e) => setError(e.message));
  }, []);

  const s = data?.summary;
  return (
    <div className="mx-auto max-w-[1200px] space-y-4 px-1 pb-10 sm:px-4">
      <header className="flex flex-wrap items-end justify-between gap-3 pt-2">
        <div>
          <h1 className="text-[24px] font-bold tracking-tight text-txt">Rekap UAT</h1>
          <p className="mt-1 text-[13px] text-txtMuted">
            Dihitung dari jawaban yang benar-benar dikirim responden. Sumber: {data?.source ?? "…"}.
          </p>
        </div>
        <a href="/api/uat/admin/export" className="rounded-lg bg-txt px-4 py-2 text-[13px] font-semibold text-panel hover:opacity-90">
          Ekspor CSV per responden
        </a>
      </header>
      {error && <p className="rounded-lg border border-bearish/30 bg-bearish/5 px-3 py-2 text-[12.5px] text-bearish">{error}</p>}
      {!data && !error && <div className={card}>Memuat…</div>}

      {s && s.n === 0 && <div className={card}>Belum ada responden yang mengirim jawaban.</div>}

      {s && s.n > 0 && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className={card}>
              <div className="metric-label">Responden selesai</div>
              <div className="mt-1 font-mono text-[22px] text-txt">{s.n}</div>
            </div>
            <div className={card}>
              <div className="metric-label">Kelayakan (P_UAT)</div>
              <div className="mt-1 font-mono text-[22px] text-txt">{n(s.likert.pct)}%</div>
              <div className="text-[12px] text-txtMuted">
                {s.likert.total_score}/{s.likert.total_max} · {s.likert.category}
              </div>
            </div>
            <div className={card}>
              <div className="metric-label">Skor SUS rata-rata</div>
              <div className="mt-1 font-mono text-[22px] text-txt">{n(s.sus.mean, 1)}</div>
              <div className="text-[12px] text-txtMuted">
                SD {n(s.sus.sd, 1)} · median {n(s.sus.median, 1)} · {s.sus.grade} · acuan rata-rata 68
              </div>
            </div>
          </div>

          <div className={card}>
            <h2 className="text-[15px] font-semibold text-txt">Kelayakan per butir (Likert 1–5)</h2>
            <p className="mt-1 text-2xs text-txtMuted">
              Skor butir = Σ(jumlah jawaban × bobot); maksimum = n × 5. P_UAT = Σ skor / Σ maksimum × 100%.
            </p>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1.5 text-left font-medium">Kode</th>
                    <th className="py-1.5 text-left font-medium">Aspek</th>
                    {["SS", "S", "CS", "TS", "STS"].map((k) => (
                      <th key={k} className={th}>
                        {k}
                      </th>
                    ))}
                    <th className={th}>Skor</th>
                    <th className={th}>%</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-txtDim">
                  {s.likert.items.map((it) => (
                    <tr key={it.code} className="border-b border-edge/50">
                      <td className="py-1.5">{it.code}</td>
                      <td className="py-1.5 font-sans">{it.aspect}</td>
                      {(["SS", "S", "CS", "TS", "STS"] as const).map((k) => (
                        <td key={k} className="py-1.5 text-right">
                          {it.counts[k]}
                        </td>
                      ))}
                      <td className="py-1.5 text-right">
                        {it.score}/{it.max}
                      </td>
                      <td className="py-1.5 text-right text-txt">{n(it.pct)}</td>
                    </tr>
                  ))}
                  <tr className="bg-surface/70 text-txt">
                    <td className="py-1.5 font-sans font-semibold" colSpan={7}>
                      Total
                    </td>
                    <td className="py-1.5 text-right">
                      {s.likert.total_score}/{s.likert.total_max}
                    </td>
                    <td className="py-1.5 text-right font-semibold">{n(s.likert.pct)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className={card}>
              <h2 className="text-[15px] font-semibold text-txt">Tugas terpandu</h2>
              <p className="mt-1 text-2xs text-txtMuted">Benar = jawaban cocok dengan isi sistem saat tugas dimulai atau dijawab. SEQ 1–7 (7 = sangat mudah).</p>
              <table className="mt-2 w-full text-[12px]">
                <thead className="text-txtMuted">
                  <tr className="border-b border-edge">
                    <th className="py-1.5 text-left font-medium">Tugas</th>
                    <th className={th}>Berhasil</th>
                    <th className={th}>Median waktu</th>
                    <th className={th}>SEQ</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-txtDim">
                  {s.tasks.map((t) => (
                    <tr key={t.id} className="border-b border-edge/50">
                      <td className="py-1.5 font-sans">
                        {t.id} · {t.title}
                      </td>
                      <td className="py-1.5 text-right">
                        {t.correct}/{t.n} ({n(t.success_pct, 0)}%)
                      </td>
                      <td className="py-1.5 text-right">{t.median_seconds == null ? "–" : `${Math.round(t.median_seconds)} s`}</td>
                      <td className="py-1.5 text-right">{n(t.mean_seq, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className={card}>
              <h2 className="text-[15px] font-semibold text-txt">Profil responden</h2>
              <div className="mt-2 space-y-2 text-[12px]">
                {PROFILE_FIELDS.map((f) => (
                  <div key={f.key}>
                    <div className="text-txtMuted">{f.label}</div>
                    <div className="text-txtDim">
                      {Object.entries(s.profile[f.key] ?? {})
                        .filter(([, c]) => c > 0)
                        .map(([k, c]) => `${k} (${c})`)
                        .join(" · ") || "–"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {data && data.responses.length > 0 && (
        <div className={card}>
          <h2 className="text-[15px] font-semibold text-txt">Responden</h2>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead className="text-txtMuted">
                <tr className="border-b border-edge">
                  <th className="py-1.5 text-left font-medium">Kode</th>
                  <th className="py-1.5 text-left font-medium">Status</th>
                  <th className="py-1.5 text-left font-medium">Persetujuan</th>
                  <th className="py-1.5 text-left font-medium">Dikirim</th>
                  <th className={th}>Tugas benar</th>
                  <th className={th}>SUS</th>
                </tr>
              </thead>
              <tbody className="font-mono text-txtDim">
                {data.responses.map((r) => {
                  const ok = Object.values(r.tasks).filter((t) => t.correct).length;
                  const sus = s?.sus.scores.find((x) => x.code === r.code)?.score;
                  return (
                    <tr key={r.code} className="border-b border-edge/50">
                      <td className="py-1.5">{r.code}</td>
                      <td className="py-1.5 font-sans">{r.status === "done" ? "selesai" : r.status === "tasks" ? "mengerjakan tugas" : "mengisi kuesioner"}</td>
                      <td className="py-1.5 font-sans">{when(r.consent_at)}</td>
                      <td className="py-1.5 font-sans">{when(r.submitted_at)}</td>
                      <td className="py-1.5 text-right">
                        {ok}/{Object.keys(r.tasks).length}
                      </td>
                      <td className="py-1.5 text-right">{sus == null ? "–" : n(sus, 1)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-2xs text-txtMuted">Email akun tidak ditampilkan dan tidak ikut diekspor. SUS: {SUS_ITEMS.length} butir, rumus Brooke (1996).</p>
        </div>
      )}
    </div>
  );
}

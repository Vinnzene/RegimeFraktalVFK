"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  LIKERT_ITEMS,
  LIKERT_SCALE,
  PROFILE_FIELDS,
  SUS_ITEMS,
  TASKS,
  UAT_BANDS,
  respondentScore,
  susGrade,
  taskAnswerLabel,
  type AdminResponse,
  type UatSummary,
} from "@/lib/uat";

/**
 * Dashboard admin UAT, mirip tab Respons di Google Form:
 * - Ringkasan: persentase kelayakan (P_UAT) langsung dihitung dari jawaban yang masuk.
 * - Per pertanyaan: sebaran jawaban tiap butir.
 * - Individu: jawaban lengkap satu responden beserta akunnya.
 * Akun (nama/email) hanya tampil di sini; ekspor CSV tetap anonim.
 */

type Payload = { source: string; demo: boolean; summary: UatSummary; responses: AdminResponse[] };
type Tab = "ringkasan" | "pertanyaan" | "individu";

const n = (v: number | null | undefined, d = 2) =>
  v == null ? "–" : v.toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });
const when = (t: number | null) =>
  t ? new Date(t * 1000).toLocaleString("id-ID", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "–";
const card = "rounded-xl border border-edge bg-panel p-5 shadow-panel";
const th = "py-1.5 font-medium text-right";
const STATUS = { done: "Selesai", tasks: "Mengerjakan tugas", questionnaire: "Mengisi kuesioner" } as const;

function categoryTone(cat: string | null) {
  if (cat === "Sangat Layak" || cat === "Layak") return "border-bullish/40 bg-bullish/10 text-bullish";
  if (cat === "Cukup Layak") return "border-warn/40 bg-warn/10 text-warn";
  if (cat) return "border-bearish/40 bg-bearish/10 text-bearish";
  return "border-edge bg-surface text-txtMuted";
}

function CategoryBadge({ cat }: { cat: string | null }) {
  return <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${categoryTone(cat)}`}>{cat ?? "Belum lengkap"}</span>;
}

/** Skala kelayakan 0–100 dengan lima pita kategori dan penanda nilai. */
function FeasibilityScale({ pct }: { pct: number }) {
  return (
    <div className="mt-4">
      <div className="relative flex h-3 overflow-hidden rounded-full">
        {UAT_BANDS.map((b, i) => (
          <div key={b.label} className="h-full border-r border-panel last:border-r-0" style={{ width: `${b.to - b.from + (i === 0 ? 0 : 1)}%`, background: `hsl(${i * 30} 65% 55% / ${0.25 + i * 0.12})` }} />
        ))}
        <div className="absolute top-[-3px] h-[18px] w-[3px] -translate-x-1/2 rounded bg-txt" style={{ left: `${Math.min(100, Math.max(0, pct))}%` }} />
      </div>
      <div className="mt-1.5 grid grid-cols-5 text-center text-[10.5px] text-txtMuted">
        {UAT_BANDS.map((b) => (
          <div key={b.label}>
            {b.label}
            <div className="font-mono">
              {b.from}–{b.to}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Batang sebaran jawaban, seperti grafik ringkasan Google Form. */
function DistBar({ label, count, total, highlight = false }: { label: string; count: number; total: number; highlight?: boolean }) {
  const pct = total ? (100 * count) / total : 0;
  return (
    <div className="grid grid-cols-[150px_1fr_74px] items-center gap-2 text-[12px]">
      <div className={`truncate ${highlight ? "font-semibold text-txt" : "text-txtDim"}`}>{label}</div>
      <div className="h-4 rounded bg-surface">
        <div className="h-4 rounded bg-accent/70" style={{ width: `${pct}%` }} />
      </div>
      <div className="text-right font-mono text-txtDim">
        {count} ({n(pct, 0)}%)
      </div>
    </div>
  );
}

/** Lima pilihan skala dengan pilihan responden disorot, seperti tampilan Individu Google Form. */
function ScalePick({ value }: { value: number | undefined }) {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {LIKERT_SCALE.map((s) => (
        <span
          key={s.value}
          title={s.label}
          className={`rounded-md border px-2 py-1 text-[11.5px] ${
            value === s.value ? "border-accent bg-accent/15 font-semibold text-accent" : "border-edge text-txtMuted"
          }`}
        >
          {s.value} · {s.label}
        </span>
      ))}
    </div>
  );
}

export default function AdminUatPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("ringkasan");
  const [idx, setIdx] = useState(0);
  const [onlyDone, setOnlyDone] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/uat/admin", { cache: "no-store" });
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

  const demoAction = async (action: "seed_demo" | "clear_demo") => {
    const res = await fetch("/api/uat/admin", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) });
    if (!res.ok) setError((await res.json().catch(() => ({}))).error ?? "Gagal.");
    setIdx(0);
    await load();
  };

  const s = data?.summary;
  const people = useMemo(() => (data?.responses ?? []).filter((r) => !onlyDone || r.status === "done"), [data, onlyDone]);
  const done = useMemo(() => (data?.responses ?? []).filter((r) => r.status === "done"), [data]);
  const current = people[Math.min(idx, Math.max(0, people.length - 1))];
  const openPerson = (code: string) => {
    setOnlyDone(false);
    setIdx(Math.max(0, (data?.responses ?? []).findIndex((r) => r.code === code)));
    setTab("individu");
  };
  const taskSuccess = s && s.tasks.length ? s.tasks.reduce((a, t) => a + t.correct, 0) / Math.max(1, s.tasks.reduce((a, t) => a + t.n, 0)) : null;

  return (
    <div className="mx-auto max-w-[1200px] space-y-4 px-1 pb-10 sm:px-4">
      <header className="flex flex-wrap items-end justify-between gap-3 pt-2">
        <div>
          <h1 className="text-[24px] font-bold tracking-tight text-txt">Dashboard UAT</h1>
          <p className="mt-1 text-[13px] text-txtMuted">
            Dihitung langsung dari jawaban yang dikirim responden. Sumber: {data?.source ?? "…"}.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {data?.demo && (
            <>
              <button type="button" onClick={() => demoAction("seed_demo")} className="rounded-lg border border-edge px-3 py-2 text-[12.5px] text-txtDim hover:text-txt">
                Isi data contoh (demo)
              </button>
              <button type="button" onClick={() => demoAction("clear_demo")} className="rounded-lg border border-edge px-3 py-2 text-[12.5px] text-txtDim hover:text-txt">
                Kosongkan demo
              </button>
            </>
          )}
          <button type="button" onClick={() => void load()} className="rounded-lg border border-edge px-3 py-2 text-[12.5px] text-txtDim hover:text-txt">
            Muat ulang
          </button>
          <a href="/api/uat/admin/export" className="rounded-lg bg-txt px-4 py-2 text-[13px] font-semibold text-panel hover:opacity-90">
            Ekspor CSV (anonim)
          </a>
        </div>
      </header>
      {error && <p className="rounded-lg border border-bearish/30 bg-bearish/5 px-3 py-2 text-[12.5px] text-bearish">{error}</p>}
      {!data && !error && <div className={card}>Memuat…</div>}

      {s && (
        <section className={card}>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="metric-label">Persentase kelayakan (P_UAT)</div>
              <div className="mt-1 flex items-baseline gap-3">
                <span className="font-mono text-[40px] font-semibold leading-none text-txt">{s.n ? `${n(s.likert.pct)}%` : "–"}</span>
                {s.n > 0 && <CategoryBadge cat={s.likert.category} />}
              </div>
              <div className="mt-1.5 text-[12px] text-txtMuted">
                {s.n
                  ? `Σ skor ${s.likert.total_score} / Σ maksimum ${s.likert.total_max} (${s.n} responden × ${LIKERT_ITEMS.length} butir × 5) × 100%`
                  : "Belum ada responden yang mengirim jawaban."}
              </div>
            </div>
            <div className="grid grid-cols-3 gap-6 text-right">
              <div>
                <div className="metric-label">Responden</div>
                <div className="font-mono text-[20px] text-txt">
                  {s.n}
                  <span className="text-[13px] text-txtMuted">/{data!.responses.length}</span>
                </div>
                <div className="text-2xs text-txtMuted">selesai / mulai</div>
              </div>
              <div>
                <div className="metric-label">SUS rata-rata</div>
                <div className="font-mono text-[20px] text-txt">{n(s.sus.mean, 1)}</div>
                <div className="text-2xs text-txtMuted">{s.sus.grade ?? "–"}</div>
              </div>
              <div>
                <div className="metric-label">Tugas benar</div>
                <div className="font-mono text-[20px] text-txt">{taskSuccess === null ? "–" : `${n(100 * taskSuccess, 0)}%`}</div>
                <div className="text-2xs text-txtMuted">semua tugas</div>
              </div>
            </div>
          </div>
          {s.n > 0 && <FeasibilityScale pct={s.likert.pct} />}
        </section>
      )}

      {data && (
        <div className="flex flex-wrap gap-1.5 border-b border-edge" role="tablist">
          {(
            [
              ["ringkasan", "Ringkasan"],
              ["pertanyaan", "Per pertanyaan"],
              ["individu", `Individu (${data.responses.length})`],
            ] as [Tab, string][]
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={tab === k}
              onClick={() => setTab(k)}
              className={`-mb-px border-b-2 px-3 py-2 text-[13px] font-medium ${tab === k ? "border-accent text-txt" : "border-transparent text-txtDim hover:text-txt"}`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {/* ------------------------------------------------------------ Ringkasan */}
      {data && s && tab === "ringkasan" && (
        <>
          {s.n > 0 && (
            <div className={card}>
              <h2 className="text-[15px] font-semibold text-txt">Kelayakan per butir (Likert 1–5)</h2>
              <p className="mt-1 text-2xs text-txtMuted">Skor butir = Σ(jumlah jawaban × bobot); maksimum = n × 5. P_UAT = Σ skor / Σ maksimum × 100%.</p>
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
                      <th className="w-[160px] py-1.5 pl-4 text-left font-medium">%</th>
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
                        <td className="py-1.5 pl-4">
                          <div className="flex items-center gap-2">
                            <div className="h-2 flex-1 rounded bg-surface">
                              <div className="h-2 rounded bg-accent/70" style={{ width: `${it.pct}%` }} />
                            </div>
                            <span className="w-12 text-right text-txt">{n(it.pct, 1)}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                    <tr className="bg-surface/70 text-txt">
                      <td className="py-1.5 font-sans font-semibold" colSpan={7}>
                        Total · {s.likert.category}
                      </td>
                      <td className="py-1.5 text-right">
                        {s.likert.total_score}/{s.likert.total_max}
                      </td>
                      <td className="py-1.5 pl-4 text-right font-semibold">{n(s.likert.pct)}%</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className={card}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-[15px] font-semibold text-txt">Responden</h2>
              <span className="text-2xs text-txtMuted">Klik baris untuk melihat jawaban lengkap.</span>
            </div>
            {data.responses.length === 0 ? (
              <p className="mt-2 text-[13px] text-txtMuted">Belum ada akun yang memulai UAT.</p>
            ) : (
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead className="text-txtMuted">
                    <tr className="border-b border-edge">
                      <th className="py-1.5 text-left font-medium">Kode</th>
                      <th className="py-1.5 text-left font-medium">Akun</th>
                      <th className="py-1.5 text-left font-medium">Status</th>
                      <th className="py-1.5 text-left font-medium">Dikirim</th>
                      <th className={th}>Tugas benar</th>
                      <th className={th}>SUS</th>
                      <th className={th}>Kelayakan</th>
                      <th className="py-1.5 pl-3 text-left font-medium">Kategori</th>
                    </tr>
                  </thead>
                  <tbody className="text-txtDim">
                    {data.responses.map((r) => {
                      const sc = respondentScore(r);
                      return (
                        <tr key={r.code} onClick={() => openPerson(r.code)} className="cursor-pointer border-b border-edge/50 hover:bg-surface/60">
                          <td className="py-2 font-mono">{r.code}</td>
                          <td className="py-2">
                            <div className="text-txt">{r.account.name ?? "–"}</div>
                            <div className="text-2xs text-txtMuted">{r.account.email ?? "–"}</div>
                          </td>
                          <td className="py-2">{STATUS[r.status]}</td>
                          <td className="py-2">{when(r.submitted_at)}</td>
                          <td className="py-2 text-right font-mono">
                            {sc.tasks.correct}/{sc.tasks.total}
                          </td>
                          <td className="py-2 text-right font-mono">{n(sc.sus, 1)}</td>
                          <td className="py-2 text-right font-mono text-txt">{sc.likert.pct === null ? "–" : `${n(sc.likert.pct, 1)}%`}</td>
                          <td className="py-2 pl-3">
                            <CategoryBadge cat={sc.likert.category} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <p className="mt-2 text-2xs text-txtMuted">
              Kelayakan per responden = Σ 8 butir / 40 × 100%. P_UAT keseluruhan = rata-rata kelayakan responden yang selesai. Nama dan email hanya tampil
              untuk admin dan tidak ikut ekspor CSV.
            </p>
          </div>

          {s.n > 0 && (
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
                <h2 className="text-[15px] font-semibold text-txt">System Usability Scale</h2>
                <p className="mt-1 text-2xs text-txtMuted">Rumus Brooke (1996), 0–100; acuan rata-rata industri ±68.</p>
                <div className="mt-2 grid grid-cols-3 gap-3 text-[12px]">
                  <div>
                    <div className="text-txtMuted">Rata-rata</div>
                    <div className="font-mono text-[18px] text-txt">{n(s.sus.mean, 1)}</div>
                  </div>
                  <div>
                    <div className="text-txtMuted">Median</div>
                    <div className="font-mono text-[18px] text-txt">{n(s.sus.median, 1)}</div>
                  </div>
                  <div>
                    <div className="text-txtMuted">SD</div>
                    <div className="font-mono text-[18px] text-txt">{n(s.sus.sd, 1)}</div>
                  </div>
                </div>
                <div className="mt-2 text-[12px] text-txtDim">Nilai: {s.sus.grade ?? "–"}</div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ------------------------------------------------------------ Per pertanyaan */}
      {data && s && tab === "pertanyaan" && (
        <>
          {s.n === 0 && <div className={card}>Belum ada jawaban kuesioner yang dikirim.</div>}
          {s.n > 0 && (
            <>
              <h2 className="pt-1 text-[14px] font-semibold text-txt">Kuesioner kelayakan ({s.n} responden)</h2>
              {LIKERT_ITEMS.map((it) => {
                const rec = s.likert.items.find((x) => x.code === it.code)!;
                return (
                  <div key={it.code} className={card}>
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="text-2xs font-semibold text-txtMuted">
                          {it.code} · {it.aspect}
                        </div>
                        <div className="mt-0.5 text-[13px] text-txt">{it.statement}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-[16px] text-txt">{n(rec.pct, 1)}%</div>
                        <div className="text-2xs text-txtMuted">
                          {rec.score}/{rec.max}
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 space-y-1.5">
                      {[...LIKERT_SCALE].reverse().map((sc) => (
                        <DistBar key={sc.value} label={`${sc.value} · ${sc.label}`} count={rec.counts[sc.short as keyof typeof rec.counts]} total={s.n} />
                      ))}
                    </div>
                  </div>
                );
              })}

              <h2 className="pt-2 text-[14px] font-semibold text-txt">System Usability Scale</h2>
              {SUS_ITEMS.map((q, i) => (
                <div key={q} className={card}>
                  <div className="text-2xs font-semibold text-txtMuted">
                    SUS{i + 1} · {i % 2 === 0 ? "positif" : "negatif"}
                  </div>
                  <div className="mt-0.5 text-[13px] text-txt">{q}</div>
                  <div className="mt-3 space-y-1.5">
                    {[...LIKERT_SCALE].reverse().map((sc) => (
                      <DistBar key={sc.value} label={`${sc.value} · ${sc.label}`} count={done.filter((r) => r.sus[i] === sc.value).length} total={s.n} />
                    ))}
                  </div>
                </div>
              ))}

              <h2 className="pt-2 text-[14px] font-semibold text-txt">Tugas terpandu</h2>
              {TASKS.map((t) => {
                const rs = done.map((r) => r.tasks[t.id]).filter((x) => x?.answer);
                const counts = new Map<string, number>();
                rs.forEach((x) => counts.set(x.answer!, (counts.get(x.answer!) ?? 0) + 1));
                const expected = new Set(rs.flatMap((x) => x.expected));
                return (
                  <div key={t.id} className={card}>
                    <div className="text-2xs font-semibold text-txtMuted">
                      {t.id} · {t.title}
                    </div>
                    <div className="mt-0.5 text-[13px] text-txt">{t.question}</div>
                    <div className="mt-3 space-y-1.5">
                      {[...counts.entries()]
                        .sort((a, b) => b[1] - a[1])
                        .map(([v, c]) => (
                          <DistBar key={v} label={`${taskAnswerLabel(t.id, v)}${expected.has(v) ? " ✓" : ""}`} count={c} total={rs.length} highlight={expected.has(v)} />
                        ))}
                    </div>
                    <div className="mt-2 text-2xs text-txtMuted">✓ = cocok dengan jawaban sistem saat tugas dikerjakan.</div>
                  </div>
                );
              })}

              <h2 className="pt-2 text-[14px] font-semibold text-txt">Profil responden</h2>
              <div className="grid gap-4 md:grid-cols-2">
                {PROFILE_FIELDS.map((f) => (
                  <div key={f.key} className={card}>
                    <div className="text-[13px] text-txt">{f.label}</div>
                    <div className="mt-3 space-y-1.5">
                      {f.options.map((o) => (
                        <DistBar key={o} label={o} count={s.profile[f.key]?.[o] ?? 0} total={s.n} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <h2 className="pt-2 text-[14px] font-semibold text-txt">Saran dan masukan</h2>
              <div className={card}>
                {done.filter((r) => r.feedback.trim()).length === 0 ? (
                  <p className="text-[13px] text-txtMuted">Tidak ada saran tertulis.</p>
                ) : (
                  <ul className="space-y-2">
                    {done
                      .filter((r) => r.feedback.trim())
                      .map((r) => (
                        <li key={r.code} className="border-b border-edge/50 pb-2 text-[13px] text-txtDim last:border-0">
                          <span className="mr-2 font-mono text-2xs text-txtMuted">{r.code}</span>
                          {r.feedback}
                        </li>
                      ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </>
      )}

      {/* ------------------------------------------------------------ Individu */}
      {data && tab === "individu" && (
        <>
          {data.responses.length === 0 && <div className={card}>Belum ada akun yang memulai UAT.</div>}
          {current && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={idx <= 0}
                  onClick={() => setIdx((i) => Math.max(0, i - 1))}
                  className="rounded-md border border-edge px-2.5 py-1.5 text-[13px] text-txtDim hover:text-txt disabled:opacity-40"
                  aria-label="Responden sebelumnya"
                >
                  ‹
                </button>
                <select
                  value={current.code}
                  onChange={(e) => setIdx(people.findIndex((r) => r.code === e.target.value))}
                  className="rounded-md border border-edge bg-panel px-2.5 py-1.5 text-[13px] text-txt"
                  aria-label="Pilih responden"
                >
                  {people.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.code} · {r.account.name ?? r.account.email ?? "tanpa nama"}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={idx >= people.length - 1}
                  onClick={() => setIdx((i) => Math.min(people.length - 1, i + 1))}
                  className="rounded-md border border-edge px-2.5 py-1.5 text-[13px] text-txtDim hover:text-txt disabled:opacity-40"
                  aria-label="Responden berikutnya"
                >
                  ›
                </button>
                <span className="text-[12px] text-txtMuted">
                  {Math.min(idx, people.length - 1) + 1} dari {people.length}
                </span>
                <label className="ml-auto flex items-center gap-1.5 text-[12px] text-txtDim">
                  <input
                    type="checkbox"
                    checked={onlyDone}
                    onChange={(e) => {
                      setOnlyDone(e.target.checked);
                      setIdx(0);
                    }}
                  />
                  Hanya yang selesai
                </label>
              </div>
              <Individual r={current} />
            </>
          )}
        </>
      )}
    </div>
  );
}

function Individual({ r }: { r: AdminResponse }) {
  const sc = respondentScore(r);
  return (
    <div className="space-y-4">
      <section className={card}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="font-mono text-2xs text-txtMuted">{r.code}</div>
            <div className="text-[17px] font-semibold text-txt">{r.account.name ?? "Tanpa nama"}</div>
            <div className="text-[12.5px] text-txtDim">{r.account.email ?? "–"}</div>
            <div className="mt-2 text-[12px] text-txtMuted">
              {STATUS[r.status]} · persetujuan {when(r.consent_at)} · dikirim {when(r.submitted_at)}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-6 text-right">
            <div>
              <div className="metric-label">Kelayakan</div>
              <div className="font-mono text-[22px] text-txt">{sc.likert.pct === null ? "–" : `${n(sc.likert.pct, 1)}%`}</div>
              <div className="mt-0.5">
                <CategoryBadge cat={sc.likert.category} />
              </div>
            </div>
            <div>
              <div className="metric-label">SUS</div>
              <div className="font-mono text-[22px] text-txt">{n(sc.sus, 1)}</div>
              <div className="text-2xs text-txtMuted">{sc.sus === null ? "–" : susGrade(sc.sus)}</div>
            </div>
            <div>
              <div className="metric-label">Tugas benar</div>
              <div className="font-mono text-[22px] text-txt">
                {sc.tasks.correct}/{sc.tasks.total}
              </div>
              <div className="text-2xs text-txtMuted">{sc.tasks.answered} dijawab</div>
            </div>
          </div>
        </div>
        {sc.likert.pct !== null && (
          <div className="mt-3 text-2xs text-txtMuted">
            Σ {sc.likert.total} / {sc.likert.max} × 100% = {n(sc.likert.pct, 1)}%
          </div>
        )}
      </section>

      <section className={card}>
        <h3 className="text-[14px] font-semibold text-txt">Profil</h3>
        <dl className="mt-2 grid gap-x-6 gap-y-2 text-[12.5px] sm:grid-cols-2">
          {PROFILE_FIELDS.map((f) => (
            <div key={f.key}>
              <dt className="text-txtMuted">{f.label}</dt>
              <dd className="text-txt">{r.profile[f.key] ?? "–"}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className={card}>
        <h3 className="text-[14px] font-semibold text-txt">Tugas terpandu</h3>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead className="text-txtMuted">
              <tr className="border-b border-edge">
                <th className="py-1.5 text-left font-medium">Tugas</th>
                <th className="py-1.5 text-left font-medium">Jawaban responden</th>
                <th className="py-1.5 text-left font-medium">Jawaban sistem</th>
                <th className={th}>Hasil</th>
                <th className={th}>Waktu</th>
                <th className={th}>SEQ</th>
              </tr>
            </thead>
            <tbody className="text-txtDim">
              {TASKS.map((t) => {
                const x = r.tasks[t.id];
                return (
                  <tr key={t.id} className="border-b border-edge/50 align-top">
                    <td className="py-2 pr-3">
                      <div className="text-txt">
                        {t.id} · {t.title}
                      </div>
                      <div className="text-2xs text-txtMuted">{t.question}</div>
                    </td>
                    <td className="py-2 pr-3 text-txt">{taskAnswerLabel(t.id, x?.answer)}</td>
                    <td className="py-2 pr-3">{x?.expected?.length ? x.expected.map((e) => taskAnswerLabel(t.id, e)).join(" / ") : "–"}</td>
                    <td className="py-2 text-right">
                      {x?.correct == null ? (
                        "–"
                      ) : x.correct ? (
                        <span className="font-semibold text-bullish">Benar</span>
                      ) : (
                        <span className="font-semibold text-bearish">Salah</span>
                      )}
                    </td>
                    <td className="py-2 text-right font-mono">{x?.seconds == null ? "–" : `${x.seconds} s`}</td>
                    <td className="py-2 text-right font-mono">{x?.seq ?? "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className={card}>
        <h3 className="text-[14px] font-semibold text-txt">Kuesioner kelayakan</h3>
        <div className="mt-2 divide-y divide-edge/60">
          {LIKERT_ITEMS.map((it) => (
            <div key={it.code} className="py-3">
              <div className="text-2xs font-semibold text-txtMuted">
                {it.code} · {it.aspect}
              </div>
              <div className="text-[13px] text-txt">{it.statement}</div>
              <ScalePick value={r.likert[it.code]} />
            </div>
          ))}
        </div>
      </section>

      <section className={card}>
        <h3 className="text-[14px] font-semibold text-txt">System Usability Scale</h3>
        <div className="mt-2 divide-y divide-edge/60">
          {SUS_ITEMS.map((q, i) => (
            <div key={q} className="py-3">
              <div className="text-2xs font-semibold text-txtMuted">SUS{i + 1}</div>
              <div className="text-[13px] text-txt">{q}</div>
              <ScalePick value={r.sus[i]} />
            </div>
          ))}
        </div>
      </section>

      <section className={card}>
        <h3 className="text-[14px] font-semibold text-txt">Saran dan masukan</h3>
        <p className="mt-2 whitespace-pre-wrap text-[13px] text-txtDim">{r.feedback?.trim() || "Tidak ada."}</p>
      </section>
    </div>
  );
}

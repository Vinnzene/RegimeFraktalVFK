"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/components/useApi";
import { api } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";
import type { EvidenceLevel, RegimeGuide } from "@/lib/setup-guide";

/**
 * Panduan Setup per regime, terkunci per akun: pengguna meminta akses dan
 * admin menyetujui. Isi panduan hanya dikirim server untuk akun yang disetujui.
 */

type GuideResponse = {
  access: "pending" | "approved" | "rejected" | null;
  requested_at: number | null;
  admin: boolean;
  guide: RegimeGuide[] | null;
  notes: string[] | null;
};

const EVIDENCE: Record<EvidenceLevel, { label: string; className: string }> = {
  didukung: { label: "Didukung hasil uji", className: "border-bullish/40 bg-bullish/10 text-bullish" },
  indikasi: { label: "Indikasi, belum menguntungkan", className: "border-warn/40 bg-warn/10 text-warn" },
  belum_diuji: { label: "Belum dapat diuji", className: "border-edge bg-surface text-txtDim" },
  tidak_disarankan: { label: "Tidak disarankan", className: "border-bearish/40 bg-bearish/10 text-bearish" },
};

function LockIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <rect x="4" y="10" width="16" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function Locked({ data, onRequest }: { data: GuideResponse; onRequest: (note: string) => Promise<void> }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    await onRequest(note);
    setBusy(false);
  };
  return (
    <section className="mx-auto max-w-[640px] rounded-xl border border-edge bg-panel p-6 text-center shadow-panel">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-surface text-txtDim">
        <LockIcon />
      </div>
      <h2 className="mt-3 text-[18px] font-semibold text-txt">Panduan Setup terkunci</h2>
      <p className="mt-1.5 text-[13px] leading-relaxed text-txtDim">
        Panduan jenis setup yang cocok dan yang sebaiknya dihindari untuk tiap kondisi pasar, lengkap dengan status bukti dari uji
        sistem. Akses diberikan setelah disetujui admin.
      </p>

      {data.access === "pending" ? (
        <p className="mt-4 rounded-lg border border-warn/40 bg-warn/10 px-4 py-3 text-[13px] text-txt">
          Permintaan terkirim
          {data.requested_at
            ? ` pada ${new Date(data.requested_at * 1000).toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}`
            : ""}
          . Menunggu persetujuan admin.
        </p>
      ) : (
        <div className="mt-4 text-left">
          {data.access === "rejected" && (
            <p className="mb-3 rounded-lg border border-bearish/30 bg-bearish/5 px-3 py-2 text-[12.5px] text-bearish">
              Permintaan sebelumnya tidak disetujui. Anda dapat mengajukan lagi.
            </p>
          )}
          <label className="block text-[12px] font-medium text-txtDim" htmlFor="alasan">
            Alasan (opsional)
          </label>
          <textarea
            id="alasan"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={300}
            rows={3}
            placeholder="Mis. responden UAT, dosen penguji, trader yang ingin mencoba."
            className="mt-1 w-full rounded-lg border border-edge bg-panel px-3 py-2 text-[13px] text-txt outline-none focus:border-accent"
          />
          <button
            type="button"
            onClick={submit}
            disabled={busy}
            className="mt-3 w-full rounded-lg bg-txt px-5 py-2.5 text-[14px] font-semibold text-panel transition hover:opacity-90 disabled:opacity-40"
          >
            {busy ? "Mengirim…" : "Minta akses"}
          </button>
        </div>
      )}
    </section>
  );
}

function GuideCard({ g, activeOn }: { g: RegimeGuide; activeOn: string[] }) {
  const meta = REGIME_META[g.regime as Regime];
  const ev = EVIDENCE[g.evidence.level];
  const active = activeOn.length > 0;
  return (
    <article
      className={`flex flex-col rounded-xl border bg-panel p-5 shadow-panel ${active ? "" : "border-edge"}`}
      style={active ? { borderColor: meta.color, boxShadow: `0 0 0 1px ${meta.color}` } : undefined}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: meta.color }} />
        <h3 className="text-[16px] font-semibold" style={{ color: meta.color }}>
          {REGIME_PLAIN[g.regime as Regime].name}
        </h3>
        {activeOn.map((tf) => (
          <span key={tf} className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-panel" style={{ backgroundColor: meta.color }}>
            Kondisi {tf} saat ini
          </span>
        ))}
      </div>
      <p className="mt-2 text-[15px] font-semibold text-txt">{g.headline}</p>
      <p className="mt-1 text-[13px] leading-relaxed text-txtDim">{g.logic}</p>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-bullish">Cocok</div>
          <ul className="mt-1.5 space-y-2">
            {g.suitable.map((s) => (
              <li key={s.name} className="text-[13px]">
                <div className="font-medium text-txt">{s.name}</div>
                <div className="text-[12.5px] leading-snug text-txtDim">{s.detail}</div>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-bearish">Hindari</div>
          <ul className="mt-1.5 space-y-2">
            {g.avoid.map((s) => (
              <li key={s.name} className="text-[13px]">
                <div className="font-medium text-txt">{s.name}</div>
                <div className="text-[12.5px] leading-snug text-txtDim">{s.detail}</div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-4 space-y-1 text-[12.5px] text-txtDim">
        {g.risk.map((r) => (
          <p key={r}>• {r}</p>
        ))}
        {g.tools.map((t) => (
          <p key={t}>
            • {t}{" "}
            <Link href="/analisa-teknikal" className="font-medium text-accent hover:underline">
              Buka Analisa Teknikal →
            </Link>
          </p>
        ))}
      </div>

      <div className="mt-auto pt-4">
        <div className="rounded-lg bg-surface/70 px-3 py-2.5">
          <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-semibold ${ev.className}`}>{ev.label}</span>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-txtDim">{g.evidence.text}</p>
        </div>
      </div>
    </article>
  );
}

export default function SetupPage() {
  const [data, setData] = useState<GuideResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ai1h = useApi(() => api.aiRegime("1h"), []);
  const ai4h = useApi(() => api.aiRegime("4h"), []);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/setup-guide", { cache: "no-store" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setData(body);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const request = async (note: string) => {
    const res = await fetch("/api/setup-guide", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note }) });
    if (!res.ok) setError("Permintaan gagal dikirim.");
    await load();
  };

  // Kondisi yang ditampilkan: label ragu bila keyakinan di bawah ambang, sama seperti beranda.
  const current = (d: typeof ai1h.data) =>
    d?.current_regime ? ((d.current_low_confidence ? "uncertain_lowconf" : d.current_regime) as string) : null;
  const now = { "1H": current(ai1h.data), "4H": current(ai4h.data) };

  return (
    <div className="mx-auto max-w-[1300px] space-y-4 px-1 pb-8 sm:px-4">
      <header className="pt-2">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-[26px] font-bold tracking-tight text-txt">Panduan Setup</h1>
          {data?.guide && <span className="rounded-md border border-bullish/40 bg-bullish/10 px-2 py-0.5 text-[12px] font-medium text-bullish">Akses diberikan</span>}
          {data?.admin && (
            <Link href="/admin/akses" className="rounded-md border border-edge px-2 py-0.5 text-[12px] font-medium text-txtDim hover:text-txt">
              Kelola akses →
            </Link>
          )}
        </div>
        <p className="mt-1 text-[13px] text-txtMuted">Jenis setup yang sesuai dengan sifat gerakan tiap kondisi pasar. Edukatif, bukan sinyal beli/jual.</p>
      </header>

      {error && <div className="rounded-lg border border-bearish/30 bg-bearish/5 px-4 py-2.5 text-[13px] text-bearish">{error}</div>}
      {!data && !error && <div className="h-40 animate-pulse rounded-xl bg-surface" />}
      {data && !data.guide && <Locked data={data} onRequest={request} />}

      {data?.guide && (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            {data.guide.map((g) => (
              <GuideCard key={g.regime} g={g} activeOn={Object.entries(now).filter(([, r]) => r === g.regime).map(([tf]) => tf)} />
            ))}
          </div>
          <section className="rounded-xl border border-edge bg-panel p-4 text-[12.5px] leading-relaxed text-txtDim shadow-panel">
            {data.notes?.map((n) => (
              <p key={n}>• {n}</p>
            ))}
          </section>
        </>
      )}
    </div>
  );
}

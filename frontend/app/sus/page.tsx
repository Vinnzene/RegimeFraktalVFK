"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AGE_MAX,
  AGE_MIN,
  CONSENT_TEXT,
  EXPERIENCE_MAX_MONTHS,
  EXPLORE_GROUPS,
  EXPLORE_PAGES,
  ROLE_OPTIONS,
  SUS_ITEMS,
  SUS_SCALE,
  type PublicSus,
} from "@/lib/sus";

/** Kuesioner System Usability Scale. */

type State = { demo: boolean; admin: boolean; response: PublicSus | null };

async function call(body: Record<string, unknown>) {
  const res = await fetch("/api/sus", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
  return data.response as PublicSus | null;
}

const card = "rounded-xl border border-edge bg-panel p-5 shadow-panel";
const btn = "rounded-lg bg-txt px-5 py-2 text-[14px] font-semibold text-panel transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40";
const input = "rounded-lg border border-edge bg-panel px-3 py-2 text-[13px] text-txt outline-none focus:border-accent";
const STEPS = ["Persetujuan & profil", "Mencoba aplikasi", "Kuesioner SUS", "Selesai"];

export default function SusPage() {
  const [state, setState] = useState<State | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await fetch("/api/sus", { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setError(data.error ?? `HTTP ${res.status}`);
    setState(data);
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const setResponse = (r: PublicSus | null) => setState((s) => (s ? { ...s, response: r } : s));
  const r = state?.response ?? null;
  const step = !r ? 0 : r.status === "explore" ? 1 : r.status === "questionnaire" ? 2 : 3;

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-1 pb-10 sm:px-4">
      <header className="pt-2">
        <h1 className="text-[24px] font-bold tracking-tight text-txt">Kuesioner SUS RFraktal</h1>
        <p className="mt-1 text-[13px] text-txtMuted">
          Persetujuan → mencoba aplikasi → 10 pernyataan System Usability Scale. Perkiraan waktu 20–30 menit.
        </p>
        <ol className="mt-3 flex flex-wrap gap-2 text-[12px]">
          {STEPS.map((label, i) => (
            <li
              key={label}
              className={`rounded-full border px-3 py-1 ${i === step ? "border-accent bg-accent/10 text-txt" : i < step ? "border-edge text-txtDim" : "border-edge text-txtMuted"}`}
            >
              {i + 1}. {label}
            </li>
          ))}
        </ol>
      </header>

      {error && <p className="rounded-lg border border-bearish/30 bg-bearish/5 px-3 py-2 text-[12.5px] text-bearish">{error}</p>}
      {!state && !error && <div className={card}>Memuat…</div>}
      {state && state.demo && (
        <p className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-[12px] text-txtDim">
          Mode demo lokal: jawaban hanya disimpan di memori server (kode D..), tidak ikut data responden sungguhan.
        </p>
      )}
      {state && step === 0 && <Consent onDone={setResponse} onError={setError} />}
      {r && step === 1 && <Explore response={r} onUpdate={setResponse} onError={setError} />}
      {r && step === 2 && <Questionnaire onDone={setResponse} onError={setError} />}
      {r && step === 3 && (
        <div className={card}>
          <h2 className="text-[17px] font-semibold text-txt">Terima kasih!</h2>
          <p className="mt-2 text-[13px] leading-relaxed text-txtDim">
            Jawaban Anda sudah tersimpan dengan kode responden <b className="font-mono text-txt">{r.code}</b> dan tidak dapat diubah lagi.
          </p>
          <div className="mt-4 flex gap-2">
            <Link href="/" className={btn}>
              Kembali ke Ringkasan
            </Link>
            {state?.demo && (
              <button
                type="button"
                className="rounded-lg border border-edge px-4 py-2 text-[13px] text-txtDim hover:text-txt"
                onClick={async () => setResponse(await call({ action: "reset" }))}
              >
                Ulangi (demo)
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Consent({ onDone, onError }: { onDone: (r: PublicSus | null) => void; onError: (e: string | null) => void }) {
  const [agree, setAgree] = useState(false);
  const [role, setRole] = useState("");
  const [experience, setExperience] = useState("");
  const [age, setAge] = useState("");
  const [busy, setBusy] = useState(false);
  const complete = agree && role && experience.trim() !== "";

  return (
    <form
      className={`${card} space-y-4`}
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        onError(null);
        try {
          onDone(
            await call({
              action: "start",
              consent: agree,
              profile: { role, experience_months: experience.trim(), age: age.trim() === "" ? null : age.trim() },
            }),
          );
        } catch (err: any) {
          onError(err.message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <div>
        <h2 className="text-[16px] font-semibold text-txt">Persetujuan</h2>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-[13px] leading-relaxed text-txtDim">
          {CONSENT_TEXT.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
        <label className="mt-3 flex items-start gap-2 text-[13px] text-txt">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5" />
          Saya sudah membaca keterangan di atas dan bersedia mengisi kuesioner.
        </label>
      </div>

      <div>
        <h2 className="text-[16px] font-semibold text-txt">Profil singkat</h2>
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-[12px] font-medium text-txtDim">Peran utama</span>
            <select value={role} onChange={(e) => setRole(e.target.value)} className={`${input} w-full`}>
              <option value="" disabled>
                Pilih…
              </option>
              {ROLE_OPTIONS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-[12px] font-medium text-txtDim">Pengalaman trading/analisis kripto (bulan)</span>
            <input
              inputMode="numeric"
              value={experience}
              onChange={(e) => setExperience(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder="mis. 18"
              maxLength={3}
              className={`${input} w-full font-mono`}
            />
            <span className="mt-1 block text-2xs text-txtMuted">0–{EXPERIENCE_MAX_MONTHS}; 1 tahun = 12 bulan</span>
          </label>
          <label className="block">
            <span className="mb-1 block text-[12px] font-medium text-txtDim">Usia (opsional)</span>
            <input
              inputMode="numeric"
              value={age}
              onChange={(e) => setAge(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder="boleh dikosongkan"
              maxLength={3}
              className={`${input} w-full font-mono`}
            />
            <span className="mt-1 block text-2xs text-txtMuted">
              {AGE_MIN}–{AGE_MAX} tahun
            </span>
          </label>
        </div>
      </div>
      <button type="submit" disabled={!complete || busy} className={btn}>
        {busy ? "Memulai…" : "Mulai"}
      </button>
    </form>
  );
}

function Explore({ response, onUpdate, onError }: { response: PublicSus; onUpdate: (r: PublicSus | null) => void; onError: (e: string | null) => void }) {
  const [busy, setBusy] = useState(false);
  const opened = (key: string) => Boolean(response.visited?.[key]);
  const allOpened = EXPLORE_PAGES.every((p) => opened(p.key));

  const open = (key: string) => {
    // Tautan dibuka di tab baru oleh browser; kunjungan dicatat di latar belakang.
    call({ action: "visit", page: key }).then(onUpdate).catch((e) => onError(e.message));
  };

  return (
    <div className={`${card} space-y-4`}>
      <div className="text-[12px] text-txtMuted">
        Kode responden <span className="font-mono">{response.code}</span>
      </div>
      <div>
        <h2 className="text-[17px] font-semibold text-txt">Silakan mencoba aplikasi</h2>
        <p className="mt-2 text-[13.5px] leading-relaxed text-txtDim">
          Buka semua halaman di bawah (masing-masing di tab baru), coba fiturnya, lalu kembali ke tab ini. Halaman dikelompokkan
          sesuai menu Pasar, Identifikasi, dan Strategi. Tidak ada tugas yang dinilai; yang penting kesan Anda saat memakai aplikasi.
        </p>
      </div>
      {EXPLORE_GROUPS.map((g) => (
      <div key={g}>
      <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-txtMuted">Menu {g}</h3>
      <ul className="space-y-2">
        {EXPLORE_PAGES.filter((p) => p.group === g).map((p) => (
          <li key={p.key} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-edge px-4 py-3">
            <div>
              <div className="flex items-center gap-2 text-[13.5px] font-medium text-txt">
                <span
                  aria-hidden
                  className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] ${opened(p.key) ? "bg-bullish/15 text-bullish" : "border border-edge text-txtMuted"}`}
                >
                  {opened(p.key) ? "✓" : ""}
                </span>
                {p.label}
                {opened(p.key) && <span className="text-2xs font-normal text-bullish">sudah dibuka</span>}
              </div>
              <div className="mt-0.5 pl-7 text-[12px] text-txtMuted">{p.hint}</div>
            </div>
            <a
              href={p.href}
              target="_blank"
              rel="noreferrer"
              onClick={() => open(p.key)}
              className="rounded-lg border border-accent/50 bg-accent/10 px-3 py-1.5 text-[12.5px] font-medium text-txt hover:bg-accent/20"
            >
              Buka di tab baru ↗
            </a>
          </li>
        ))}
      </ul>
      </div>
      ))}
      <div className="flex flex-wrap items-center gap-3 border-t border-edge pt-4">
        <button
          type="button"
          disabled={!allOpened || busy}
          className={btn}
          onClick={async () => {
            setBusy(true);
            onError(null);
            try {
              onUpdate(await call({ action: "explore_done" }));
            } catch (err: any) {
              onError(err.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          Saya sudah mencoba, lanjut ke kuesioner
        </button>
        {!allOpened && (
          <span className="text-[12px] text-txtMuted">
            {EXPLORE_PAGES.filter((p) => !opened(p.key)).length} halaman belum dibuka
          </span>
        )}
      </div>
    </div>
  );
}

function Questionnaire({ onDone, onError }: { onDone: (r: PublicSus | null) => void; onError: (e: string | null) => void }) {
  const [answers, setAnswers] = useState<(number | undefined)[]>(Array(10).fill(undefined));
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const missing = answers.filter((v) => v === undefined).length;

  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!window.confirm("Kirim jawaban? Setelah dikirim, jawaban tidak dapat diubah.")) return;
        setBusy(true);
        onError(null);
        try {
          onDone(await call({ action: "submit", answers, feedback }));
        } catch (err: any) {
          onError(err.message);
          setBusy(false);
        }
      }}
    >
      <div className={card}>
        <h2 className="text-[16px] font-semibold text-txt">System Usability Scale (SUS)</h2>
        <p className="mt-1 text-[12px] text-txtMuted">
          Pilih 1 (sangat tidak setuju) sampai 5 (sangat setuju) sesuai kesan Anda. Jawab sesuai kesan pertama; jangan terlalu lama
          memikirkan tiap butir.
        </p>
        <div className="mt-3 space-y-4">
          {SUS_ITEMS.map((text, i) => (
            <fieldset key={i}>
              <legend className="text-[13px] text-txt">
                <span className="font-mono text-txtMuted">{i + 1}.</span> {text}
              </legend>
              <div className="mt-2 grid grid-cols-5 gap-1.5">
                {SUS_SCALE.map((s) => (
                  <label
                    key={s.value}
                    className={`cursor-pointer rounded-md border px-1 py-1.5 text-center text-[11.5px] ${answers[i] === s.value ? "border-accent bg-accent/10 text-txt" : "border-edge text-txtDim hover:border-edgeBright"}`}
                  >
                    <input
                      type="radio"
                      name={`sus${i + 1}`}
                      value={s.value}
                      checked={answers[i] === s.value}
                      onChange={() => setAnswers((a) => a.map((x, j) => (j === i ? s.value : x)))}
                      className="sr-only"
                    />
                    <div className="font-semibold">{s.value}</div>
                    <div className="hidden text-2xs sm:block">{s.label}</div>
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        </div>
      </div>

      <div className={card}>
        <h2 className="text-[16px] font-semibold text-txt">Saran (opsional)</h2>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          rows={4}
          maxLength={2000}
          placeholder="Apa yang paling membingungkan atau perlu diperbaiki?"
          className={`${input} mt-2 w-full`}
        />
        <div className="mt-3 flex items-center gap-3">
          <button type="submit" disabled={missing > 0 || busy} className={btn}>
            {busy ? "Mengirim…" : "Kirim jawaban"}
          </button>
          {missing > 0 && <span className="text-[12px] text-txtMuted">{missing} butir belum dijawab</span>}
        </div>
      </div>
    </form>
  );
}

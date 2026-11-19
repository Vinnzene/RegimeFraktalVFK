"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CONSENT_TEXT,
  LIKERT_ITEMS,
  LIKERT_SCALE,
  PROFILE_FIELDS,
  SEQ_SCALE,
  SUS_ITEMS,
  TASKS,
  type UatTask,
} from "@/lib/uat";

type ClientTask = { started_at: number | null; answered_at: number | null; answer: string | null; seq: number | null };
type ClientResponse = {
  code: string;
  status: "tasks" | "questionnaire" | "done";
  tasks: Record<string, ClientTask>;
  submitted_at: number | null;
  demo: boolean;
};
type State = { open: boolean; invite_required: boolean; demo: boolean; admin: boolean; response: ClientResponse | null };

async function call(body: Record<string, unknown>) {
  const res = await fetch("/api/uat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
  return data.response as ClientResponse | null;
}

const card = "rounded-xl border border-edge bg-panel p-5 shadow-panel";
const btn = "rounded-lg bg-txt px-5 py-2 text-[14px] font-semibold text-panel transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40";

/**
 * Uji penerimaan pengguna (UAT) di dalam aplikasi: persetujuan dan profil, lima tugas
 * terpandu (jawaban dicek otomatis, waktu dicatat), lalu kuesioner kelayakan dan SUS.
 */
export default function UatPage() {
  const [state, setState] = useState<State | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await fetch("/api/uat", { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setError(data.error ?? `HTTP ${res.status}`);
    setState(data);
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const setResponse = (r: ClientResponse | null) => setState((s) => (s ? { ...s, response: r } : s));
  const r = state?.response ?? null;
  const step = !r ? 0 : r.status === "tasks" ? 1 : r.status === "questionnaire" ? 2 : 3;

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-1 pb-10 sm:px-4">
      <header className="pt-2">
        <h1 className="text-[24px] font-bold tracking-tight text-txt">Uji Pengguna (UAT) RFraktal</h1>
        <p className="mt-1 text-[13px] text-txtMuted">
          Persetujuan → 5 tugas singkat di aplikasi → kuesioner. Perkiraan waktu 10–15 menit.
        </p>
        <ol className="mt-3 flex flex-wrap gap-2 text-[12px]">
          {["Persetujuan & profil", "Tugas", "Kuesioner", "Selesai"].map((label, i) => (
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
      {state && !state.open && (
        <div className={card}>UAT belum dibuka. Hubungi peneliti untuk mendapatkan tautan atau kode undangan.</div>
      )}
      {state && state.open && step === 0 && <Consent inviteRequired={state.invite_required} onDone={setResponse} onError={setError} />}
      {r && step === 1 && <Tasks response={r} onUpdate={setResponse} onError={setError} />}
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

function Consent({ inviteRequired, onDone, onError }: { inviteRequired: boolean; onDone: (r: ClientResponse | null) => void; onError: (e: string | null) => void }) {
  const [invite, setInvite] = useState("");
  const [agree, setAgree] = useState(false);
  const [profile, setProfile] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const complete = agree && PROFILE_FIELDS.every((f) => profile[f.key]) && (!inviteRequired || invite.trim());

  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("kode");
    if (code) setInvite(code);
  }, []);

  return (
    <form
      className={`${card} space-y-4`}
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        onError(null);
        try {
          onDone(await call({ action: "start", invite, consent: agree, profile }));
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
          Saya sudah membaca keterangan di atas dan bersedia mengikuti pengujian.
        </label>
      </div>

      {inviteRequired && (
        <label className="block">
          <span className="mb-1 block text-[12px] font-medium text-txtDim">Kode undangan</span>
          <input
            value={invite}
            onChange={(e) => setInvite(e.target.value)}
            className="w-48 rounded-lg border border-edge bg-panel px-3 py-2 font-mono text-[14px] text-txt outline-none focus:border-accent"
          />
        </label>
      )}

      <div>
        <h2 className="text-[16px] font-semibold text-txt">Profil singkat</h2>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          {PROFILE_FIELDS.map((f) => (
            <label key={f.key} className="block">
              <span className="mb-1 block text-[12px] font-medium text-txtDim">{f.label}</span>
              <select
                value={profile[f.key] ?? ""}
                onChange={(e) => setProfile((p) => ({ ...p, [f.key]: e.target.value }))}
                className="w-full rounded-lg border border-edge bg-panel px-3 py-2 text-[13px] text-txt outline-none focus:border-accent"
              >
                <option value="" disabled>
                  Pilih…
                </option>
                {f.options.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      </div>
      <button type="submit" disabled={!complete || busy} className={btn}>
        {busy ? "Memulai…" : "Mulai pengujian"}
      </button>
    </form>
  );
}

function Tasks({ response, onUpdate, onError }: { response: ClientResponse; onUpdate: (r: ClientResponse | null) => void; onError: (e: string | null) => void }) {
  const idx = TASKS.findIndex((t) => response.tasks[t.id]?.answered_at === null);
  const task: UatTask | undefined = TASKS[idx];
  const [answer, setAnswer] = useState("");
  const [seq, setSeq] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setAnswer("");
    setSeq(null);
    if (task && response.tasks[task.id]?.started_at === null) {
      call({ action: "task_start", task: task.id }).then(onUpdate).catch((e) => onError(e.message));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task?.id]);

  if (!task) return null;
  return (
    <div className={`${card} space-y-4`}>
      <div className="text-[12px] text-txtMuted">
        Tugas {idx + 1} dari {TASKS.length} · kode responden <span className="font-mono">{response.code}</span>
      </div>
      <div>
        <h2 className="text-[17px] font-semibold text-txt">{task.title}</h2>
        <p className="mt-2 text-[13.5px] leading-relaxed text-txtDim">{task.instruction}</p>
        <a
          href={task.href}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-block rounded-lg border border-accent/50 bg-accent/10 px-4 py-2 text-[13px] font-medium text-txt hover:bg-accent/20"
        >
          Buka halaman di tab baru ↗
        </a>
        <p className="mt-2 text-2xs text-txtMuted">Kerjakan di tab baru, lalu kembali ke tab ini untuk menjawab.</p>
      </div>

      <form
        className="space-y-4 border-t border-edge pt-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          onError(null);
          try {
            onUpdate(await call({ action: "task_answer", task: task.id, answer, seq }));
          } catch (err: any) {
            onError(err.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <fieldset>
          <legend className="text-[13.5px] font-medium text-txt">{task.question}</legend>
          {task.kind === "choice" ? (
            <div className="mt-2 space-y-1.5">
              {task.choices!.map((c) => (
                <label key={c.value} className="flex items-center gap-2 text-[13px] text-txtDim">
                  <input type="radio" name="answer" value={c.value} checked={answer === c.value} onChange={() => setAnswer(c.value)} />
                  {c.label}
                </label>
              ))}
            </div>
          ) : (
            <div className="mt-2 flex items-center gap-2">
              <input
                inputMode="decimal"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                aria-label={task.question}
                className="w-32 rounded-lg border border-edge bg-panel px-3 py-2 font-mono text-[14px] text-txt outline-none focus:border-accent"
              />
              {task.unit && <span className="text-[13px] text-txtDim">{task.unit}</span>}
            </div>
          )}
        </fieldset>
        <fieldset>
          <legend className="text-[13.5px] font-medium text-txt">Seberapa mudah tugas ini?</legend>
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[12px] text-txtMuted">
            <span>Sangat sulit</span>
            {SEQ_SCALE.map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={seq === v}
                onClick={() => setSeq(v)}
                className={`h-8 w-8 rounded-md border text-[13px] ${seq === v ? "border-accent bg-accent text-white" : "border-edge text-txtDim hover:border-edgeBright"}`}
              >
                {v}
              </button>
            ))}
            <span>Sangat mudah</span>
          </div>
        </fieldset>
        <button type="submit" disabled={!answer.trim() || seq === null || busy} className={btn}>
          {busy ? "Menyimpan…" : idx === TASKS.length - 1 ? "Simpan & lanjut ke kuesioner" : "Simpan & lanjut"}
        </button>
      </form>
    </div>
  );
}

function ScaleRow({ name, value, onChange }: { name: string; value: number | undefined; onChange: (v: number) => void }) {
  return (
    <div className="mt-2 grid grid-cols-5 gap-1.5">
      {LIKERT_SCALE.map((s) => (
        <label
          key={s.value}
          className={`cursor-pointer rounded-md border px-1 py-1.5 text-center text-[11.5px] ${value === s.value ? "border-accent bg-accent/10 text-txt" : "border-edge text-txtDim hover:border-edgeBright"}`}
        >
          <input type="radio" name={name} value={s.value} checked={value === s.value} onChange={() => onChange(s.value)} className="sr-only" />
          <div className="font-semibold">{s.short}</div>
          <div className="hidden text-2xs sm:block">{s.label}</div>
        </label>
      ))}
    </div>
  );
}

function Questionnaire({ onDone, onError }: { onDone: (r: ClientResponse | null) => void; onError: (e: string | null) => void }) {
  const [likert, setLikert] = useState<Record<string, number>>({});
  const [sus, setSus] = useState<(number | undefined)[]>(Array(10).fill(undefined));
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const missing = useMemo(
    () => LIKERT_ITEMS.filter((i) => !likert[i.code]).length + sus.filter((v) => v === undefined).length,
    [likert, sus],
  );

  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!window.confirm("Kirim jawaban? Setelah dikirim, jawaban tidak dapat diubah.")) return;
        setBusy(true);
        onError(null);
        try {
          onDone(await call({ action: "questionnaire", likert, sus, feedback }));
        } catch (err: any) {
          onError(err.message);
          setBusy(false);
        }
      }}
    >
      <div className={card}>
        <h2 className="text-[16px] font-semibold text-txt">Bagian A · Kelayakan aplikasi</h2>
        <p className="mt-1 text-[12px] text-txtMuted">STS = sangat tidak setuju, TS = tidak setuju, CS = cukup setuju, S = setuju, SS = sangat setuju.</p>
        <div className="mt-3 space-y-4">
          {LIKERT_ITEMS.map((it) => (
            <div key={it.code}>
              <div className="text-[13px] text-txt">
                <span className="font-mono text-txtMuted">{it.code}</span> {it.statement}
              </div>
              <ScaleRow name={it.code} value={likert[it.code]} onChange={(v) => setLikert((s) => ({ ...s, [it.code]: v }))} />
            </div>
          ))}
        </div>
      </div>

      <div className={card}>
        <h2 className="text-[16px] font-semibold text-txt">Bagian B · System Usability Scale (SUS)</h2>
        <p className="mt-1 text-[12px] text-txtMuted">Jawab sesuai kesan pertama Anda; jangan terlalu lama memikirkan tiap butir.</p>
        <div className="mt-3 space-y-4">
          {SUS_ITEMS.map((text, i) => (
            <div key={i}>
              <div className="text-[13px] text-txt">
                <span className="font-mono text-txtMuted">SUS{i + 1}</span> {text}
              </div>
              <ScaleRow name={`sus${i}`} value={sus[i]} onChange={(v) => setSus((s) => s.map((x, j) => (j === i ? v : x)))} />
            </div>
          ))}
        </div>
      </div>

      <div className={card}>
        <h2 className="text-[16px] font-semibold text-txt">Bagian C · Saran (opsional)</h2>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          rows={4}
          maxLength={2000}
          placeholder="Apa yang paling membingungkan atau perlu diperbaiki?"
          className="mt-2 w-full rounded-lg border border-edge bg-panel px-3 py-2 text-[13px] text-txt outline-none focus:border-accent"
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

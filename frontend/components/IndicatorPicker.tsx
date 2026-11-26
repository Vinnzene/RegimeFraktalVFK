"use client";

import { useEffect, useState } from "react";
import { INDICATORS, type IndicatorId } from "@/lib/indicators";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

/** Tombol dan jendela pemilih indikator per kondisi pasar. */

function Preview({ id }: { id: IndicatorId }) {
  // Sketsa kecil, bukan data.
  if (id === "trend")
    return (
      <svg viewBox="0 0 160 70" className="h-full w-full" aria-hidden>
        <path d="M5 60 L25 52 L40 55 L60 40 L75 44 L95 28 L115 30 L135 15 L155 10" fill="none" stroke="rgb(var(--c-txt-muted))" strokeWidth="1.5" />
        <path d="M5 58 C40 50 70 42 100 30 S140 16 155 13" fill="none" stroke="#f0b90b" strokeWidth="2" />
        <path d="M5 62 C50 58 90 48 120 38 S150 26 155 24" fill="none" stroke="#a78bfa" strokeWidth="2" />
      </svg>
    );
  if (id === "meanrev")
    return (
      <svg viewBox="0 0 160 70" className="h-full w-full" aria-hidden>
        <path d="M5 18 C40 14 70 22 100 16 S140 20 155 17" fill="none" stroke="#38bdf8" strokeOpacity="0.6" strokeWidth="1.5" />
        <path d="M5 35 C40 33 70 37 100 34 S140 36 155 35" fill="none" stroke="#38bdf8" strokeDasharray="4 3" strokeWidth="1.5" />
        <path d="M5 52 C40 56 70 48 100 54 S140 50 155 53" fill="none" stroke="#38bdf8" strokeOpacity="0.6" strokeWidth="1.5" />
        <path d="M5 36 L20 22 L32 44 L45 15 L58 50 L72 30 L85 56 L100 33 L115 20 L130 48 L145 36 L155 34" fill="none" stroke="rgb(var(--c-txt-muted))" strokeWidth="1.5" />
      </svg>
    );
  return (
    <svg viewBox="0 0 160 70" className="h-full w-full" aria-hidden>
      {[8, 16, 24, 30, 46, 52, 58, 64].map((y, i) => (
        <rect key={y} x="0" y={y - 3} width="160" height="5" fill={i < 4 ? "#f6465d" : "#2ebd85"} opacity={[0.15, 0.45, 0.25, 0.7, 0.6, 0.2, 0.4, 0.15][i]} />
      ))}
      <path d="M5 40 L20 34 L35 42 L50 36 L65 41 L80 37 L95 42 L110 35 L125 40 L140 37 L155 39" fill="none" stroke="rgb(var(--c-txt))" strokeWidth="1.5" />
    </svg>
  );
}

export default function IndicatorPicker({
  active,
  onToggle,
  currentRegime,
  unavailable = {},
}: {
  active: IndicatorId[];
  onToggle: (id: IndicatorId) => void;
  currentRegime?: string | null;
  unavailable?: Partial<Record<IndicatorId, React.ReactNode>>;
}) {
  const [open, setOpen] = useState(false);
  const recommended = INDICATORS.find((d) => d.regime === currentRegime)?.id;
  const [sel, setSel] = useState<IndicatorId>(recommended ?? "trend");

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const def = INDICATORS.find((d) => d.id === sel)!;
  const on = active.includes(sel);
  const blocked = unavailable[sel];
  const col = (r: string) => REGIME_META[r as Regime]?.color ?? "#808896";

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setSel(recommended ?? sel);
          setOpen(true);
        }}
        className="flex items-center gap-1.5 rounded border border-edge px-2.5 py-1 text-[11.5px] text-txtDim transition hover:border-accent/60 hover:text-accent"
        aria-haspopup="dialog"
      >
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <path d="M2 15 L7 9 L11 12 L18 4" />
        </svg>
        Indikator
        {active.length > 0 && <span className="rounded bg-accent/20 px-1 font-mono text-2xs text-accent">{active.length}</span>}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3" onClick={() => setOpen(false)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Indikator"
            className="flex max-h-[90vh] w-full max-w-[820px] flex-col overflow-hidden rounded-xl border border-edge bg-panel shadow-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-edge px-5 py-3">
              <h2 className="text-[15px] font-semibold text-txt">Indikator per kondisi pasar</h2>
              <button type="button" onClick={() => setOpen(false)} className="rounded px-2 py-1 text-txtMuted hover:bg-surface hover:text-txt" aria-label="Tutup">
                ✕
              </button>
            </div>
            <div className="grid min-h-0 flex-1 overflow-y-auto md:grid-cols-[1fr_1.1fr]">
              <ul className="space-y-2 border-b border-edge p-4 md:border-b-0 md:border-r">
                {INDICATORS.map((d) => {
                  const isOn = active.includes(d.id);
                  return (
                    <li key={d.id}>
                      <button
                        type="button"
                        onClick={() => setSel(d.id)}
                        aria-pressed={sel === d.id}
                        className={`w-full rounded-lg border p-3 text-left transition ${sel === d.id ? "border-accent/60 bg-accent/5" : "border-edge hover:border-edgeBright"}`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-2xs font-semibold uppercase tracking-wider" style={{ color: col(d.regime) }}>
                            {REGIME_PLAIN[d.regime].name} · {REGIME_META[d.regime].label}
                          </span>
                          {isOn && <span className="rounded bg-accent/20 px-1.5 text-2xs text-accent">aktif</span>}
                        </div>
                        <div className="mt-1 text-[14px] font-semibold text-txt">{d.family}</div>
                        <div className="text-[12px] text-txtDim">{d.name}</div>
                        {recommended === d.id && <div className="mt-1 text-2xs text-accent">Cocok untuk kondisi sekarang</div>}
                      </button>
                    </li>
                  );
                })}
              </ul>
              <div className="flex flex-col p-5">
                <div className="h-[110px] rounded-lg border border-edge bg-surface/40 p-2">
                  <Preview id={def.id} />
                </div>
                <div className="mt-3 text-2xs uppercase tracking-wider" style={{ color: col(def.regime) }}>
                  {def.family} · untuk kondisi {REGIME_PLAIN[def.regime].name}
                </div>
                <h3 className="mt-0.5 text-[18px] font-bold text-txt">{def.name}</h3>
                <p className="mt-1 text-[12.5px] text-txtDim">{def.short}</p>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-[12.5px] text-txtDim">
                  {def.how.map((h) => (
                    <li key={h}>{h}</li>
                  ))}
                </ul>
                <p className="mt-2 text-2xs text-txtMuted">{def.source} Bukan saran investasi.</p>
                <div className="mt-auto pt-4">
                  {blocked ? (
                    <div className="rounded-lg border border-edge bg-surface/40 px-3 py-2 text-[12px] text-txtDim">{blocked}</div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => onToggle(def.id)}
                      className={`w-full rounded-lg px-4 py-2 text-[13px] font-semibold transition ${on ? "border border-edge text-txtDim hover:text-txt" : "bg-txt text-panel hover:opacity-90"}`}
                    >
                      {on ? "Hapus dari chart" : "Tambahkan ke chart"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

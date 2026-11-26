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
  if (id === "vofs")
    return (
      <svg viewBox="0 0 160 70" className="h-full w-full" aria-hidden>
        <path d="M20 22 H110" stroke="#2ebd85" strokeOpacity="0.55" />
        <path d="M20 22 H70" stroke="#2ebd85" strokeWidth="3" />
        <rect x="52" y="8" width="26" height="10" rx="2" fill="rgb(var(--c-panel))" stroke="#2ebd85" />
        <text x="65" y="15.5" fontSize="7" fill="#2ebd85" textAnchor="middle">BOS</text>
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <rect key={i} x="120" y={34 + i * 4} width={[4, 7, 10, 16, 10, 7, 4][i]} height="3" fill={i === 3 ? "#ff7a1a" : "#2ebd85"} opacity={i === 3 ? 0.85 : 0.4} />
        ))}
        <rect x="20" y="34" width="95" height="28" fill="#2ebd85" opacity="0.06" />
        <path d="M20 34 H115 M20 62 H115" stroke="#2ebd85" strokeOpacity="0.35" />
        <path d="M5 50 L20 46 L35 56 L50 40 L65 44 L80 30 L95 26 L110 20" fill="none" stroke="rgb(var(--c-txt-muted))" strokeWidth="1.5" />
        <circle cx="60" cy="62" r="4" fill="#2ebd85" fillOpacity="0.16" stroke="#2ebd85" />
      </svg>
    );
  if (id === "orderblocks")
    return (
      <svg viewBox="0 0 160 70" className="h-full w-full" aria-hidden>
        <rect x="30" y="44" width="130" height="10" fill="#2ebd85" opacity="0.1" />
        <rect x="30" y="44" width="2" height="10" fill="#2ebd85" />
        <rect x="55" y="12" width="45" height="9" fill="#f6465d" opacity="0.1" />
        <rect x="55" y="12" width="2" height="9" fill="#f6465d" />
        <path d="M100 12 H160 M100 21 H160" stroke="#2ebd85" strokeDasharray="4 4" />
        <path d="M5 40 L20 34 L30 50 L45 30 L55 16 L70 26 L85 22 L100 34 L115 18 L130 30 L145 38 L155 32" fill="none" stroke="rgb(var(--c-txt-muted))" strokeWidth="1.5" />
      </svg>
    );
  if (id === "hurst")
    return (
      <svg viewBox="0 0 160 70" className="h-full w-full" aria-hidden>
        <path d="M0 35 H160" stroke="#808896" strokeOpacity="0.6" />
        <path d="M0 29 H160" stroke="#3b82f6" strokeOpacity="0.5" strokeDasharray="1 3" />
        <path d="M0 41 H160" stroke="#d4a20a" strokeOpacity="0.5" strokeDasharray="1 3" />
        <path d="M5 35 L5 34 L20 30 L35 20 L50 16 L60 24 L62 35 Z" fill="#3b82f6" opacity="0.18" />
        <path d="M80 35 L80 37 L95 46 L110 52 L125 48 L135 41 L135 35 Z" fill="#d4a20a" opacity="0.18" />
        <path d="M5 34 L20 30 L35 20 L50 16 L60 24" fill="none" stroke="#3b82f6" strokeWidth="2" />
        <path d="M60 24 L70 33 L80 37" fill="none" stroke="#808896" strokeWidth="2" />
        <path d="M80 37 L95 46 L110 52 L125 48 L135 41" fill="none" stroke="#d4a20a" strokeWidth="2" />
        <path d="M135 41 L155 33" fill="none" stroke="#808896" strokeWidth="2" />
      </svg>
    );
  if (id === "trail")
    return (
      <svg viewBox="0 0 160 70" className="h-full w-full" aria-hidden>
        <path d="M5 55 L20 48 L32 50 L45 38 L58 40 L70 28 L82 30 L90 22 L100 34 L112 44 L125 40 L140 50 L155 46" fill="none" stroke="rgb(var(--c-txt-muted))" strokeWidth="1.5" />
        <path d="M5 64 H25 V58 H45 V50 H62 V40 H78 V34" fill="none" stroke="#2ebd85" strokeWidth="2" />
        <path d="M100 18 H118 V24 H135 V30 H155" fill="none" stroke="#f6465d" strokeWidth="2" />
        <path d="M100 8 l-4 -5 h8 z" fill="#f6465d" />
        <path d="M5 66 l-4 4 h8 z" fill="#2ebd85" />
      </svg>
    );
  if (id === "ofvwap")
    return (
      <svg viewBox="0 0 160 70" className="h-full w-full" aria-hidden>
        <path d="M5 22 C40 18 70 24 105 20 L105 52 C70 48 40 54 5 50 Z" fill="#94a3b8" opacity="0.1" />
        <path d="M5 22 C40 18 70 24 105 20" fill="none" stroke="#94a3b8" strokeOpacity="0.6" strokeDasharray="1 2" />
        <path d="M5 36 C40 34 70 38 105 35" fill="none" stroke="#94a3b8" strokeWidth="2" />
        <path d="M5 50 C40 54 70 48 105 52" fill="none" stroke="#94a3b8" strokeOpacity="0.6" strokeDasharray="1 2" />
        <path d="M5 38 L18 28 L30 44 L45 30 L58 46 L72 32 L86 40 L100 34" fill="none" stroke="rgb(var(--c-txt-muted))" strokeWidth="1.3" />
        <path d="M10 12 L100 12" stroke="#f6465d" strokeOpacity="0.45" strokeDasharray="2 3" />
        {[[26, 10, 0.18], [32, 22, 0.42], [38, 30, 0], [44, 16, 0.18], [50, 8, 0.18]].map(([y, w, o]) => (
          <rect key={y} x="112" y={y} width={w} height="5" fill={o === 0 ? "#ff7a1a" : "#94a3b8"} opacity={o === 0 ? 0.85 : o} />
        ))}
        <rect x="132" y="32" width="2" height="5" fill="#2ebd85" />
      </svg>
    );
  if (id === "zregime")
    return (
      <svg viewBox="0 0 160 70" className="h-full w-full" aria-hidden>
        <rect x="40" y="0" width="70" height="70" fill="#d4a20a" opacity="0.12" />
        <path d="M5 20 L20 28 L35 22 L50 12 L62 30 L75 45 L88 36 L100 22 L115 30 L130 26 L155 24" fill="none" stroke="rgb(var(--c-txt-muted))" strokeWidth="1.5" />
        <path d="M5 55 L155 55" stroke="#d4a20a" strokeOpacity="0.4" strokeDasharray="3 3" />
        <path d="M5 58 L20 60 L35 57 L50 50 L62 62 L75 67 L88 61 L100 56 L115 59 L130 58 L155 57" fill="none" stroke="#d4a20a" strokeWidth="1.5" />
        <path d="M75 52 l-4 6 h8 z" fill="#2ebd85" />
        <path d="M50 4 l-4 -0 l4 6 l4 -6 z" fill="#f6465d" />
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
  const fits = INDICATORS.filter((d) => d.regime === currentRegime).map((d) => d.id);
  const recommended = fits[0];
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
  const col = (r: string) => (r === "any" ? "rgb(var(--c-accent))" : REGIME_META[r as Regime]?.color ?? "#808896");
  const regimeTag = (r: string) =>
    r === "any" ? "Semua kondisi · Exit plan" : `${REGIME_PLAIN[r as Regime].name} · ${REGIME_META[r as Regime].label}`;

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
                            {regimeTag(d.regime)}
                          </span>
                          {isOn && <span className="rounded bg-accent/20 px-1.5 text-2xs text-accent">aktif</span>}
                        </div>
                        <div className="mt-1 text-[14px] font-semibold text-txt">{d.family}</div>
                        <div className="text-[12px] text-txtDim">{d.name}</div>
                        {fits.includes(d.id) && <div className="mt-1 text-2xs text-accent">Cocok untuk kondisi sekarang</div>}
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
                  {def.family} · {def.regime === "any" ? "untuk semua kondisi" : `untuk kondisi ${REGIME_PLAIN[def.regime].name}`}
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

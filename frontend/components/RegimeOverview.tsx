"use client";

import Link from "next/link";
import { useState } from "react";
import type { AiRegimeClass, AiRegimeResponse, Candle } from "@/lib/api-client";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";
import { STRATEGY_PLAN, VERDICT_META } from "@/lib/strategy";

/**
 * Kartu ringkasan beranda: satu kesimpulan besar, empat angka pendukung, dan
 * satu kalimat penjelasan yang buktinya dapat dibuka.
 *
 * Label besar selalu dari detektor AI. Estimator klasik R/S dan DFA hanya
 * pembanding dan dibaca terhadap pita acak (persentil 2,5–97,5% pada deret
 * tanpa memori), bukan terhadap 0,5: pada jendela 500 bar R/S bias ke atas,
 * sehingga 0,59 pun masih sepenuhnya acak.
 */

const DAY = 24 * 3600;
const AI_CLASSES: AiRegimeClass[] = ["persistent", "random_like", "anti_persistent"];

export type Band = { lower: number; median: number; upper: number };
export type RandomBand = { scenario: string; window: number; hurst_rs: Band; dfa_alpha: Band } | null;
export type ClassicPoint = { time?: number; hurst?: number | null; dfa_alpha?: number | null };

export const num = (v: number, d = 3) => v.toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });
export const signed = (v: number, d = 3) => `${v >= 0 ? "+" : "−"}${num(Math.abs(v), d)}`;
export const pct = (v: number) => `${Math.round(v * 100)}%`;
/** Keyakinan; satu desimal di sekitar ambang agar 74,8% tidak tampil "75% · rendah" pada τ = 75%. */
export const pctConf = (v: number, tau: number) =>
  Math.abs(v - tau) < 0.01 ? `${(v * 100).toLocaleString("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%` : pct(v);

export function formatDate(t: number) {
  return new Date(t * 1000).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

export function formatDuration(seconds: number) {
  const days = Math.floor(seconds / DAY);
  const hours = Math.round((seconds % DAY) / 3600);
  if (days >= 1) return hours ? `${days} hari ${hours} jam` : `${days} hari`;
  return `${Math.max(1, hours)} jam`;
}

/** Awal kondisi berjalan dan jumlah pergantian 30 hari terakhir. */
export function runInfo(series: { time: number; regime: string }[]) {
  if (!series.length) return null;
  const last = series[series.length - 1];
  let i = series.length - 1;
  while (i > 0 && series[i - 1].regime === last.regime) i--;
  const recent = series.filter((p) => p.time >= last.time - 30 * DAY);
  let switches = 0;
  for (let k = 1; k < recent.length; k++) if (recent[k].regime !== recent[k - 1].regime) switches++;
  return { since: series[i].time, last: last.time, switches };
}

/** Titik terdekat ke `target` (deret klasik dijarangkan, jaraknya tidak seragam). */
export function nearest(points: ClassicPoint[], target: number) {
  let best: ClassicPoint | null = null;
  for (const p of points) {
    if (p.time === undefined) continue;
    if (!best || Math.abs(p.time - target) < Math.abs((best.time ?? 0) - target)) best = p;
  }
  return best;
}

export function bandStatus(value: number | null | undefined, band: Band | undefined) {
  if (value === null || value === undefined || !band) return null;
  if (value > band.upper) return { label: "Di atas pita acak", tone: "persistent" as const, outside: true };
  if (value < band.lower) return { label: "Di bawah pita acak", tone: "anti_persistent" as const, outside: true };
  return { label: "Dalam pita acak", tone: "random_like" as const, outside: false };
}

export function Chip({ children, color, title }: { children: React.ReactNode; color?: string; title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11.5px] font-semibold uppercase tracking-wide"
      style={
        color
          ? { color, borderColor: `${color}55`, backgroundColor: `${color}14` }
          : { color: "rgb(var(--c-txt))", borderColor: "rgb(var(--c-edge))" }
      }
    >
      {children}
    </span>
  );
}

export function MetricCard({
  title,
  value,
  status,
  statusColor,
  foot,
  hint,
}: {
  title: string;
  value: string;
  status: string | null;
  statusColor: string;
  foot: string | null;
  hint: string;
}) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-edge px-3 py-3 text-center" title={hint}>
      {/* Judul ditulis kapital di sumber: kelas uppercase akan mengubah α menjadi Α. */}
      <div className="text-[11px] font-medium tracking-wider text-txtDim">{title}</div>
      <div className="mt-1 font-mono text-[26px] font-semibold leading-none tabular-nums" style={{ color: statusColor }}>
        {value}
      </div>
      {status && (
        <span
          className="mt-2 rounded px-1.5 py-0.5 text-[11px] font-medium"
          style={{ color: statusColor, backgroundColor: `${statusColor}1a` }}
        >
          {status}
        </span>
      )}
      {foot && <div className="mt-1.5 text-[11.5px] text-txtMuted">{foot}</div>}
    </div>
  );
}

export function InfoCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-edge px-4 py-3 text-center">
      <div className="text-[11px] font-medium uppercase tracking-wider text-txtDim">{title}</div>
      {children}
    </div>
  );
}

export function ProbabilityBars({
  title,
  data,
}: {
  title: string;
  data: { current_probabilities?: Record<AiRegimeClass, number> | null } | null;
}) {
  const probs = data?.current_probabilities;
  if (!probs) return null;
  return (
    <div>
      <div className="mb-1.5 text-[12px] font-medium text-txt">{title}</div>
      <div className="space-y-1.5">
        {AI_CLASSES.map((c) => (
          <div key={c} className="grid grid-cols-[120px_1fr_40px] items-center gap-2 text-[12px]">
            <span className="text-txtDim">{REGIME_PLAIN[c].name}</span>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface">
              <div className="h-full rounded-full" style={{ width: `${probs[c] * 100}%`, backgroundColor: REGIME_META[c].color }} />
            </div>
            <span className="text-right font-mono text-txt">{pct(probs[c])}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function RegimeOverview({
  timeframe,
  ai1h,
  ai4h,
  classic,
  band,
  candles,
}: {
  timeframe: string;
  ai1h: AiRegimeResponse | null;
  ai4h: AiRegimeResponse | null;
  classic: ClassicPoint[];
  band: RandomBand;
  candles: Candle[];
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const active = timeframe === "4h" ? ai4h : ai1h;
  const other = timeframe === "4h" ? ai1h : ai4h;
  const otherTf = timeframe === "4h" ? "1H" : "4H";
  const key = active?.current_regime ?? null;
  const low = Boolean(active?.current_low_confidence);

  if (!active || !key) {
    return (
      <section className="rounded-xl border border-edge bg-panel p-5 shadow-panel">
        <div className="text-[11px] font-medium uppercase tracking-wider text-txtDim">Kondisi pasar</div>
        <div className="mt-3 h-9 w-64 animate-pulse rounded bg-surface" />
        <div className="mt-3 h-4 w-96 max-w-full animate-pulse rounded bg-surface" />
      </section>
    );
  }

  const shown: Regime = low ? "uncertain_lowconf" : key;
  const color = REGIME_META[shown].color;
  const conf = active.current_probabilities?.[key] ?? null;
  const tau = active.detector.abstain_tau;
  const run = runInfo(active.series);
  const plan = STRATEGY_PLAN[shown];
  const verdict = plan ? VERDICT_META[plan.verdict] : null;

  const otherKey = other?.current_regime ?? null;
  const agree = otherKey !== null && otherKey === key && !other?.current_low_confidence && !low;

  // Perubahan harga 30 hari dari candle tertutup terakhir.
  let priceChange: number | null = null;
  if (candles.length > 1) {
    const last = candles[candles.length - 1];
    const ref = candles.find((c) => c.time >= last.time - 30 * DAY);
    if (ref && ref.close) priceChange = (last.close - ref.close) / ref.close;
  }

  // Pembanding klasik: nilai terakhir dan selisih terhadap ±30 hari lalu.
  const lastClassic = classic.length ? classic[classic.length - 1] : null;
  const prevClassic = lastClassic?.time ? nearest(classic, lastClassic.time - 30 * DAY) : null;
  const rs = lastClassic?.hurst ?? null;
  const dfa = lastClassic?.dfa_alpha ?? null;
  const rsStatus = bandStatus(rs, band?.hurst_rs);
  const dfaStatus = bandStatus(dfa, band?.dfa_alpha);
  const outside = [rsStatus, dfaStatus].filter((s) => s?.outside).length;

  const aiCard = (tf: string, d: AiRegimeResponse | null) => {
    const k = d?.current_regime ?? null;
    const lowConf = Boolean(d?.current_low_confidence);
    const r: Regime | null = k ? (lowConf ? "uncertain_lowconf" : k) : null;
    const c = k && d?.current_probabilities ? d.current_probabilities[k] : null;
    const info = d ? runInfo(d.series) : null;
    return (
      <MetricCard
        key={tf}
        title={`DETEKTOR AI ${tf}`}
        value={c !== null ? pctConf(c, tau) : "–"}
        status={r ? `${REGIME_PLAIN[k as Regime].name}${lowConf ? " · ragu" : ""}` : null}
        statusColor={r ? REGIME_META[r].color : "rgb(var(--c-txt-muted))"}
        foot={info ? `sejak ${formatDate(info.since)}` : null}
        hint={`Keyakinan detektor untuk kelas teratas pada ${tf}. Di bawah ${pct(tau)} label dianggap ragu.`}
      />
    );
  };

  const classicCard = (title: string, value: number | null, prev: number | null | undefined, status: ReturnType<typeof bandStatus>, b: Band | undefined, hint: string) => (
    <MetricCard
      title={title}
      value={value !== null ? num(value) : "–"}
      status={status?.label ?? null}
      statusColor={status ? REGIME_META[status.tone].color : "rgb(var(--c-txt-muted))"}
      foot={
        value !== null && prev !== null && prev !== undefined
          ? `${signed(value - prev)} vs 30 hari lalu`
          : b
            ? `pita ${num(b.lower, 2)}–${num(b.upper, 2)}`
            : null
      }
      hint={hint}
    />
  );

  const sentence = [
    `Detektor AI menilai pasar ${timeframe.toUpperCase()} ${REGIME_PLAIN[key].name.toLowerCase()}${
      conf !== null ? ` dengan keyakinan ${pctConf(conf, tau)}` : ""
    }${low ? `, di bawah batas ${pct(tau)} sehingga diperlakukan sebagai tidak pasti` : ""}.`,
    otherKey
      ? agree
        ? `Skala ${otherTf} sepakat.`
        : `Skala ${otherTf} berbeda: ${REGIME_PLAIN[otherKey].name.toLowerCase()}${other?.current_low_confidence ? " (ragu)" : ""}.`
      : "",
    band
      ? outside === 0
        ? "Estimator klasik R/S dan DFA sama-sama berada di dalam pita acak, jadi keduanya tidak dapat membedakan pasar ini dari pasar tanpa memori."
        : `${outside} dari 2 estimator klasik berada di luar pita acak.`
      : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className="rounded-xl border border-edge bg-panel p-4 shadow-panel sm:p-5" aria-label="Kondisi pasar saat ini">
      <div className="grid gap-4 xl:grid-cols-[minmax(260px,0.9fr)_2fr]">
        {/* Kesimpulan utama */}
        <div className="flex flex-col justify-center">
          <div className="text-[11px] font-medium uppercase tracking-wider text-txtDim">
            Kondisi pasar · {timeframe.toUpperCase()}
          </div>
          <h2 className="mt-1 text-[30px] font-bold uppercase leading-tight tracking-tight" style={{ color }}>
            {REGIME_PLAIN[shown].name}
          </h2>
          <p className="mt-1 text-[13.5px] text-txtDim">{REGIME_PLAIN[shown].summary}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {conf !== null && (
              <Chip color={low ? REGIME_META.uncertain_lowconf.color : undefined} title={`Ambang ragu ${pct(tau)}`}>
                Keyakinan {pctConf(conf, tau)}
                {low ? " · rendah" : ""}
              </Chip>
            )}
            {otherKey && (
              <Chip color={agree ? REGIME_META[key].color : undefined}>
                {agree ? `1H & 4H sepakat` : `${otherTf}: ${REGIME_PLAIN[otherKey].name}`}
              </Chip>
            )}
            {band && <Chip>{outside} dari 2 di luar pita acak</Chip>}
            {priceChange !== null && (
              <Chip>
                Harga {priceChange >= 0 ? "naik" : "turun"} {Math.abs(priceChange * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 })}% · 30 hari
              </Chip>
            )}
          </div>
        </div>

        {/* Empat angka pendukung */}
        <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
          {aiCard("1H", ai1h)}
          {aiCard("4H", ai4h)}
          {classicCard(
            `HURST R/S · ${band?.window ?? 500}`,
            rs,
            prevClassic?.hurst,
            rsStatus,
            band?.hurst_rs,
            "Pembanding klasik (bukan penentu label). Dibaca terhadap pita acak, bukan 0,5: R/S bias ke atas pada jendela terbatas."
          )}
          {classicCard(
            `DFA α · ${band?.window ?? 500}`,
            dfa,
            prevClassic?.dfa_alpha,
            dfaStatus,
            band?.dfa_alpha,
            "Pembanding klasik (bukan penentu label). Dibaca terhadap pita acak pada panjang jendela yang sama."
          )}
        </div>
      </div>

      <div className="mt-3 grid gap-2.5 md:grid-cols-3">
        <InfoCard title="Berlangsung sejak">
          <div className="mt-1 text-[18px] font-semibold text-txt">{run ? formatDate(run.since) : "–"}</div>
          <div className="text-[12px] text-txtMuted">{run ? `± ${formatDuration(run.last - run.since)}` : ""}</div>
        </InfoCard>
        <InfoCard title="Pergantian kondisi">
          <div className="mt-1 text-[18px] font-semibold text-txt">{run ? `${run.switches}×` : "–"}</div>
          <div className="text-[12px] text-txtMuted">dalam 30 hari terakhir</div>
        </InfoCard>
        <InfoCard title="Apa artinya untuk Anda?">
          <div className="mt-1 text-[16px] font-semibold text-txt">{plan?.strategy ?? "–"}</div>
          <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
            {verdict && <span className={`rounded-full border px-2 py-0.5 text-2xs font-medium ${verdict.className}`}>{verdict.label}</span>}
            <Link href="/strategi" className="text-[12px] font-medium text-accent hover:underline">
              Peta strategi →
            </Link>
          </div>
        </InfoCard>
      </div>

      <div className="mt-4 border-t border-edge pt-3">
        <p className="text-[13px] leading-relaxed text-txtDim">{sentence}</p>
        <button
          type="button"
          onClick={() => setShowEvidence((v) => !v)}
          aria-expanded={showEvidence}
          className="mt-1.5 flex items-center gap-1 text-[12.5px] font-medium text-txt hover:text-accent"
        >
          <span className={`text-[10px] transition-transform ${showEvidence ? "rotate-90" : ""}`} aria-hidden>
            ▸
          </span>
          {showEvidence ? "Sembunyikan bukti" : "Tunjukkan bukti"}
        </button>

        {showEvidence && (
          <div className="mt-3 grid gap-5 text-[12.5px] leading-relaxed text-txtDim lg:grid-cols-3">
            <div className="space-y-4">
              <ProbabilityBars title="Probabilitas detektor · 1H" data={ai1h} />
              <ProbabilityBars title="Probabilitas detektor · 4H" data={ai4h} />
            </div>
            <div>
              <div className="mb-1.5 text-[12px] font-medium text-txt">Pita acak estimator klasik</div>
              {band ? (
                <>
                  <p>
                    Pada {band.window} bar deret sintetis tanpa memori (H = 0,5, karakter kripto), R/S terbaca{" "}
                    {num(band.hurst_rs.lower)}–{num(band.hurst_rs.upper)} (median {num(band.hurst_rs.median)}) dan DFA{" "}
                    {num(band.dfa_alpha.lower)}–{num(band.dfa_alpha.upper)}. Nilai di dalam rentang ini tidak dapat dibedakan dari
                    pasar acak.
                  </p>
                  <p className="mt-2">
                    Karena itu R/S sekitar 0,59 tidak berarti &ldquo;tren&rdquo;: median R/S pada pasar acak pun{" "}
                    {num(band.hurst_rs.median)}.
                  </p>
                </>
              ) : (
                <p>Pita acak belum tersedia.</p>
              )}
            </div>
            <div>
              <div className="mb-1.5 text-[12px] font-medium text-txt">Mengapa detektor AI yang menentukan</div>
              <p>
                Pada deret sintetis mirip kripto dengan H diketahui, detektor mencapai akurasi seimbang{" "}
                {active.detector.test_ba_synthetic?.S4 !== undefined ? num(active.detector.test_ba_synthetic.S4) : "0,813"}, sedangkan
                estimator klasik terbaik 0,654 dan konsensus R/S–DFA 0,268.
              </p>
              <p className="mt-2">
                Di bawah keyakinan {pct(tau)} label dianggap ragu; pada riwayat {timeframe.toUpperCase()} ini{" "}
                {pct(active.low_confidence_share ?? 0)} titik berkeyakinan rendah.{" "}
                <Link href="/methodology" className="font-medium text-accent hover:underline">
                  Metodologi →
                </Link>
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

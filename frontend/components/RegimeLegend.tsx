"use client";

import { REGIME_META, REGIME_ORDER, REGIME_PLAIN } from "@/lib/regime";

/**
 * Legenda 5 kategori. Dua jenis Uncertain ditampilkan dengan pola berbeda.
 * Nama awam ditampilkan lebih dulu; istilah teknis tetap ada sebagai keterangan.
 */
export default function RegimeLegend({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2">
      {REGIME_ORDER.map((key) => {
        const meta = REGIME_META[key];
        const plain = REGIME_PLAIN[key];
        const patternClass =
          meta.pattern === "diagonal"
            ? "pattern-diagonal"
            : meta.pattern === "dots"
              ? "pattern-dots"
              : "";
        return (
          <div
            key={key}
            className="flex items-start gap-2"
            title={`${meta.label} — ${plain.summary}`}
          >
            <span
              className={`mt-0.5 inline-block h-3 w-3 shrink-0 rounded-sm ${patternClass}`}
              style={{
                backgroundColor: meta.pattern === "solid" ? meta.color : "transparent",
                border: `1px solid ${meta.color}`,
              }}
            />
            <div className="leading-tight">
              <div className="text-[11px] text-txtDim">
                {plain.name}
                {!compact && <span className="ml-1 text-2xs text-txtMuted">({meta.label})</span>}
              </div>
              {!compact && <div className="text-2xs text-txtMuted">{plain.summary}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

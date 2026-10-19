"use client";

import { REGIME_META } from "@/lib/regime";

/**
 * Skala horizontal 0–1 dengan tiga zona warna dan penanda nilai saat ini.
 *
 * Angka eksponen sulit dibaca orang awam; posisi penanda pada zona berwarna
 * jauh lebih mudah dipahami daripada membandingkan angka dengan ambang.
 */
export default function ExponentGauge({
  label,
  hint,
  value,
  lower,
  upper,
  loading,
}: {
  label: string;
  hint: string;
  value: number | null | undefined;
  lower: number;
  upper: number;
  loading?: boolean;
}) {
  const min = 0.2;
  const max = 0.8;
  const pos = (v: number) => ((Math.min(max, Math.max(min, v)) - min) / (max - min)) * 100;
  const zone =
    value == null
      ? null
      : value > upper
        ? "persistent"
        : value < lower
          ? "anti_persistent"
          : "random_like";
  const zoneText =
    zone === "persistent"
      ? "zona tren berlanjut"
      : zone === "anti_persistent"
        ? "zona cenderung berbalik"
        : zone === "random_like"
          ? "zona acak"
          : "";

  return (
    <div className="rounded border border-edge bg-surface px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-[12px] font-medium text-txt" title={hint}>
          {label}
          <span className="ml-1 cursor-help text-txtMuted">ⓘ</span>
        </div>
        <div className="font-mono text-[15px] font-semibold tabular-nums text-txt">
          {loading ? "…" : (value?.toFixed(2) ?? "—")}
        </div>
      </div>

      <div className="relative mt-2 h-2.5">
        <div className="absolute inset-0 flex overflow-hidden rounded-full">
          <div style={{ width: `${pos(lower)}%`, backgroundColor: REGIME_META.anti_persistent.color }} className="opacity-60" />
          <div
            style={{ width: `${pos(upper) - pos(lower)}%`, backgroundColor: REGIME_META.random_like.color }}
            className="opacity-60"
          />
          <div className="flex-1 opacity-60" style={{ backgroundColor: REGIME_META.persistent.color }} />
        </div>
        {value != null && !loading && (
          <div
            className="absolute -top-1 w-1 -translate-x-1/2 rounded bg-white shadow"
            style={{ left: `${pos(value)}%`, height: 18 }}
          />
        )}
      </div>

      <div className="mt-1 flex justify-between text-[10px] text-txtMuted">
        <span>berbalik</span>
        <span>acak</span>
        <span>berlanjut</span>
      </div>
      {zoneText && !loading && (
        <div className="mt-1 text-[11px] text-txtDim">
          Saat ini di <span style={{ color: REGIME_META[zone!].color }}>{zoneText}</span>
        </div>
      )}
    </div>
  );
}

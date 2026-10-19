/**
 * Tema bersama untuk seluruh chart Recharts.
 *
 * Disatukan agar panel metrik tampil konsisten dengan candlestick
 * (lightweight-charts) yang memakai palet dan tipografi monospace serupa.
 * Tanpa ini, tiap panel mudah menyimpang saat ditambahkan belakangan.
 */

export const AXIS_TICK = {
  fontSize: 10,
  fill: "#64748b",
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
} as const;

export const GRID_STROKE = "rgba(39,43,49,0.5)";

export const TOOLTIP_STYLE = {
  background: "#0a0b0d",
  border: "1px solid #272b31",
  borderRadius: 6,
  fontSize: 11,
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
} as const;

export const TOOLTIP_LABEL_STYLE = { color: "#94a3b8" } as const;

export const LEGEND_STYLE = { fontSize: 11 } as const;

/** Palet garis untuk deret bertumpuk, urut sesuai kepentingan. */
export const SERIES_COLORS = [
  "#3b82f6",
  "#f59e0b",
  "#10b981",
  "#a78bfa",
  "#ef4444",
  "#06b6d4",
] as const;

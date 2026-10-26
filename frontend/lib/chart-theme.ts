/**
 * Tema bersama untuk seluruh chart Recharts.
 *
 * Disatukan agar panel metrik tampil konsisten dengan candlestick
 * (lightweight-charts) yang memakai palet dan tipografi monospace serupa.
 * Tanpa ini, tiap panel mudah menyimpang saat ditambahkan belakangan.
 */

// Warna memakai variabel CSS tema (globals.css) agar ikut berganti terang/gelap.
export const AXIS_TICK = {
  fontSize: 10,
  fill: "rgb(var(--c-txt-muted))",
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
} as const;

export const GRID_STROKE = "rgb(var(--c-edge) / 0.7)";

export const TOOLTIP_STYLE = {
  background: "rgb(var(--c-panel))",
  border: "1px solid rgb(var(--c-edge))",
  borderRadius: 6,
  fontSize: 11,
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  boxShadow: "var(--shadow-pop)",
  color: "rgb(var(--c-txt))",
} as const;

export const TOOLTIP_LABEL_STYLE = { color: "rgb(var(--c-txt-dim))" } as const;

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

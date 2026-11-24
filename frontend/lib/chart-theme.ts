/** Tema bersama untuk seluruh chart Recharts. */

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


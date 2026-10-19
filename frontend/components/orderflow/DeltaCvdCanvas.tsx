"use client";

import { useEffect } from "react";
import type { OrderFlowEngine } from "@/lib/orderflow/engine";
import { FOOT_COL_W, visibleCandles } from "./FootprintCanvas";
import { AXIS_W, FONT, fmtQty, prepare, useCanvasSize } from "./useOrderFlow";

/** Delta per candle (batang) dan CVD (garis), sejajar dengan kolom footprint. */
export default function DeltaCvdCanvas({ engine, version }: { engine: OrderFlowEngine; version: number }) {
  const { ref, w, h, dpr } = useCanvasSize();

  useEffect(() => {
    const ctx = prepare(ref.current, w, h, dpr);
    if (!ctx) return;
    const plotW = w - AXIS_W;
    ctx.fillStyle = "#0a0b0d";
    ctx.fillRect(0, 0, w, h);
    const all = engine.candles;
    const candles = visibleCandles(all, w);
    if (!candles.length) return;

    // CVD sejak candle pertama yang dimuat.
    const cvdAll: number[] = [];
    let run = 0;
    for (const c of all) {
      run += c.buy - c.sell;
      cvdAll.push(run);
    }
    const cvd = cvdAll.slice(-candles.length);
    const deltas = candles.map((c) => c.buy - c.sell);
    const maxD = Math.max(...deltas.map(Math.abs), 1e-9);
    const lo = Math.min(...cvd);
    const hi = Math.max(...cvd);
    const x0 = plotW - candles.length * FOOT_COL_W;
    const mid = h / 2;

    ctx.strokeStyle = "rgba(39,43,49,0.8)";
    ctx.beginPath();
    ctx.moveTo(0, mid + 0.5);
    ctx.lineTo(plotW, mid + 0.5);
    ctx.stroke();

    ctx.font = FONT;
    ctx.textAlign = "center";
    candles.forEach((c, i) => {
      const d = deltas[i];
      const bh = (Math.abs(d) / maxD) * (h / 2 - 12);
      const x = x0 + i * FOOT_COL_W + 14;
      const bw = FOOT_COL_W - 20;
      ctx.fillStyle = d >= 0 ? "rgba(46,189,133,0.55)" : "rgba(246,70,93,0.55)";
      ctx.fillRect(x, d >= 0 ? mid - bh : mid, bw, Math.max(1, bh));
      ctx.fillStyle = d >= 0 ? "#4fe0a5" : "#ff6b7d";
      ctx.fillText(`${d >= 0 ? "+" : "−"}${fmtQty(Math.abs(d))}`, x + bw / 2, d >= 0 ? mid + 12 : mid - 6);
    });

    ctx.beginPath();
    ctx.strokeStyle = "#ff7a1a";
    ctx.lineWidth = 2;
    cvd.forEach((v, i) => {
      const x = x0 + i * FOOT_COL_W + FOOT_COL_W / 2;
      const y = 8 + (1 - (v - lo) / (hi - lo || 1)) * (h - 16);
      if (i) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    ctx.stroke();

    ctx.fillStyle = "#131518";
    ctx.fillRect(plotW, 0, AXIS_W, h);
    ctx.textAlign = "left";
    ctx.fillStyle = "#a8a29b";
    ctx.fillText("Delta", plotW + 6, 14);
    ctx.fillStyle = "#ff7a1a";
    ctx.fillText("CVD", plotW + 6, 28);
    ctx.fillStyle = "#d9d3cc";
    const lastCvd = cvd[cvd.length - 1];
    ctx.fillText(`${lastCvd >= 0 ? "+" : "−"}${fmtQty(Math.abs(lastCvd))}`, plotW + 6, 44);
  }, [engine, version, w, h, dpr, ref]);

  return <canvas ref={ref} className="block h-full w-full" aria-label="Delta dan CVD" role="img" />;
}

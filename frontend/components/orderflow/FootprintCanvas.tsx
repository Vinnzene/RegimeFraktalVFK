"use client";

import { useEffect, useRef, useState } from "react";
import type { Candle, OrderFlowEngine } from "@/lib/orderflow/engine";
import { AXIS_W, FONT, fmtPrice, fmtQty, prepare, useCanvasSize } from "./useOrderFlow";

export const FOOT_COL_W = 128;
const ROW_H = 18;
const IMBALANCE = 3;

/** Kolom candle yang terlihat (rata kanan), dipakai juga panel delta agar sejajar. */
export function visibleCandles(candles: Candle[], width: number) {
  const n = Math.max(1, Math.floor((width - AXIS_W) / FOOT_COL_W));
  return candles.slice(-n);
}

export default function FootprintCanvas({ engine, version }: { engine: OrderFlowEngine; version: number }) {
  const { ref, w, h, dpr } = useCanvasSize();
  const [offset, setOffset] = useState(0); // geser vertikal dalam baris
  const wheel = useRef(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      wheel.current += e.deltaY;
      const rows = Math.trunc(wheel.current / 40);
      if (rows) {
        wheel.current -= rows * 40;
        setOffset((o) => o + rows);
      }
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [ref]);

  useEffect(() => {
    const ctx = prepare(ref.current, w, h, dpr);
    if (!ctx) return;
    const plotW = w - AXIS_W;
    const plotH = h - 22;
    const nRows = Math.max(1, Math.floor(plotH / ROW_H));
    const step = engine.footStep;
    const candles = visibleCandles(engine.candles, w);

    ctx.fillStyle = "#0a0b0d";
    ctx.fillRect(0, 0, w, h);
    if (!candles.length) {
      ctx.fillStyle = "#a8a29b";
      ctx.font = "13px system-ui, sans-serif";
      ctx.fillText("Memuat transaksi…", 16, 28);
      return;
    }

    const topIdx = Math.floor(engine.lastPrice / step) + Math.floor(nRows / 2) - offset;
    const x0 = plotW - candles.length * FOOT_COL_W;
    const rowY = (k: number) => (topIdx - k) * ROW_H;

    // Garis bantu harga.
    ctx.strokeStyle = "rgba(39,43,49,0.5)";
    ctx.lineWidth = 1;
    for (let r = 0; r <= nRows; r++) {
      ctx.beginPath();
      ctx.moveTo(0, r * ROW_H + 0.5);
      ctx.lineTo(plotW, r * ROW_H + 0.5);
      ctx.stroke();
    }

    let maxTotal = 0;
    candles.forEach((c) => c.levels.forEach((v) => (maxTotal = Math.max(maxTotal, v.a + v.b))));

    ctx.font = FONT;
    ctx.textBaseline = "middle";
    candles.forEach((c, ci) => {
      const x = x0 + ci * FOOT_COL_W;
      const cellX = x + 14;
      const cellW = FOOT_COL_W - 20;
      const up = c.c >= c.o;

      // Candle tipis di kiri kolom.
      const yH = rowY(Math.floor(c.h / step));
      const yL = rowY(Math.floor(c.l / step)) + ROW_H;
      const yO = rowY(Math.floor(c.o / step)) + ROW_H / 2;
      const yC = rowY(Math.floor(c.c / step)) + ROW_H / 2;
      ctx.strokeStyle = up ? "#2ebd85" : "#f6465d";
      ctx.beginPath();
      ctx.moveTo(x + 6, yH);
      ctx.lineTo(x + 6, yL);
      ctx.stroke();
      ctx.fillStyle = up ? "#2ebd85" : "#f6465d";
      ctx.fillRect(x + 3, Math.min(yO, yC), 6, Math.max(2, Math.abs(yC - yO)));

      // Titik kontrol (POC): level dengan volume terbesar di candle.
      let poc = -Infinity;
      let pocVol = -1;
      c.levels.forEach((v, k) => {
        if (v.a + v.b > pocVol) {
          pocVol = v.a + v.b;
          poc = k;
        }
      });

      c.levels.forEach((v, k) => {
        const y = rowY(k);
        if (y < -ROW_H || y > plotH) return;
        const total = v.a + v.b;
        const delta = v.a - v.b;
        const alpha = 0.08 + 0.42 * (total / (maxTotal || 1));
        ctx.fillStyle = delta >= 0 ? `rgba(46,189,133,${alpha})` : `rgba(246,70,93,${alpha})`;
        ctx.fillRect(cellX, y + 1, cellW, ROW_H - 2);
        if (k === poc) {
          ctx.strokeStyle = "#ff7a1a";
          ctx.lineWidth = 1.2;
          ctx.strokeRect(cellX + 0.5, y + 1.5, cellW - 1, ROW_H - 3);
        }
        // Ketimpangan diagonal: beli agresif di level ini vs jual agresif satu level di bawah.
        const below = c.levels.get(k - 1);
        const above = c.levels.get(k + 1);
        const buyImb = v.a > 0 && v.a >= IMBALANCE * Math.max(below?.b ?? 0, 1e-9) && (below?.b ?? 0) > 0;
        const sellImb = v.b > 0 && v.b >= IMBALANCE * Math.max(above?.a ?? 0, 1e-9) && (above?.a ?? 0) > 0;
        ctx.textAlign = "left";
        ctx.fillStyle = sellImb ? "#ff6b7d" : "#d9d3cc";
        ctx.font = sellImb ? `bold ${FONT}` : FONT;
        ctx.fillText(fmtQty(v.b), cellX + 4, y + ROW_H / 2);
        ctx.textAlign = "right";
        ctx.fillStyle = buyImb ? "#4fe0a5" : "#d9d3cc";
        ctx.font = buyImb ? `bold ${FONT}` : FONT;
        ctx.fillText(fmtQty(v.a), cellX + cellW - 4, y + ROW_H / 2);
      });

      // Label waktu.
      ctx.font = FONT;
      ctx.textAlign = "center";
      ctx.fillStyle = "#a8a29b";
      const d = new Date(c.t);
      ctx.fillText(`${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`, x + FOOT_COL_W / 2, h - 10);
    });

    // Sumbu harga.
    ctx.textAlign = "left";
    ctx.fillStyle = "#131518";
    ctx.fillRect(plotW, 0, AXIS_W, h);
    ctx.fillStyle = "#a8a29b";
    for (let r = 0; r < nRows; r++) {
      if (r % 2) continue;
      ctx.fillText(fmtPrice((topIdx - r) * step, step), plotW + 6, r * ROW_H + ROW_H / 2);
    }
    const yp = rowY(Math.floor(engine.lastPrice / step)) + ROW_H / 2;
    if (yp > 0 && yp < plotH) {
      ctx.fillStyle = "#ff7a1a";
      ctx.fillRect(plotW, yp - 8, AXIS_W, 16);
      ctx.fillStyle = "#0a0b0d";
      ctx.fillText(fmtPrice(engine.lastPrice, step / 10), plotW + 6, yp);
    }
  }, [engine, version, w, h, dpr, ref, offset]);

  return (
    <div className="relative h-full w-full">
      <canvas ref={ref} className="block h-full w-full" aria-label="Footprint candle" role="img" />
      {offset !== 0 && (
        <button
          type="button"
          onClick={() => setOffset(0)}
          className="absolute left-3 top-3 rounded-md border border-edge bg-panel/90 px-2 py-1 text-[11px] text-txtDim hover:text-txt"
        >
          Kembali ke harga terakhir
        </button>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef } from "react";
import type { OrderFlowEngine } from "@/lib/orderflow/engine";
import { AXIS_W, FONT, fmtPrice, fmtQty, prepare, useCanvasSize } from "./useOrderFlow";

const COL_PX = 2;
const ROW_PX = 3;

/** Palet panas likuiditas: gelap -> biru -> sian -> kuning -> putih. */
const LUT = (() => {
  const stops: [number, number, number, number][] = [
    [0, 10, 11, 13],
    [0.25, 22, 52, 120],
    [0.5, 20, 150, 190],
    [0.75, 245, 200, 60],
    [1, 255, 250, 235],
  ];
  const out = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    const x = i / 255;
    let j = 0;
    while (j < stops.length - 2 && x > stops[j + 1][0]) j++;
    const [x0, r0, g0, b0] = stops[j];
    const [x1, r1, g1, b1] = stops[j + 1];
    const f = (x - x0) / (x1 - x0);
    const r = Math.round(r0 + (r1 - r0) * f);
    const g = Math.round(g0 + (g1 - g0) * f);
    const b = Math.round(b0 + (b1 - b0) * f);
    out[i] = (255 << 24) | (b << 16) | (g << 8) | r; // ABGR little-endian
  }
  return out;
})();

export default function HeatmapCanvas({ engine, version }: { engine: OrderFlowEngine; version: number }) {
  const { ref, w, h, dpr } = useCanvasSize();
  const off = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const ctx = prepare(ref.current, w, h, dpr);
    if (!ctx) return;
    const plotW = w - AXIS_W;
    const plotH = h - 18;
    const nCols = Math.max(1, Math.floor(plotW / COL_PX));
    const nRows = Math.max(1, Math.floor(plotH / ROW_PX));
    const cols = engine.columns.slice(-nCols);
    const step = engine.heatStep;

    ctx.fillStyle = "#0a0b0d";
    ctx.fillRect(0, 0, w, h);
    if (!cols.length) {
      ctx.fillStyle = "#a8a29b";
      ctx.font = "13px system-ui, sans-serif";
      ctx.fillText("Mengumpulkan data order book…", 16, 28);
      return;
    }

    const last = cols[cols.length - 1];
    const mid = (last.bestBid + last.bestAsk) / 2 || engine.lastPrice;
    const topIdx = Math.floor(mid / step) + Math.floor(nRows / 2);
    const x0 = nCols - cols.length;

    // Normalisasi: persentil 99 bucket yang terlihat di kolom terbaru, kurva
    // pangkat 0,6 agar hanya antrean yang benar-benar besar tampak terang.
    const lo = topIdx - nRows;
    const recent = [...last.liq.entries()].filter(([k, q]) => q > 0 && k > lo && k <= topIdx).map(([, q]) => q).sort((a, b) => a - b);
    const ref99 = (recent.length ? recent[Math.floor(recent.length * 0.99)] : 1) || 1;

    const img = new ImageData(nCols, nRows);
    const px = new Uint32Array(img.data.buffer);
    px.fill(LUT[0]);
    cols.forEach((c, i) => {
      const x = x0 + i;
      c.liq.forEach((q, k) => {
        const r = topIdx - k;
        if (r < 0 || r >= nRows) return;
        const v = Math.min(1, Math.pow(q / ref99, 0.6));
        px[r * nCols + x] = LUT[Math.round(v * 255)];
      });
    });
    if (!off.current) off.current = document.createElement("canvas");
    const oc = off.current;
    oc.width = nCols;
    oc.height = nRows;
    oc.getContext("2d")!.putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(oc, 0, 0, nCols * COL_PX, nRows * ROW_PX);

    const yOf = (p: number) => (topIdx - p / step + 0.5) * ROW_PX;

    // Garis best bid / best ask.
    for (const [key, color] of [["bestBid", "#2ebd85"], ["bestAsk", "#f6465d"]] as const) {
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      cols.forEach((c, i) => {
        const x = (x0 + i) * COL_PX;
        const y = yOf(c[key]);
        if (i) ctx.lineTo(x, y);
        else ctx.moveTo(x, y);
      });
      ctx.stroke();
    }

    // Gelembung transaksi agresif per kolom (beli hijau, jual merah) di harga VWAP.
    let maxVol = 0;
    cols.forEach((c) => (maxVol = Math.max(maxVol, c.buyVol, c.sellVol)));
    cols.forEach((c, i) => {
      const x = (x0 + i) * COL_PX;
      for (const [vol, notional, color] of [
        [c.buyVol, c.buyNotional, "rgba(46,189,133,0.75)"],
        [c.sellVol, c.sellNotional, "rgba(246,70,93,0.75)"],
      ] as const) {
        if (vol <= 0 || !maxVol) continue;
        const r = 1.5 + 9 * Math.sqrt(vol / maxVol);
        if (r < 2.5) continue;
        ctx.beginPath();
        ctx.fillStyle = color;
        ctx.arc(x, yOf(notional / vol), r, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    // Sumbu harga.
    ctx.fillStyle = "#131518";
    ctx.fillRect(plotW, 0, AXIS_W, h);
    ctx.font = FONT;
    ctx.fillStyle = "#a8a29b";
    const every = Math.max(1, Math.round(40 / ROW_PX));
    for (let r = 0; r < nRows; r += every) {
      const price = (topIdx - r) * step;
      ctx.fillText(fmtPrice(price, step), plotW + 6, r * ROW_PX + 4);
    }
    const y = yOf(engine.lastPrice);
    ctx.fillStyle = "#ff7a1a";
    ctx.fillRect(plotW, y - 8, AXIS_W, 16);
    ctx.fillStyle = "#0a0b0d";
    ctx.fillText(fmtPrice(engine.lastPrice, step / 10), plotW + 6, y + 4);

    // Keterangan bawah.
    ctx.fillStyle = "#6f6a64";
    ctx.fillText(
      `${((cols.length * 500) / 60000).toFixed(1)} menit terakhir · bucket ${fmtPrice(step, step)} · putih = ${fmtQty(ref99)} atau lebih`,
      8,
      h - 5
    );
  }, [engine, version, w, h, dpr, ref]);

  return <canvas ref={ref} className="block h-full w-full" aria-label="Heatmap likuiditas order book" role="img" />;
}

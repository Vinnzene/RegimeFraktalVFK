"use client";

import { useEffect, useRef, useState } from "react";
import { OrderFlowEngine } from "@/lib/orderflow/engine";

/** Satu mesin per halaman; mulai ulang saat aset, timeframe candle, atau kerapatan berubah. */
export function useOrderFlow(symbol: string, candleMs: number, stepMult: number) {
  const engine = useRef<OrderFlowEngine | null>(null);
  if (!engine.current) engine.current = new OrderFlowEngine();
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const e = engine.current!;
    let frame = 0;
    // Gabungkan banyak pembaruan menjadi satu render per frame animasi.
    const unsub = e.subscribe(() => {
      if (!frame) frame = requestAnimationFrame(() => {
        frame = 0;
        setVersion(e.version);
      });
    });
    void e.start(symbol, candleMs, stepMult);
    return () => {
      unsub();
      cancelAnimationFrame(frame);
      e.stop();
    };
  }, [symbol, candleMs, stepMult]);

  return { engine: engine.current, version };
}

/** Ukuran kanvas mengikuti elemen induk, dengan resolusi layar tinggi. */
export function useCanvasSize() {
  const ref = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0, dpr: 1 });
  useEffect(() => {
    const el = ref.current?.parentElement;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight, dpr: Math.min(window.devicePixelRatio || 1, 2) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, ...size };
}

export function prepare(canvas: HTMLCanvasElement | null, w: number, h: number, dpr: number) {
  if (!canvas || !w || !h) return null;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return ctx;
}

export function fmtPrice(p: number, step: number) {
  // Desimal mengikuti ukuran langkah, termasuk langkah pecahan seperti 2,5.
  const frac = String(Number(step.toPrecision(6))).split(".")[1] ?? "";
  const d = Math.min(6, frac.length);
  return p.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function fmtQty(q: number) {
  if (q >= 1e6) return `${(q / 1e6).toFixed(1)}M`;
  if (q >= 1e3) return `${(q / 1e3).toFixed(1)}k`;
  if (q >= 100) return q.toFixed(0);
  if (q >= 10) return q.toFixed(1);
  return q.toFixed(2);
}

export const AXIS_W = 72;
export const FONT = "11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";

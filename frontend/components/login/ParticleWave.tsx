"use client";

import { useEffect, useRef } from "react";

/** Latar partikel bergelombang. Diam bila pengguna memilih "kurangi gerakan". */
export default function ParticleWave({ className = "" }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let t = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = canvas.clientWidth * dpr;
      canvas.height = canvas.clientHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      const rows = 26;
      const cols = Math.ceil(w / 9);
      for (let j = 0; j < rows; j++) {
        const depth = j / rows;
        for (let i = 0; i < cols; i++) {
          const x = i * 9 + depth * 40;
          const base = h * (0.35 + depth * 0.55);
          const y = base + Math.sin(i * 0.09 + j * 0.35 + t) * (18 + depth * 30) + Math.cos(i * 0.035 - t * 0.6) * 22;
          const a = 0.06 + 0.32 * depth * (0.5 + 0.5 * Math.sin(i * 0.05 + j + t));
          ctx.fillStyle = j % 4 === 0 ? `rgba(255,140,60,${a})` : `rgba(230,226,220,${a * 0.7})`;
          ctx.fillRect(x, y, 1.4 + depth, 1.4 + depth);
        }
      }
    };

    const loop = () => {
      t += 0.006;
      draw();
      raf = requestAnimationFrame(loop);
    };

    resize();
    window.addEventListener("resize", resize);
    if (reduce) draw();
    else loop();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className={className} aria-hidden="true" />;
}

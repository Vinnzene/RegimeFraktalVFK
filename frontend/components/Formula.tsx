"use client";

import { useEffect, useRef } from "react";
import katex from "katex";

/** Render rumus LaTeX dengan KaTeX. */
export default function Formula({ tex, block = true }: { tex: string; block?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    try {
      katex.render(tex, ref.current, {
        displayMode: block,
        throwOnError: false,
        output: "html",
      });
    } catch {
      ref.current.textContent = tex;
    }
  }, [tex, block]);

  return <span ref={ref} className={block ? "block overflow-x-auto py-2 text-txt" : ""} />;
}

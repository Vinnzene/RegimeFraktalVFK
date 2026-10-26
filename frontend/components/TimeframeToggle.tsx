"use client";

import { useAppConfig } from "@/components/ConfigContext";

export default function TimeframeToggle() {
  const { timeframe, setTimeframe, config } = useAppConfig();
  const options = config?.data.timeframes ?? ["1h", "4h"];
  return (
    <div className="inline-flex gap-0.5 rounded-lg border border-edge bg-surface p-0.5" role="group" aria-label="Skala waktu">
      {options.map((tf) => (
        <button
          key={tf}
          onClick={() => setTimeframe(tf)}
          aria-pressed={timeframe === tf}
          className={`rounded-md px-3 py-1 font-mono text-[12px] font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
            timeframe === tf ? "bg-txt text-panel shadow-panel" : "text-txtDim hover:text-txt"
          }`}
        >
          {tf.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

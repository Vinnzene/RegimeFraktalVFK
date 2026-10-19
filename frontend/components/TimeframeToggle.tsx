"use client";

import { useAppConfig } from "@/components/ConfigContext";

export default function TimeframeToggle() {
  const { timeframe, setTimeframe, config } = useAppConfig();
  const options = config?.data.timeframes ?? ["1h", "4h"];
  return (
    <div className="inline-flex overflow-hidden rounded border border-edge">
      {options.map((tf) => (
        <button
          key={tf}
          onClick={() => setTimeframe(tf)}
          className={`px-3 py-1 font-mono text-2xs transition ${
            timeframe === tf
              ? "bg-accent/20 text-accent"
              : "text-txtMuted hover:bg-surface hover:text-txtDim"
          }`}
        >
          {tf.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

/**
 * Ilustrasi grafik untuk halaman login: candlestick, gelombang bercahaya, dan
 * bar volume dalam perspektif. Data dibangkitkan deterministik (dekoratif),
 * bukan harga sungguhan.
 */

const W = 640;
const H = 380;

function rng(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return s / 2147483647;
  };
}

function smooth(points: [number, number][]) {
  // Catmull-Rom -> Bezier agar gelombang halus.
  let d = `M${points[0][0].toFixed(1)},${points[0][1].toFixed(1)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
}

const r = rng(20261020);
const N = 44;
const candles = Array.from({ length: N }, (_, i) => {
  const x = 40 + (i * (W - 80)) / (N - 1);
  const trend = 300 - i * 4.6 - 28 * Math.sin(i / 5.5);
  const open = trend + (r() - 0.5) * 26;
  const close = trend + (r() - 0.55) * 30;
  const high = Math.min(open, close) - 6 - r() * 18;
  const low = Math.max(open, close) + 6 + r() * 18;
  return { x, open, close, high, low, up: close < open };
});

const wave = (amp: number, phase: number, offset: number): [number, number][] =>
  Array.from({ length: 12 }, (_, i) => {
    const x = 20 + (i * (W - 40)) / 11;
    const y = 320 - i * 19 + offset - amp * Math.sin(i / 1.6 + phase);
    return [x, y];
  });

const waves = [
  { pts: wave(26, 0.4, 18), stroke: "url(#hc-orange)", width: 3.2, glow: true },
  { pts: wave(20, 1.6, 52), stroke: "#e9e7e4", width: 2.4, glow: true },
  { pts: wave(30, 2.7, 86), stroke: "#c2531d", width: 2.4, glow: false },
];

const bars = Array.from({ length: 9 }, (_, i) => ({
  x: 400 + i * 24,
  h: 40 + i * 9 + r() * 46,
  warm: i % 3 !== 1,
}));

export default function HeroChart() {
  return (
    <div className="relative mx-auto w-full max-w-[620px] [perspective:1100px]" aria-hidden="true">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full [transform:rotateX(16deg)_rotateY(-18deg)_rotateZ(-3deg)] [transform-origin:50%_70%]"
        style={{ maskImage: "linear-gradient(to bottom, black 70%, transparent)" }}
      >
        <defs>
          <linearGradient id="hc-orange" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" stopColor="#c2410c" />
            <stop offset="0.6" stopColor="#ff7a1a" />
            <stop offset="1" stopColor="#ffc187" />
          </linearGradient>
          <linearGradient id="hc-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#ff7a1a" stopOpacity="0.28" />
            <stop offset="1" stopColor="#ff7a1a" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="hc-bar-warm" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#ff8c3a" />
            <stop offset="1" stopColor="#7c2d12" stopOpacity="0.2" />
          </linearGradient>
          <linearGradient id="hc-bar-cool" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#f1efec" />
            <stop offset="1" stopColor="#6b6f76" stopOpacity="0.15" />
          </linearGradient>
          <filter id="hc-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {Array.from({ length: 9 }, (_, i) => (
          <line key={`h${i}`} x1="0" x2={W} y1={40 + i * 40} y2={40 + i * 40} stroke="#ffffff" strokeOpacity="0.06" />
        ))}
        {Array.from({ length: 13 }, (_, i) => (
          <line key={`v${i}`} y1="0" y2={H} x1={i * 53} x2={i * 53} stroke="#ffffff" strokeOpacity="0.045" />
        ))}

        {bars.map((b) => (
          <rect key={b.x} x={b.x} y={H - 20 - b.h} width="14" height={b.h} rx="2" fill={b.warm ? "url(#hc-bar-warm)" : "url(#hc-bar-cool)"} opacity="0.85" />
        ))}

        <path d={`${smooth(waves[0].pts)} L${W - 20},${H} L20,${H} Z`} fill="url(#hc-area)" />

        {candles.map((c) => (
          <g key={c.x} opacity="0.95">
            <line x1={c.x} x2={c.x} y1={c.high} y2={c.low} stroke={c.up ? "#ff8a3d" : "#d6d3cf"} strokeWidth="1.2" />
            <rect
              x={c.x - 3.5}
              y={Math.min(c.open, c.close)}
              width="7"
              height={Math.max(2, Math.abs(c.close - c.open))}
              rx="1"
              fill={c.up ? "#ff7a1a" : "#e7e5e2"}
            />
          </g>
        ))}

        {waves.map((w, i) => (
          <path
            key={i}
            d={smooth(w.pts)}
            fill="none"
            stroke={w.stroke}
            strokeWidth={w.width}
            strokeLinecap="round"
            filter={w.glow ? "url(#hc-glow)" : undefined}
            opacity={i === 2 ? 0.8 : 1}
          />
        ))}
      </svg>
    </div>
  );
}

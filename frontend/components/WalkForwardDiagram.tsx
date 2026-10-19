"use client";

/**
 * Diagram walk-forward statis (SVG).
 *
 * Bersifat penjelas, bukan interaktif: jendela training bergeser maju dan
 * selalu diikuti purge gap sebelum jendela test, sehingga tidak ada window
 * training yang tumpang tindih dengan window test.
 */
export default function WalkForwardDiagram() {
  const folds = [0, 1, 2, 3];
  const rowH = 34;
  const width = 640;

  return (
    <svg viewBox={`0 0 ${width} ${folds.length * rowH + 34}`} className="w-full">
      <text x={0} y={12} fill="#64748b" fontSize={10}>
        waktu →
      </text>
      {folds.map((f) => {
        const y = 24 + f * rowH;
        const trainW = 240 + f * 60;
        const purgeW = 34;
        const testW = 90;
        return (
          <g key={f}>
            <text x={0} y={y + 13} fill="#64748b" fontSize={10}>
              fold {f + 1}
            </text>
            <rect x={52} y={y} width={trainW} height={18} fill="rgba(59,130,246,0.55)" rx={2} />
            <text x={56} y={y + 13} fill="#e2e8f0" fontSize={9}>
              train
            </text>
            <rect
              x={52 + trainW}
              y={y}
              width={purgeW}
              height={18}
              fill="rgba(239,68,68,0.6)"
              rx={2}
            />
            <text x={54 + trainW} y={y + 13} fill="#fee2e2" fontSize={8}>
              purge
            </text>
            <rect
              x={52 + trainW + purgeW}
              y={y}
              width={testW}
              height={18}
              fill="rgba(34,197,94,0.6)"
              rx={2}
            />
            <text x={56 + trainW + purgeW} y={y + 13} fill="#dcfce7" fontSize={9}>
              test
            </text>
          </g>
        );
      })}
    </svg>
  );
}

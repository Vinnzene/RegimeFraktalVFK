"use client";

import { regimeLabel } from "@/lib/regime";

/**
 * Heatmap matriks transisi P(R_t+1 = j | R_t = i).
 *
 * Dibuat dengan grid CSS, bukan Recharts — Recharts tidak punya tipe heatmap,
 * dan matriks 5x5 terlalu kecil untuk membenarkan dependensi tambahan.
 */
export default function TransitionMatrix({
  categories,
  matrix,
  counts,
}: {
  categories: string[];
  matrix: number[][];
  counts?: number[][];
}) {
  const cell = (v: number) => {
    const a = Math.min(v, 1);
    return `rgba(59,130,246,${0.08 + a * 0.72})`;
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-2xs">
        <thead>
          <tr>
            <th className="p-1 text-left text-txtMuted">dari \ ke</th>
            {categories.map((c) => (
              <th key={c} className="p-1 text-txtDim">
                <div className="mx-auto w-16 leading-tight">{regimeLabel(c)}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {categories.map((row, i) => (
            <tr key={row}>
              <td className="whitespace-nowrap p-1 pr-2 text-txtDim">{regimeLabel(row)}</td>
              {categories.map((col, j) => {
                const v = matrix[i]?.[j] ?? 0;
                return (
                  <td key={col} className="p-0.5">
                    <div
                      className="flex h-9 items-center justify-center rounded font-mono text-txt"
                      style={{ backgroundColor: cell(v) }}
                      title={
                        counts
                          ? `${regimeLabel(row)} → ${regimeLabel(col)}: ${counts[i]?.[j] ?? 0} transisi`
                          : undefined
                      }
                    >
                      {v > 0 ? v.toFixed(2) : "·"}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Alat gambar chart: garis tren, garis horizontal, dan Fibonacci retracement. */

export type DrawTool = "trend" | "hline" | "fib";
export type Point = { time: number; price: number };
export type Drawing =
  | { kind: "hline"; price: number }
  | { kind: "trend"; a: Point; b: Point }
  | { kind: "fib"; a: Point; b: Point };

export const DRAW_TOOLS: { id: DrawTool; label: string; hint: string; clicks: 1 | 2 }[] = [
  { id: "trend", label: "Garis tren", hint: "Klik titik awal lalu titik akhir", clicks: 2 },
  { id: "hline", label: "Garis horizontal", hint: "Klik pada harga yang ingin ditandai", clicks: 1 },
  { id: "fib", label: "Fibonacci", hint: "Klik titik ekstrem pertama lalu kedua", clicks: 2 },
];

export const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];

/** Harga tiap level Fibonacci retracement dari titik a ke b (level 0 = b, level 1 = a). */
export function fibPrices(a: Point, b: Point): { level: number; price: number }[] {
  return FIB_LEVELS.map((level) => ({ level, price: b.price + (a.price - b.price) * level }));
}

/** Candle terdekat untuk waktu tertentu (indeks), memakai pencarian biner pada waktu yang terurut. */
export function nearestIndex(times: number[], t: number): number {
  if (!times.length) return -1;
  let lo = 0, hi = times.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (times[mid] < t) lo = mid + 1;
    else hi = mid;
  }
  if (lo > 0 && Math.abs(times[lo - 1] - t) <= Math.abs(times[lo] - t)) return lo - 1;
  return lo;
}

const KEY = (k: string) => `rf-gambar:${k}`;

export function loadDrawings(key: string): Drawing[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY(key)) ?? "[]");
    return Array.isArray(v) ? v.filter((d) => d && ["hline", "trend", "fib"].includes(d.kind)) : [];
  } catch {
    return [];
  }
}

export function saveDrawings(key: string, list: Drawing[]): void {
  try {
    if (list.length) localStorage.setItem(KEY(key), JSON.stringify(list));
    else localStorage.removeItem(KEY(key));
  } catch {
    // Penyimpanan peramban tidak tersedia: gambar hanya bertahan sampai halaman ditutup.
  }
}

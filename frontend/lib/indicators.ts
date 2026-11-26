/** Indikator chart per kondisi pasar: trend following, mean reversion, dan liquidity heatmap. */

export type IndicatorId = "trend" | "meanrev" | "heatmap";

export type IndicatorDef = {
  id: IndicatorId;
  regime: "persistent" | "anti_persistent" | "random_like";
  family: string;
  name: string;
  short: string;
  how: string[];
  source: string;
};

export const INDICATORS: IndicatorDef[] = [
  {
    id: "trend",
    regime: "persistent",
    family: "Trend following",
    name: "MA 15 + MA 50",
    short: "Dua rata-rata bergerak sederhana untuk mengikuti arah tren.",
    how: [
      "Harga di atas kedua MA dan MA 15 di atas MA 50: tren naik masih berjalan.",
      "Harga di bawah kedua MA dan MA 15 di bawah MA 50: tren turun masih berjalan.",
      "Persilangan MA 15 dan MA 50 ditandai panah: kemungkinan arah tren berganti.",
    ],
    source: "Dihitung dari harga penutupan candle di chart.",
  },
  {
    id: "meanrev",
    regime: "anti_persistent",
    family: "Mean reversion",
    name: "Bollinger Bands (20, 2σ)",
    short: "Pita dua simpangan baku di sekitar MA 20 untuk melihat harga yang menjauh dari rata-ratanya.",
    how: [
      "Harga menembus pita atas: relatif mahal, cenderung kembali ke garis tengah.",
      "Harga menembus pita bawah: relatif murah, cenderung kembali ke garis tengah.",
      "Garis tengah (MA 20) adalah sasaran kembalinya harga.",
    ],
    source: "Dihitung dari harga penutupan candle di chart.",
  },
  {
    id: "heatmap",
    regime: "random_like",
    family: "Likuiditas",
    name: "Liquidity heatmap",
    short: "Kepadatan order beli dan jual yang sedang menunggu di order book, per tingkat harga.",
    how: [
      "Pita terang = banyak order menunggu di harga itu; sering menjadi area pantulan atau tahanan.",
      "Hijau = order beli (bid) di bawah harga, merah = order jual (ask) di atas harga.",
      "Saat pasar acak, level likuiditas lebih berguna daripada sinyal arah.",
    ],
    source: "Order book spot Binance saat ini (5.000 level), diperbarui tiap 15 detik; bukan riwayat.",
  },
];

export const INDICATOR_COLORS = {
  ma15: "#f0b90b",
  ma50: "#a78bfa",
  bb: "#38bdf8",
  bid: [46, 189, 133] as const,
  ask: [246, 70, 93] as const,
};

/** Rata-rata bergerak sederhana; null sampai jendela pertama penuh. */
export function sma(values: number[], n: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= n) sum -= values[i - n];
    if (i >= n - 1) out[i] = sum / n;
  }
  return out;
}

/** Bollinger Bands: tengah = SMA n, pita = tengah ± k × simpangan baku populasi. */
export function bollinger(values: number[], n = 20, k = 2) {
  const mid = sma(values, n);
  const upper: (number | null)[] = new Array(values.length).fill(null);
  const lower: (number | null)[] = new Array(values.length).fill(null);
  for (let i = n - 1; i < values.length; i++) {
    const m = mid[i] as number;
    let ss = 0;
    for (let j = i - n + 1; j <= i; j++) ss += (values[j] - m) ** 2;
    const sd = Math.sqrt(ss / n);
    upper[i] = m + k * sd;
    lower[i] = m - k * sd;
  }
  return { mid, upper, lower };
}

/** Indeks persilangan: "up" saat cepat naik melewati lambat, "down" sebaliknya. */
export function crosses(fast: (number | null)[], slow: (number | null)[]): { i: number; dir: "up" | "down" }[] {
  const out: { i: number; dir: "up" | "down" }[] = [];
  for (let i = 1; i < fast.length; i++) {
    const a0 = fast[i - 1], b0 = slow[i - 1], a1 = fast[i], b1 = slow[i];
    if (a0 == null || b0 == null || a1 == null || b1 == null) continue;
    if (a0 <= b0 && a1 > b1) out.push({ i, dir: "up" });
    else if (a0 >= b0 && a1 < b1) out.push({ i, dir: "down" });
  }
  return out;
}

export type DepthRow = {
  y: number;
  bid: number;
  ask: number;
  /** Harga level dengan kuantitas terbesar di baris itu (per sisi). */
  bidPrice: number;
  askPrice: number;
  bidTop: number;
  askTop: number;
};

/** Kelompokkan level order book per baris piksel (setinggi `rowPx`) di dalam area 0..height. */
export function depthRows(
  bids: [number, number][],
  asks: [number, number][],
  toY: (price: number) => number | null,
  rowPx: number,
  height: number,
): DepthRow[] {
  const rows = new Map<number, DepthRow>();
  const add = (price: number, qty: number, side: "bid" | "ask") => {
    const y = toY(price);
    if (y == null || y < 0 || y >= height) return;
    const k = Math.floor(y / rowPx);
    const r = rows.get(k) ?? { y: k * rowPx, bid: 0, ask: 0, bidPrice: 0, askPrice: 0, bidTop: 0, askTop: 0 };
    r[side] += qty;
    if (side === "bid" && qty > r.bidTop) [r.bidTop, r.bidPrice] = [qty, price];
    if (side === "ask" && qty > r.askTop) [r.askTop, r.askPrice] = [qty, price];
    rows.set(k, r);
  };
  for (const [p, q] of bids) add(p, q, "bid");
  for (const [p, q] of asks) add(p, q, "ask");
  return [...rows.values()].sort((a, b) => a.y - b.y);
}

const STORE_KEY = "rf-indikator";

export function loadActive(): IndicatorId[] {
  try {
    const v = JSON.parse(localStorage.getItem(STORE_KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x): x is IndicatorId => INDICATORS.some((d) => d.id === x)) : [];
  } catch {
    return [];
  }
}

export function saveActive(ids: IndicatorId[]): void {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(ids));
  } catch {
    // Penyimpanan peramban tidak tersedia: pilihan hanya berlaku sampai halaman ditutup.
  }
}

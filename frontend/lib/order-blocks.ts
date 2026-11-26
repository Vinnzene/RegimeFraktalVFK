/**
 * Order Blocks & Breaker Blocks: zona candle terakhir sebelum harga menembus swing,
 * yang berubah menjadi breaker saat ditembus balik.
 *
 * Diadaptasi dari indikator Pine Script "Order Blocks & Breaker Blocks" © LuxAlgo,
 * berlisensi CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/).
 * Perubahan: ditulis ulang dalam TypeScript untuk lightweight-charts; label perubahan polaritas
 * historis tidak disertakan.
 * Berkas ini dilisensikan dengan lisensi yang sama: CC BY-NC-SA 4.0 (non-komersial).
 */

export type Bar = { time: number; open: number; high: number; low: number; close: number; volume: number };

export type OrderBlock = {
  side: "bull" | "bear";
  top: number;
  btm: number;
  /** Waktu candle asal order block. */
  loc: number;
  breaker: boolean;
  /** Waktu saat order block ditembus dan menjadi breaker. */
  breakLoc: number | null;
};

type Swing = { y: number | null; x: number | null; crossed: boolean };

/** Perulangan `for i = a to b` gaya Pine: menurun bila b < a. */
function pineRange(a: number, b: number): number[] {
  const out: number[] = [];
  if (b >= a) for (let i = a; i <= b; i++) out.push(i);
  else for (let i = a; i >= b; i--) out.push(i);
  return out;
}

export function orderBlocks(bars: Bar[], length = 10, showBull = 3, showBear = 3, useBody = false) {
  const hi = (i: number) => (useBody ? Math.max(bars[i].close, bars[i].open) : bars[i].high);
  const lo = (i: number) => (useBody ? Math.min(bars[i].close, bars[i].open) : bars[i].low);
  let os = 0, prevOs = 0;
  let top: Swing = { y: null, x: null, crossed: false };
  let btm: Swing = { y: null, x: null, crossed: false };
  const bull: OrderBlock[] = [], bear: OrderBlock[] = [];

  for (let n = 0; n < bars.length; n++) {
    // Swing: high/low `length` bar lalu dibanding tertinggi/terendah `length` bar terakhir.
    if (n >= length) {
      let upper = -Infinity, lower = Infinity;
      for (let j = n - length + 1; j <= n; j++) {
        upper = Math.max(upper, bars[j].high);
        lower = Math.min(lower, bars[j].low);
      }
      const p = n - length;
      os = bars[p].high > upper ? 0 : bars[p].low < lower ? 1 : os;
      if (os === 0 && prevOs !== 0) top = { y: bars[p].high, x: p, crossed: false };
      if (os === 1 && prevOs !== 1) btm = { y: bars[p].low, x: p, crossed: false };
    }
    prevOs = os;
    const c = bars[n].close, o = bars[n].open, t = bars[n].time;

    // Bullish OB: close menembus swing tinggi → candle dengan low terendah sejak swing.
    if (top.y != null && top.x != null && c > top.y && !top.crossed && n >= 1) {
      top.crossed = true;
      let minima = hi(n - 1), maxima = lo(n - 1), loc = bars[n - 1].time;
      for (const i of pineRange(1, n - top.x - 1)) {
        if (n - i < 0) continue;
        minima = Math.min(lo(n - i), minima);
        if (minima === lo(n - i)) {
          maxima = hi(n - i);
          loc = bars[n - i].time;
        }
      }
      bull.unshift({ side: "bull", top: maxima, btm: minima, loc, breaker: false, breakLoc: null });
    }
    for (let i = bull.length - 1; i >= 0; i--) {
      const e = bull[i];
      if (!e.breaker) {
        if (Math.min(c, o) < e.btm) {
          e.breaker = true;
          e.breakLoc = t;
        }
      } else if (c > e.top) bull.splice(i, 1);
    }

    // Bearish OB: close menembus swing rendah → candle dengan high tertinggi sejak swing.
    if (btm.y != null && btm.x != null && c < btm.y && !btm.crossed && n >= 1) {
      btm.crossed = true;
      let minima = lo(n - 1), maxima = hi(n - 1), loc = bars[n - 1].time;
      for (const i of pineRange(1, n - btm.x - 1)) {
        if (n - i < 0) continue;
        maxima = Math.max(hi(n - i), maxima);
        if (maxima === hi(n - i)) {
          minima = lo(n - i);
          loc = bars[n - i].time;
        }
      }
      bear.unshift({ side: "bear", top: maxima, btm: minima, loc, breaker: false, breakLoc: null });
    }
    for (let i = bear.length - 1; i >= 0; i--) {
      const e = bear[i];
      if (!e.breaker) {
        if (Math.max(c, o) > e.top) {
          e.breaker = true;
          e.breakLoc = t;
        }
      } else if (c < e.btm) bear.splice(i, 1);
    }
  }
  // Hanya beberapa order block terbaru yang ditampilkan.
  return { bull: bull.slice(0, showBull), bear: bear.slice(0, showBear) };
}

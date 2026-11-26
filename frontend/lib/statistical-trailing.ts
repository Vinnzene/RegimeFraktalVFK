/**
 * Statistical Trailing Stop: jarak stop = exp(rata-rata + k × simpangan baku) dari log rentang 10 bar
 * selama 100 bar terakhir; stop mengikuti harga dan berbalik arah saat tersentuh.
 *
 * Diadaptasi dari indikator Pine Script "Statistical Trailing Stop" © LuxAlgo,
 * berlisensi CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/).
 * Perubahan: ditulis ulang dalam TypeScript untuk lightweight-charts; tabel statistik disajikan di bawah chart.
 * Berkas ini dilisensikan dengan lisensi yang sama: CC BY-NC-SA 4.0 (non-komersial).
 */

export type Bar = { time: number; open: number; high: number; low: number; close: number; volume: number };
export type Bias = "long" | "short";

export type SideStats = {
  trades: number;
  pnl: number;
  profit: number;
  loss: number;
  winners: number;
  losers: number;
  winnerBars: number;
  loserBars: number;
};

export type TrailResult = {
  /** Level stop tiap bar (null sebelum data cukup). */
  level: (number | null)[];
  bias: (Bias | null)[];
  anchor: (number | null)[];
  /** Indeks bar saat arah berbalik (stop tersentuh). */
  flips: number[];
  long: SideStats;
  short: SideStats;
  current: { bias: Bias; level: number | null; anchor: number | null; extreme: number | null; since: number | null };
};

const emptyStats = (): SideStats => ({ trades: 0, pnl: 0, profit: 0, loss: 0, winners: 0, losers: 0, winnerBars: 0, loserBars: 0 });

/** Rentang "benar" 10 bar: max(tertinggi − terendah, |tertinggi − close 11 bar lalu|, |terendah − close 11 bar lalu|). */
export function trueRange10(bars: Bar[], n = 10): (number | null)[] {
  return bars.map((_, i) => {
    if (i < n + 1) return null;
    let hi = -Infinity, lo = Infinity;
    for (let j = i - n + 1; j <= i; j++) {
      hi = Math.max(hi, bars[j].high);
      lo = Math.min(lo, bars[j].low);
    }
    const ref = bars[i - n - 1].close;
    return Math.max(hi - lo, Math.abs(hi - ref), Math.abs(lo - ref));
  });
}

/** Jarak stop: exp(rata-rata + k × simpangan baku populasi) dari log rentang selama `dist` bar. */
export function trailDelta(bars: Bar[], dist = 100, k = 2): (number | null)[] {
  const tr = trueRange10(bars);
  const lg = tr.map((v) => (v != null && v > 0 ? Math.log(v) : null));
  return lg.map((_, i) => {
    if (i < dist - 1) return null;
    const win = lg.slice(i - dist + 1, i + 1);
    if (win.some((v) => v == null)) return null;
    const vals = win as number[];
    const m = vals.reduce((s, v) => s + v, 0) / dist;
    const sd = Math.sqrt(vals.reduce((s, v) => s + (v - m) ** 2, 0) / dist);
    return Math.exp(m + k * sd);
  });
}

export function statisticalTrailing(bars: Bar[], dist = 100, k = 2): TrailResult {
  const delta = trailDelta(bars, dist, k);
  const level: (number | null)[] = [], biasOut: (Bias | null)[] = [], anchorOut: (number | null)[] = [];
  const flips: number[] = [];
  const stats = { long: emptyStats(), short: emptyStats() };
  let bias: Bias = "short";
  let lvl: number | null = null, extreme: number | null = null, anchor: number | null = null, since: number | null = null;

  for (let i = 0; i < bars.length; i++) {
    const b = bars[i], d = delta[i];
    const hlc3 = (b.high + b.low + b.close) / 3;
    const target = d == null ? null : bias === "short" ? hlc3 + d : Math.max(hlc3 - d, 0);
    if (lvl == null && target != null) lvl = target;
    if (extreme != null) extreme = bias === "short" ? Math.min(extreme, b.low) : Math.max(extreme, b.high);
    // Stop hanya bergerak searah keuntungan (turun untuk short, naik untuk long).
    lvl = lvl == null || target == null ? null : bias === "short" ? Math.min(lvl, target) : Math.max(lvl, target);

    const hit = lvl != null && ((bias === "short" && b.close >= lvl) || (bias === "long" && b.close <= lvl));
    if (hit) {
      if (anchor != null && since != null) {
        const s = bias === "short" ? stats.short : stats.long;
        const pnl = bias === "short" ? anchor - b.close : b.close - anchor;
        s.trades += 1;
        s.pnl += pnl;
        if (pnl > 0) {
          s.winners += 1;
          s.winnerBars += i - since;
          s.profit += pnl;
        } else {
          s.losers += 1;
          s.loserBars += i - since;
          s.loss += pnl;
        }
      }
      anchor = b.close;
      since = i;
      bias = bias === "short" ? "long" : "short";
      lvl = d == null ? null : bias === "short" ? hlc3 + d : Math.max(hlc3 - d, 0);
      extreme = bias === "short" ? b.low : b.high;
      flips.push(i);
    }
    level.push(lvl);
    biasOut.push(lvl == null ? null : bias);
    anchorOut.push(anchor);
  }
  return { level, bias: biasOut, anchor: anchorOut, flips, long: stats.long, short: stats.short, current: { bias, level: lvl, anchor, extreme, since } };
}

export type StatsRow = {
  trades: number;
  pnl: number;
  profit: number;
  loss: number;
  winners: number;
  losers: number;
  avgWinner: number | null;
  avgLoser: number | null;
  winRate: number | null;
  rr: number | null;
  expectancy: number | null;
  avgBars: number | null;
};

/** Ringkasan statistik per sisi (dan total), sama dengan tabel indikator aslinya. */
export function summarize(s: SideStats): StatsRow {
  const avgWinner = s.winners ? s.profit / s.winners : null;
  const avgLoser = s.losers ? s.loss / s.losers : null;
  const winRate = s.trades ? s.winners / s.trades : null;
  const rr = avgWinner != null && avgLoser ? Math.abs(avgWinner / avgLoser) : null;
  const expectancy = winRate != null && avgWinner != null && avgLoser != null ? winRate * avgWinner - (1 - winRate) * Math.abs(avgLoser) : null;
  return {
    trades: s.trades, pnl: s.pnl, profit: s.profit, loss: s.loss, winners: s.winners, losers: s.losers,
    avgWinner, avgLoser, winRate, rr, expectancy,
    avgBars: s.trades ? (s.winnerBars + s.loserBars) / s.trades : null,
  };
}

export function combine(a: SideStats, b: SideStats): SideStats {
  return {
    trades: a.trades + b.trades, pnl: a.pnl + b.pnl, profit: a.profit + b.profit, loss: a.loss + b.loss,
    winners: a.winners + b.winners, losers: a.losers + b.losers,
    winnerBars: a.winnerBars + b.winnerBars, loserBars: a.loserBars + b.loserBars,
  };
}

/**
 * Volumetric Order Flow Structure: penembusan struktur (BOS/CHoCH) dari pivot, order block
 * berprofil volume pada candle pivot, dan "gelembung manipulasi" saat harga menyapu order block.
 *
 * Diadaptasi dari indikator Pine Script "Volumetric Order Flow Structure" © LuxAlgo,
 * berlisensi CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/).
 * Perubahan: ditulis ulang dalam TypeScript untuk lightweight-charts; opsi "Hide Overlapping Blocks"
 * (bawaan mati) tidak disertakan.
 * Berkas ini dilisensikan dengan lisensi yang sama: CC BY-NC-SA 4.0 (non-komersial).
 */

export type Bar = { time: number; open: number; high: number; low: number; close: number; volume: number };

export type StructureBreak = {
  bullish: boolean;
  kind: "BOS" | "CHoCH";
  level: number;
  /** Indeks candle pivot dan candle penembusan. */
  start: number;
  end: number;
  /** Ujung isian inti, sebanding dengan delta volume candle penembusan. */
  fillEnd: number;
  /** Setengah tebal batang (0,05 × ATR 14). */
  h: number;
};

export type Bubble = { i: number; price: number; high: boolean; volume: number; scale: number };

export type VolBlock = {
  bullish: boolean;
  high: number;
  low: number;
  open: number;
  close: number;
  start: number;
  volume: number;
  /** Bobot 15 baris profil (baris 0 = teratas) dan indeks POC. */
  weights: number[];
  poc: number;
  bubbles: Bubble[];
};

export const PROFILE_ROWS = 15;

/** Bobot baris profil seperti indikator asli: tertinggi di tengah, +5 untuk baris di badan candle. */
export function profileWeights(high: number, low: number, open: number, close: number): { weights: number[]; poc: number } {
  const step = (high - low) / PROFILE_ROWS;
  const bodyMax = Math.max(open, close), bodyMin = Math.min(open, close);
  const weights: number[] = [];
  let poc = -1, maxW = 0;
  for (let i = 0; i < PROFILE_ROWS; i++) {
    let w = Math.trunc(Math.max(2, 12 - Math.abs(i - PROFILE_ROWS / 2) * 1.5));
    const top = high - i * step, btm = top - step;
    if ((top <= bodyMax && top >= bodyMin) || (btm <= bodyMax && btm >= bodyMin)) w += 5;
    weights.push(w);
    if (w > maxW) {
      maxW = w;
      poc = i;
    }
  }
  return { weights, poc };
}

/** Pivot gaya Pine: lebih tinggi dari `len` bar kiri dan tidak lebih rendah dari `len` bar kanan. */
function isPivot(bars: Bar[], c: number, len: number, high: boolean): boolean {
  const v = high ? bars[c].high : bars[c].low;
  for (let j = c - len; j <= c + len; j++) {
    if (j === c) continue;
    const u = high ? bars[j].high : bars[j].low;
    if (high ? (j < c ? u >= v : u > v) : j < c ? u <= v : u < v) return false;
  }
  return true;
}

export function volumetricStructure(bars: Bar[], pivotLen = 3, maxBlocks = 5, sensitivity = 1) {
  const breaks: StructureBreak[] = [];
  let active: VolBlock[] = [];
  let trend = 0;
  let lastPh: number | null = null, lastPhIdx: number | null = null;
  let lastPl: number | null = null, lastPlIdx: number | null = null;
  let prevPh: number | null = null, prevPl: number | null = null;
  let atr: number | null = null;
  const trs: number[] = [];

  for (let n = 0; n < bars.length; n++) {
    const b = bars[n];
    // ATR 14 (RMA dari true range).
    const tr = n === 0 ? b.high - b.low : Math.max(b.high - b.low, Math.abs(b.high - bars[n - 1].close), Math.abs(b.low - bars[n - 1].close));
    trs.push(tr);
    if (n === 13) atr = trs.reduce((s, v) => s + v, 0) / 14;
    else if (n > 13 && atr != null) atr = (atr * 13 + tr) / 14;
    // Volume tertinggi 200 bar (skala gelembung).
    let maxVol = 0;
    for (let j = Math.max(0, n - 199); j <= n; j++) maxVol = Math.max(maxVol, bars[j].volume);

    const c = n - pivotLen;
    if (c >= pivotLen) {
      if (isPivot(bars, c, pivotLen, true)) {
        lastPh = bars[c].high;
        lastPhIdx = c;
      }
      if (isPivot(bars, c, pivotLen, false)) {
        lastPl = bars[c].low;
        lastPlIdx = c;
      }
    }

    // Order block termitigasi dihapus; yang masih aktif bisa mendapat gelembung manipulasi.
    active = active.filter((ob) => {
      const mitigated = ob.bullish ? b.close < ob.low : b.close > ob.high;
      if (mitigated) return false;
      const raidHigh = !ob.bullish && b.high > ob.high && b.close <= ob.high;
      const raidLow = ob.bullish && b.low < ob.low && b.close >= ob.low;
      if (raidHigh || raidLow) {
        ob.bubbles.push({ i: n, price: raidHigh ? b.high : b.low, high: raidHigh, volume: b.volume, scale: maxVol > 0 ? (b.volume / maxVol) * sensitivity : 0 });
      }
      return true;
    });

    const prevClose = n > 0 ? bars[n - 1].close : null;
    const crossUp = lastPh != null && prevPh != null && prevClose != null && b.close > lastPh && prevClose <= prevPh;
    const crossDown = lastPl != null && prevPl != null && prevClose != null && b.close < lastPl && prevClose >= prevPl;

    const draw = (start: number, level: number, bullish: boolean) => {
      const range = Math.max(b.high - b.low, 1e-12);
      const delta = bullish ? (b.close - b.low) / range : (b.high - b.close) / range;
      const dist = n - start;
      const p = bars[start];
      breaks.push({
        bullish,
        kind: (bullish ? trend === -1 : trend === 1) ? "CHoCH" : "BOS",
        level,
        start,
        end: n,
        fillEnd: start + Math.round(dist * Math.max(0.1, delta)),
        h: (atr ?? range) * 0.05,
      });
      const { weights, poc } = profileWeights(p.high, p.low, p.open, p.close);
      active.push({ bullish, high: p.high, low: p.low, open: p.open, close: p.close, start, volume: p.volume, weights, poc, bubbles: [] });
      if (active.length > maxBlocks) active.shift();
    };

    if (crossUp && lastPhIdx != null) {
      draw(lastPhIdx, lastPh as number, true);
      trend = 1;
      lastPh = null;
    }
    if (crossDown && lastPlIdx != null) {
      draw(lastPlIdx, lastPl as number, false);
      trend = -1;
      lastPl = null;
    }
    prevPh = lastPh;
    prevPl = lastPl;
  }
  return { breaks, blocks: active, trend };
}

/** Format volume seperti indikator asli: 1,234K / 2,5M. */
export function formatVolume(v: number): string {
  if (v >= 1e6) return `${+(v / 1e6).toFixed(3)}M`;
  if (v >= 1e3) return `${+(v / 1e3).toFixed(3)}K`;
  return `${Math.round(v)}`;
}

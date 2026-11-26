/**
 * Order Flow VWAP Deviation: VWAP berjangkar dengan pita simpangan baku, stop zones dari pivot,
 * dan profil volume sesi berjalan (POC, baris volume tinggi, dominasi beli/jual).
 *
 * Diadaptasi dari indikator Pine Script "Order Flow VWAP Deviation" © LuxAlgo,
 * berlisensi CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/).
 * Perubahan: ditulis ulang dalam TypeScript untuk lightweight-charts, jangkar sesi memakai UTC
 * (pasar kripto 24 jam), profil volume di chart dihitung dari rentang candle yang terlihat,
 * dan bagian IFVG tidak disertakan.
 * Berkas ini dilisensikan dengan lisensi yang sama: CC BY-NC-SA 4.0 (non-komersial).
 */

export type Bar = { time: number; open: number; high: number; low: number; close: number; volume: number };
export type VwapAnchor = "day" | "week" | "month";

const DAY = 86400;

/** Kunci periode jangkar (UTC); periode baru dimulai saat kunci berubah. */
export function anchorKey(time: number, anchor: VwapAnchor): number {
  const d = Math.floor(time / DAY);
  if (anchor === "day") return d;
  if (anchor === "week") return Math.floor((d + 3) / 7); // minggu dimulai Senin
  const dt = new Date(time * 1000);
  return dt.getUTCFullYear() * 12 + dt.getUTCMonth();
}

/** VWAP berjangkar dari hlc3 dengan pita ± mult × simpangan baku berbobot volume (setara ta.vwap). */
export function anchoredVwap(bars: Bar[], anchor: VwapAnchor, mult = 2) {
  const vwap: (number | null)[] = [], upper: (number | null)[] = [], lower: (number | null)[] = [];
  let key = NaN, sv = 0, spv = 0, sp2v = 0;
  for (const b of bars) {
    const k = anchorKey(b.time, anchor);
    if (k !== key) {
      key = k;
      sv = spv = sp2v = 0;
    }
    const src = (b.high + b.low + b.close) / 3;
    sv += b.volume;
    spv += src * b.volume;
    sp2v += src * src * b.volume;
    if (sv <= 0) {
      vwap.push(null), upper.push(null), lower.push(null);
      continue;
    }
    const m = spv / sv;
    const sd = Math.sqrt(Math.max(sp2v / sv - m * m, 0));
    vwap.push(m);
    upper.push(m + mult * sd);
    lower.push(m - mult * sd);
  }
  return { vwap, upper, lower };
}

export type StopLine = { side: "high" | "low"; price: number; from: number; to: number; active: boolean };
export type StopTrigger = { i: number; side: "high" | "low" };

/**
 * Stop zones: pivot tinggi/rendah (lookback kiri = kanan = n) menjadi garis sampai harga menyentuhnya.
 * Sentuhan dengan volume > 1,2 × rata-rata 20 bar ditandai sebagai "stop terpicu".
 */
export function stopZones(bars: Bar[], n = 50, maxActive = 10) {
  const lines: StopLine[] = [];
  const triggers: StopTrigger[] = [];
  const activeHigh: StopLine[] = [], activeLow: StopLine[] = [];
  let volSum = 0;
  for (let i = 0; i < bars.length; i++) {
    volSum += bars[i].volume;
    if (i >= 20) volSum -= bars[i - 20].volume;
    const avgVol = i >= 19 ? volSum / 20 : null;
    // Pivot di bar i − n terkonfirmasi pada bar i.
    const p = i - n;
    if (p >= n) {
      let isHigh = true, isLow = true;
      for (let j = p - n; j <= p + n && (isHigh || isLow); j++) {
        if (j === p) continue;
        if (bars[j].high >= bars[p].high) isHigh = false;
        if (bars[j].low <= bars[p].low) isLow = false;
      }
      const add = (side: "high" | "low", price: number, list: StopLine[]) => {
        const line: StopLine = { side, price, from: p, to: i, active: true };
        lines.push(line);
        list.unshift(line);
        if (list.length > maxActive) {
          const old = list.pop()!;
          lines.splice(lines.indexOf(old), 1);
        }
      };
      if (isHigh) add("high", bars[p].high, activeHigh);
      if (isLow) add("low", bars[p].low, activeLow);
    }
    const check = (list: StopLine[], hit: (l: StopLine) => boolean, side: "high" | "low") => {
      let fired = false;
      for (let k = list.length - 1; k >= 0; k--) {
        const l = list[k];
        l.to = i;
        if (hit(l)) {
          if (avgVol != null && bars[i].volume > avgVol * 1.2) fired = true;
          l.active = false;
          list.splice(k, 1);
        }
      }
      if (fired) triggers.push({ i, side });
    };
    check(activeHigh, (l) => bars[i].high >= l.price, "high");
    check(activeLow, (l) => bars[i].low <= l.price, "low");
  }
  return { lines, triggers };
}

export type ProfileRow = { low: number; high: number; vol: number; buy: number; sell: number; poc: boolean; stop: boolean; mult: number };

/**
 * Profil volume sesi berjalan dari harga penutupan (sama seperti indikator aslinya).
 * Volume beli/jual diperkirakan dari posisi close di dalam rentang bar.
 */
export function sessionProfile(bars: Bar[], rows = 24, stopThreshold = 1.5): ProfileRow[] {
  if (!bars.length) return [];
  const closes = bars.map((b) => b.close);
  const lo = Math.min(...closes), hi = Math.max(...closes);
  const size = (hi - lo) / rows;
  if (size <= 0) return [];
  const out: ProfileRow[] = Array.from({ length: rows }, (_, i) => ({
    low: lo + i * size, high: lo + (i + 1) * size, vol: 0, buy: 0, sell: 0, poc: false, stop: false, mult: 0,
  }));
  for (const b of bars) {
    const idx = Math.min(rows - 1, Math.max(0, Math.floor((b.close - lo) / size)));
    const range = Math.max(b.high - b.low, 1e-12);
    out[idx].vol += b.volume;
    out[idx].buy += (b.volume * (b.close - b.low)) / range;
    out[idx].sell += (b.volume * (b.high - b.close)) / range;
  }
  const total = out.reduce((s, r) => s + r.vol, 0);
  const avg = total / rows;
  let p = 0;
  out.forEach((r, i) => {
    if (r.vol > out[p].vol) p = i;
  });
  out.forEach((r, i) => {
    r.poc = i === p && r.vol > 0;
    r.mult = avg > 0 ? r.vol / avg : 0;
    r.stop = r.vol > avg * stopThreshold;
  });
  return out;
}

/** Bar sejak awal periode jangkar terakhir. */
export function currentSession(bars: Bar[], anchor: VwapAnchor): Bar[] {
  if (!bars.length) return [];
  const k = anchorKey(bars[bars.length - 1].time, anchor);
  let i = bars.length - 1;
  while (i > 0 && anchorKey(bars[i - 1].time, anchor) === k) i--;
  return bars.slice(i);
}

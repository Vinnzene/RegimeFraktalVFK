/** Unit test Order Blocks & Breaker Blocks (adaptasi LuxAlgo, CC BY-NC-SA 4.0). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { orderBlocks, type Bar } from "./order-blocks.ts";

const bar = (i: number, o: number, h: number, l: number, c: number): Bar => ({ time: i * 3600, open: o, high: h, low: l, close: c, volume: 1 });

/** Puncak di bar 3, turun ke dasar di bar 6, lalu naik menembus puncak di bar 10. */
function rally(): Bar[] {
  const p = [
    [10, 11, 9, 10], [10, 12, 9, 11], [11, 13, 10, 12], [12, 20, 11, 18],
    [18, 18, 14, 15], [15, 16, 12, 13], [13, 14, 8, 9], [9, 12, 9, 11],
    [11, 14, 10, 13], [13, 16, 12, 15], [15, 22, 14, 21], [21, 22, 19, 20],
  ];
  return p.map(([o, h, l, c], i) => bar(i, o, h, l, c));
}

test("Close menembus swing tinggi membentuk bullish OB dari candle ber-low terendah sejak swing", () => {
  const { bull } = orderBlocks(rally(), 3, 3, 3);
  assert.equal(bull.length, 1);
  const ob = bull[0];
  assert.equal(ob.btm, 8); // low terendah (bar 6)
  assert.equal(ob.top, 14); // high candle yang sama
  assert.equal(ob.loc, 6 * 3600);
  assert.equal(ob.breaker, false);
});

test("Bullish OB menjadi breaker saat badan candle turun di bawahnya", () => {
  const bars = rally();
  bars.push(bar(12, 20, 20, 6, 7)); // badan turun di bawah 8
  const { bull } = orderBlocks(bars, 3, 3, 3);
  assert.equal(bull[0].breaker, true);
  assert.equal(bull[0].breakLoc, 12 * 3600);
});

test("Breaker dihapus saat close kembali di atas puncak zona", () => {
  const bars = rally();
  bars.push(bar(12, 20, 20, 6, 7));
  bars.push(bar(13, 7, 16, 7, 15)); // close 15 > top 14
  const { bull } = orderBlocks(bars, 3, 3, 3);
  assert.equal(bull.length, 0);
});

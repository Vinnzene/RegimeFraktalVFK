/** Unit test Statistical Trailing Stop (adaptasi LuxAlgo, CC BY-NC-SA 4.0). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { combine, statisticalTrailing, summarize, trailDelta, trueRange10, type Bar } from "./statistical-trailing.ts";

const flat = (n: number, price = 100, spread = 1): Bar[] =>
  Array.from({ length: n }, (_, i) => ({ time: i * 3600, open: price, high: price + spread, low: price - spread, close: price, volume: 1 }));

test("Rentang 10 bar memakai tertinggi/terendah dan close 11 bar lalu", () => {
  const bars = flat(12);
  bars[11] = { ...bars[11], high: 105, close: 104 };
  const tr = trueRange10(bars);
  assert.equal(tr[10], null);
  assert.equal(tr[11], 6); // 105 − 99
});

test("Jarak stop = exp(rata-rata + k·sd) dari log rentang; konstan bila rentang konstan", () => {
  const d = trailDelta(flat(120), 100, 2);
  assert.equal(d[109], null); // butuh 11 + 100 bar
  assert.ok(Math.abs((d[110] as number) - 2) < 1e-9); // rentang selalu 2 → sd 0
});

test("Stop short berbalik ke long saat close menembus stop, lalu mencatat trade", () => {
  const bars = flat(115);
  // Lonjakan: close menembus stop short (≈ hlc3 + 2) di bar 112 → berbalik long.
  bars[112] = { ...bars[112], high: 110, low: 99, close: 109 };
  // Turun tajam: close menembus stop long → trade long ditutup.
  bars[113] = { ...bars[113], high: 101, low: 90, close: 91 };
  // Harga terus turun, jadi stop short tidak tersentuh.
  bars[114] = { ...bars[114], high: 91, low: 88, close: 89 };
  const r = statisticalTrailing(bars, 100, 2);
  assert.deepEqual(r.flips, [112, 113]);
  assert.equal(r.bias[112], "long");
  assert.equal(r.bias[113], "short");
  // Trade pertama (short) tidak dihitung karena belum ada jangkar; trade long 109 → 91 rugi 18.
  assert.equal(r.short.trades, 0);
  assert.equal(r.long.trades, 1);
  assert.equal(r.long.loss, -18);
  const s = summarize(combine(r.long, r.short));
  assert.equal(s.winRate, 0);
  assert.equal(s.trades, 1);
});

test("Stop long hanya naik, tidak pernah turun", () => {
  const bars = flat(112);
  bars[111] = { ...bars[111], high: 110, low: 99, close: 109 }; // berbalik long
  for (let i = 0; i < 5; i++) bars.push({ time: (112 + i) * 3600, open: 109, high: 110 - i * 0.2, low: 108, close: 109, volume: 1 });
  const r = statisticalTrailing(bars, 100, 2);
  const lv = r.level.slice(111) as number[];
  for (let i = 1; i < lv.length; i++) assert.ok(lv[i] >= lv[i - 1]);
});

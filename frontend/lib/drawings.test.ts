/** Unit test alat gambar chart. */
import assert from "node:assert/strict";
import { test } from "node:test";
import { fibPrices, nearestIndex } from "./drawings.ts";

test("Fibonacci: level 0 di titik kedua, level 1 di titik pertama, 0,5 di tengah", () => {
  const lv = fibPrices({ time: 0, price: 100 }, { time: 1, price: 200 });
  assert.equal(lv.find((x) => x.level === 0)!.price, 200);
  assert.equal(lv.find((x) => x.level === 1)!.price, 100);
  assert.equal(lv.find((x) => x.level === 0.5)!.price, 150);
  assert.ok(Math.abs(lv.find((x) => x.level === 0.618)!.price - 138.2) < 1e-9);
});

test("Candle terdekat dicari dengan pencarian biner", () => {
  const times = [0, 10, 20, 30];
  assert.equal(nearestIndex(times, -5), 0);
  assert.equal(nearestIndex(times, 14), 1);
  assert.equal(nearestIndex(times, 16), 2);
  assert.equal(nearestIndex(times, 99), 3);
  assert.equal(nearestIndex([], 5), -1);
});

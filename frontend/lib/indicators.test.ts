/** Unit test rumus indikator chart. */
import assert from "node:assert/strict";
import { test } from "node:test";
import { bollinger, crosses, depthRows, regimeAtCandles, regimeZSignals, sma, zscore } from "./indicators.ts";

test("Z-score = (harga − SMA) / simpangan baku", () => {
  const z = zscore([2, 4, 4, 4, 5, 5, 7, 9], 8);
  assert.equal(z[7], 2); // (9 − 5) / 2
  assert.equal(z[6], null);
});

test("Sinyal z hanya muncul saat regime diizinkan, keluar saat z melewati 0", () => {
  const z = [0, -1, -2.5, -1, 0.5, 1, 2.5, 1, -0.2];
  const anti = z.map(() => "anti_persistent");
  assert.deepEqual(regimeZSignals(z, anti), [
    { i: 2, kind: "buy" },
    { i: 4, kind: "exit" },
    { i: 6, kind: "sell" },
    { i: 8, kind: "exit" },
  ]);
  // Kondisi lain: tidak ada sinyal sama sekali.
  assert.deepEqual(regimeZSignals(z, z.map(() => "persistent")), []);
});

test("Regime tiap candle mengikuti jendela terakhir yang sudah lewat", () => {
  const r = regimeAtCandles([1, 5, 9], [{ time: 4, regime: "anti_persistent" }, { time: 8, regime: "persistent" }]);
  assert.deepEqual(r, [null, "anti_persistent", "persistent"]);
});

test("SMA null sampai jendela penuh lalu rata-rata bergerak", () => {
  assert.deepEqual(sma([1, 2, 3, 4, 5], 3), [null, null, 2, 3, 4]);
});

test("Bollinger: pita simetris di sekitar SMA dengan simpangan baku populasi", () => {
  const { mid, upper, lower } = bollinger([2, 4, 4, 4, 5, 5, 7, 9], 8, 2);
  assert.equal(mid[7], 5);
  assert.equal(upper[7], 9); // simpangan baku populasi = 2
  assert.equal(lower[7], 1);
  assert.equal(upper[6], null);
});

test("Persilangan MA terdeteksi di dua arah", () => {
  const fast = [null, 1, 3, 2, 0];
  const slow = [null, 2, 2, 2, 2];
  assert.deepEqual(crosses(fast, slow), [
    { i: 2, dir: "up" },
    { i: 4, dir: "down" },
  ]);
});

test("Order book dikelompokkan per baris piksel; di luar area dibuang", () => {
  // Harga 100 → y 0, tiap 1 harga = 10 piksel ke bawah.
  const toY = (p: number) => (100 - p) * 10;
  const rows = depthRows([[99.5, 1], [99.2, 2], [80, 9]], [[99.9, 4], [100.1, 3]], toY, 5, 50);
  // 99,9 → y 1 (baris 0); 99,5 → y 5 dan 99,2 → y 8 (baris 1); 80 dan 100,1 di luar area.
  assert.deepEqual(rows, [
    { y: 0, bid: 0, ask: 4, bidPrice: 0, askPrice: 99.9, bidTop: 0, askTop: 4 },
    { y: 5, bid: 3, ask: 0, bidPrice: 99.2, askPrice: 0, bidTop: 2, askTop: 0 },
  ]);
});

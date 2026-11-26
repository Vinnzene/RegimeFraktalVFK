/** Unit test Volumetric Order Flow Structure (adaptasi LuxAlgo, CC BY-NC-SA 4.0). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { formatVolume, profileWeights, volumetricStructure, type Bar } from "./volumetric-structure.ts";

const bar = (i: number, o: number, h: number, l: number, c: number, v = 10): Bar => ({ time: i * 3600, open: o, high: h, low: l, close: c, volume: v });

/** Pivot tinggi 20 di bar 4, lalu harga menembusnya di bar 10 (BOS naik), lalu menembus pivot rendah (CHoCH turun). */
function series(): Bar[] {
  const p = [
    [10, 11, 9, 10], [10, 12, 9, 11], [11, 13, 10, 12], [12, 15, 11, 14], [14, 20, 13, 15],
    [15, 16, 12, 13], [13, 14, 11, 12], [12, 13, 10, 11], [11, 15, 10, 14], [14, 18, 13, 17],
    [17, 23, 16, 22], [22, 24, 20, 21], [21, 22, 18, 19], [19, 20, 5, 6], [6, 8, 5, 7],
  ];
  return p.map(([o, h, l, c], i) => bar(i, o, h, l, c));
}

test("Penembusan pivot tinggi pertama dicatat sebagai BOS naik beserta order block di candle pivot", () => {
  const { breaks } = volumetricStructure(series(), 3);
  const up = breaks.find((x) => x.bullish)!;
  assert.equal(up.kind, "BOS");
  assert.equal(up.level, 20);
  assert.equal(up.start, 4);
  assert.equal(up.end, 10);
});

test("Penembusan ke bawah setelah tren naik dicatat sebagai CHoCH, dan OB bullish termitigasi", () => {
  const { breaks, blocks } = volumetricStructure(series(), 3);
  const down = breaks.find((x) => !x.bullish);
  assert.ok(down);
  assert.equal(down!.kind, "CHoCH");
  // Close 6 < low OB bullish (13) → OB itu dihapus.
  assert.ok(!blocks.some((b) => b.bullish));
});

test("Bobot profil: POC di baris badan candle dekat tengah", () => {
  const { weights, poc } = profileWeights(20, 10, 14, 16);
  assert.equal(weights.length, 15);
  assert.ok(poc >= 5 && poc <= 9);
  assert.equal(weights[poc], Math.max(...weights));
});

test("Format volume", () => {
  assert.equal(formatVolume(950), "950");
  assert.equal(formatVolume(12345), "12.345K");
  assert.equal(formatVolume(2500000), "2.5M");
});

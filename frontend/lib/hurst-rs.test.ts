/** Unit test Hurst Exponent R/S (adaptasi LuxAlgo, CC BY-NC-SA 4.0). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { rescaledRangeHurst, rollingHurst } from "./hurst-rs.ts";

// Pembangkit acak dengan seed agar hasil tes stabil.
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}
const gauss = (r: () => number) => Math.sqrt(-2 * Math.log(r() || 1e-12)) * Math.cos(2 * Math.PI * r());

test("Inkremen yang selalu berbalik tanda (anti-persisten) memberi H jauh di bawah 0,5", () => {
  const alt = Array.from({ length: 128 }, (_, i) => (i % 2 ? -1 : 1));
  const fit = rescaledRangeHurst(alt);
  assert.ok(fit.h != null && fit.h < 0.2);
  assert.equal(fit.points, 5); // ukuran 128, 64, 32, 16, 8
});

test("Inkremen yang saling menguatkan (persisten) memberi H di atas 0,5", () => {
  const r = rng(1);
  let e = 0;
  const ar = Array.from({ length: 128 }, () => (e = 0.9 * e + gauss(r)));
  const fit = rescaledRangeHurst(ar);
  assert.ok(fit.h != null && fit.h > 0.6);
});

test("H bergulir: kosong sampai jendela penuh, lalu dihaluskan dan diberi status", () => {
  const r = rng(7);
  const closes = [100];
  for (let i = 0; i < 300; i++) closes.push(closes[i] * Math.exp(0.01 * gauss(r)));
  const out = rollingHurst(closes, 128, 5, 0.05);
  assert.equal(out.raw[127], null); // butuh 128 log-return (= 129 harga)
  assert.ok(out.raw[128] != null);
  assert.equal(out.smooth[131], null);
  assert.ok(out.smooth[132] != null);
  const v = out.smooth[200] as number;
  assert.equal(out.state[200], v > 0.55 ? 1 : v < 0.45 ? -1 : 0);
});

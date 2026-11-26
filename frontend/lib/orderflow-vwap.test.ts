/** Unit test Order Flow VWAP Deviation (adaptasi LuxAlgo, CC BY-NC-SA 4.0). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { anchorKey, anchoredVwap, currentSession, sessionProfile, stopZones, type Bar } from "./orderflow-vwap.ts";

const bar = (time: number, price: number, volume = 1, spread = 0): Bar => ({
  time, open: price, high: price + spread, low: price - spread, close: price, volume,
});

test("VWAP berbobot volume dan reset saat hari UTC berganti", () => {
  const bars = [bar(0, 10, 1), bar(3600, 20, 3), bar(86400, 50, 2)];
  const { vwap, upper, lower } = anchoredVwap(bars, "day", 2);
  assert.equal(vwap[0], 10);
  assert.equal(vwap[1], 17.5); // (10×1 + 20×3) / 4
  assert.equal(vwap[2], 50); // hari baru
  // Simpangan baku berbobot: sqrt(E[x²] − E[x]²) = sqrt(325 − 306,25) ≈ 4,33.
  assert.ok(Math.abs((upper[1] as number) - (17.5 + 2 * Math.sqrt(18.75))) < 1e-9);
  assert.ok(Math.abs((lower[1] as number) - (17.5 - 2 * Math.sqrt(18.75))) < 1e-9);
});

test("Jangkar minggu dimulai Senin (UTC)", () => {
  const sunday = Date.UTC(2026, 10, 22) / 1000; // Minggu
  const monday = Date.UTC(2026, 10, 23) / 1000;
  assert.notEqual(anchorKey(sunday, "week"), anchorKey(monday, "week"));
  assert.equal(anchorKey(monday, "week"), anchorKey(monday + 6 * 86400, "week"));
});

test("Pivot tinggi menjadi garis stop sampai disentuh; sentuhan bervolume tinggi memicu tanda", () => {
  // n = 2: puncak di indeks 2, terkonfirmasi di indeks 4; disentuh lagi di indeks 6 dengan volume besar.
  const prices = [1, 2, 5, 2, 1, 2, 6, 1];
  const bars = prices.map((p, i) => bar(i * 3600, p, i === 6 ? 100 : 1));
  const { lines, triggers } = stopZones(bars, 2, 10);
  const high = lines.find((l) => l.side === "high" && l.price === 5);
  assert.ok(high);
  assert.equal(high!.from, 2);
  assert.equal(high!.active, false);
  assert.equal(high!.to, 6);
  // Rata-rata volume 20 bar belum tersedia (< 20 bar), jadi tidak ada tanda.
  assert.deepEqual(triggers, []);
});

test("Profil volume: POC di baris dengan volume terbesar, beli/jual dari posisi close", () => {
  const bars: Bar[] = [
    { time: 0, open: 10, high: 11, low: 9, close: 10, volume: 1 },
    { time: 1, open: 19, high: 20, low: 18, close: 20, volume: 5 },
    { time: 2, open: 19, high: 20, low: 18, close: 20, volume: 1 },
  ];
  const rows = sessionProfile(bars, 2, 1.5);
  assert.equal(rows.length, 2);
  assert.equal(rows[1].poc, true);
  assert.equal(rows[1].vol, 6);
  assert.equal(rows[1].buy, 6); // close di puncak rentang
  assert.equal(rows[1].sell, 0);
  assert.equal(rows[1].stop, true); // 6 > 1,5 × rata-rata 3,5
});

test("Sesi berjalan = bar sejak awal hari terakhir", () => {
  const bars = [bar(86400 - 3600, 1), bar(86400, 2), bar(86400 + 3600, 3)];
  assert.deepEqual(currentSession(bars, "day").map((b) => b.close), [2, 3]);
});

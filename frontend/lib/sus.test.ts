/**
 * Unit test rumus SUS yang dipakai aplikasi (halaman Rekap SUS dan ekspor CSV).
 * Jalankan: `npm test` di folder frontend (Node ≥ 22.6, TypeScript dijalankan langsung).
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { SUS_ITEMS, SusInputError, acceptability, bangorAdjective, summarize, susScore, toCsv, type PublicSus } from "./sus.ts";

test("teks 10 butir SUS sama persis dengan instrumen yang ditetapkan peneliti", () => {
  assert.deepEqual(SUS_ITEMS, [
    "Saya pikir saya akan sering menggunakan sistem/produk ini.",
    "Saya merasa sistem/produk ini terlalu rumit.",
    "Saya merasa sistem/produk ini mudah digunakan.",
    "Saya pikir saya membutuhkan bantuan dari orang teknis untuk dapat menggunakan sistem/produk ini.",
    "Saya menemukan berbagai fungsi dalam sistem/produk ini terintegrasi dengan baik.",
    "Saya merasa terlalu banyak hal yang tidak konsisten dalam sistem/produk ini.",
    "Saya membayangkan bahwa kebanyakan orang akan belajar menggunakan sistem/produk ini dengan sangat cepat.",
    "Saya merasa sistem/produk ini sangat merepotkan/rumit untuk digunakan.",
    "Saya merasa sangat percaya diri menggunakan sistem/produk ini.",
    "Saya perlu mempelajari banyak hal terlebih dahulu sebelum saya bisa mulai menggunakan sistem/produk ini.",
  ]);
});

const odd5even1 = [5, 1, 5, 1, 5, 1, 5, 1, 5, 1];
const odd1even5 = [1, 5, 1, 5, 1, 5, 1, 5, 1, 5];

test("semua jawaban 3 menghasilkan 50", () => {
  assert.equal(susScore(Array(10).fill(3)), 50);
});

test("ganjil 5 dan genap 1 menghasilkan 100", () => {
  assert.equal(susScore(odd5even1), 100);
});

test("ganjil 1 dan genap 5 menghasilkan 0", () => {
  assert.equal(susScore(odd1even5), 0);
});

test("contoh campuran sesuai rumus 2,5 × [Σ(ganjil − 1) + Σ(5 − genap)]", () => {
  // ganjil 4,4,5,4,3 → 3+3+4+3+2 = 15; genap 2,1,2,3,1 → 3+4+3+2+4 = 16; 31 × 2,5 = 77,5
  assert.equal(susScore([4, 2, 4, 1, 5, 2, 4, 3, 3, 1]), 77.5);
});

test("jawaban tidak lengkap ditolak", () => {
  assert.throws(() => susScore([3, 3, 3, 3, 3, 3, 3, 3, 3]), SusInputError);
  assert.throws(() => susScore([3, 3, 3, 3, 3, 3, 3, 3, 3, undefined]), SusInputError);
  assert.throws(() => susScore([]), SusInputError);
  assert.throws(() => susScore(null), SusInputError);
});

test("nilai di luar 1–5 atau bukan bilangan bulat ditolak", () => {
  assert.throws(() => susScore([0, 3, 3, 3, 3, 3, 3, 3, 3, 3]), SusInputError);
  assert.throws(() => susScore([6, 3, 3, 3, 3, 3, 3, 3, 3, 3]), SusInputError);
  assert.throws(() => susScore([2.5, 3, 3, 3, 3, 3, 3, 3, 3, 3]), SusInputError);
  assert.throws(() => susScore(Array(11).fill(3)), SusInputError);
});

test("skala kata sifat Bangor dan rentang penerimaan", () => {
  assert.equal(bangorAdjective(0), "Worst Imaginable");
  assert.equal(bangorAdjective(50), "OK");
  assert.equal(bangorAdjective(68), "Good");
  assert.equal(bangorAdjective(80), "Excellent");
  assert.equal(bangorAdjective(100), "Best Imaginable");
  assert.equal(acceptability(49.9), "Not Acceptable");
  assert.equal(acceptability(50), "Marginal");
  assert.equal(acceptability(70), "Marginal");
  assert.equal(acceptability(70.1), "Acceptable");
});

function resp(code: string, answers: number[], status: PublicSus["status"] = "done"): PublicSus {
  return {
    version: "sus-v1", code, status, consent_at: 1, profile: { role: "Trader ritel", experience_months: 12, age: null },
    visited: { ringkasan: 1, evaluasi: 1, fokus: 1 }, explore_done_at: 2, answers, score: null, feedback: "", submitted_at: 3, demo: false,
  };
}

test("rekap: rata-rata, SD sampel, median, min, maks, jumlah ≥ 68, butir terlemah", () => {
  const s = summarize([
    resp("R01", Array(10).fill(3)), // 50
    resp("R02", odd5even1), // 100
    resp("R03", [4, 2, 4, 1, 5, 2, 4, 3, 3, 1]), // 77,5
    resp("R04", [], "explore"), // belum selesai: tidak dihitung
  ]);
  assert.equal(s.n, 3);
  assert.equal(s.in_progress, 1);
  assert.equal(s.mean, (50 + 100 + 77.5) / 3);
  const m = (50 + 100 + 77.5) / 3;
  assert.ok(Math.abs(s.sd! - Math.sqrt(((50 - m) ** 2 + (100 - m) ** 2 + (77.5 - m) ** 2) / 2)) < 1e-12);
  assert.equal(s.median, 77.5);
  assert.equal(s.min, 50);
  assert.equal(s.max, 100);
  assert.equal(s.at_or_above_68, 2);
  assert.equal(s.items[0].mean, 4); // butir 1: (3 + 5 + 4) / 3
  // Butir 8: 5 − (3+1+3)/3 = 2,67 dan butir 9: (3+5+3)/3 − 1 = 2,67 sama-sama terkecil;
  // bila seri, butir bernomor terkecil yang ditandai.
  assert.ok(Math.abs(s.items[7].contribution - 8 / 3) < 1e-12 && Math.abs(s.items[8].contribution - 8 / 3) < 1e-12);
  assert.equal(s.weakest_item, 8);
});

test("tidak ada butir terlemah bila semua butir menyumbang sama", () => {
  assert.equal(summarize([resp("R01", Array(10).fill(3))]).weakest_item, null);
});

test("CSV tanpa nama/email dan memuat skor", () => {
  const csv = toCsv([resp("R01", Array(10).fill(3))]);
  const [head, row] = csv.trim().split("\n");
  assert.ok(!/email|nama|uid/i.test(head));
  assert.ok(head.endsWith("skor_sus,saran"));
  assert.ok(row.startsWith("R01,done,sus-v1,"));
  assert.ok(row.includes(",3,3,3,3,3,3,3,3,3,3,50,"));
});

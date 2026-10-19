import type { Regime } from "@/lib/regime";

/**
 * Peta regime → strategi. Satu sumber untuk beranda, halaman Strategi, dan
 * (secara terpisah, di backend) pesan Telegram.
 *
 * Masih RANCANGAN: kinerjanya pada aset nyata baru diuji di Fase 2. Setiap
 * tampilan wajib menyertakan label itu.
 */
export type StrategyPlan = { strategy: string; tool: string; action: string; tone: "go" | "wait" };

export const STRATEGY_PLAN: Record<Regime, StrategyPlan> = {
  persistent: {
    strategy: "Trend-following",
    tool: "Trend bot, breakout, MA crossover",
    action: "Ikuti arah gerakan. Masuk saat harga menembus level, keluar dengan trailing stop.",
    tone: "go",
  },
  anti_persistent: {
    strategy: "Mean-reversion",
    tool: "Grid bot, fade Bollinger/RSI",
    action: "Lawan gerakan ekstrem. Masuk di ujung range, ambil untung ke rata-rata, stop ketat.",
    tone: "go",
  },
  random_like: {
    strategy: "Tidak trading",
    tool: "Matikan bot atau posisi minimal",
    action: "Tidak ada pola yang bisa dimanfaatkan; biaya transaksi akan menggerus hasil.",
    tone: "wait",
  },
  uncertain_rule: {
    strategy: "Tunggu konfirmasi",
    tool: "Kurangi posisi",
    action: "Dua alat ukur tidak sepakat. Tunggu sampai kondisi terkonfirmasi beberapa window berturut-turut.",
    tone: "wait",
  },
  uncertain_lowconf: {
    strategy: "Tunggu konfirmasi",
    tool: "Kurangi posisi",
    action: "Model tidak cukup yakin. Tunggu sampai kondisi terkonfirmasi.",
    tone: "wait",
  },
};

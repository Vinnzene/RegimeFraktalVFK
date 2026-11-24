import type { Regime } from "@/lib/regime";

/** Peta regime → strategi beserta bukti Fase 2. */
export type StrategyPlan = {
  strategy: string;
  tool: string;
  action: string;
  tone: "go" | "wait";
  evidence: string;
  verdict: "supported" | "not_supported" | "untested";
};

export const STRATEGY_PLAN: Record<Regime, StrategyPlan> = {
  persistent: {
    strategy: "Trend-following (teori)",
    tool: "Trend bot, breakout, MA crossover",
    action: "Secara teori ikuti arah gerakan. Di BTC 1H kondisi ini sangat jarang terdeteksi (±1% waktu).",
    tone: "go",
    evidence:
      "Belum bisa dibuktikan di BTC 1H: detektor hampir tidak pernah memberi label ini, sehingga sampelnya terlalu sedikit untuk diuji.",
    verdict: "untested",
  },
  anti_persistent: {
    strategy: "Mean-reversion (teori)",
    tool: "Grid bot, fade Bollinger/RSI",
    action: "Harga memang lebih sering berbalik daripada saat acak, tetapi strategi mean-reversion sederhana tetap rugi setelah biaya.",
    tone: "go",
    evidence:
      "Setelah label ini, harga lebih sering berbalik arah dibanding setelah label acak (7 dari 7 kripto, eksploratif). Namun mean-reversion 24 bar di BTC 1H tetap rugi setelah biaya 0,085% per sisi.",
    verdict: "not_supported",
  },
  random_like: {
    strategy: "Tidak trading",
    tool: "Matikan bot atau posisi minimal",
    action: "Tidak ada pola yang bisa dimanfaatkan; biaya transaksi akan menggerus hasil.",
    tone: "wait",
    evidence:
      "Didukung data: di BTC 1H, momentum (Sharpe −2,46) dan mean-reversion (−1,47) sama-sama rugi besar bila dijalankan saat label ini. Menghindari trading di kondisi ini adalah nilai praktis utama detektor.",
    verdict: "supported",
  },
  uncertain_rule: {
    strategy: "Tunggu konfirmasi",
    tool: "Kurangi posisi",
    action: "Dua alat ukur tidak sepakat. Tunggu sampai kondisi terkonfirmasi beberapa window berturut-turut.",
    tone: "wait",
    evidence: "Label dari estimator klasik, bukan dari detektor AI.",
    verdict: "untested",
  },
  uncertain_lowconf: {
    strategy: "Tunggu konfirmasi",
    tool: "Kurangi posisi",
    action: "Model tidak cukup yakin (keyakinan di bawah 75%). Perlakukan seperti kondisi acak: jangan membuka posisi baru.",
    tone: "wait",
    evidence:
      "Pada set validasi BTC, jendela dengan keyakinan ≥ 75% teridentifikasi benar 85,7% (1H) dan 94,8% (4H), lebih tinggi daripada seluruh jendela (61,8% dan 72,5%). Aturan Fase 2 memperlakukan kondisi tidak pasti sama dengan acak: tidak memegang posisi.",
    verdict: "untested",
  },
};

export const VERDICT_META: Record<StrategyPlan["verdict"], { label: string; className: string }> = {
  supported: { label: "Didukung uji Fase 2", className: "border-bullish/40 bg-bullish/10 text-bullish" },
  not_supported: { label: "Tidak didukung setelah biaya", className: "border-warn/40 bg-warn/10 text-warn" },
  untested: { label: "Belum teruji", className: "border-edge bg-surface text-txtMuted" },
};

/** Hasil Fase 2 BTC/USDT 1H (Sharpe tahunan bersih; drawdown maksimum; % waktu memegang posisi). */
export const FASE2_BTC_1H: { key: string; name: string; sharpe: number; maxDd: number; exposure: number; note?: string }[] = [
  { key: "SW", name: "Switching berbasis regime (detektor sintetis Fase 2)", sharpe: -2.18, maxDd: -0.99, exposure: 0.19 },
  { key: "MOM", name: "Momentum 24 bar terus-menerus", sharpe: -2.39, maxDd: -1.0, exposure: 1.0 },
  { key: "MR", name: "Mean-reversion 24 bar terus-menerus", sharpe: -2.04, maxDd: -1.0, exposure: 0.78 },
  { key: "BH", name: "Beli dan tahan", sharpe: 0.97, maxDd: -0.77, exposure: 1.0 },
];

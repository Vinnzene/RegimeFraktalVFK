/** Indikator chart per kondisi pasar: trend following, mean reversion, dan liquidity heatmap. */

export type IndicatorId = "trend" | "meanrev" | "zregime" | "heatmap" | "ofvwap" | "trail" | "hurst" | "orderblocks" | "vofs";

export type IndicatorDef = {
  id: IndicatorId;
  /** "any" = berlaku di semua kondisi (mis. rencana keluar). */
  regime: "persistent" | "anti_persistent" | "random_like" | "any";
  family: string;
  name: string;
  short: string;
  how: string[];
  source: string;
};

export const INDICATORS: IndicatorDef[] = [
  {
    id: "trend",
    regime: "persistent",
    family: "Trend following",
    name: "MA 15 + MA 50",
    short: "Dua rata-rata bergerak sederhana untuk mengikuti arah tren.",
    how: [
      "Harga di atas kedua MA dan MA 15 di atas MA 50: tren naik masih berjalan.",
      "Harga di bawah kedua MA dan MA 15 di bawah MA 50: tren turun masih berjalan.",
      "Persilangan MA 15 dan MA 50 ditandai panah: kemungkinan arah tren berganti.",
    ],
    source: "Dihitung dari harga penutupan candle di chart.",
  },
  {
    id: "meanrev",
    regime: "anti_persistent",
    family: "Mean reversion",
    name: "Bollinger Bands (20, 2σ)",
    short: "Pita dua simpangan baku di sekitar MA 20 untuk melihat harga yang menjauh dari rata-ratanya.",
    how: [
      "Harga menembus pita atas: relatif mahal, cenderung kembali ke garis tengah.",
      "Harga menembus pita bawah: relatif murah, cenderung kembali ke garis tengah.",
      "Garis tengah (MA 20) adalah sasaran kembalinya harga.",
    ],
    source: "Dihitung dari harga penutupan candle di chart.",
  },
  {
    id: "zregime",
    regime: "anti_persistent",
    family: "Mean reversion + filter regime",
    name: "Z-score 20 + filter Cenderung Berbalik",
    short: "Seberapa jauh harga dari rata-rata 20 candle (dalam simpangan baku), dan sinyal hanya saat model mengidentifikasi Cenderung Berbalik.",
    how: [
      "Z ≤ −2 saat kondisi Cenderung Berbalik: sinyal beli (harga jauh di bawah rata-rata).",
      "Z ≥ +2 saat kondisi Cenderung Berbalik: sinyal jual (harga jauh di atas rata-rata).",
      "Z kembali melewati 0: tanda keluar (harga sudah kembali ke rata-rata).",
      "Di kondisi lain, atau saat model ragu (keyakinan < 75%), tidak ada sinyal, karena mean reversion tanpa filter sering kalah dari beli-dan-tahan.",
    ],
    source:
      "Dasar: s-score Avellaneda & Lee (2010) dan filter Hurst < 0,5 Grande dkk. (2024). Garis Z di bagian bawah chart; filter memakai hasil identifikasi AI.",
  },
  {
    id: "heatmap",
    regime: "random_like",
    family: "Likuiditas",
    name: "Liquidity heatmap",
    short: "Kepadatan order beli dan jual yang sedang menunggu di order book, per tingkat harga.",
    how: [
      "Pita terang = banyak order menunggu di harga itu; sering menjadi area pantulan atau tahanan.",
      "Hijau = order beli (bid) di bawah harga, merah = order jual (ask) di atas harga.",
      "Saat pasar acak, level likuiditas lebih berguna daripada sinyal arah.",
    ],
    source: "Order book spot Binance saat ini (5.000 level), diperbarui tiap 15 detik; bukan riwayat.",
  },
  {
    id: "ofvwap",
    regime: "random_like",
    family: "Order flow · VWAP",
    name: "VWAP Sesi & Zona Stop",
    short: "VWAP berjangkar dengan pita ±2σ, stop zones dari pivot, dan profil volume rentang yang terlihat.",
    how: [
      "Garis abu-abu = VWAP, harga rata-rata berbobot volume sejak awal sesi. Koridor arsir di antara garis titik-titik = ±2σ; harga di luar koridor sudah jauh dari harga wajar.",
      "Garis titik-titik merah/hijau tipis = pivot tinggi/rendah 50 candle, tempat stop banyak menumpuk; kotak kecil menandai stop terpicu dengan volume > 1,2× rata-rata.",
      "Profil di ruang kosong kanan (ikut rentang yang terlihat): oranye berlabel POC = volume terbesar; batang lebih pekat = volume tinggi (> 1,5× rata-rata), ujung hijau/merah = dominasi beli/jual.",
    ],
    source:
      "Diadaptasi dari indikator \"Order Flow VWAP Deviation\" © LuxAlgo, lisensi CC BY-NC-SA 4.0 (non-komersial). Sesi = hari UTC (1H) atau minggu (4H); bagian IFVG tidak disertakan.",
  },
  {
    id: "hurst",
    regime: "any",
    family: "Deteksi regime",
    name: "Hurst Bergulir (R/S)",
    short: "Eksponen Hurst bergulir dari log-return 128 candle, dengan metode rescaled range dan pita netral 0,5 ± 0,05.",
    how: [
      "Warna mengikuti warna kondisi pasar di aplikasi. H di atas 0,55 (biru): gerak harga cenderung tren, logika trend following punya dasar statistik.",
      "H di bawah 0,45 (kuning): cenderung berbalik, logika mean reversion punya dasar statistik.",
      "Di dalam pita 0,45–0,55 (abu-abu): menyerupai random walk, tidak ada pola yang bisa diandalkan.",
      "Legenda menampilkan H, regime, dan R² regresi log-log; estimasi pada jendela pendek tetap kasar.",
    ],
    source:
      "Diadaptasi dari indikator \"Hurst Exponent\" © LuxAlgo, lisensi CC BY-NC-SA 4.0 (non-komersial). Berbeda dari label penelitian (jendela 500, R/S + DFA, ambang kuantil data latih).",
  },
  {
    id: "orderblocks",
    regime: "any",
    family: "Struktur pasar",
    name: "Zona Order Block & Breaker",
    short: "Zona candle terakhir sebelum harga menembus swing (order block), yang berubah menjadi breaker saat ditembus balik.",
    how: [
      "Zona hijau (\"Zona beli\") = candle dengan low terendah sebelum harga menembus swing tinggi; sering menjadi area pantulan naik.",
      "Zona merah (\"Zona jual\") = candle dengan high tertinggi sebelum harga menembus swing rendah; sering menjadi area tahanan.",
      "Garis putus-putus = breaker: zona yang sudah ditembus dan berganti fungsi, jadi warnanya ikut berganti (zona beli yang jebol kini menjadi zona jual).",
      "Ditampilkan 3 OB terbaru per arah; swing memakai lookback 10 candle.",
    ],
    source:
      "Diadaptasi dari indikator \"Order Blocks & Breaker Blocks\" © LuxAlgo, lisensi CC BY-NC-SA 4.0 (non-komersial). Label perubahan polaritas historis tidak disertakan.",
  },
  {
    id: "vofs",
    regime: "any",
    family: "Struktur pasar",
    name: "Struktur Pasar & Volume",
    short: "Penembusan struktur (BOS/CHoCH) dari pivot 3 candle, order block berprofil di candle pivot, dan gelembung saat order block disapu.",
    how: [
      "BOS = harga menembus pivot searah tren; CHoCH = menembus berlawanan arah, tanda awal pergantian tren.",
      "Garis tipis di level pivot, dengan ruas tebal di awalnya: makin panjang ruas tebal, makin kuat dominasi pembeli/penjual pada candle penembusan.",
      "Zona tipis dari candle pivot = order block aktif (maks. 5), dengan histogram di kanan; batang oranye = POC.",
      "Lingkaran = harga menyapu order block lalu kembali (manipulasi); makin besar, makin besar volumenya. Angka volume hanya untuk sapuan besar.",
      "Agar chart tetap bersih, hanya 20 penembusan terbaru yang digambar dan hanya 8 terbaru yang diberi label.",
    ],
    source:
      "Diadaptasi dari indikator \"Volumetric Order Flow Structure\" © LuxAlgo, lisensi CC BY-NC-SA 4.0 (non-komersial). Bobot histogram profil mengikuti rumus asli (bentuk, bukan volume per harga).",
  },
  {
    id: "trail",
    regime: "any",
    family: "Exit plan",
    name: "Trailing Stop Statistik",
    short: "Stop yang mengikuti harga, dengan jarak dari sebaran statistik rentang harga 10 candle selama 100 candle terakhir.",
    how: [
      "Garis hijau = stop untuk posisi beli (hanya naik), garis merah = stop untuk posisi jual (hanya turun).",
      "Jarak stop = exp(rata-rata + 2 × simpangan baku) dari log rentang 10 candle: cukup longgar agar tidak tersentuh oleh gerakan biasa.",
      "Close menembus stop: posisi ditutup dan arah berbalik (panah di chart; pembalikan terakhir diberi label Beli/Jual).",
      "Tabel statistik merangkum semua pembalikan di data chart: jumlah trade, win rate, R/R, ekspektasi.",
    ],
    source:
      "Diadaptasi dari indikator \"Statistical Trailing Stop\" © LuxAlgo, lisensi CC BY-NC-SA 4.0 (non-komersial). Statistik dalam satuan harga, tanpa biaya transaksi; bukan hasil backtest penelitian.",
  },
];

export const INDICATOR_COLORS = {
  ma15: "#f0b90b",
  ma50: "#a78bfa",
  bb: "#38bdf8",
  z: "#d4a20a",
  bid: [46, 189, 133] as const,
  ask: [246, 70, 93] as const,
  // Palet bersama indikator struktur & order flow: naik/turun, netral, dan sorotan (POC).
  up: "#2ebd85",
  down: "#f6465d",
  neutral: "#94a3b8",
  highlight: "#ff7a1a",
};

/** Rata-rata bergerak sederhana; null sampai jendela pertama penuh. */
export function sma(values: number[], n: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= n) sum -= values[i - n];
    if (i >= n - 1) out[i] = sum / n;
  }
  return out;
}

/** Bollinger Bands: tengah = SMA n, pita = tengah ± k × simpangan baku populasi. */
export function bollinger(values: number[], n = 20, k = 2) {
  const mid = sma(values, n);
  const upper: (number | null)[] = new Array(values.length).fill(null);
  const lower: (number | null)[] = new Array(values.length).fill(null);
  for (let i = n - 1; i < values.length; i++) {
    const m = mid[i] as number;
    let ss = 0;
    for (let j = i - n + 1; j <= i; j++) ss += (values[j] - m) ** 2;
    const sd = Math.sqrt(ss / n);
    upper[i] = m + k * sd;
    lower[i] = m - k * sd;
  }
  return { mid, upper, lower };
}

/** Z-score harga terhadap SMA n: (harga − SMA) / simpangan baku populasi n candle. */
export function zscore(values: number[], n = 20): (number | null)[] {
  const { mid, upper } = bollinger(values, n, 1);
  return values.map((v, i) => {
    const m = mid[i], u = upper[i];
    if (m == null || u == null) return null;
    const sd = u - m;
    return sd > 0 ? (v - m) / sd : 0;
  });
}

export type ZSignal = { i: number; kind: "buy" | "sell" | "exit" };

/**
 * Sinyal mean reversion berfilter regime.
 * Masuk saat |z| melewati `entry` dan regime candle itu `allowed`; keluar saat z melewati 0.
 */
export function regimeZSignals(z: (number | null)[], regimes: (string | null)[], allowed = "anti_persistent", entry = 2): ZSignal[] {
  const out: ZSignal[] = [];
  let pos: "long" | "short" | null = null;
  for (let i = 1; i < z.length; i++) {
    const a = z[i - 1], b = z[i];
    if (a == null || b == null) continue;
    if (pos === "long" && a < 0 && b >= 0) {
      out.push({ i, kind: "exit" });
      pos = null;
    } else if (pos === "short" && a > 0 && b <= 0) {
      out.push({ i, kind: "exit" });
      pos = null;
    }
    if (pos === null && regimes[i] === allowed) {
      if (a > -entry && b <= -entry) {
        out.push({ i, kind: "buy" });
        pos = "long";
      } else if (a < entry && b >= entry) {
        out.push({ i, kind: "sell" });
        pos = "short";
      }
    }
  }
  return out;
}

/** Regime aktif tiap candle dari deret regime per jendela (regime terakhir yang waktunya ≤ candle). */
export function regimeAtCandles(times: number[], series: { time: number; regime: string }[]): (string | null)[] {
  const sorted = [...series].sort((a, b) => a.time - b.time);
  let p = -1;
  return times.map((t) => {
    while (p + 1 < sorted.length && sorted[p + 1].time <= t) p += 1;
    return p >= 0 ? sorted[p].regime : null;
  });
}

/** Indeks persilangan: "up" saat cepat naik melewati lambat, "down" sebaliknya. */
export function crosses(fast: (number | null)[], slow: (number | null)[]): { i: number; dir: "up" | "down" }[] {
  const out: { i: number; dir: "up" | "down" }[] = [];
  for (let i = 1; i < fast.length; i++) {
    const a0 = fast[i - 1], b0 = slow[i - 1], a1 = fast[i], b1 = slow[i];
    if (a0 == null || b0 == null || a1 == null || b1 == null) continue;
    if (a0 <= b0 && a1 > b1) out.push({ i, dir: "up" });
    else if (a0 >= b0 && a1 < b1) out.push({ i, dir: "down" });
  }
  return out;
}

export type DepthRow = {
  y: number;
  bid: number;
  ask: number;
  /** Harga level dengan kuantitas terbesar di baris itu (per sisi). */
  bidPrice: number;
  askPrice: number;
  bidTop: number;
  askTop: number;
};

/** Kelompokkan level order book per baris piksel (setinggi `rowPx`) di dalam area 0..height. */
export function depthRows(
  bids: [number, number][],
  asks: [number, number][],
  toY: (price: number) => number | null,
  rowPx: number,
  height: number,
): DepthRow[] {
  const rows = new Map<number, DepthRow>();
  const add = (price: number, qty: number, side: "bid" | "ask") => {
    const y = toY(price);
    if (y == null || y < 0 || y >= height) return;
    const k = Math.floor(y / rowPx);
    const r = rows.get(k) ?? { y: k * rowPx, bid: 0, ask: 0, bidPrice: 0, askPrice: 0, bidTop: 0, askTop: 0 };
    r[side] += qty;
    if (side === "bid" && qty > r.bidTop) [r.bidTop, r.bidPrice] = [qty, price];
    if (side === "ask" && qty > r.askTop) [r.askTop, r.askPrice] = [qty, price];
    rows.set(k, r);
  };
  for (const [p, q] of bids) add(p, q, "bid");
  for (const [p, q] of asks) add(p, q, "ask");
  return [...rows.values()].sort((a, b) => a.y - b.y);
}

const STORE_KEY = "rf-indikator";

export function loadActive(): IndicatorId[] {
  try {
    const v = JSON.parse(localStorage.getItem(STORE_KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x): x is IndicatorId => INDICATORS.some((d) => d.id === x)) : [];
  } catch {
    return [];
  }
}

export function saveActive(ids: IndicatorId[]): void {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(ids));
  } catch {
    // Penyimpanan peramban tidak tersedia: pilihan hanya berlaku sampai halaman ditutup.
  }
}

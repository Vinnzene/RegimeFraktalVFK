import { NextResponse } from "next/server";
import { requireUser } from "@/lib/server-user";

export const dynamic = "force-dynamic";

/**
 * Pencarian simbol untuk Analisis Aset, seperti kotak pencarian TradingView:
 * ketik "a" → simbol berawalan A lebih dulu.
 *
 * Binance: daftar pair aktif dari exchangeInfo (±6 MB) disimpan di memori
 * proses dan diperbarui tiap 6 jam, sehingga pencarian berikutnya instan.
 * Yahoo Finance: diteruskan ke API pencarian Yahoo, lalu hasil berawalan
 * kata kunci diurutkan ke atas.
 */

type SymbolItem = { symbol: string; name: string; exchange: string; type: string };

const BINANCE_BASES = ["https://data-api.binance.vision", "https://api.binance.com"];
const BINANCE_TTL = 6 * 3600 * 1000;
// Urutan quote seperti TradingView: pasangan stablecoin paling umum di atas.
const QUOTE_RANK: Record<string, number> = { USDT: 0, FDUSD: 1, USDC: 1, BTC: 2, ETH: 3, BNB: 3 };
const BINANCE_POPULAR = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "PAXGUSDT", "LINKUSDT", "AVAXUSDT"];

const YAHOO_TYPES = new Set(["EQUITY", "ETF", "INDEX", "CURRENCY", "FUTURE", "CRYPTOCURRENCY"]);
const YAHOO_TYPE_LABEL: Record<string, string> = {
  EQUITY: "saham",
  ETF: "ETF",
  INDEX: "indeks",
  CURRENCY: "forex",
  FUTURE: "futures",
  CRYPTOCURRENCY: "kripto",
};
const YAHOO_POPULAR: SymbolItem[] = [
  { symbol: "^JKSE", name: "IDX Composite (IHSG)", exchange: "Jakarta", type: "indeks" },
  { symbol: "BBCA.JK", name: "Bank Central Asia Tbk", exchange: "Jakarta", type: "saham" },
  { symbol: "BBRI.JK", name: "Bank Rakyat Indonesia (Persero) Tbk", exchange: "Jakarta", type: "saham" },
  { symbol: "TLKM.JK", name: "Telkom Indonesia (Persero) Tbk", exchange: "Jakarta", type: "saham" },
  { symbol: "ANTM.JK", name: "Aneka Tambang Tbk", exchange: "Jakarta", type: "saham" },
  { symbol: "GC=F", name: "Gold Futures", exchange: "COMEX", type: "futures" },
  { symbol: "EURUSD=X", name: "EUR/USD", exchange: "CCY", type: "forex" },
  { symbol: "USDIDR=X", name: "USD/IDR", exchange: "CCY", type: "forex" },
  { symbol: "^GSPC", name: "S&P 500", exchange: "SNP", type: "indeks" },
  { symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ", type: "saham" },
];

type BinancePair = { symbol: string; base: string; quote: string; volume: number };
const VOLUME_TTL = 3600 * 1000;
const cache: {
  at: number;
  pairs: BinancePair[] | null;
  loading: Promise<BinancePair[]> | null;
  volumeAt: number;
  volumes: Map<string, number>;
} = ((globalThis as any).__binancePairs ??= { at: 0, pairs: null, loading: null, volumeAt: 0, volumes: new Map() });

/** Volume 24 jam (dalam mata uang quote) untuk mengurutkan pair populer ke atas, seperti TradingView. */
async function refreshVolumes(): Promise<void> {
  if (Date.now() - cache.volumeAt < VOLUME_TTL) return;
  cache.volumeAt = Date.now();
  for (const base of BINANCE_BASES) {
    try {
      const res = await fetch(`${base}/api/v3/ticker/24hr?type=MINI`, { cache: "no-store" });
      if (!res.ok) continue;
      const rows: any[] = await res.json();
      cache.volumes = new Map(rows.map((r) => [r.symbol, Number(r.quoteVolume) || 0]));
      return;
    } catch {
      /* coba alamat berikutnya */
    }
  }
}

async function binancePairs(): Promise<BinancePair[]> {
  if (cache.pairs && Date.now() - cache.at < BINANCE_TTL) return cache.pairs;
  if (cache.loading) return cache.loading;
  cache.loading = (async () => {
    for (const base of BINANCE_BASES) {
      try {
        const res = await fetch(`${base}/api/v3/exchangeInfo?symbolStatus=TRADING`, { cache: "no-store" });
        if (!res.ok) continue;
        const data = await res.json();
        const pairs: BinancePair[] = (data.symbols ?? [])
          .filter((s: any) => s.status === "TRADING" && s.isSpotTradingAllowed !== false)
          .map((s: any) => ({ symbol: s.symbol, base: s.baseAsset, quote: s.quoteAsset, volume: 0 }));
        if (pairs.length) {
          cache.pairs = pairs;
          cache.at = Date.now();
          return pairs;
        }
      } catch {
        /* coba alamat berikutnya */
      }
    }
    return cache.pairs ?? [];
  })().finally(() => {
    cache.loading = null;
  });
  return cache.loading;
}

const binanceItem = (p: BinancePair): SymbolItem => ({ symbol: p.symbol, name: `${p.base} / ${p.quote}`, exchange: "Binance", type: "spot" });

async function searchBinance(q: string): Promise<SymbolItem[]> {
  const [pairs] = await Promise.all([binancePairs(), refreshVolumes()]);
  const vol = (p: BinancePair) => cache.volumes.get(p.symbol) ?? 0;
  if (!q) {
    const bySymbol = new Map(pairs.map((p) => [p.symbol, p]));
    return BINANCE_POPULAR.map((s) => bySymbol.get(s)).filter(Boolean).map((p) => binanceItem(p!));
  }
  const key = q.toUpperCase().replace(/[^A-Z0-9]/g, "");
  return pairs
    .map((p) => ({ p, score: p.symbol.startsWith(key) ? 0 : p.base.startsWith(key) ? 1 : p.symbol.includes(key) ? 2 : -1 }))
    .filter((x) => x.score >= 0)
    .sort(
      (a, b) =>
        a.score - b.score ||
        (QUOTE_RANK[a.p.quote] ?? 9) - (QUOTE_RANK[b.p.quote] ?? 9) ||
        vol(b.p) - vol(a.p) ||
        a.p.symbol.localeCompare(b.p.symbol),
    )
    .slice(0, 40)
    .map((x) => binanceItem(x.p));
}

// Saham IDX yang paling sering dicari. Pencarian Yahoo mengutamakan bursa AS
// ("bb" → BlackBerry), jadi ticker IDX yang cocok ditampilkan lebih dulu.
// Ticker IDX lain tetap ditemukan lewat pencarian Yahoo bila diketik lebih lengkap.
const IDX_STOCKS: [string, string][] = [
  ["BBCA", "Bank Central Asia Tbk"], ["BBRI", "Bank Rakyat Indonesia (Persero) Tbk"], ["BMRI", "Bank Mandiri (Persero) Tbk"],
  ["BBNI", "Bank Negara Indonesia (Persero) Tbk"], ["BBTN", "Bank Tabungan Negara (Persero) Tbk"], ["BRIS", "Bank Syariah Indonesia Tbk"],
  ["BNGA", "Bank CIMB Niaga Tbk"], ["BDMN", "Bank Danamon Indonesia Tbk"], ["ARTO", "Bank Jago Tbk"],
  ["TLKM", "Telkom Indonesia (Persero) Tbk"], ["ISAT", "Indosat Tbk"], ["EXCL", "XLSmart Telecom Sejahtera Tbk"],
  ["TOWR", "Sarana Menara Nusantara Tbk"], ["TBIG", "Tower Bersama Infrastructure Tbk"], ["ASII", "Astra International Tbk"],
  ["UNTR", "United Tractors Tbk"], ["UNVR", "Unilever Indonesia Tbk"], ["ICBP", "Indofood CBP Sukses Makmur Tbk"],
  ["INDF", "Indofood Sukses Makmur Tbk"], ["MYOR", "Mayora Indah Tbk"], ["CPIN", "Charoen Pokphand Indonesia Tbk"],
  ["JPFA", "Japfa Comfeed Indonesia Tbk"], ["KLBF", "Kalbe Farma Tbk"], ["SIDO", "Industri Jamu dan Farmasi Sido Muncul Tbk"],
  ["HMSP", "HM Sampoerna Tbk"], ["GGRM", "Gudang Garam Tbk"], ["AMRT", "Sumber Alfaria Trijaya Tbk"],
  ["MAPI", "Mitra Adiperkasa Tbk"], ["ADRO", "Alamtri Resources Indonesia Tbk"], ["PTBA", "Bukit Asam Tbk"],
  ["ITMG", "Indo Tambangraya Megah Tbk"], ["HRUM", "Harum Energy Tbk"], ["ANTM", "Aneka Tambang Tbk"],
  ["INCO", "Vale Indonesia Tbk"], ["MDKA", "Merdeka Copper Gold Tbk"], ["MBMA", "Merdeka Battery Materials Tbk"],
  ["AMMN", "Amman Mineral Internasional Tbk"], ["MEDC", "Medco Energi Internasional Tbk"], ["PGAS", "Perusahaan Gas Negara Tbk"],
  ["AKRA", "AKR Corporindo Tbk"], ["BRPT", "Barito Pacific Tbk"], ["BREN", "Barito Renewables Energy Tbk"],
  ["TPIA", "Chandra Asri Pacific Tbk"], ["CUAN", "Petrindo Jaya Kreasi Tbk"], ["ESSA", "ESSA Industries Indonesia Tbk"],
  ["SMGR", "Semen Indonesia (Persero) Tbk"], ["INTP", "Indocement Tunggal Prakarsa Tbk"], ["INKP", "Indah Kiat Pulp & Paper Tbk"],
  ["TKIM", "Pabrik Kertas Tjiwi Kimia Tbk"], ["GOTO", "GoTo Gojek Tokopedia Tbk"], ["BUKA", "Bukalapak.com Tbk"],
  ["EMTK", "Elang Mahkota Teknologi Tbk"], ["SCMA", "Surya Citra Media Tbk"], ["BSDE", "Bumi Serpong Damai Tbk"],
  ["CTRA", "Ciputra Development Tbk"], ["PWON", "Pakuwon Jati Tbk"], ["PANI", "Pantai Indah Kapuk Dua Tbk"],
  ["JSMR", "Jasa Marga (Persero) Tbk"], ["MIKA", "Mitra Keluarga Karyasehat Tbk"], ["HEAL", "Medikaloka Hermina Tbk"],
];

function searchIdx(q: string): SymbolItem[] {
  const key = q.toUpperCase().replace(/\.JK$/, "");
  return IDX_STOCKS.filter(([t]) => t.startsWith(key)).map(([t, name]) => ({ symbol: `${t}.JK`, name, exchange: "Jakarta", type: "saham" }));
}

async function searchYahoo(q: string): Promise<SymbolItem[]> {
  if (!q) return YAHOO_POPULAR;
  const idx = searchIdx(q);
  const global = await searchYahooApi(q).catch((e) => {
    if (idx.length) return [] as SymbolItem[];
    throw e;
  });
  const seen = new Set(idx.map((i) => i.symbol));
  return [...idx, ...global.filter((i) => !seen.has(i.symbol))].slice(0, 40);
}

async function searchYahooApi(q: string): Promise<SymbolItem[]> {
  const url = `https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&quotesCount=25&newsCount=0&listsCount=0`;
  const res = await fetch(url, { cache: "no-store", headers: { "User-Agent": "Mozilla/5.0" } }).catch(() => null);
  if (!res || !res.ok) throw new Error("Pencarian Yahoo Finance tidak dapat dihubungi.");
  const data = await res.json();
  const key = q.toUpperCase();
  return (data.quotes ?? [])
    .filter((x: any) => x.symbol && YAHOO_TYPES.has(x.quoteType))
    .map((x: any) => ({
      symbol: String(x.symbol),
      name: String(x.shortname || x.longname || x.symbol).trim(),
      exchange: String(x.exchDisp || x.exchange || ""),
      type: YAHOO_TYPE_LABEL[x.quoteType] ?? String(x.quoteType).toLowerCase(),
    }))
    .map((item: SymbolItem, i: number) => ({ item, i, prefix: item.symbol.toUpperCase().startsWith(key) ? 0 : 1 }))
    .sort((a: any, b: any) => a.prefix - b.prefix || a.i - b.i)
    .map((x: any) => x.item);
}

export async function GET(req: Request) {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const { searchParams } = new URL(req.url);
  const source = searchParams.get("source") === "yahoo" ? "yahoo" : "binance";
  const q = (searchParams.get("q") ?? "").trim().slice(0, 20);
  try {
    const items = source === "binance" ? await searchBinance(q) : await searchYahoo(q);
    return NextResponse.json({ items });
  } catch (e: any) {
    return NextResponse.json({ items: [], error: e.message ?? "Pencarian gagal." }, { status: 502 });
  }
}

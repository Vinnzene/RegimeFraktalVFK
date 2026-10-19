/**
 * Mesin order flow real-time untuk aset kripto Binance (tanpa React).
 *
 * Sumber (mirror market-data Binance yang tidak diblokir jaringan):
 *   REST  https://data-api.binance.vision/api/v3/{depth,aggTrades}
 *   WS    wss://data-stream.binance.vision/stream?streams=<sym>@depth@100ms/<sym>@aggTrade
 *
 * - Order book lokal: snapshot 5.000 level lalu diff berurutan, sesuai prosedur
 *   resmi Binance; celah urutan memicu sinkron ulang.
 * - Heatmap: tiap 500 ms likuiditas buku diringkas per bucket harga menjadi satu
 *   kolom; 1.200 kolom terakhir (10 menit) disimpan. Hanya real-time: order book
 *   historis spot tidak tersedia gratis.
 * - Footprint: transaksi agresif per candle per bucket harga. aggTrade dengan
 *   m=true berarti pembeli adalah maker, jadi penjual yang agresif.
 *   Diisi mundur 30 menit dari REST aggTrades.
 */

const REST = "https://data-api.binance.vision/api/v3";
const WS = "wss://data-stream.binance.vision/stream";
const COLUMN_MS = 500;
const MAX_COLUMNS = 1200;
const MAX_CANDLES = 240;
const BACKFILL_MIN = 30;

export type Side = { b: number; a: number }; // b: jual agresif (kena bid), a: beli agresif (angkat ask)

export type Candle = {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  buy: number;
  sell: number;
  levels: Map<number, Side>; // indeks bucket footprint -> volume
};

export type HeatColumn = {
  t: number;
  bestBid: number;
  bestAsk: number;
  liq: Map<number, number>; // indeks bucket heatmap -> kuantitas di buku
  buyVol: number;
  buyNotional: number;
  sellVol: number;
  sellNotional: number;
};

export type Status = "idle" | "connecting" | "syncing" | "live" | "reconnecting" | "error";

export function niceStep(x: number): number {
  const p = Math.pow(10, Math.floor(Math.log10(x)));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= x) return m * p;
  return 10 * p;
}

type DepthEvent = { U: number; u: number; b: [string, string][]; a: [string, string][] };
type TradeEvent = { a: number; p: string; q: string; T: number; m: boolean };

export class OrderFlowEngine {
  symbol = "";
  status: Status = "idle";
  error: string | null = null;
  candleMs = 60_000;
  footStep = 10;
  heatStep = 2.5;
  bids = new Map<number, number>();
  asks = new Map<number, number>();
  columns: HeatColumn[] = [];
  candles: Candle[] = [];
  lastPrice = 0;
  cvd = 0;
  paused = false;
  version = 0;

  private ws: WebSocket | null = null;
  private lastUpdateId = 0;
  private buffer: DepthEvent[] = [];
  private synced = false;
  private lastSeenTradeId = 0;
  private pending = { buyVol: 0, buyNotional: 0, sellVol: 0, sellNotional: 0 };
  private timer: ReturnType<typeof setInterval> | null = null;
  private retry: ReturnType<typeof setTimeout> | null = null;
  private stopped = true;
  private listeners = new Set<() => void>();

  subscribe(fn: () => void) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit() {
    this.version++;
    this.listeners.forEach((fn) => fn());
  }

  async start(symbol: string, candleMs: number, stepMult: number) {
    this.stop();
    this.stopped = false;
    this.symbol = symbol.toUpperCase();
    this.candleMs = candleMs;
    this.bids.clear();
    this.asks.clear();
    this.columns = [];
    this.candles = [];
    this.cvd = 0;
    this.lastSeenTradeId = 0;
    this.error = null;
    this.setStatus("connecting");
    try {
      const ticker = await fetch(`${REST}/ticker/price?symbol=${this.symbol}`).then((r) => r.json());
      const price = Number(ticker.price);
      this.lastPrice = price;
      this.footStep = niceStep(price * 0.00012) * stepMult;
      this.heatStep = niceStep(price * 0.00003) * stepMult;
      await this.backfillTrades();
      this.connect();
      this.timer = setInterval(() => this.snapshotColumn(), COLUMN_MS);
    } catch (e) {
      this.fail(e);
    }
  }

  stop() {
    this.stopped = true;
    if (this.timer) clearInterval(this.timer);
    if (this.retry) clearTimeout(this.retry);
    this.timer = null;
    this.retry = null;
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
    }
    this.ws = null;
    this.synced = false;
    this.buffer = [];
  }

  setPaused(p: boolean) {
    this.paused = p;
    this.emit();
  }

  private setStatus(s: Status) {
    this.status = s;
    this.emit();
  }

  private fail(e: unknown) {
    this.error = e instanceof Error ? e.message : String(e);
    this.setStatus("error");
  }

  // ---------------------------------------------------------------- transaksi

  private async backfillTrades() {
    const end = Date.now();
    let rows: TradeEvent[] = await fetch(
      `${REST}/aggTrades?symbol=${this.symbol}&startTime=${end - BACKFILL_MIN * 60_000}&endTime=${end}&limit=1000`
    ).then((r) => r.json());
    for (let page = 0; page < 40 && rows.length; page++) {
      for (const t of rows) this.applyTrade(t, false);
      if (rows.length < 1000) break;
      rows = await fetch(`${REST}/aggTrades?symbol=${this.symbol}&fromId=${rows[rows.length - 1].a + 1}&limit=1000`).then((r) =>
        r.json()
      );
    }
  }

  private applyTrade(t: TradeEvent, live: boolean) {
    if (t.a <= this.lastSeenTradeId) return; // duplikat backfill vs stream
    this.lastSeenTradeId = t.a;
    const price = Number(t.p);
    const qty = Number(t.q);
    const start = Math.floor(t.T / this.candleMs) * this.candleMs;
    let c = this.candles[this.candles.length - 1];
    if (!c || c.t !== start) {
      if (c && start < c.t) return;
      c = { t: start, o: price, h: price, l: price, c: price, buy: 0, sell: 0, levels: new Map() };
      this.candles.push(c);
      if (this.candles.length > MAX_CANDLES) this.candles.shift();
    }
    c.h = Math.max(c.h, price);
    c.l = Math.min(c.l, price);
    c.c = price;
    const idx = Math.floor(price / this.footStep);
    const lvl = c.levels.get(idx) ?? { b: 0, a: 0 };
    if (t.m) {
      lvl.b += qty;
      c.sell += qty;
      this.cvd -= qty;
      if (live) {
        this.pending.sellVol += qty;
        this.pending.sellNotional += qty * price;
      }
    } else {
      lvl.a += qty;
      c.buy += qty;
      this.cvd += qty;
      if (live) {
        this.pending.buyVol += qty;
        this.pending.buyNotional += qty * price;
      }
    }
    c.levels.set(idx, lvl);
    this.lastPrice = price;
  }

  // ---------------------------------------------------------------- order book

  private connect() {
    const s = this.symbol.toLowerCase();
    const ws = new WebSocket(`${WS}?streams=${s}@depth@100ms/${s}@aggTrade`);
    this.ws = ws;
    this.synced = false;
    this.buffer = [];
    ws.onopen = () => {
      this.setStatus("syncing");
      void this.loadSnapshot();
    };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data as string);
      if (msg.stream?.endsWith("@aggTrade")) {
        this.applyTrade(msg.data as TradeEvent, true);
      } else if (msg.data) {
        const d = msg.data as DepthEvent;
        if (!this.synced) this.buffer.push(d);
        else this.applyDepth(d);
      }
    };
    ws.onclose = () => this.scheduleReconnect();
    ws.onerror = () => ws.close();
  }

  private scheduleReconnect() {
    if (this.stopped) return;
    this.setStatus("reconnecting");
    this.retry = setTimeout(() => {
      if (!this.stopped) this.connect();
    }, 3000);
  }

  private async loadSnapshot() {
    try {
      const snap = await fetch(`${REST}/depth?symbol=${this.symbol}&limit=5000`).then((r) => r.json());
      this.bids.clear();
      this.asks.clear();
      for (const [p, q] of snap.bids as [string, string][]) this.bids.set(Number(p), Number(q));
      for (const [p, q] of snap.asks as [string, string][]) this.asks.set(Number(p), Number(q));
      this.lastUpdateId = snap.lastUpdateId;
      const queued = this.buffer.filter((e) => e.u > this.lastUpdateId);
      this.buffer = [];
      this.synced = true;
      for (const e of queued) this.applyDepth(e);
      this.setStatus("live");
    } catch (e) {
      this.fail(e);
    }
  }

  private applyDepth(e: DepthEvent) {
    if (e.u <= this.lastUpdateId) return;
    // Event pertama setelah snapshot boleh melompati; sesudahnya wajib berurutan.
    if (e.U > this.lastUpdateId + 1) {
      this.synced = false;
      this.buffer = [e];
      this.setStatus("syncing");
      void this.loadSnapshot();
      return;
    }
    for (const [p, q] of e.b) {
      const qty = Number(q);
      if (qty === 0) this.bids.delete(Number(p));
      else this.bids.set(Number(p), qty);
    }
    for (const [p, q] of e.a) {
      const qty = Number(q);
      if (qty === 0) this.asks.delete(Number(p));
      else this.asks.set(Number(p), qty);
    }
    this.lastUpdateId = e.u;
  }

  bestBid() {
    let best = 0;
    this.bids.forEach((_, p) => (best = p > best ? p : best));
    return best;
  }

  bestAsk() {
    let best = Infinity;
    this.asks.forEach((_, p) => (best = p < best ? p : best));
    return best === Infinity ? 0 : best;
  }

  /** Buku diringkas per bucket `step` untuk tangga order. */
  aggregated(step: number, levels: number) {
    const bb = this.bestBid();
    const ba = this.bestAsk();
    const bids = new Map<number, number>();
    const asks = new Map<number, number>();
    this.bids.forEach((q, p) => {
      const k = Math.floor(p / step);
      if (k >= Math.floor(bb / step) - levels) bids.set(k, (bids.get(k) ?? 0) + q);
    });
    this.asks.forEach((q, p) => {
      const k = Math.floor(p / step);
      if (k <= Math.floor(ba / step) + levels) asks.set(k, (asks.get(k) ?? 0) + q);
    });
    const toRows = (m: Map<number, number>, desc: boolean) =>
      [...m.entries()].sort((x, y) => (desc ? y[0] - x[0] : x[0] - y[0])).slice(0, levels).map(([k, q]) => ({ price: k * step, qty: q }));
    return { bestBid: bb, bestAsk: ba, bids: toRows(bids, true), asks: toRows(asks, false) };
  }

  private snapshotColumn() {
    if (!this.synced || this.paused) {
      this.pending = { buyVol: 0, buyNotional: 0, sellVol: 0, sellNotional: 0 };
      if (!this.paused) this.emit();
      return;
    }
    const liq = new Map<number, number>();
    const add = (p: number, q: number) => {
      const k = Math.floor(p / this.heatStep);
      liq.set(k, (liq.get(k) ?? 0) + q);
    };
    this.bids.forEach((q, p) => add(p, q));
    this.asks.forEach((q, p) => add(p, q));
    this.columns.push({ t: Date.now(), bestBid: this.bestBid(), bestAsk: this.bestAsk(), liq, ...this.pending });
    if (this.columns.length > MAX_COLUMNS) this.columns.shift();
    this.pending = { buyVol: 0, buyNotional: 0, sellVol: 0, sellNotional: 0 };
    this.emit();
  }
}

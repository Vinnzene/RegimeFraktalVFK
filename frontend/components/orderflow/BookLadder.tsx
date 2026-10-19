"use client";

import type { OrderFlowEngine } from "@/lib/orderflow/engine";
import { fmtPrice, fmtQty } from "./useOrderFlow";

const LEVELS = 12;

/** Tangga order book diringkas per bucket footprint, dengan bar kedalaman. */
export default function BookLadder({ engine }: { engine: OrderFlowEngine; version: number }) {
  const step = engine.footStep;
  const book = engine.aggregated(step, LEVELS);
  const max = Math.max(1e-9, ...book.bids.map((r) => r.qty), ...book.asks.map((r) => r.qty));
  const sumBid = book.bids.reduce((s, r) => s + r.qty, 0);
  const sumAsk = book.asks.reduce((s, r) => s + r.qty, 0);
  const ratio = sumBid + sumAsk ? sumBid / (sumBid + sumAsk) : 0.5;
  const spread = book.bestAsk && book.bestBid ? book.bestAsk - book.bestBid : 0;

  const Row = ({ price, qty, side }: { price: number; qty: number; side: "bid" | "ask" }) => (
    <div className="relative flex h-[19px] items-center justify-between px-2 font-mono text-[11px] tabular-nums">
      <div
        className={`absolute inset-y-0.5 right-0 rounded-sm ${side === "bid" ? "bg-bullish/20" : "bg-bearish/20"}`}
        style={{ width: `${(qty / max) * 100}%` }}
      />
      <span className={`relative ${side === "bid" ? "text-bullish" : "text-bearish"}`}>{fmtPrice(price, step)}</span>
      <span className="relative text-txtDim">{fmtQty(qty)}</span>
    </div>
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-edge px-2 py-1.5 text-[11px] text-txtMuted">
        <span>Harga</span>
        <span>Jumlah</span>
      </div>
      <div className="flex-1 overflow-hidden">
        {[...book.asks].reverse().map((r) => (
          <Row key={`a${r.price}`} price={r.price} qty={r.qty} side="ask" />
        ))}
        <div className="my-1 flex items-center justify-between border-y border-edge bg-surface/60 px-2 py-1 font-mono text-[12px]">
          <span className="font-semibold text-accent">{fmtPrice(engine.lastPrice, step / 10)}</span>
          <span className="text-2xs text-txtMuted">spread {fmtPrice(spread, step / 100)}</span>
        </div>
        {book.bids.map((r) => (
          <Row key={`b${r.price}`} price={r.price} qty={r.qty} side="bid" />
        ))}
      </div>
      <div className="border-t border-edge px-2 py-2">
        <div className="mb-1 flex justify-between text-2xs text-txtMuted">
          <span>Bid {(ratio * 100).toFixed(0)}%</span>
          <span>Ask {((1 - ratio) * 100).toFixed(0)}%</span>
        </div>
        <div className="flex h-1.5 overflow-hidden rounded-full">
          <div className="bg-bullish/70" style={{ width: `${ratio * 100}%` }} />
          <div className="flex-1 bg-bearish/70" />
        </div>
        <p className="mt-1 text-2xs text-txtMuted">Ketimpangan {LEVELS} bucket terdekat</p>
      </div>
    </div>
  );
}

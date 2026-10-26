"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { AnalysisSource } from "@/lib/analyses-client";

/**
 * Kotak pencarian simbol ala TradingView: ketik "a", muncul simbol berawalan A.
 * Pengguna memilih dari daftar (klik, atau panah ↑↓ + Enter); simbol yang
 * dikirim selalu berasal dari daftar sumber data, bukan ketikan bebas.
 */

export type SymbolItem = { symbol: string; name: string; exchange: string; type: string };

function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim().toUpperCase();
  if (q && text.toUpperCase().startsWith(q)) {
    return (
      <>
        <span className="text-accent">{text.slice(0, q.length)}</span>
        {text.slice(q.length)}
      </>
    );
  }
  return <>{text}</>;
}

export default function SymbolSearch({
  source,
  value,
  onChange,
}: {
  source: AnalysisSource;
  value: SymbolItem | null;
  onChange: (item: SymbolItem | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SymbolItem[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();

  // Ganti sumber data: pilihan lama tidak berlaku lagi.
  useEffect(() => {
    setQuery("");
    setItems([]);
  }, [source]);

  // Cari dengan jeda singkat agar tidak memanggil server tiap ketukan.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/analyses/symbols?source=${source}&q=${encodeURIComponent(query)}`, { cache: "no-store" });
        const data = await res.json();
        if (cancelled) return;
        setItems(data.items ?? []);
        setError(data.error ?? null);
        setActive(0);
      } catch {
        if (!cancelled) setError("Pencarian gagal dimuat.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, query ? 180 : 0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, source, open]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const pick = (item: SymbolItem) => {
    onChange(item);
    setQuery("");
    setOpen(false);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, Math.max(0, items.length - 1)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      if (open && items[active]) {
        e.preventDefault();
        pick(items[active]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  // Daftar menggulir mengikuti pilihan aktif saat memakai panah.
  useEffect(() => {
    document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active, listId]);

  return (
    <div ref={boxRef} className="relative">
      <div
        className={`flex items-center gap-2 rounded-lg border bg-panel px-3 py-2 transition ${open ? "border-accent" : "border-edge"}`}
        onClick={() => inputRef.current?.focus()}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 text-txtMuted" aria-hidden>
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        {value && !query ? (
          <span className="flex min-w-0 flex-1 items-baseline gap-2">
            <span className="font-mono text-[14px] font-semibold text-txt">{value.symbol}</span>
            <span className="truncate text-[12.5px] text-txtMuted">{value.name}</span>
          </span>
        ) : null}
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            if (value) onChange(null);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
          placeholder={value ? "" : source === "binance" ? "Cari pair, mis. ETH, SOL, BNB…" : "Cari saham, indeks, emas, forex…"}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && items[active] ? `${listId}-${active}` : undefined}
          autoComplete="off"
          spellCheck={false}
          className={`min-w-0 bg-transparent font-mono text-[14px] text-txt outline-none placeholder:font-sans placeholder:text-txtMuted ${value && !query ? "w-6" : "flex-1"}`}
        />
        {loading && <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-edge border-t-accent" aria-hidden />}
      </div>

      {open && (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 overflow-hidden rounded-lg border border-edge bg-panel shadow-pop">
          <div className="border-b border-edge px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider text-txtMuted">
            {query ? `Hasil untuk “${query}”` : "Populer"}
          </div>
          <ul id={listId} role="listbox" className="max-h-80 overflow-y-auto py-1">
            {items.map((item, i) => (
              <li
                key={`${item.symbol}-${item.exchange}`}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(item);
                }}
                className={`flex cursor-pointer items-center gap-3 px-3 py-2 text-[13px] ${i === active ? "bg-surface" : ""}`}
              >
                <span className="w-28 shrink-0 font-mono font-semibold text-txt">
                  <Highlight text={item.symbol} query={query} />
                </span>
                <span className="min-w-0 flex-1 truncate text-txtDim">{item.name}</span>
                <span className="shrink-0 text-[11px] text-txtMuted">
                  {item.type} · {item.exchange}
                </span>
              </li>
            ))}
            {!loading && items.length === 0 && (
              <li className="px-3 py-3 text-[13px] text-txtMuted">{error ?? "Tidak ada simbol yang cocok."}</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

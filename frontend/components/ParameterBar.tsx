"use client";

import { useState } from "react";
import { useAppConfig } from "@/components/ConfigContext";
import TimeframeToggle from "@/components/TimeframeToggle";

/**
 * Bar parameter global.
 *
 * Reproducibility untuk keperluan akademik: semua parameter yang memengaruhi
 * hasil tetap tersedia, tetapi disembunyikan di balik tombol agar tidak
 * membingungkan pembaca awam. Tiap parameter diberi keterangan singkat.
 */
export default function ParameterBar({ showTimeframe = true }: { showTimeframe?: boolean }) {
  const { config, shortHash, loading, error } = useAppConfig();
  const [open, setOpen] = useState(false);

  if (error) {
    return (
      <div className="rounded border border-bearish/40 bg-bearish/10 px-3 py-2 text-[12px] text-bearish">
        Server analisis belum bisa dihubungi ({error}). Pastikan backend FastAPI berjalan di{" "}
        <span className="font-mono">http://localhost:8000</span>, lalu muat ulang halaman.
      </div>
    );
  }
  if (loading || !config) {
    return <div className="h-9 animate-pulse rounded border border-edge bg-panel" />;
  }

  const items: [string, string | number, string][] = [
    ["L", config.analysis.L, "Panjang jendela: jumlah batang harga yang dianalisis sekaligus"],
    ["J", config.analysis.J, "Jumlah level dekomposisi wavelet (SWT)"],
    ["H thr", config.analysis.hurst_threshold.join("/"), "Batas bawah/atas Hurst untuk membagi kondisi"],
    ["α thr", config.analysis.dfa_threshold.join("/"), "Batas bawah/atas DFA untuk membagi kondisi"],
    ["h", config.model.h, "Horizon: berapa batang ke depan yang diprediksi model"],
    ["purge", config.model.purge_gap, "Jarak pengaman antara data latih dan uji agar tidak bocor"],
    ["τ", config.model.tau, "Batas keyakinan minimum model; di bawahnya ditandai 'Model Ragu'"],
    ["input", config.analysis.input, "Jenis data masukan"],
  ];

  return (
    <div className="rounded-md border border-edge bg-panel px-3 py-2">
      <div className="flex flex-wrap items-center gap-3">
        {showTimeframe && (
          <div className="flex items-center gap-2">
            <span className="text-[12px] text-txtDim">Skala waktu:</span>
            <TimeframeToggle />
            <span className="hidden text-[11px] text-txtMuted md:inline">
              1H = tiap batang 1 jam (detail) · 4H = tiap batang 4 jam (lebih halus)
            </span>
          </div>
        )}
        <button
          onClick={() => setOpen((v) => !v)}
          className="ml-auto rounded border border-edge px-2 py-1 text-[11px] text-txtMuted transition hover:border-edgeBright hover:text-txtDim"
        >
          {open ? "Sembunyikan parameter teknis" : "Parameter teknis"}
        </button>
      </div>

      {open && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-edge pt-2">
          {items.map(([k, v, hint]) => (
            <span key={k} className="chip cursor-help" title={hint}>
              {k} <span className="text-txt">{v}</span>
            </span>
          ))}
          <span className="ml-auto font-mono text-2xs text-txtMuted" title="Sidik jari konfigurasi">
            {shortHash}
          </span>
        </div>
      )}
    </div>
  );
}

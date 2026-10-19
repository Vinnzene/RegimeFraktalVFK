"use client";

import { useEffect, useState } from "react";
import { REGIME_META, REGIME_PLAIN, type Regime } from "@/lib/regime";

const STORAGE_KEY = "howto-read-dismissed";
const MAIN: Regime[] = ["persistent", "random_like", "anti_persistent", "uncertain_rule"];

/**
 * Panduan singkat untuk pengunjung pertama kali.
 *
 * Terbuka otomatis pada kunjungan pertama, lalu ingat pilihan pengguna lewat
 * localStorage supaya tidak mengganggu pemakai yang sudah paham.
 */
export default function HowToRead() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(localStorage.getItem(STORAGE_KEY) !== "1");
  }, []);

  const toggle = () => {
    setOpen((v) => {
      localStorage.setItem(STORAGE_KEY, v ? "1" : "0");
      return !v;
    });
  };

  return (
    <section className="rounded-md border border-persistent/30 bg-persistent/5">
      <button
        onClick={toggle}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-[13px] font-medium text-txt"
      >
        <span className={`text-txtMuted transition-transform ${open ? "rotate-90" : ""}`}>▸</span>
        Cara membaca dashboard ini
        {!open && <span className="text-[11px] font-normal text-txtMuted">— klik untuk panduan singkat</span>}
      </button>

      {open && (
        <div className="space-y-4 border-t border-persistent/20 px-4 pb-4 pt-3 text-[13px] leading-relaxed text-txtDim">
          <p>
            Dashboard ini <b className="text-txt">tidak menebak harga naik atau turun</b>. Yang diukur
            adalah <b className="text-txt">sifat gerakan</b> harga Bitcoin: apakah gerakannya cenderung
            berlanjut, acak, atau bolak-balik. Sifat ini disebut <i>regime</i>.
          </p>

          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {MAIN.map((k) => (
              <div key={k} className="rounded border border-edge bg-panel p-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block h-3 w-3 rounded-sm ${k === "uncertain_rule" ? "pattern-diagonal" : ""}`}
                    style={{
                      backgroundColor: k === "uncertain_rule" ? "transparent" : REGIME_META[k].color,
                      border: `1px solid ${REGIME_META[k].color}`,
                    }}
                  />
                  <span className="font-medium text-txt">{REGIME_PLAIN[k].name}</span>
                </div>
                <p className="mt-1 text-[12px]">{REGIME_PLAIN[k].summary}</p>
                <p className="mt-1 text-[11px] italic text-txtMuted">{REGIME_PLAIN[k].analogy}</p>
              </div>
            ))}
          </div>

          <ol className="list-decimal space-y-1 pl-5 text-[12px]">
            <li>
              <b className="text-txt">Kartu atas</b> menunjukkan kondisi pasar terbaru beserta artinya.
            </li>
            <li>
              <b className="text-txt">Grafik harga</b> diberi latar berwarna sesuai kondisi pada saat itu.
              Arahkan kursor ke grafik untuk melihat harga dan kondisi pada titik tertentu.
            </li>
            <li>
              <b className="text-txt">Tombol 1H / 4H</b> mengganti sudut pandang: tiap batang mewakili 1 jam
              atau 4 jam. 4H lebih tenang, 1H lebih detail.
            </li>
            <li>
              <b className="text-txt">Meteran Hurst &amp; DFA</b> adalah dua alat ukur. Penanda di zona biru
              berarti tren berlanjut, abu-abu acak, kuning cenderung berbalik.
            </li>
          </ol>

          <p className="text-[11px] text-txtMuted">
            Hasil ini berasal dari analisis statistik data historis, bukan saran investasi.
          </p>
        </div>
      )}
    </section>
  );
}

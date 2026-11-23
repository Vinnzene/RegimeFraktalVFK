"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

/**
 * Panduan pertama kali membuka aplikasi: sorotan (spotlight) pada bagian penting
 * halaman Ringkasan dan menu, satu per satu, dengan penjelasan singkat.
 *
 * - Muncul otomatis sekali per browser saat pertama membuka Ringkasan ("/").
 * - Dapat diulang lewat tombol "Panduan" di header (event `rfraktal:tour`).
 * - Elemen ditandai dengan atribut `data-tour="..."`. Bila elemen tidak ada
 *   (mis. data belum dimuat), kartu tampil di tengah layar.
 */

const STORAGE_KEY = "rfraktal_tour_v1";
export const TOUR_EVENT = "rfraktal:tour";

/** Buka panduan dari komponen mana pun. */
export function startTour() {
  window.dispatchEvent(new Event(TOUR_EVENT));
}

type Step = {
  /** Kandidat `data-tour`; dipakai yang pertama terlihat. Kosong = kartu di tengah. */
  target?: string[];
  title: string;
  body: React.ReactNode;
  only?: "desktop" | "mobile";
};

const STEPS: Step[] = [
  {
    title: "Selamat datang di RFraktal",
    body: (
      <>
        <p>
          RFraktal mengenali <b>sifat gerakan pasar</b> BTC/USDT saat ini: <b>Tren Berlanjut</b>, <b>Acak / Tanpa Pola</b>, atau{" "}
          <b>Cenderung Berbalik</b>, memakai model AI <b>Hybrid Attention-BiLSTM</b>: sekuens statistik persistensi (Hurst, DFA) digabung dengan
          fitur struktural, termasuk energi wavelet (SWT).
        </p>
        <p className="mt-2">Panduan singkat ini menunjukkan bagian-bagian penting. Sekitar satu menit.</p>
        <p className="mt-2 text-txtMuted">Bersifat edukatif, bukan sinyal beli atau jual.</p>
      </>
    ),
  },
  {
    target: ["overview"],
    title: "Kondisi pasar sekarang",
    body: (
      <>
        <p>Kesimpulan utama ada di sini: kondisi pasar menurut model, beserta tingkat keyakinannya.</p>
        <p className="mt-2">
          Bila keyakinan di bawah ambang, label ditandai <b>ragu</b>. Chip &quot;1H &amp; 4H sepakat&quot; menunjukkan apakah dua skala waktu
          memberi kesimpulan yang sama.
        </p>
      </>
    ),
  },
  {
    target: ["timeframe"],
    title: "Pilih skala waktu",
    body: <p>Ganti antara 1 jam (1H) dan 4 jam (4H). Seluruh halaman ikut menyesuaikan skala yang dipilih.</p>,
  },
  {
    target: ["chart"],
    title: "Grafik harga dan pita kondisi",
    body: (
      <>
        <p>Warna latar grafik menunjukkan kondisi pasar pada saat itu, jadi Anda bisa melihat kapan pasar cenderung berlanjut, berbalik, atau acak.</p>
        <p className="mt-2">Tombol 1D–ALL mengubah rentang waktu; gulir di atas grafik untuk zoom.</p>
      </>
    ),
  },
  {
    target: ["nav-pasar"],
    only: "desktop",
    title: "Menu Pasar",
    body: (
      <p>
        Ringkasan, uji Walk-Forward 2019–2026 pada 12 aset, <b>Analisis Aset</b> untuk pair atau ticker lain (Binance, Yahoo; 10 kali per hari),
        Analisa Teknikal, dan Order Flow Live.
      </p>
    ),
  },
  {
    target: ["nav-strategi"],
    only: "desktop",
    title: "Menu Strategi",
    body: (
      <p>
        Strategi yang cocok untuk tiap kondisi, <b>Panduan Setup</b> (perlu persetujuan admin), dan <b>Notifikasi Telegram</b> untuk menerima pesan saat
        kondisi pasar berganti serta ringkasan setiap pagi.
      </p>
    ),
  },
  {
    target: ["nav-riset"],
    only: "desktop",
    title: "Menu Riset",
    body: (
      <p>
        Bukti di balik model: Hasil Uji Identifikasi, Walk-Forward Multi-Aset, Hurst-DFA klasik, multifraktal, wavelet, dan Fokus Model (bobot attention).
        Menu bertanda <b>Terkunci</b> hanya terbuka setelah disetujui pemilik.
      </p>
    ),
  },
  {
    target: ["nav-mobile"],
    only: "mobile",
    title: "Semua menu",
    body: (
      <p>
        Ketuk <b>Menu</b> untuk membuka semua halaman: <b>Pasar</b> (ringkasan, analisis aset lain), <b>Strategi</b> (strategi per kondisi, notifikasi
        Telegram), <b>Riset</b> (hasil uji dan bukti model), dan <b>Tentang</b> (metodologi).
      </p>
    ),
  },
  {
    target: ["user"],
    title: "Akun Anda",
    body: <p>Status akun, notifikasi Telegram, dan tombol keluar. Ganti tema terang/gelap dengan tombol di sebelahnya.</p>,
  },
  {
    target: ["help"],
    title: "Selesai",
    body: <p>Buka panduan ini lagi kapan saja lewat tombol ini. Selamat mencoba.</p>,
  },
];

type Rect = { top: number; left: number; width: number; height: number };
const PAD = 6;
const CARD_W = 340;

function visibleTarget(names: string[] | undefined): HTMLElement | null {
  for (const name of names ?? []) {
    for (const el of Array.from(document.querySelectorAll<HTMLElement>(`[data-tour="${name}"]`))) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) return el;
    }
  }
  return null;
}

function readDone(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "done";
  } catch {
    return false;
  }
}

function writeDone() {
  try {
    window.localStorage.setItem(STORAGE_KEY, "done");
  } catch {
    /* penyimpanan diblokir: panduan bisa muncul lagi, tidak apa-apa */
  }
}

export default function GuidedTour() {
  const pathname = usePathname();
  const router = useRouter();
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const [vw, setVw] = useState(0);
  const [vh, setVh] = useState(0);
  const pending = useRef(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const [cardH, setCardH] = useState(220);

  const begin = useCallback(() => {
    const desktop = window.innerWidth >= 1024;
    setSteps(STEPS.filter((s) => !s.only || s.only === (desktop ? "desktop" : "mobile")));
    setI(0);
  }, []);

  const finish = useCallback(() => {
    writeDone();
    setSteps(null);
    setRect(null);
  }, []);

  // Otomatis sekali per browser di halaman Ringkasan, setelah data sempat dimuat.
  useEffect(() => {
    if (pathname !== "/") return;
    if (pending.current) {
      pending.current = false;
      const t = setTimeout(begin, 600);
      return () => clearTimeout(t);
    }
    if (readDone()) return;
    const t = setTimeout(begin, 1200);
    return () => clearTimeout(t);
  }, [pathname, begin]);

  // Tombol "Panduan": dari halaman lain, pindah dulu ke Ringkasan.
  useEffect(() => {
    const onStart = () => {
      if (window.location.pathname !== "/") {
        pending.current = true;
        router.push("/");
      } else begin();
    };
    window.addEventListener(TOUR_EVENT, onStart);
    return () => window.removeEventListener(TOUR_EVENT, onStart);
  }, [router, begin]);

  const step = steps?.[i];

  // Cari elemen sasaran (menunggu sebentar bila data belum tampil), gulir ke sana, lalu ukur.
  useEffect(() => {
    if (!step) return;
    let cancelled = false;
    let tries = 0;
    const locate = () => {
      if (cancelled) return;
      const el = visibleTarget(step.target);
      if (!el && step.target && tries++ < 15) {
        setTimeout(locate, 200);
        return;
      }
      if (!el) {
        setRect(null);
        return;
      }
      const r0 = el.getBoundingClientRect();
      const fits = r0.top >= 64 && r0.bottom <= window.innerHeight - 16;
      if (!fits) el.scrollIntoView({ block: r0.height > window.innerHeight * 0.6 ? "start" : "center", behavior: "smooth" });
      setTimeout(() => {
        if (cancelled) return;
        const r = el.getBoundingClientRect();
        setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
      }, fits ? 0 : 380);
    };
    setRect(null);
    locate();
    return () => {
      cancelled = true;
    };
  }, [step]);

  // Ikuti perubahan ukuran layar dan guliran.
  useEffect(() => {
    if (!step) return;
    const update = () => {
      setVw(window.innerWidth);
      setVh(window.innerHeight);
      const el = visibleTarget(step.target);
      if (el) {
        const r = el.getBoundingClientRect();
        setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
      }
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [step]);

  useLayoutEffect(() => {
    if (cardRef.current) setCardH(cardRef.current.offsetHeight);
  });

  useEffect(() => {
    if (step) nextRef.current?.focus({ preventScroll: true });
  }, [step]);

  const next = useCallback(() => {
    if (!steps) return;
    if (i >= steps.length - 1) finish();
    else setI(i + 1);
  }, [steps, i, finish]);
  const prev = useCallback(() => setI((v) => Math.max(0, v - 1)), []);

  useEffect(() => {
    if (!steps) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
      else if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [steps, next, prev, finish]);

  if (!steps || !step) return null;

  // Posisi kartu: di bawah sasaran bila muat, di atas bila tidak, atau menempel di bawah layar.
  const w = Math.min(CARD_W, vw - 32);
  let style: React.CSSProperties;
  if (!rect) {
    style = { top: Math.max(16, (vh - cardH) / 2), left: Math.max(16, (vw - w) / 2) };
  } else {
    const below = rect.top + rect.height + PAD + 12;
    const above = rect.top - PAD - 12 - cardH;
    const left = Math.min(Math.max(16, rect.left + rect.width / 2 - w / 2), vw - w - 16);
    if (below + cardH <= vh - 12) style = { top: below, left };
    else if (above >= 12) style = { top: above, left };
    else style = { bottom: 16, left: Math.max(16, (vw - w) / 2) };
  }

  const last = i === steps.length - 1;
  return (
    <div className="fixed inset-0 z-[100]" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      {/* Lapisan penghalang: klik di luar kartu tidak mengubah halaman di belakangnya. */}
      <div className="absolute inset-0" onClick={(e) => e.stopPropagation()} />
      {rect ? (
        <div
          className="pointer-events-none absolute rounded-lg ring-2 ring-accent transition-all duration-200"
          style={{
            top: rect.top - PAD,
            left: rect.left - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
            boxShadow: "0 0 0 9999px rgba(8, 12, 20, 0.62)",
          }}
        />
      ) : (
        <div className="pointer-events-none absolute inset-0 bg-[rgba(8,12,20,0.62)]" />
      )}

      <div
        ref={cardRef}
        className="absolute rounded-xl border border-edge bg-panel p-4 text-[13px] leading-relaxed text-txtDim shadow-pop"
        style={{ ...style, width: w }}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="text-[11px] font-medium text-txtMuted">
            Panduan · {i + 1} dari {steps.length}
          </div>
          <button type="button" onClick={finish} className="text-[12px] text-txtMuted hover:text-txt">
            Lewati
          </button>
        </div>
        <h2 id="tour-title" className="mt-1 text-[15px] font-semibold text-txt">
          {step.title}
        </h2>
        <div className="mt-1.5">{step.body}</div>
        <div className="mt-4 flex items-center justify-between gap-2">
          <div className="flex gap-1" aria-hidden>
            {steps.map((_, k) => (
              <span key={k} className={`h-1.5 rounded-full transition-all ${k === i ? "w-4 bg-accent" : "w-1.5 bg-edge"}`} />
            ))}
          </div>
          <div className="flex gap-2">
            {i > 0 && (
              <button type="button" onClick={prev} className="rounded-md border border-edge px-3 py-1.5 text-[12.5px] text-txtDim hover:text-txt">
                Kembali
              </button>
            )}
            <button
              ref={nextRef}
              type="button"
              onClick={next}
              className="rounded-md bg-txt px-3.5 py-1.5 text-[12.5px] font-semibold text-panel hover:opacity-90"
            >
              {i === 0 ? "Mulai" : last ? "Selesai" : "Lanjut"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

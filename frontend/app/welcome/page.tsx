import type { Metadata } from "next";
import Link from "next/link";
import BrandMark from "@/components/login/BrandMark";
import ThemeToggle from "@/components/ThemeToggle";

/**
 * Landing page publik (tanpa login). Pengunjung yang belum masuk dan membuka
 * "/" diarahkan ke sini oleh middleware; tombol Masuk menuju /login.
 * Angka di halaman ini sama dengan hasil uji di naskah dan ml/artifacts.
 */

export const metadata: Metadata = {
  title: "regimefraktalVFK — Kenali sifat pasar sebelum memilih strategi",
  description:
    "Detektor regime fraktal BTC/USDT berbasis Attention-BiLSTM: berlanjut, berbalik, atau acak, lengkap dengan tingkat keyakinan dan bukti uji.",
};

const STATS = [
  { value: "0,813", label: "akurasi seimbang pada deret sintetis berkarakter kripto" },
  { value: "+0,159", label: "di atas estimator Hurst-DFA klasik terbaik" },
  { value: "2×", label: "lebih cepat mendeteksi pergantian regime dibanding konsensus Hurst-DFA" },
  { value: "20", label: "aset diuji tanpa latih ulang" },
];

const FEATURES = [
  {
    title: "Kondisi pasar 1H & 4H",
    text: "Detektor AI menilai 500 bar terakhir dan menyatakan apakah gerakan cenderung berlanjut, berbalik, atau acak, beserta keyakinannya.",
  },
  {
    title: "Jujur saat ragu",
    text: "Keyakinan di bawah 75% ditandai “ragu”. Sistem tidak memaksakan label ketika datanya memang tidak cukup jelas.",
  },
  {
    title: "Pembanding klasik",
    text: "Hurst R/S dan DFA ditampilkan terhadap pita acak, sehingga terlihat kapan angka klasik sebenarnya tidak berbeda dari pasar tanpa memori.",
  },
  {
    title: "Analisis aset apa pun",
    text: "Pilih pair Binance atau saham, indeks, emas, dan forex dari Yahoo Finance, lalu jalankan detektor yang sama.",
  },
  {
    title: "Notifikasi Telegram",
    text: "Pesan otomatis saat regime berganti, setelah dikonfirmasi tiga jendela berturut-turut agar tidak mudah salah alarm.",
  },
  {
    title: "Panduan setup",
    text: "Jenis setup yang cocok dan yang sebaiknya dihindari untuk tiap kondisi, dengan status bukti dari hasil uji.",
  },
];

const STEPS = [
  { n: "01", title: "Data tertutup saja", text: "Hanya candle yang sudah tutup. Harga diubah menjadi log-return dan dinilai per jendela 500 bar." },
  {
    n: "02",
    title: "Belajar dari kunci jawaban",
    text: "Model Attention-BiLSTM dilatih pada deret sintetis yang eksponen Hurst-nya diketahui pasti, dengan ekor tebal, volatilitas berkelompok, dan lonjakan seperti kripto.",
  },
  { n: "03", title: "Label + keyakinan", text: "Setiap 4 bar sistem memberi label dan probabilitas tiap kelas. Notifikasi dikirim setelah tiga konfirmasi berturut-turut." },
];

const BARS = [
  { label: "Konsensus Hurst R/S–DFA", value: 0.268, tone: "bg-txtMuted/50" },
  { label: "Estimator klasik terbaik (VR(2) terkalibrasi)", value: 0.654, tone: "bg-txtMuted" },
  { label: "Attention-BiLSTM (sistem ini)", value: 0.813, tone: "bg-accent" },
];

const LIMITS = [
  "Bukan peramal arah harga. “Berlanjut” berlaku untuk naik maupun turun.",
  "BTC 1H paling sering terbaca acak. Itu temuan penelitian, bukan galat: estimator klasik pun membaca 98% jendela sebagai acak.",
  "Untuk aset selain BTC/USDT 1H, hasil bersifat eksperimental; uji generalisasi belum memenuhi kriteria.",
  "Memilih strategi berdasarkan regime tidak menambah Sharpe setelah biaya pada uji kami. Nilai utamanya sebagai filter “jangan trading”.",
];

function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-edge/70 bg-panel/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-6 px-5">
        <Link href="/welcome" className="flex items-center gap-2">
          <BrandMark size={28} />
          <span className="text-[16px] font-semibold tracking-tight text-txt">
            regimefraktal<span className="text-accent">VFK</span>
          </span>
        </Link>
        <nav className="hidden items-center gap-6 text-[14px] text-txtDim md:flex" aria-label="Navigasi landing">
          <a href="#fitur" className="hover:text-txt">Fitur</a>
          <a href="#cara-kerja" className="hover:text-txt">Cara kerja</a>
          <a href="#bukti" className="hover:text-txt">Bukti</a>
          <a href="#batasan" className="hover:text-txt">Batasan</a>
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <div className="rounded-full border border-edge p-0.5">
            <ThemeToggle />
          </div>
          <Link href="/login" className="hidden text-[14px] text-txtDim hover:text-txt sm:inline">
            Masuk
          </Link>
          <Link href="/login" className="rounded-full bg-txt px-4 py-2 text-[14px] font-semibold text-panel transition hover:opacity-90">
            Mulai
          </Link>
        </div>
      </div>
    </header>
  );
}

function Screenshot({ src, alt, caption }: { src: string; alt: string; caption?: string }) {
  return (
    <figure>
      <div className="overflow-hidden rounded-2xl border border-edge bg-panelAlt shadow-[0_30px_80px_-20px_rgba(16,24,40,0.35)]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt={alt} className="block w-full" loading="lazy" />
      </div>
      {caption && <figcaption className="mt-3 text-center text-[13px] text-txtMuted">{caption}</figcaption>}
    </figure>
  );
}

export default function WelcomePage() {
  return (
    <div className="h-screen overflow-y-auto bg-panel text-txt">
      <Nav />

      <main>
        <section className="relative overflow-hidden">
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-[520px] opacity-60"
            style={{ background: "radial-gradient(60% 60% at 50% 0%, rgb(var(--c-surface)) 0%, transparent 100%)" }}
            aria-hidden
          />
          <div className="relative mx-auto max-w-[1100px] px-5 pb-10 pt-16 text-center sm:pt-24">
            <p className="mx-auto inline-flex items-center gap-2 rounded-full border border-edge px-3 py-1 text-[12.5px] text-txtDim">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" /> Identifikasi regime fraktal BTC/USDT
            </p>
            <h1 className="mx-auto mt-6 max-w-[900px] text-[44px] font-semibold leading-[1.02] tracking-[-0.035em] sm:text-[72px] lg:text-[88px]">
              Kenali sifat pasar, sebelum memilih strategi.
            </h1>
            <p className="mx-auto mt-6 max-w-[720px] text-[17px] leading-relaxed text-txtDim sm:text-[19px]">
              Detektor berbasis SWT dan Attention-BiLSTM yang menyatakan apakah gerakan harga cenderung berlanjut, berbalik, atau
              sekadar acak, lengkap dengan tingkat keyakinan dan bukti ujinya.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/login"
                className="inline-flex items-center gap-2 rounded-full bg-txt px-6 py-3 text-[15px] font-semibold text-panel transition hover:opacity-90"
              >
                Buka dashboard <span aria-hidden>→</span>
              </Link>
              <a
                href="#cara-kerja"
                className="rounded-full border border-edge bg-panel px-6 py-3 text-[15px] font-medium text-txt transition hover:bg-surface"
              >
                Lihat cara kerja
              </a>
            </div>
            <p className="mt-5 text-[13px] text-txtMuted">Untuk riset dan edukasi. Bukan saran keuangan.</p>
          </div>

          <div className="relative mx-auto max-w-[1180px] px-5 pb-16">
            <Screenshot src="/landing/dashboard-dark.webp" alt="Tampilan ringkasan pasar: kondisi 1H dan 4H, pembanding Hurst/DFA, grafik dengan pita regime" />
          </div>
        </section>

        <section className="border-y border-edge bg-panelAlt">
          <div className="mx-auto grid max-w-[1200px] grid-cols-2 gap-px px-5 py-10 md:grid-cols-4">
            {STATS.map((s) => (
              <div key={s.value} className="px-4 py-2 text-center">
                <div className="font-mono text-[34px] font-semibold tracking-tight text-txt sm:text-[40px]">{s.value}</div>
                <div className="mx-auto mt-1 max-w-[220px] text-[13px] leading-snug text-txtMuted">{s.label}</div>
              </div>
            ))}
          </div>
        </section>

        <section id="fitur" className="mx-auto max-w-[1200px] scroll-mt-20 px-5 py-20">
          <h2 className="max-w-[640px] text-[34px] font-semibold leading-tight tracking-[-0.02em] sm:text-[44px]">
            Satu layar untuk tahu kondisi pasar sekarang.
          </h2>
          <p className="mt-3 max-w-[640px] text-[16px] text-txtDim">
            Bukan indikator yang menebak arah, tetapi pembaca sifat gerakan, supaya strategi yang dijalankan sesuai kondisinya.
          </p>
          <div className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-edge bg-edge sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-panel p-6">
                <h3 className="text-[17px] font-semibold text-txt">{f.title}</h3>
                <p className="mt-2 text-[14px] leading-relaxed text-txtDim">{f.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="cara-kerja" className="scroll-mt-20 border-t border-edge bg-panelAlt">
          <div className="mx-auto max-w-[1200px] px-5 py-20">
            <h2 className="text-[34px] font-semibold tracking-[-0.02em] sm:text-[44px]">Cara kerja</h2>
            <div className="mt-10 grid gap-8 md:grid-cols-3">
              {STEPS.map((s) => (
                <div key={s.n}>
                  <div className="font-mono text-[13px] text-accent">{s.n}</div>
                  <h3 className="mt-2 text-[19px] font-semibold text-txt">{s.title}</h3>
                  <p className="mt-2 text-[14.5px] leading-relaxed text-txtDim">{s.text}</p>
                </div>
              ))}
            </div>
            <div className="mt-14">
              <Screenshot
                src="/landing/analisis-light.webp"
                alt="Hasil Analisis Aset ETHUSDT 1H: kondisi, pembanding klasik, grafik, dan riwayat kondisi"
                caption="Analisis Aset: detektor yang sama untuk pair lain, ditandai eksperimental di luar BTC/USDT 1H."
              />
            </div>
          </div>
        </section>

        <section id="bukti" className="mx-auto max-w-[1200px] scroll-mt-20 px-5 py-20">
          <div className="grid gap-10 lg:grid-cols-[1fr_1.2fr] lg:items-center">
            <div>
              <h2 className="text-[34px] font-semibold leading-tight tracking-[-0.02em] sm:text-[44px]">Diuji dengan kunci jawaban.</h2>
              <p className="mt-3 text-[16px] leading-relaxed text-txtDim">
                Di pasar nyata, regime yang sebenarnya tidak pernah terlihat. Karena itu akurasi diukur pada deret sintetis yang eksponen
                Hurst-nya diketahui, dengan karakter kripto. Seluruh hipotesis dikunci sebelum hasilnya dihitung.
              </p>
            </div>
            <div className="rounded-2xl border border-edge bg-panel p-6 shadow-panel">
              <div className="text-[13px] font-medium text-txtDim">Akurasi seimbang (skenario mirip kripto, jendela 500 bar)</div>
              <div className="mt-5 space-y-5">
                {BARS.map((b) => (
                  <div key={b.label}>
                    <div className="flex items-baseline justify-between gap-3 text-[14px]">
                      <span className="text-txt">{b.label}</span>
                      <span className="font-mono font-semibold text-txt">{b.value.toLocaleString("id-ID", { minimumFractionDigits: 3 })}</span>
                    </div>
                    <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-surface">
                      <div className={`h-full rounded-full ${b.tone}`} style={{ width: `${b.value * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-5 text-[12.5px] text-txtMuted">Tebakan acak = 0,333. Sumber: benchmark sintetis Fase 1 (3.000 deret uji).</p>
            </div>
          </div>
        </section>

        <section id="batasan" className="scroll-mt-20 border-t border-edge bg-panelAlt">
          <div className="mx-auto max-w-[1200px] px-5 py-20">
            <h2 className="text-[34px] font-semibold tracking-[-0.02em] sm:text-[44px]">Jujur soal batasannya.</h2>
            <ul className="mt-8 grid gap-4 md:grid-cols-2">
              {LIMITS.map((l) => (
                <li key={l} className="rounded-xl border border-edge bg-panel p-5 text-[14.5px] leading-relaxed text-txtDim">
                  {l}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="mx-auto max-w-[1100px] px-5 py-24 text-center">
          <h2 className="text-[36px] font-semibold tracking-[-0.025em] sm:text-[56px]">Lihat kondisi pasar hari ini.</h2>
          <div className="mt-8 flex justify-center">
            <Link href="/login" className="inline-flex items-center gap-2 rounded-full bg-txt px-7 py-3.5 text-[15px] font-semibold text-panel transition hover:opacity-90">
              Buka dashboard <span aria-hidden>→</span>
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-edge">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-5 py-8 text-[12.5px] text-txtMuted">
          <span>© 2026 Vinnzene Fernando Karim · Skripsi S1 Informatika, Universitas Bunda Mulia</span>
          <span>Konten untuk riset dan edukasi, bukan saran keuangan. Hasil masa lalu tidak menjamin hasil di masa depan.</span>
        </div>
      </footer>
    </div>
  );
}

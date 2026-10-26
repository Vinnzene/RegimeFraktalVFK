/**
 * Isi Panduan Setup per regime. HANYA diimpor oleh rute server
 * (/api/setup-guide), sehingga tidak ikut terkirim ke peramban pengguna yang
 * belum disetujui.
 *
 * Panduan ini bersifat edukatif: jenis setup yang secara logika sesuai atau
 * tidak sesuai dengan sifat gerakan tiap regime, beserta status buktinya dari
 * uji Fase 2 (ml/artifacts/strategy_selection.md). Bukan sinyal entry dan
 * bukan prediksi arah harga.
 */

export type EvidenceLevel = "didukung" | "indikasi" | "belum_diuji" | "tidak_disarankan";

export type SetupItem = { name: string; detail: string };

export type RegimeGuide = {
  regime: "persistent" | "random_like" | "anti_persistent" | "uncertain_lowconf";
  headline: string;
  logic: string;
  suitable: SetupItem[];
  avoid: SetupItem[];
  risk: string[];
  tools: string[];
  evidence: { level: EvidenceLevel; text: string };
};

export const SETUP_GUIDE: RegimeGuide[] = [
  {
    regime: "random_like",
    headline: "Sebaiknya tidak membuka posisi aktif",
    logic:
      "Langkah harga tidak berhubungan dengan langkah sebelumnya. Setup apa pun yang bertumpu pada kelanjutan atau pembalikan kehilangan dasarnya, sementara biaya transaksi tetap dibayar.",
    suitable: [
      { name: "Tidak trading / menunggu", detail: "Tunggu sampai detektor mengonfirmasi kondisi lain (3 jendela berturut-turut)." },
      { name: "Posisi investasi jangka panjang", detail: "Bila memang berniat menyimpan aset, bukan memperdagangkan gerakan jangka pendek." },
    ],
    avoid: [
      { name: "Breakout jangka pendek", detail: "Tembusan level mudah gagal karena tidak ada momentum yang berlanjut." },
      { name: "Grid / scalping frekuensi tinggi", detail: "Banyak transaksi kecil tanpa keunggulan; biaya menggerus modal." },
      { name: "Pola grafik sebagai pemicu tunggal", detail: "Pola terlihat di mana-mana pada data acak (ilusi pola)." },
    ],
    risk: ["Bila tetap trading: ukuran posisi minimal.", "Hitung biaya per sisi sebelum masuk; di kripto ±0,085%."],
    tools: [],
    evidence: {
      level: "didukung",
      text: "Uji Fase 2 BTC 1H: saat detektor memberi label acak, momentum dan mean-reversion sama-sama rugi besar setelah biaya (Sharpe −2,46 dan −1,47).",
    },
  },
  {
    regime: "anti_persistent",
    headline: "Setup pembalikan di dalam kisaran",
    logic:
      "Gerakan cenderung berbalik arah, sehingga harga lebih sering bolak-balik di dalam kisaran daripada melanjutkan tembusan.",
    suitable: [
      { name: "Reversal di batas kisaran", detail: "Masuk berlawanan arah di dekat support/resistance kisaran yang jelas, dengan stop di luar kisaran." },
      { name: "Kembali ke rata-rata", detail: "Target ke tengah kisaran, VWAP, atau rata-rata bergerak, bukan target jauh." },
      { name: "Grid dalam kisaran", detail: "Hanya bila kisaran jelas dan biaya per transaksi rendah." },
    ],
    avoid: [
      { name: "Mengejar breakout", detail: "Tembusan cenderung kembali ke dalam kisaran (false breakout)." },
      { name: "Trailing stop lebar ala trend-following", detail: "Keuntungan cenderung terkikis saat harga berbalik." },
    ],
    risk: [
      "Pasang stop di luar kisaran; kondisi bisa berganti tanpa tanda.",
      "Hentikan setup pembalikan bila detektor berpindah ke kondisi Tren Berlanjut (persistent).",
    ],
    tools: [
      "Pola harmonic (XABCD, Gartley, Bat) lazim dipakai sebagai konfirmasi zona pembalikan; tersedia di alat gambar halaman Analisa Teknikal. Belum diuji di sistem ini.",
    ],
    evidence: {
      level: "indikasi",
      text: "Eksploratif: setelah label cenderung berbalik, harga lebih sering berbalik daripada setelah label acak pada 7 dari 7 aset kripto. Namun strategi mean-reversion sederhana (24 bar) di BTC 1H tetap rugi setelah biaya; keunggulannya belum cukup menutup biaya.",
    },
  },
  {
    regime: "persistent",
    headline: "Setup mengikuti arah gerakan",
    logic:
      "Langkah harga cenderung searah dengan langkah sebelumnya (naik maupun turun). Kondisi ini secara teori mendukung setup yang ikut arah.",
    suitable: [
      { name: "Pullback searah gerakan", detail: "Masuk saat harga terkoreksi ke struktur atau rata-rata bergerak, searah gerakan utama." },
      { name: "Breakout dengan konfirmasi", detail: "Tembusan dari konsolidasi yang disertai volume meningkat." },
      { name: "Trailing stop", detail: "Biarkan posisi berjalan selama gerakan berlanjut." },
    ],
    avoid: [
      { name: "Melawan arah (fading)", detail: "Menebak puncak atau dasar saat gerakan masih berlanjut." },
      { name: "Grid / mean-reversion", detail: "Terseret saat harga terus bergerak searah." },
    ],
    risk: ["Tren Berlanjut berarti gerakan cenderung berlanjut, naik maupun turun; label ini tidak menunjukkan arah.", "Detektor mengonfirmasi pergantian dengan jeda ±300 bar."],
    tools: [],
    evidence: {
      level: "belum_diuji",
      text: "Di BTC 1H detektor jarang sekali memberi label ini (±1% waktu), sehingga sampelnya terlalu kecil untuk diuji. Panduan ini berdasar teori, belum didukung data sistem.",
    },
  },
  {
    regime: "uncertain_lowconf",
    headline: "Model ragu: tunggu atau perkecil posisi",
    logic: "Keyakinan detektor di bawah 75%. Kondisi pasar belum dapat ditentukan dengan cukup yakin.",
    suitable: [
      { name: "Menunggu konfirmasi", detail: "Lihat apakah label berikutnya menjadi yakin, atau 1H dan 4H sepakat." },
      { name: "Posisi kecil", detail: "Bila tetap masuk, kurangi ukuran sesuai ketidakpastian." },
    ],
    avoid: [{ name: "Setup agresif dengan leverage", detail: "Ketidakpastian tinggi tidak sejalan dengan risiko besar." }],
    risk: ["Perlakukan seperti kondisi acak sampai ada konfirmasi."],
    tools: [],
    evidence: {
      level: "didukung",
      text: "Pada data uji sintetis, label dengan keyakinan ≥ 75% jauh lebih tepat (akurasi seimbang 0,905) daripada seluruh label (0,813).",
    },
  },
];

export const GUIDE_NOTES = [
  "Panduan ini edukatif: jenis setup yang sesuai dengan sifat gerakan tiap kondisi, bukan sinyal beli/jual dan bukan prediksi arah.",
  "Elliott Wave tidak dimasukkan: hitungan gelombangnya subjektif dan dapat direvisi setelah harga bergerak, sehingga tidak dapat diuji secara objektif.",
  "Hasil masa lalu tidak menjamin hasil di masa depan. Selalu gunakan manajemen risiko.",
];

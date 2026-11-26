/** Atribusi pustaka chart dan indikator adaptasi, ditampilkan di luar area chart (diwajibkan lisensi). */
export default function ChartCredits({ className = "" }: { className?: string }) {
  return (
    <p className={`text-[11px] leading-relaxed text-txtMuted ${className}`}>
      Grafik memakai{" "}
      <a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer" className="hover:text-txtDim hover:underline">
        TradingView Lightweight Charts™
      </a>{" "}
      (© TradingView, Inc., Apache 2.0). Indikator Order Flow VWAP Deviation, Statistical Trailing Stop, Hurst Exponent, Order Blocks &amp;
      Breaker Blocks, dan Volumetric Order Flow Structure diadaptasi dari karya{" "}
      <a href="https://www.luxalgo.com/" target="_blank" rel="noopener noreferrer" className="hover:text-txtDim hover:underline">
        © LuxAlgo
      </a>{" "}
      dengan lisensi{" "}
      <a
        href="https://creativecommons.org/licenses/by-nc-sa/4.0/"
        target="_blank"
        rel="noopener noreferrer"
        className="hover:text-txtDim hover:underline"
      >
        CC BY-NC-SA 4.0
      </a>{" "}
      (non-komersial).
    </p>
  );
}

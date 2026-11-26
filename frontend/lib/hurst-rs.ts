/**
 * Hurst Exponent bergulir dengan rescaled range (R/S) klasik pada ukuran subsampel dyadic
 * (n, n/2, n/4, ... sampai 8), dihaluskan SMA, dengan pita netral di sekitar 0,5.
 *
 * Diadaptasi dari indikator Pine Script "Hurst Exponent" © LuxAlgo,
 * berlisensi CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/).
 * Perubahan: ditulis ulang dalam TypeScript untuk lightweight-charts; hanya penghalusan SMA,
 * inkremen log-return, dan tabel ringkas disajikan di legenda chart.
 * Berkas ini dilisensikan dengan lisensi yang sama: CC BY-NC-SA 4.0 (non-komersial).
 */

const MIN_SUBSAMPLE = 8;
const EPS = 1e-12;

export type RsFit = { h: number | null; r2: number | null; points: number };

/** Estimasi R/S: kemiringan log(R/S rata-rata) terhadap log(ukuran subsampel), beserta R² regresinya. */
export function rescaledRangeHurst(sample: number[]): RsFit {
  const n = sample.length;
  const xs: number[] = [], ys: number[] = [];
  for (let size = n; size >= MIN_SUBSAMPLE; size = Math.floor(size / 2)) {
    const count = Math.floor(n / size);
    let rsSum = 0, rsCount = 0;
    for (let s = 0; s < count; s++) {
      const head = s * size;
      let mean = 0;
      for (let i = head; i < head + size; i++) mean += sample[i];
      mean /= size;
      let run = 0, max = 0, min = 0, varSum = 0;
      for (let i = head; i < head + size; i++) {
        const d = sample[i] - mean;
        run += d;
        if (run > max) max = run;
        if (run < min) min = run;
        varSum += d * d;
      }
      const sigma = Math.sqrt(varSum / size);
      if (sigma > EPS) {
        rsSum += (max - min) / sigma;
        rsCount += 1;
      }
    }
    if (rsCount > 0 && rsSum / rsCount > EPS) {
      xs.push(Math.log(size));
      ys.push(Math.log(rsSum / rsCount));
    }
  }
  if (xs.length < 2) return { h: null, r2: null, points: xs.length };
  const mx = xs.reduce((a, b) => a + b, 0) / xs.length;
  const my = ys.reduce((a, b) => a + b, 0) / ys.length;
  let sxx = 0, sxy = 0, syy = 0;
  for (let i = 0; i < xs.length; i++) {
    const dx = xs[i] - mx, dy = ys[i] - my;
    sxx += dx * dx;
    sxy += dx * dy;
    syy += dy * dy;
  }
  if (sxx <= EPS) return { h: null, r2: null, points: xs.length };
  return { h: sxy / sxx, r2: syy > EPS ? (sxy * sxy) / (sxx * syy) : 1, points: xs.length };
}

export type HurstSeries = {
  raw: (number | null)[];
  smooth: (number | null)[];
  r2: (number | null)[];
  /** 1 = tren (di atas pita), −1 = berbalik (di bawah pita), 0 = acak / belum ada nilai. */
  state: number[];
};

/** H bergulir dari log-return `length` bar terakhir, dihaluskan SMA `smooth`, pita netral 0,5 ± band. */
export function rollingHurst(closes: number[], length = 128, smooth = 5, band = 0.05): HurstSeries {
  const inc: (number | null)[] = closes.map((c, i) => (i > 0 && c > 0 && closes[i - 1] > 0 ? Math.log(c / closes[i - 1]) : null));
  const raw: (number | null)[] = [], r2: (number | null)[] = [];
  const win: number[] = [];
  for (const v of inc) {
    if (v != null) {
      win.push(v);
      if (win.length > length) win.shift();
    }
    if (win.length === length) {
      const fit = rescaledRangeHurst(win);
      raw.push(fit.h);
      r2.push(fit.r2);
    } else {
      raw.push(null);
      r2.push(null);
    }
  }
  const smoothArr = raw.map((_, i) => {
    if (i < smooth - 1) return null;
    let s = 0;
    for (let j = i - smooth + 1; j <= i; j++) {
      const v = raw[j];
      if (v == null) return null;
      s += v;
    }
    return s / smooth;
  });
  const state = smoothArr.map((v) => (v == null ? 0 : v > 0.5 + band ? 1 : v < 0.5 - band ? -1 : 0));
  return { raw, smooth: smoothArr, r2, state };
}

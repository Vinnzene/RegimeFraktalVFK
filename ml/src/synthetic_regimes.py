"""Generator deret sintetis berkarakter kripto untuk benchmark Fase 1.

Rancangan dan alasannya: docs/praregistrasi_fase1_sintetis.md §2–§3.

Kebenaran dasar selalu H milik komponen fGn. Transformasi yang ditambahkan
dipilih agar tidak mengubah eksponen memori itu:
- S2: transformasi monoton ganjil ke Student-t lewat copula Gaussian
  (peringkat Hermite 1, eksponen memori jangka panjang tetap H).
- S3: dikalikan volatilitas stokastik yang independen dari fGn, sehingga
  autokorelasi return hanya diskalakan, tidak diubah bentuknya.
- S4: S2 + S3 + lonjakan Poisson independen.
- S5: dua segmen fGn dengan H dari kelas berbeda; label = segmen terakhir.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
from scipy import signal, stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.hurst_dfa import fbm_increments  # noqa: E402

SIGMA = 0.0066  # simpangan baku return BTC 1H
CLASSES = ("anti_persistent", "random_like", "persistent")
PRIMARY = (0.47, 0.53)
SENSITIVITY = (0.45, 0.55)
H_RANGE = (0.30, 0.70)
SCENARIOS = ("S1", "S2", "S3", "S4", "S5", "S4k")


@dataclass(frozen=True)
class CryptoParams:
    """Parameter S2–S4. SV dari kalibrasi (praregistrasi Fase 1, adendum 1)."""

    t_dof: float = 3.0
    sv_phi: float = 0.995
    sv_eta: float = 0.20
    jump_prob: float = 0.002
    jump_scale: float = 10.0


# S4k (eksploratif, adendum 1): ekor dan lonjakan dikalibrasi ke kurtosis per
# window BTC, SV dikalibrasi ulang bersamanya. S4 asli tetap sesuai praregistrasi.
S4K_PARAMS = CryptoParams(t_dof=4.0, sv_phi=0.99, sv_eta=0.18, jump_prob=0.002, jump_scale=3.0)


def label(h: float, thresholds: Tuple[float, float] = PRIMARY) -> str:
    lo, hi = thresholds
    if h < lo:
        return "anti_persistent"
    if h > hi:
        return "persistent"
    return "random_like"


def sample_h(cls: str, rng: np.random.Generator, thresholds: Tuple[float, float] = PRIMARY) -> float:
    """H seragam di dalam rentang kelas (pengambilan sampel seimbang per kelas)."""
    lo, hi = thresholds
    bounds = {"anti_persistent": (H_RANGE[0], lo), "random_like": (lo, hi), "persistent": (hi, H_RANGE[1])}[cls]
    while True:
        h = float(rng.uniform(*bounds))
        if label(h, thresholds) == cls:  # tepi interval terbuka/tertutup
            return h


def fgn(n: int, h: float, rng: np.random.Generator) -> np.ndarray:
    x = fbm_increments(n, h, seed=int(rng.integers(0, 2**31 - 1)))
    return (x - x.mean()) / x.std()


def to_student_t(z: np.ndarray, dof: float) -> np.ndarray:
    """Transformasi monoton Gaussian -> Student-t, varians 1."""
    t = stats.t.ppf(stats.norm.cdf(z), dof)
    return t / np.sqrt(dof / (dof - 2))


def sv_sigma(n: int, phi: float, eta: float, rng: np.random.Generator, burn: int = 2000) -> np.ndarray:
    """exp(h/2), h_t = phi*h_{t-1} + eta*e_t; dinormalkan agar E[sigma^2] = 1."""
    e = rng.normal(size=n + burn)
    e[0] /= np.sqrt(1 - phi**2)  # mulai dari sebaran stasioner
    h = np.asarray(signal.lfilter([eta], [1.0, -phi], e))
    s = np.exp(h[burn:] / 2)
    return s / np.sqrt(np.mean(s**2))


def jumps(n: int, prob: float, scale: float, sigma: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    hit = rng.random(n) < prob
    return np.where(hit, rng.normal(size=n) * scale * sigma, 0.0)


def crypto_noise(z: np.ndarray, p: CryptoParams, rng: np.random.Generator, heavy: bool, sv: bool, jump: bool) -> np.ndarray:
    n = len(z)
    x = to_student_t(z, p.t_dof) if heavy else z
    s = sv_sigma(n, p.sv_phi, p.sv_eta, rng) if sv else np.ones(n)
    r = x * s
    if jump:
        r = r + jumps(n, p.jump_prob, p.jump_scale, s, rng)
    return r


def make_series(
    scenario: str, n: int, h: float, rng: np.random.Generator, p: CryptoParams = CryptoParams(),
    thresholds: Tuple[float, float] = PRIMARY,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """Satu deret return sepanjang n dengan kebenaran dasar H (S5: H segmen terakhir).

    Mengembalikan (return, info) dengan info berisi h_true dan, untuk S5,
    h_first serta posisi titik ganti.
    """
    info: Dict[str, float] = {"h_true": h}
    if scenario == "S5":
        first_cls = rng.choice([c for c in CLASSES if c != label(h, thresholds)])
        h1 = sample_h(str(first_cls), rng, thresholds)
        cut = int(n * rng.uniform(0.4, 0.9))
        z = np.concatenate([fgn(cut, h1, rng), fgn(n - cut, h, rng)])
        info.update({"h_first": h1, "switch_at": cut})
        r = crypto_noise(z, p, rng, heavy=True, sv=True, jump=True)
    elif scenario == "S4k":
        r = crypto_noise(fgn(n, h, rng), S4K_PARAMS, rng, heavy=True, sv=True, jump=True)
    else:
        z = fgn(n, h, rng)
        r = crypto_noise(
            z, p, rng,
            heavy=scenario in ("S2", "S4"),
            sv=scenario in ("S3", "S4"),
            jump=scenario == "S4",
        )
    return SIGMA * r / r.std(), info

"""Statistical Jump Model untuk pelabelan regime yang persistence-aware.

Masalah yang diatasi
--------------------
Pelabelan berbasis ambang per titik menghasilkan label yang berkedip
(flip-flop). Pengukuran pada data BTC/USDT 1H menunjukkan kelas `random_like`
hanya bertahan rata-rata 1,8 window dengan peluang bertahan 0,446 — padahal
window bertetangga berbagi 99,2% data yang sama (stride 4 bar, L=500). Label
berubah sementara datanya nyaris identik; itu derau estimator, bukan perubahan
pasar.

Penyebabnya terukur: pita ambang hasil kalibrasi kuantil hanya selebar ~0,028
pada Hurst, sementara selisih |ΔH| antar-window bertetangga berada pada orde
yang sebanding. Sesempit itu, derau saja cukup melempar window keluar-masuk
kelas.

Solusi (Nystrup, Kolm & Lindström, 2020)
----------------------------------------
Jump Model meminimalkan biaya gabungan: jarak tiap titik ke pusat state-nya,
ditambah penalti setiap kali state berganti.

    min_{Θ,S}  Σ_t ‖x_t − θ_{s_t}‖²  +  λ Σ_t 1{s_{t−1} ≠ s_t}

Parameter λ mengatur seberapa "malas" model berpindah state: λ = 0 setara
k-means tanpa memori, λ besar menghasilkan sedikit blok panjang. Optimasi
dilakukan bergantian (coordinate descent):

1. **Penugasan state** — dynamic programming (Viterbi) yang menemukan barisan
   state optimal secara global untuk parameter tetap, bukan greedy per titik.
2. **Pembaruan parameter** — pusat tiap state dihitung ulang sebagai rata-rata
   anggotanya.

Keduanya menurunkan fungsi objektif secara monoton, sehingga iterasi dijamin
konvergen ke optimum lokal.

Catatan metodologis
-------------------
Masukan model adalah nilai Hurst dan DFA — keduanya dipakai untuk MEMBENTUK
label, bukan sebagai fitur model klasifikasi. Ini tetap konsisten dengan
prinsip anti-kebocoran: yang dilarang adalah memberi Hurst/DFA sebagai input
Attention-BiLSTM, sedangkan di sini keduanya berperan sebagai sumber ground
truth seperti sebelumnya.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# Urutan state diselaraskan berdasarkan nilai Hurst: indeks 0 = paling rendah
# (anti-persistent), indeks terakhir = paling tinggi (persistent).
DEFAULT_MAX_ITER = 50
DEFAULT_N_INIT = 5


def _standardize(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Standarisasi kolom agar tiap fitur berkontribusi setara pada jarak."""
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std < 1e-12] = 1.0
    return (X - mean) / std, mean, std


def _init_centers(X: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """Inisialisasi k-means++ — lebih stabil daripada pemilihan acak."""
    n = X.shape[0]
    centers = [X[rng.integers(n)]]
    for _ in range(k - 1):
        d2 = np.min(
            np.stack([((X - c) ** 2).sum(axis=1) for c in centers], axis=1), axis=1
        )
        total = d2.sum()
        if total <= 0:
            centers.append(X[rng.integers(n)])
            continue
        centers.append(X[rng.choice(n, p=d2 / total)])
    return np.asarray(centers)


def _assign_states(costs: np.ndarray, jump_penalty: float) -> np.ndarray:
    """Barisan state optimal lewat dynamic programming.

    `costs[t, s]` adalah biaya menempatkan titik t pada state s. Penalti
    dikenakan setiap kali state berganti antar langkah waktu. Pendekatan DP
    menemukan solusi optimal global untuk parameter tetap — berbeda dari
    penugasan greedy per titik yang justru menghasilkan flip-flop.
    """
    n, k = costs.shape
    dp = np.empty((n, k))
    back = np.zeros((n, k), dtype=int)
    dp[0] = costs[0]

    for t in range(1, n):
        for s in range(k):
            # Biaya bertahan di state s, atau pindah dari state lain + penalti.
            transition = dp[t - 1] + jump_penalty
            transition[s] = dp[t - 1, s]
            best = int(np.argmin(transition))
            back[t, s] = best
            dp[t, s] = costs[t, s] + transition[best]

    states = np.empty(n, dtype=int)
    states[-1] = int(np.argmin(dp[-1]))
    for t in range(n - 2, -1, -1):
        states[t] = back[t + 1, states[t + 1]]
    return states


def fit_jump_model(
    X: np.ndarray,
    n_states: int = 3,
    jump_penalty: float = 1.0,
    max_iter: int = DEFAULT_MAX_ITER,
    n_init: int = DEFAULT_N_INIT,
    seed: int = 42,
) -> Dict[str, object]:
    """Fit Statistical Jump Model lewat coordinate descent.

    Mengembalikan barisan state, pusat tiap state, dan nilai objektif. Beberapa
    inisialisasi dicoba karena objektifnya non-konveks; hasil terbaik dipilih.
    """
    X = np.atleast_2d(np.asarray(X, dtype=float))
    if X.shape[0] < n_states * 2:
        return {
            "states": np.zeros(X.shape[0], dtype=int),
            "centers": np.zeros((n_states, X.shape[1])),
            "objective": float("inf"),
            "n_switches": 0,
            "converged": False,
        }

    Z, mean, std = _standardize(X)
    rng = np.random.default_rng(seed)

    best: Optional[Dict[str, object]] = None
    for _ in range(max(1, n_init)):
        centers = _init_centers(Z, n_states, rng)
        states = np.zeros(Z.shape[0], dtype=int)
        prev_obj = np.inf
        converged = False
        # Diinisialisasi sebelum loop: dengan max_iter = 0 loop tidak berjalan
        # sama sekali, dan tanpa nilai awal ini pembentukan `best` di bawah
        # gagal dengan UnboundLocalError.
        obj = float("inf")
        fit_cost = float("inf")
        switches = 0

        for _ in range(max_iter):
            # Langkah 1: penugasan state optimal untuk pusat tetap.
            costs = np.stack([((Z - c) ** 2).sum(axis=1) for c in centers], axis=1)
            states = _assign_states(costs, jump_penalty)

            # Langkah 2: perbarui pusat sebagai rata-rata anggotanya.
            for s in range(n_states):
                sel = states == s
                if sel.any():
                    centers[s] = Z[sel].mean(axis=0)

            fit_cost = float(costs[np.arange(len(states)), states].sum())
            switches = int((states[1:] != states[:-1]).sum())
            obj = fit_cost + jump_penalty * switches

            if abs(prev_obj - obj) < 1e-8:
                converged = True
                break
            prev_obj = obj

        if best is None or obj < best["objective"]:  # type: ignore[index]
            best = {
                "states": states.copy(),
                "centers": centers * std + mean,
                "centers_standardized": centers.copy(),
                "objective": obj,
                "fit_cost": fit_cost,
                "n_switches": switches,
                "converged": converged,
            }

    return best  # type: ignore[return-value]


def order_states_by_feature(
    states: np.ndarray,
    centers: np.ndarray,
    feature_index: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Urutkan state menaik menurut satu fitur acuan.

    Tanpa ini, indeks state bersifat arbitrer antar-pemanggilan dan pemetaan ke
    nama regime menjadi tidak konsisten. Dengan mengurutkan berdasarkan nilai
    Hurst, state 0 selalu yang paling anti-persistent.
    """
    order = np.argsort(centers[:, feature_index])
    remap = {int(old): new for new, old in enumerate(order)}
    return np.array([remap[int(s)] for s in states]), centers[order]


def label_with_jump_model(
    hurst: Sequence[float] | np.ndarray,
    dfa: Sequence[float] | np.ndarray,
    class_names: Sequence[str],
    jump_penalty: float = 1.0,
    seed: int = 42,
    n_init: int = DEFAULT_N_INIT,
) -> Dict[str, Any]:
    """Label regime dari deret Hurst dan DFA memakai Jump Model.

    Kedua estimator dipakai bersama sebagai vektor dua dimensi, sehingga model
    tidak perlu memutuskan mana yang "benar" ketika keduanya berbeda — posisi
    relatif dalam ruang dua dimensi itulah yang menentukan state.
    """
    h = np.asarray(list(hurst), dtype=float)
    a = np.asarray(list(dfa), dtype=float)

    # Nilai tak hingga diganti median agar tidak menarik pusat state.
    for arr in (h, a):
        bad = ~np.isfinite(arr)
        if bad.any():
            arr[bad] = np.nanmedian(arr[~bad]) if (~bad).any() else 0.5

    X = np.column_stack([h, a])
    result = fit_jump_model(
        X,
        n_states=len(class_names),
        jump_penalty=jump_penalty,
        seed=seed,
        n_init=n_init,
    )

    states, centers = order_states_by_feature(
        np.asarray(result["states"]), np.asarray(result["centers"]), feature_index=0
    )
    labels = [class_names[int(s)] for s in states]

    runs: List[int] = []
    if len(labels):
        current, length = labels[0], 1
        for lab in labels[1:]:
            if lab == current:
                length += 1
            else:
                runs.append(length)
                current, length = lab, 1
        runs.append(length)

    return {
        "labels": labels,
        "states": states,
        "centers": centers.tolist(),
        "jump_penalty": jump_penalty,
        "objective": result["objective"],
        "n_switches": int(result["n_switches"]),  # type: ignore[arg-type,call-overload]
        "mean_run_length": round(float(np.mean(runs)), 3) if runs else 0.0,
        "median_run_length": float(np.median(runs)) if runs else 0.0,
        "n_runs": len(runs),
        "converged": bool(result["converged"]),
    }

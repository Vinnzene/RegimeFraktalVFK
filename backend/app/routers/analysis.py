"""Endpoint analisis: Hurst-DFA, SWT, regime, attention, transisi, durasi."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from app.core.config import ARTIFACTS_DIR, get_config
from app.db.repository import get_repository
from app.services.downsample import apply_downsample
from app.services.hurst_dfa import to_log_return
from app.services.multifractal import DEFAULT_Q, rolling_hq
from app.services.regime_labeling import (
    regime_distribution,
    regime_durations,
    transition_matrix,
)
from app.services.splitting import assign_segment, bars_to_rows, stride_bars_of
from app.services.swt import causal_swt_at, max_useful_level, swt_decompose

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

# Kolom bernilai konstan di seluruh baris. Dikirim sekali lewat `parameters`,
# tidak diulang 16.771 kali di dalam deret.
THRESHOLD_COLUMNS = {
    "hurst_lower",
    "hurst_upper",
    "dfa_lower",
    "dfa_upper",
    "threshold_mode",
    "effective_window",
    "stride_bars",
}


@lru_cache(maxsize=1)
def _random_bands() -> Optional[dict]:
    path = ARTIFACTS_DIR / "random_band.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def random_band(window: Optional[int], scenario: str = "S4") -> Optional[dict]:
    """Pita acak R/S dan DFA untuk jendela terdekat (ml/src/random_band.py).

    Persentil 2,5–97,5% estimator pada deret sintetis H = 0,5: nilai di dalam
    pita tidak dapat dibedakan dari pasar tanpa memori pada panjang jendela itu.
    """
    data = _random_bands()
    if not data or not window or scenario not in data["bands"]:
        return None
    bands = data["bands"][scenario]
    nearest = min(bands, key=lambda n: abs(int(n) - window))
    return {"scenario": scenario, "window": int(nearest), "h_true": data["h_true"], **bands[nearest]}


@router.get("/hurst-dfa")
def read_hurst_dfa(
    tf: str = Query("1h"),
    symbol: str = Query("BTCUSDT"),
    window: Optional[int] = Query(None, ge=32),
    limit: Optional[int] = Query(
        2000,
        ge=100,
        le=50000,
        description="Jumlah titik maksimum. Deret dijarangkan bila melebihi.",
    ),
) -> dict:
    """Deret Hurst dan DFA.

    Deret dijarangkan memakai LTTB sebelum dikirim: layar tidak dapat
    menampilkan belasan ribu titik secara bermakna, sementara payload penuh
    mencapai 4,6 MB. LTTB dipilih karena mempertahankan puncak dan lembah —
    titik ekstrem itulah yang menentukan batas kelas regime.
    """
    cfg = get_config()
    repo = get_repository()
    df = repo.get_regime(symbol, tf)

    # Kolom ambang bernilai sama di seluruh baris; cukup dikirim sekali.
    kolom = [c for c in df.columns if c not in THRESHOLD_COLUMNS]
    rows = df[kolom].replace({np.nan: None}).to_dict(orient="records")
    sampled = apply_downsample(rows, limit, method="lttb", y_key="hurst")

    return {
        "timeframe": tf,
        "config_hash": cfg.config_hash,
        "parameters": {
            "L_requested": window or cfg.analysis.L,
            "L_effective": int(df["effective_window"].iloc[0]) if len(df) else None,
            "input": cfg.analysis.input,
            "hurst_threshold": cfg.analysis.hurst_threshold,
            "dfa_threshold": cfg.analysis.dfa_threshold,
            "hurst_lower": float(df["hurst_lower"].iloc[0]) if len(df) else None,
            "hurst_upper": float(df["hurst_upper"].iloc[0]) if len(df) else None,
            "dfa_lower": float(df["dfa_lower"].iloc[0]) if len(df) else None,
            "dfa_upper": float(df["dfa_upper"].iloc[0]) if len(df) else None,
        },
        "random_band": random_band(int(df["effective_window"].iloc[0]) if len(df) else cfg.analysis.L),
        "count": len(sampled["rows"]),
        "original_count": sampled["original_count"],
        "downsampled": sampled["downsampled"],
        "series": sampled["rows"],
    }


@router.get("/regime")
def read_regime(
    tf: str = Query("1h"),
    symbol: str = Query("BTCUSDT"),
    limit: Optional[int] = Query(
        3000,
        ge=100,
        le=50000,
        description="Jumlah titik maksimum pada deret. Statistik tetap dari data penuh.",
    ),
) -> dict:
    """Deret regime beserta distribusi dan segmen split.

    Distribusi, regime aktif, dan seluruh statistik dihitung dari data PENUH;
    hanya `series` yang dijarangkan untuk keperluan gambar. Dengan begitu angka
    di panel tetap tepat meski grafiknya memakai titik yang lebih sedikit.
    """
    cfg = get_config()
    repo = get_repository()
    df = repo.get_regime(symbol, tf)
    # purge_gap di config bersatuan BAR, sedangkan df berindeks WINDOW.
    # Tanpa konversi, 1000 bar terbaca sebagai 1000 baris window (= 4000 bar)
    # dan zona purge menelan seluruh validation serta test.
    stride = stride_bars_of(df)
    purge_rows = bars_to_rows(cfg.model.purge_gap, stride)
    df = assign_segment(df, cfg.split.ratios, purge_rows)
    labels = df["regime"].tolist()

    cols = ["time", "close", "hurst", "dfa_alpha", "efficiency_ratio", "regime", "segment"]
    rows = (
        df[[c for c in cols if c in df.columns]]
        .replace({np.nan: None})
        .to_dict(orient="records")
    )
    # Dihitung dari deret PENUH; deret yang dikirim untuk grafik dijarangkan.
    n_switches = int(sum(1 for a, b in zip(labels[:-1], labels[1:]) if a != b))
    thresholds = (
        {
            "hurst": [float(df["hurst_lower"].iloc[0]), float(df["hurst_upper"].iloc[0])],
            "dfa": [float(df["dfa_lower"].iloc[0]), float(df["dfa_upper"].iloc[0])],
            "source": cfg.analysis.threshold_source,
        }
        if len(df)
        else None
    )
    # Penjarangan seragam agar urutan regime tidak terpotong tidak beraturan;
    # LTTB dapat melompati blok regime pendek.
    sampled = apply_downsample(rows, limit, method="uniform")

    return {
        "timeframe": tf,
        "config_hash": cfg.config_hash,
        "current_regime": labels[-1] if labels else None,
        "distribution": regime_distribution(labels),
        "count": len(sampled["rows"]),
        "original_count": len(labels),
        "downsampled": sampled["downsampled"],
        "stride_bars": stride,
        "n_switches": n_switches,
        "thresholds": thresholds,
        "purge_gap_bars": cfg.model.purge_gap,
        "purge_gap_rows": purge_rows,
        "series": sampled["rows"],
        # Contoh jendela terbaru (tidak dijarangkan) untuk tabel per jendela.
        "latest_windows": rows[-24:],
        # Contoh terbaru jendela uncertain_rule: R/S dan DFA tidak sepakat.
        "uncertain_example": next((r for r in reversed(rows) if r.get("regime") == "uncertain_rule"), None),
    }


@router.get("/ai-regime")
def read_ai_regime(
    tf: str = Query("1h"),
    symbol: str = Query("BTCUSDT"),
    limit: Optional[int] = Query(3000, ge=100, le=50000),
) -> dict:
    """Identifikasi regime oleh model resmi sistem (Hybrid PS Attention-BiLSTM, h = 0).

    Model yang sama dengan Bab 4: dilatih pada partisi latih BTC (70%) untuk
    mengidentifikasi label Trend-Aware Soft Consensus jendela itu sendiri.
    Titik sebelum batas latih adalah data latih model; `split_boundaries`
    menandai batasnya agar tidak dibaca sebagai hasil luar sampel.
    """
    from app.services import ai_detector  # noqa: PLC0415

    cfg = get_config()
    try:
        m = ai_detector.meta(tf)
        info = ai_detector.describe(tf)
        df = ai_detector.series(symbol, tf)
    except ai_detector.DetectorUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Model identifikasi belum tersedia: {exc}") from exc
    except ai_detector.CacheBuilding as exc:
        raise HTTPException(status_code=503, detail=f"Model identifikasi sedang menghitung riwayat ({exc}). Coba lagi beberapa menit lagi.") from exc

    classes = list(m["classes"])
    labels = df["regime"].tolist()
    last = df.iloc[-1] if len(df) else None
    rows = df.round(4).to_dict(orient="records")
    sampled = apply_downsample(rows, limit, method="uniform")
    return {
        "timeframe": tf,
        "symbol": symbol,
        "config_hash": cfg.config_hash,
        "detector": info,
        # Batas partisi model (BTCUSDT): titik ≤ train_end_time adalah data latih model.
        "split_boundaries": m.get("split_times") if symbol == "BTCUSDT" else None,
        "current_regime": labels[-1] if labels else None,
        "current_time": int(last["time"]) if last is not None else None,
        "current_probabilities": {c: round(float(last[f"p_{c}"]), 4) for c in classes} if last is not None else None,
        "current_low_confidence": bool(last["confidence"] < ai_detector.ABSTAIN_TAU) if last is not None else None,
        "low_confidence_share": round(float((df["confidence"] < ai_detector.ABSTAIN_TAU).mean()), 4) if len(df) else None,
        "distribution": regime_distribution(labels),
        "count": len(sampled["rows"]),
        "original_count": len(labels),
        "downsampled": sampled["downsampled"],
        "series": sampled["rows"],
    }


@router.get("/transition-matrix")
def read_transition_matrix(tf: str = Query("1h"), symbol: str = Query("BTCUSDT")) -> dict:
    cfg = get_config()
    df = get_repository().get_regime(symbol, tf)
    result = transition_matrix(df["regime"].tolist())
    result["timeframe"] = tf
    result["config_hash"] = cfg.config_hash
    return result


@router.get("/regime-duration")
def read_regime_duration(tf: str = Query("1h"), symbol: str = Query("BTCUSDT")) -> dict:
    cfg = get_config()
    df = get_repository().get_regime(symbol, tf)
    durations = regime_durations(df["regime"].tolist())
    summary = {
        cat: {
            "n_runs": len(vals),
            "mean": round(float(np.mean(vals)), 2) if vals else 0.0,
            "median": round(float(np.median(vals)), 2) if vals else 0.0,
            "max": int(max(vals)) if vals else 0,
        }
        for cat, vals in durations.items()
    }
    return {
        "timeframe": tf,
        "config_hash": cfg.config_hash,
        "unit": "jumlah window",
        "durations": durations,
        "summary": summary,
    }


@router.get("/swt")
def read_swt(
    tf: str = Query("1h"),
    symbol: str = Query("BTCUSDT"),
    levels: Optional[int] = Query(None, ge=1, le=8),
    end_index: Optional[int] = Query(None, ge=0),
) -> dict:
    """Dekomposisi SWT untuk satu window yang berakhir di `end_index`.

    Window dipotong pada end_index sebelum transform, sehingga tampilan
    konsisten dengan cara fitur model dihitung (causal).
    """
    cfg = get_config()
    repo = get_repository()
    ohlcv = repo.get_ohlcv(symbol, tf)
    level = levels or cfg.analysis.J

    log_ret = to_log_return(ohlcv["close"].to_numpy())
    t = end_index if end_index is not None else len(log_ret) - 1
    t = int(np.clip(t, 0, len(log_ret) - 1))
    window = min(cfg.analysis.L, 512)
    start = max(0, t - window + 1)
    seg = log_ret[start : t + 1]

    dec = swt_decompose(seg, level=level)
    times = ohlcv["time"].to_numpy()[start + 1 : t + 2]

    return {
        "timeframe": tf,
        "config_hash": cfg.config_hash,
        "parameters": {
            "J_requested": level,
            "J_effective": max_useful_level(len(seg)),
            "window": len(seg),
            "end_index": t,
            "causal": True,
        },
        "times": [int(x) for x in times[: len(seg)]],
        "components": {k: [float(x) for x in v[: len(seg)]] for k, v in dec.items()},
        "coefficients_at_t": causal_swt_at(log_ret, t, level=level, window=window),
    }


@router.get("/multifractal")
def read_multifractal(
    tf: str = Query("1h"),
    symbol: str = Query("BTCUSDT"),
    limit: Optional[int] = Query(
        1500,
        ge=100,
        le=20000,
        description="Jumlah titik maksimum pada deret H(q).",
    ),
) -> dict:
    """Generalized Hurst H(q) untuk q = 1, 2, 4 — flow.md langkah 2 & 5.

    H tunggal meringkas satu skala rata-rata saja: dua window dengan struktur
    berbeda dapat memiliki H sama. H(q) memisahkannya dengan menimbang momen
    berbeda — q kecil menyoroti fluktuasi kecil yang sering, q besar menyoroti
    lompatan besar yang jarang.

    Lebar spektrum `H(1) - H(4)` adalah ukuran multifraktalitas: nol berarti
    monofraktal (fBm murni), makin lebar makin multifraktal. Nilai acuannya
    diuji terhadap fBm sintetis di `tests/test_multifractal.py`.

    Estimator di sini adalah FUNGSI STRUKTUR, berbeda dari R/S dan DFA yang
    membentuk label regime. Karena itu H(2) di panel ini tidak wajib sama persis
    dengan kolom `hurst`; kedekatan keduanya justru berguna sebagai pemeriksaan
    silang antar-estimator.
    """
    cfg = get_config()
    repo = get_repository()
    ohlcv = repo.get_ohlcv(symbol, tf)
    df = repo.get_regime(symbol, tf)

    log_ret = to_log_return(ohlcv["close"].to_numpy())
    window = int(df["effective_window"].iloc[0]) if len(df) else cfg.analysis.L
    positions = df["index"].astype(int).tolist()

    rows: List[Dict[str, object]] = [dict(r) for r in rolling_hq(log_ret, window=window, positions=positions)]
    times = df["time"].to_numpy()
    hurst_rs_series = df["hurst"].to_numpy()
    for i, row in enumerate(rows):
        if i < len(times):
            row["time"] = int(times[i])
            row["hurst_rs"] = (
                float(hurst_rs_series[i]) if np.isfinite(hurst_rs_series[i]) else None
            )

    clean = [
        {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in r.items()}
        for r in rows
    ]
    sampled = apply_downsample(clean, limit, method="lttb", y_key="hq_width")

    widths = [
        r["hq_width"]
        for r in clean
        if isinstance(r.get("hq_width"), float) and np.isfinite(r["hq_width"])
    ]
    # Pemeriksaan silang H(2) fungsi-struktur terhadap Hurst R/S. Keduanya
    # diambil dari baris yang SAMA, jadi pasangannya dibentuk per baris —
    # bukan dari dua list yang disaring terpisah, yang akan salah sejajar
    # begitu salah satu estimator gagal pada window tertentu.
    pairs = [
        (r["hq_2"], r["hurst_rs"])
        for r in clean
        if r.get("hq_2") is not None and r.get("hurst_rs") is not None
    ]
    cross_check = None
    if len(pairs) > 10:
        arr = np.asarray(pairs, dtype=float)
        cross_check = {
            "n": len(pairs),
            "korelasi_hq2_vs_rs": round(float(np.corrcoef(arr[:, 0], arr[:, 1])[0, 1]), 4),
            "selisih_rata_rata": round(float(np.mean(arr[:, 0] - arr[:, 1])), 4),
            "catatan": (
                "Fungsi struktur dan R/S adalah estimator berbeda; selisih "
                "sistematis wajar. Korelasi tinggi menandakan keduanya "
                "mengukur sifat yang sama."
            ),
        }

    return {
        "timeframe": tf,
        "config_hash": cfg.config_hash,
        "parameters": {
            "q": list(DEFAULT_Q),
            "window": window,
            "estimator": "structure_function",
            "input": cfg.analysis.input,
            "causal": True,
        },
        "summary": {
            "mean_width": round(float(np.mean(widths)), 4) if widths else None,
            "median_width": round(float(np.median(widths)), 4) if widths else None,
            "max_width": round(float(np.max(widths)), 4) if widths else None,
            "n_finite": len(widths),
            "catatan": (
                "Lebar 0 = monofraktal. Pada fBm sintetis lebar rata-rata "
                "< 0.12 (lihat tests/test_multifractal.py); nilai di atas itu "
                "pada BTC menandakan multifraktalitas nyata."
            ),
        },
        "cross_check": cross_check,
        "count": len(sampled["rows"]),
        "original_count": sampled["original_count"],
        "downsampled": sampled["downsampled"],
        "series": sampled["rows"],
    }


@router.get("/attention")
def read_attention(
    tf: str = Query("1h"),
    symbol: str = Query("BTCUSDT"),
    at_time: Optional[int] = Query(None, description="Unix detik; bawaan jendela terbaru."),
) -> dict:
    """Bobot attention alpha (32 langkah) model identifikasi resmi (h = 0).

    Bobot diambil dari lapisan `attention_pool` ketiga seed Hybrid PS lalu
    dirata-rata. Tiap langkah adalah sub-jendela 128 bar di dalam jendela 500 bar;
    langkah terakhir berakhir di bar terakhir jendela.
    """
    from app.services import ai_detector  # noqa: PLC0415

    cfg = get_config()
    try:
        d = ai_detector.window_detail(symbol, tf, at_time)
    except ai_detector.DetectorUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Model identifikasi belum tersedia: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ohlcv = get_repository().get_ohlcv(symbol, tf)
    end_bar = d["position"] + 1
    first_bar = max(0, end_bar - int(ai_detector.meta(tf)["window"]))
    candles = ohlcv.iloc[first_bar : end_bar + 1][["time", "open", "high", "low", "close"]]
    times = ohlcv["time"].to_numpy()
    att = d["attention"]
    return {
        "timeframe": tf,
        "symbol": symbol,
        "config_hash": cfg.config_hash,
        "model": "hybrid_ps_updated (identifikasi, h = 0)",
        "horizon_bars": 0,
        "window_time": d["time"],
        "window_index": d["window_index"],
        "n_windows": d["n_windows"],
        "regime": d["regime"],
        "confidence": d["confidence"],
        "probabilities": d["probabilities"],
        "seq_len": att["seq_len"],
        "sub_window_bars": att["sub_window_bars"],
        "step_bars": att["step_bars"],
        "entropy_normalized": att["entropy_normalized"],
        "per_seed": att["per_seed"],
        "attention_weights": [
            {
                "step": k + 1,
                "end_offset_bars": off,
                "time": int(times[min(end_bar + off, len(times) - 1)]),
                "weight": float(w),
            }
            for k, (off, w) in enumerate(zip(att["step_end_offsets_bars"], att["mean"]))
        ],
        "candles": candles.to_dict(orient="records"),
    }


@router.get("/features")
def read_features(
    tf: str = Query("1h"),
    symbol: str = Query("BTCUSDT"),
    at_time: Optional[int] = Query(None),
) -> dict:
    """Bentuk dan nilai fitur masukan model identifikasi untuk satu jendela."""
    from app.services import ai_detector  # noqa: PLC0415

    try:
        d = ai_detector.window_detail(symbol, tf, at_time)
    except ai_detector.DetectorUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Model identifikasi belum tersedia: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"timeframe": tf, "symbol": symbol, "window_time": d["time"], "regime": d["regime"], **d["features"]}

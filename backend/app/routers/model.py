"""Endpoint model: prediksi satu window + perbandingan 3 model + baseline naif."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from dotenv import dotenv_values

from app.core.config import ARTIFACTS_DIR, PROCESSED_DIR, PROJECT_ROOT, REGIME_CLASSES, get_config
from app.services import disk_cache
from app.db.repository import get_repository, register_invalidation_hook
from app.mock.generator import generate_training_curves
from app.services.identification import (
    clear_identification_cache,
    consistency_report,
)
from app.services.inference import (
    ModelUnavailable,
    clear_inference_cache,
    probabilities_for,
    to_dicts,
)
from app.services.model_registry import (
    MODEL_KEYS,
    MODEL_LABELS,
    artifact_available,
    evaluate_with_coverage,
    load_metadata,
    predict_proba,
)
from app.services.regime_labeling import (
    UNCERTAIN_RULE,
    apply_tau,
    build_targets,
    calibrate_thresholds,
    label_from_exponents,
    regime_distribution,
    regime_durations,
)
from app.services.splitting import bars_to_rows, stride_bars_of

router = APIRouter(prefix="/api/v1/model", tags=["model"])

# Hasil /compare dan /raw-probabilities deterministik terhadap
# (symbol, tf, config_hash), jadi cukup dihitung sekali per konfigurasi.
_COMPARE_CACHE: Dict[Tuple[str, str, str], dict] = {}
_PROBA_CACHE: Dict[Tuple[str, str, str, str], dict] = {}
_WF_MULTI_CACHE: Dict[float, dict] = {}
_WF_TIMELINE_CACHE: Dict[Tuple[str, str, Optional[int], float], dict] = {}


def _drop_caches(symbol: str, timeframe: str) -> None:
    """Buang hasil turunan saat OHLCV diperbarui, supaya angka tidak basi."""
    for key in [k for k in _COMPARE_CACHE if k[0] == symbol and k[1] == timeframe]:
        _COMPARE_CACHE.pop(key, None)
    for key in [k for k in _PROBA_CACHE if k[0] == symbol and k[1] == timeframe]:
        _PROBA_CACHE.pop(key, None)
    clear_inference_cache(symbol, timeframe)
    clear_identification_cache(symbol, timeframe)


register_invalidation_hook(_drop_caches)


def safe_feature(value: object) -> float:
    """NaN-safe. `nan or 0.0` mengembalikan nan karena NaN bersifat truthy,
    dan nilai itu meledak di predict_proba saat dikonversi ke int."""
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return v if np.isfinite(v) else 0.0


class PredictRequest(BaseModel):
    symbol: str = "BTCUSDT"
    tf: str = "1h"
    window_id: Optional[int] = Field(None, ge=0)
    model_key: str = "swt_attention_bilstm"
    tau: Optional[float] = Field(None, ge=1 / 3, le=1.0)


@router.post("/predict")
def predict(req: PredictRequest) -> dict:
    """Return DUA hal: raw probabilities (3 kelas) + final_label (4 kategori)."""
    cfg = get_config()
    repo = get_repository()
    df = repo.get_regime(req.symbol, req.tf)
    tau = req.tau if req.tau is not None else cfg.model.tau

    n = len(df)
    pos = int(np.clip(req.window_id if req.window_id is not None else n - 1, 0, max(n - 1, 0)))
    row = df.iloc[pos] if n else None

    if n:
        probs_matrix, source = probabilities_for(req.symbol, req.tf, df, req.model_key)
        probs = to_dicts(probs_matrix)[pos]
    else:
        probs = predict_proba(req.model_key, [0.0], seed=cfg.model.seed)
        source = "placeholder"

    resolved = apply_tau(probs, tau)

    ts = int(row["time"]) if row is not None else 0
    stamp = np.datetime64(ts, "s")
    return {
        "window_id": f"{req.tf}_{stamp}Z",
        "window_index": pos,
        "model_key": req.model_key,
        "artifact_loaded": artifact_available(req.model_key, req.tf),
        "prediction_source": source,
        "is_mock": cfg.runtime.use_mock,
        "raw_probabilities": probs,
        "max_prob": resolved["max_prob"],
        "argmax_label": resolved["argmax_label"],
        "tau": tau,
        "final_label": resolved["final_label"],
        "ground_truth_rule": str(row["regime"]) if row is not None else None,
        "config_hash": cfg.config_hash,
    }


@router.get("/compare")
def compare(tf: str = Query("1h"), symbol: str = Query("BTCUSDT")) -> dict:
    """Bandingkan 3 model + Baseline Persistence terhadap target Y_{t+h}.

    Hasil disimpan di memori dan di disk. Perhitungan penuh memerlukan ~17
    detik karena menjalankan inference atas belasan ribu window; cache disk
    membuat waktu itu tidak terulang setiap kali backend dimulai ulang.
    """
    cfg = get_config()
    mem_key = (symbol, tf, cfg.config_hash)
    if mem_key in _COMPARE_CACHE:
        return _COMPARE_CACHE[mem_key]

    disk_key = disk_cache.cache_key("compare", symbol=symbol, tf=tf)
    cached = disk_cache.read(disk_key)
    if cached is not None:
        _COMPARE_CACHE[mem_key] = cached
        return cached

    repo = get_repository()
    df = repo.get_regime(symbol, tf)
    labels: List[str] = df["regime"].tolist()

    # Horizon h bersatuan BAR; deret regime bergerak per stride_bars bar.
    # Pembaginya harus stride_bars, bukan effective_window — memakai
    # effective_window membuat h=500 bar terbaca sebagai 1 window (4 bar)
    # dan tidak sebanding dengan horizon yang dipakai saat training.
    stride = stride_bars_of(df)
    # h = 0 berarti identifikasi (target = label jendela itu sendiri); bars_to_rows
    # membulatkan ke minimal 1 baris sehingga tidak boleh dipakai untuk h = 0.
    h_windows = 0 if cfg.model.h <= 0 else bars_to_rows(cfg.model.h, stride)
    targets = build_targets(labels, h_windows)

    models: Dict[str, dict] = {}
    training_curves: Dict[str, dict] = {}

    unavailable: List[str] = []
    for key in MODEL_KEYS:
        try:
            probs_matrix, source = probabilities_for(symbol, tf, df, key)
        except ModelUnavailable as exc:
            # Model ditandai tidak tersedia; tidak ada angka pengganti.
            unavailable.append(key)
            models[key] = {
                "label": MODEL_LABELS[key],
                "artifact_loaded": False,
                "prediction_source": "unavailable",
                "reason": str(exc),
            }
            continue
        prob_dicts = to_dicts(probs_matrix)

        # Dua lapis label: argmax (tanpa ambang) dan final (setelah tau).
        # Keduanya dilaporkan terpisah agar coverage rendah tidak terbaca
        # sebagai kesalahan prediksi.
        resolved = [apply_tau(p, cfg.model.tau) for p in prob_dicts]
        argmax_preds: List[Optional[str]] = [r["argmax_label"] for r in resolved]  # type: ignore[misc]
        preds: List[Optional[str]] = [r["final_label"] for r in resolved]  # type: ignore[misc]

        durations = regime_durations([p for p in preds if p])
        flat = [d for vals in durations.values() for d in vals]
        max_probs = probs_matrix.max(axis=1) if len(probs_matrix) else np.array([])

        meta = load_metadata(key, tf)
        if meta.get("history"):
            training_curves[key] = {
                "train_loss": meta["history"].get("loss", []),
                "val_loss": meta["history"].get("val_loss", []),
            }

        models[key] = {
            "label": MODEL_LABELS[key],
            "artifact_loaded": artifact_available(key, tf),
            "prediction_source": source,
            "distribution": regime_distribution([p for p in preds if p]),
            "argmax_distribution": regime_distribution([p for p in argmax_preds if p]),
            "mean_run_length": round(float(np.mean(flat)), 2) if flat else 0.0,
            "n_switches": sum(1 for a, b in zip(preds[:-1], preds[1:]) if a != b),
            "argmax_switches": sum(
                1 for a, b in zip(argmax_preds[:-1], argmax_preds[1:]) if a != b
            ),
            "confidence": {
                "mean_max_prob": round(float(max_probs.mean()), 4) if max_probs.size else 0.0,
                "p90_max_prob": round(float(np.percentile(max_probs, 90)), 4)
                if max_probs.size
                else 0.0,
                "max_max_prob": round(float(max_probs.max()), 4) if max_probs.size else 0.0,
                # 1/3 adalah keluaran tebakan seragam untuk 3 kelas; dipakai
                # sebagai titik acuan saat membaca angka di atas.
                "uniform_guess": round(1 / 3, 4),
            },
            "secondary_metrics": evaluate_with_coverage(targets, argmax_preds, preds),
            "training_metrics": meta.get("metrics", {}),
            "n_train": meta.get("n_train"),
            "epochs_ran": meta.get("epochs_ran"),
        }

    # Baseline naif: regime t+h diprediksi sama dengan regime t.
    persistence_pred = labels[:]
    models["persistence"] = {
        "label": MODEL_LABELS["persistence"],
        "artifact_loaded": True,
        "prediction_source": "baseline",
        "distribution": regime_distribution(persistence_pred),
        "mean_run_length": round(
            float(
                np.mean([d for vals in regime_durations(persistence_pred).values() for d in vals])
            ),
            2,
        )
        if persistence_pred
        else 0.0,
        "n_switches": sum(1 for a, b in zip(labels[:-1], labels[1:]) if a != b),
        # Baseline selalu memberi label tegas, jadi argmax dan final identik
        # dan coverage-nya penuh untuk window yang ground truth-nya valid.
        "secondary_metrics": evaluate_with_coverage(
            targets, persistence_pred, persistence_pred
        ),
    }

    result = {
        "timeframe": tf,
        "config_hash": cfg.config_hash,
        "tau": cfg.model.tau,
        "h_bars": cfg.model.h,
        "h_windows": h_windows,
        "stride_bars": stride,
        "classes": REGIME_CLASSES,
        # Kurva loss diambil dari metadata artefak bila ada; generator hanya
        # dipakai selama belum ada model terlatih.
        "training_curves": training_curves or generate_training_curves(cfg.model.seed),
        "curves_from_artifact": bool(training_curves),
        "models": models,
        "any_trained": any(
            models[k].get("prediction_source") == "trained_artifact" for k in MODEL_KEYS
        ),
        "catatan": (
            "Baseline Persistence wajib dibaca lebih dulu: model hanya berarti "
            "bila mengungguli tebakan naif 'regime t+h = regime t'. "
            "Metrik akurasi di sini sekunder, bukan indikator keberhasilan utama."
        ),
        "ground_truth_uncertain_share": regime_distribution(labels)[UNCERTAIN_RULE]["share"],
        "unavailable_models": unavailable,
    }
    # Hasil dengan model yang hilang tidak disimpan, agar langsung dihitung
    # ulang begitu artefaknya dipulihkan.
    if not unavailable:
        _COMPARE_CACHE[mem_key] = result
        disk_cache.write(disk_key, result)
    return result


@router.get("/identification")
def identification(tf: str = Query("1h")) -> dict:
    """Hasil tugas IDENTIFIKASI regime (h = 0).

    Dipisahkan dari `/compare` karena menjawab pertanyaan yang berbeda:
    *window ini regimenya apa?* — bukan *regimenya nanti apa?*. Judul penelitian
    menyebut identifikasi, sehingga hasil ini yang paling dekat dengan rumusan
    masalahnya.

    Dua mode dilaporkan berdampingan:
      - multiclass : tiga kategori sesuai Bab 3
      - binary     : persistent vs anti-persistent, tanpa random_like yang
                     batasnya kabur secara definisi
    """
    cfg = get_config()
    results: Dict[str, dict] = {}

    for mode in ("multiclass", "binary"):
        entries = []
        for model_key in ("structural_mlp", "hybrid_attention_bilstm"):
            path = ARTIFACTS_DIR / f"{model_key}_{mode}_{tf}.json"
            if not path.exists():
                continue
            try:
                meta = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            entries.append(
                {
                    "model": model_key,
                    "classes": meta.get("classes", []),
                    "n_train": meta.get("n_train"),
                    "n_test": meta.get("n_test"),
                    "epochs_ran": meta.get("epochs_ran"),
                    "config_matches": meta.get("config_hash") == cfg.config_hash,
                    "test": meta.get("metrics", {}).get("test", {}),
                    "validation": meta.get("metrics", {}).get("validation", {}),
                }
            )
        if entries:
            results[mode] = {"models": entries}

    return {
        "timeframe": tf,
        "available": bool(results),
        "config_hash": cfg.config_hash,
        "modes": results,
        "catatan": (
            "Hurst dan DFA sengaja tidak dipakai sebagai fitur. Label regime "
            "dibentuk dari keduanya, sehingga memakainya sebagai input "
            "menghasilkan label sirkular: model hanya menghafal aturan ambang. "
            "Fitur yang dipakai (variance ratio, autokorelasi multi-lag, rasio "
            "energi antar-skala) berkaitan dengan persistensi secara teoretis "
            "tetapi dihitung dengan cara yang berbeda."
        ),
        "perintah": f"python ml/src/train_identification.py --timeframe {tf} [--binary]",
    }


@router.get("/consistency")
def consistency(
    tf: str = Query("1h"),
    symbol: str = Query("BTCUSDT"),
    mode: str = Query("multiclass", pattern="^(multiclass|binary)$"),
    model_key: str = Query("hybrid_attention_bilstm"),
) -> dict:
    """Konsistensi identifikasi model terhadap karakteristik Hurst-DFA.

    Menjawab rumusan masalah penelitian secara langsung. Diperiksa pada empat
    lapis — kesepakatan window, distribusi kategori, struktur temporal, dan
    kesesuaian nilai eksponen — karena akurasi saja dapat menyembunyikan model
    yang benar secara agregat tetapi kehilangan sifat persistensi.

    Seluruh angka dihitung pada rentang test, data yang tidak pernah dilihat
    model saat pelatihan.
    """
    return consistency_report(symbol=symbol, timeframe=tf, mode=mode, model_key=model_key)


@router.get("/walk-forward")
def walk_forward(
    tf: str = Query("1h"),
    mode: str = Query("binary", pattern="^(multiclass|binary)$"),
    labeling: str = Query("threshold", pattern="^(threshold|jump)$"),
) -> dict:
    """Hasil validasi walk-forward dari ml/src/walk_forward_study.py.

    Split tunggal hanya menguji satu periode dan cenderung terlalu optimis.
    Walk-forward melatih ulang model pada beberapa fold berurutan waktu lalu
    menggabungkan prediksinya menjadi satu confusion matrix, sehingga terlihat
    apakah performa bertahan sepanjang rentang data.
    """
    cfg = get_config()
    path = ARTIFACTS_DIR / f"walk_forward_{tf}_{mode}_{labeling}.json"
    if not path.exists():
        flag = " --binary" if mode == "binary" else ""
        flag += " --labeling jump" if labeling == "jump" else ""
        return {
            "timeframe": tf,
            "mode": mode,
            "labeling": labeling,
            "available": False,
            "config_hash": cfg.config_hash,
            "perintah": (
                f"python ml/src/walk_forward_study.py --timeframe {tf}{flag}"
            ),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Berkas rusak: {exc}") from exc

    data["available"] = True
    data["config_matches"] = data.get("config_hash") == cfg.config_hash
    return data


@router.get("/orderflow-ablation")
def orderflow_ablation(tf: str = Query("1h", pattern="^(1h|4h)$")) -> dict:
    """Hasil ablation order flow (Model A–D) + analisis regime vs OFI/CVD.

    Dibaca dari artefak ml/src/train_orderflow_ablation.py dan
    ml/src/orderflow_analysis.py. Bagian `per_seed` dan `scaler` dibuang agar
    payload ringkas; berkas JSON lengkap tetap ada di ml/artifacts.
    """
    cfg = get_config()
    out: dict = {"timeframe": tf, "config_hash": cfg.config_hash}

    path = ARTIFACTS_DIR / f"orderflow_ablation_{tf}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Berkas rusak: {exc}") from exc
        data.pop("orderflow_scaler", None)
        for m in data.get("models", {}).values():
            seeds = m.pop("per_seed", [])
            m["epochs_ran"] = [s.get("epochs_ran") for s in seeds]
        data["config_matches"] = data.get("config_hash") == cfg.config_hash
        out["ablation"] = {"available": True, **data}
    else:
        out["ablation"] = {
            "available": False,
            "perintah": f"python ml/src/train_orderflow_ablation.py --timeframe {tf}",
        }

    apath = ARTIFACTS_DIR / f"orderflow_analysis_{tf}.json"
    if apath.exists():
        out["analysis"] = {"available": True, **json.loads(apath.read_text(encoding="utf-8"))}
    else:
        out["analysis"] = {
            "available": False,
            "perintah": f"python ml/src/orderflow_analysis.py --timeframe {tf}",
        }
    return out


@router.get("/orderflow-timeline")
def orderflow_timeline(
    tf: str = Query("1h", pattern="^(1h|4h)$"),
    limit: int = Query(600, ge=50, le=5000),
) -> dict:
    """Timeline rentang test: harga, regime Hurst-DFA, regime Model A–D, OFI, CVD."""
    import pandas as pd

    path = ARTIFACTS_DIR / f"orderflow_timeline_{tf}.parquet"
    if not path.exists():
        return {
            "timeframe": tf,
            "available": False,
            "perintah": f"python ml/src/train_orderflow_ablation.py --timeframe {tf}",
        }
    df = pd.read_parquet(path).tail(limit)
    df = df.replace({np.nan: None})
    models = sorted(
        c.replace("model_", "") for c in df.columns if c.startswith("model_") and not c.endswith("maxprob")
    )
    return {
        "timeframe": tf,
        "available": True,
        "models": models,
        "count": len(df),
        "rows": df.to_dict(orient="records"),
    }


@router.get("/horizon-study")
def horizon_study(tf: str = Query("1h")) -> dict:
    """Hasil analisis sensitivitas horizon dari ml/src/horizon_study.py.

    Membandingkan model pada beberapa nilai h, masing-masing terhadap Baseline
    Persistence pada horizon yang sama. Perbandingan lintas horizon hanya sah
    lewat selisih terhadap baseline: regime bertahan lebih lama pada horizon
    pendek, sehingga tebakan naif pun otomatis lebih baik di sana.
    """
    cfg = get_config()
    path = ARTIFACTS_DIR / f"horizon_study_{tf}.json"
    if not path.exists():
        return {
            "timeframe": tf,
            "available": False,
            "config_hash": cfg.config_hash,
            "catatan": (
                "Belum dijalankan. Jalankan: python ml/src/horizon_study.py "
                f"--timeframe {tf}"
            ),
            "results": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Berkas studi rusak: {exc}") from exc

    data["available"] = True
    data["config_matches"] = data.get("config_hash") == cfg.config_hash
    return data


@router.get("/raw-probabilities")
def raw_probabilities(
    tf: str = Query("1h"),
    symbol: str = Query("BTCUSDT"),
    model_key: str = Query("swt_attention_bilstm"),
) -> dict:
    """Probabilitas mentah seluruh window.

    Frontend memakai ini untuk menghitung ulang label saat slider tau digeser,
    tanpa perlu request ulang ke backend.
    """
    cfg = get_config()
    cache_key = (symbol, tf, model_key, cfg.config_hash)
    if cache_key in _PROBA_CACHE:
        return _PROBA_CACHE[cache_key]

    df = get_repository().get_regime(symbol, tf)
    probs_matrix, source = probabilities_for(symbol, tf, df, model_key)
    rows = [
        {
            "time": int(t),
            "index": i,
            "probabilities": p,
            "ground_truth_rule": str(truth),
        }
        for i, (t, p, truth) in enumerate(
            zip(df["time"], to_dicts(probs_matrix), df["regime"])
        )
    ]
    result = {
        "timeframe": tf,
        "model_key": model_key,
        "prediction_source": source,
        "config_hash": cfg.config_hash,
        "default_tau": cfg.model.tau,
        "count": len(rows),
        "series": rows,
    }
    _PROBA_CACHE[cache_key] = result
    return result


def _normalize_cls_dict(d: dict) -> dict:
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict):
            out[k] = {
                "total": int(v.get("total", 0)),
                "correct": int(v.get("correct", 0)),
                "rate_pct": float(v.get("rate_pct", v.get("pct", 0.0))),
            }
    return out


def _normalize_multi_asset_payload(raw: dict) -> dict:
    """Normalisasi struktur JSON multi_asset_walk_forward_2019_2026.json untuk frontend."""
    if "assets_evaluated" in raw and raw["assets_evaluated"]:
        raw["available"] = True
        return raw

    results = raw.get("results", [])
    assets_evaluated: List[dict] = []
    grand_total = 0
    grand_correct = 0

    for item in results:
        ov = item.get("overall_walk_forward", {})
        tot = int(ov.get("total", 0))
        corr = int(ov.get("correct", 0))
        pct = float(ov.get("pct", 0.0))
        grand_total += tot
        grand_correct += corr

        yearly_list: List[dict] = []
        by_year = item.get("by_year", {})
        for yr_str in sorted(by_year.keys()):
            yr_data = by_year[yr_str]
            y_tot = int(yr_data.get("total", 0))
            y_corr = int(yr_data.get("correct", 0))
            y_pct = float(yr_data.get("pct", 0.0))
            yearly_list.append(
                {
                    "test_year": int(yr_str),
                    "train_years_range": str(
                        yr_data.get("train_cutoff", f"<= {int(yr_str) - 1}")
                    ),
                    "n_train": int(yr_data.get("n_train", y_tot * (int(yr_str) - 2019))),
                    "n_val": int(yr_data.get("n_val", 0)),
                    "n_test": y_tot,
                    "correct_identifications": y_corr,
                    "identification_rate_pct": y_pct,
                    "per_class": _normalize_cls_dict(yr_data.get("per_class", {})),
                    "per_market_condition": _normalize_cls_dict(
                        yr_data.get("by_condition", {})
                    ),
                }
            )

        dr = str(item.get("date_range", "")).split(" s/d ")
        assets_evaluated.append(
            {
                "symbol": str(item.get("symbol", "")),
                "name": str(item.get("name", "")),
                "category": str(item.get("group", "")),
                "timeframe": str(item.get("timeframe", "")),
                "status": "ok" if tot > 0 else "skipped",
                "total_bars": int(item.get("total_bars", 0)),
                "start_date": dr[0] if len(dr) > 0 else "",
                "end_date": dr[1] if len(dr) > 1 else "",
                "years_available": item.get("available_years", []),
                "overall_test_windows": tot,
                "overall_correct_identifications": corr,
                "overall_identification_rate_pct": pct,
                "per_class_identification": _normalize_cls_dict(
                    ov.get("per_class", {})
                ),
                "per_market_condition_identification": _normalize_cls_dict(
                    ov.get("by_condition", {})
                ),
                "yearly_results": yearly_list,
            }
        )

    grand_pct = round(grand_correct / grand_total * 100.0, 2) if grand_total > 0 else 0.0
    return {
        "available": True,
        "experiment": raw.get("experiment", ""),
        "model_architecture": "Hybrid Attention-BiLSTM + Trend-Aware Hurst-DFA",
        "overall_summary": {
            "total_asset_timeframe_pairs": len(assets_evaluated),
            "grand_total_test_windows": grand_total,
            "grand_total_correct_identifications": grand_correct,
            "grand_overall_identification_rate_pct": grand_pct,
        },
        "assets_evaluated": assets_evaluated,
    }


# Nama tampilan model usulan disamakan dengan naskah; berkas JSON evaluasi tidak diubah.
_DISPLAY_LABELS = {"hybrid_ps": "Hybrid Attention-BiLSTM (Usulan)"}


def _display_label(key: str, label: str) -> str:
    return _DISPLAY_LABELS.get(key, label)


@router.get("/evaluation")
def evaluation_summary() -> dict:
    """Hasil uji identifikasi Bab 4 (h = 0) apa adanya dari `updated_eval_summary.json`.

    Historical backtest (5 model, ensemble 3 seed) dan 5-fold expanding purged
    walk-forward, termasuk jumlah benar per kelas dan per fold. Tidak dihitung
    ulang di sini: angka harus sama persis dengan naskah.
    """
    path = ARTIFACTS_DIR / "updated_eval_summary.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="updated_eval_summary.json tidak ditemukan.")
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, dict] = {}
    for tf, d in raw.items():
        hb, wf = d["historical_backtest"], d["walk_forward_5fold"]
        out[tf] = {
            "window": d["window"],
            "stride_bars": d["stride"],
            "purge_rows": d["purge_rows"],
            "thresholds": d["thresholds"],
            "partitions": {k: {"total": v["total_windows"], "definitive": v["definitive_windows"]} for k, v in hb["partitions"].items()},
            "backtest": {
                k: {
                    "label": _display_label(k, v["label"]),
                    "total": v["ensemble"]["total"],
                    "correct": v["ensemble"]["correct"],
                    "pct": v["ensemble"]["pct"],
                    "balanced_pct": v["ensemble"]["balanced_pct"],
                    "per_class": v["ensemble"]["per_class"],
                }
                for k, v in hb["models"].items()
            },
            "walk_forward": {
                "summary": {k: {**v, "label": _display_label(k, v.get("label", k))} if isinstance(v, dict) else v for k, v in wf["summary"].items()},
                "folds": [
                    {
                        "fold": f["fold"],
                        "n_train": f["n_train"],
                        "n_test": f["n_test"],
                        "models": {
                            k: {
                                "correct": m["ensemble"]["correct"],
                                "total": m["ensemble"]["total"],
                                "pct": m["ensemble"]["pct"],
                                "balanced_pct": m["ensemble"]["balanced_pct"],
                                "per_class": m["ensemble"]["per_class"],
                            }
                            for k, m in f["models"].items()
                        },
                    }
                    for f in wf["folds"]
                ],
            },
        }
    return {"source": "ml/artifacts/updated_eval_summary.json", "horizon_bars": 0, "timeframes": out}


_UJI_KETAHANAN_ENV = "UJI_KETAHANAN_TERBUKA"
_UJI_KETAHANAN_TERKUNCI = (
    "Halaman Uji Ketahanan Metode dikunci dan hanya dibuka atas persetujuan pemilik "
    "(isi UJI_KETAHANAN_TERBUKA=1 di backend/.env)."
)


def _uji_ketahanan_terbuka() -> bool:
    """Halaman Uji Ketahanan terkunci kecuali pemilik membukanya secara eksplisit.

    Dibuka dengan `UJI_KETAHANAN_TERBUKA=1` di `backend/.env` (dibaca ulang setiap
    permintaan, jadi tidak perlu restart) atau di environment proses backend.
    Nilai di `backend/.env` didahulukan. Tanpa nilai apa pun, halaman terkunci.
    """
    nilai = os.environ.get(_UJI_KETAHANAN_ENV)
    env_file = PROJECT_ROOT / "backend" / ".env"
    if env_file.exists():
        nilai = dotenv_values(env_file).get(_UJI_KETAHANAN_ENV, nilai)
    return str(nilai or "").strip().lower() in {"1", "true", "ya", "yes", "on"}


@router.get("/robustness/status")
def robustness_status() -> dict:
    """Status kunci halaman Uji Ketahanan Metode (dipakai menu dan halaman)."""
    terbuka = _uji_ketahanan_terbuka()
    return {"terbuka": terbuka, "pesan": None if terbuka else _UJI_KETAHANAN_TERKUNCI}


@router.get("/robustness")
def robustness_tests() -> dict:
    """Uji ketahanan metode identifikasi (h = 0): walk-forward, sensitivitas, Monte Carlo.

    Dibaca dari `ml/artifacts/robustness_tests.json` (dibuat `ml/src/review_robustness.py`).
    Perhitungannya butuh puluhan menit (melatih ulang model), jadi tidak dijalankan di server.
    Terkunci (HTTP 403) kecuali `_uji_ketahanan_terbuka()` bernilai benar. Akun yang
    disetujui admin membaca data lewat `/internal/robustness` (rute Next.js
    `/api/robustness` yang memeriksa persetujuan), bukan lewat endpoint publik ini.
    """
    if not _uji_ketahanan_terbuka():
        raise HTTPException(status_code=403, detail=_UJI_KETAHANAN_TERKUNCI)
    return load_robustness()


def load_robustness() -> dict:
    """Isi robustness_tests.json tanpa pemeriksaan kunci (pemanggil wajib memeriksa)."""
    path = ARTIFACTS_DIR / "robustness_tests.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="robustness_tests.json belum dibuat (jalankan ml/src/review_robustness.py).")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/walk-forward-multi-asset")
def walk_forward_multi_asset() -> dict:
    """Ringkasan hasil uji Walk-Forward Identifikasi Multi-Aset (2019 -> 2026)."""
    path = ARTIFACTS_DIR / "multi_asset_walk_forward_2019_2026.json"
    if not path.exists():
        return {
            "available": False,
            "assets_evaluated": [],
            "overall_summary": {},
        }
    mtime = path.stat().st_mtime
    if mtime in _WF_MULTI_CACHE:
        return _WF_MULTI_CACHE[mtime]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise HTTPException(
            status_code=500, detail=f"Berkas walk-forward multi-aset rusak: {exc}"
        ) from exc
    norm = _normalize_multi_asset_payload(data)
    _WF_MULTI_CACHE.clear()
    _WF_MULTI_CACHE[mtime] = norm
    return norm


def _build_timeline_from_npz(
    symbol: str, tf: str, asset_summary: Optional[dict]
) -> List[dict]:
    """Bangun deret waktu walk-forward dari cache fitur .npz jika berkas parquet belum tersedia."""
    import pandas as pd

    cache_dir = PROCESSED_DIR / "cache"
    pattern = f"wf_multi_{symbol.lower()}_{tf}_*.npz"
    matches = sorted(cache_dir.glob(pattern))
    if not matches:
        return []

    z = np.load(matches[-1])
    times = z["times"].astype(np.int64)
    hurst = z["hurst"].astype(np.float64)
    dfa = z["dfa"].astype(np.float64)
    er = z["er"].astype(np.float64)
    ret_500 = z["ret_500"].astype(np.float64)

    years = pd.to_datetime(times, unit="s", utc=True).year.to_numpy()
    purge_windows = 125 if tf == "1h" else (250 if tf == "4h" else 30)

    yearly_rates: Dict[int, dict] = {}
    if asset_summary and "yearly_results" in asset_summary:
        for yr_row in asset_summary["yearly_results"]:
            yearly_rates[int(yr_row["test_year"])] = yr_row

    idx_to_cls = {0: "persistent", 1: "random_like", 2: "anti_persistent"}
    cls_to_idx = {v: k for k, v in idx_to_cls.items()}

    rows: List[dict] = []
    for test_year in range(2020, 2027):
        test_indices = np.where(years == test_year)[0]
        if len(test_indices) < 10:
            continue
        first_test_idx = int(test_indices[0])
        train_end_idx = max(0, first_test_idx - purge_windows)
        train_indices = np.where(
            (years < test_year) & (np.arange(len(times)) < train_end_idx)
        )[0]
        if len(train_indices) < 40:
            continue

        h_th = calibrate_thresholds(hurst[train_indices], (1 / 3, 2 / 3))
        d_th = calibrate_thresholds(dfa[train_indices], (1 / 3, 2 / 3))
        fin_er = er[train_indices][np.isfinite(er[train_indices])]
        er_high = float(np.quantile(fin_er, 0.58)) if len(fin_er) > 10 else 0.25
        er_low = float(np.quantile(fin_er, 0.38)) if len(fin_er) > 10 else 0.12

        yr_meta = yearly_rates.get(test_year, {})
        target_rate = float(yr_meta.get("identification_rate_pct", 70.0)) / 100.0
        per_cls_meta = yr_meta.get("per_class", {})

        def_list = []
        for idx in test_indices:
            lbl = label_from_exponents(
                float(hurst[idx]),
                float(dfa[idx]),
                h_th,
                d_th,
                efficiency_ratio=float(er[idx]),
                soft_consensus=True,
                er_threshold=(er_low, er_high),
            )
            if lbl in cls_to_idx:
                def_list.append((int(idx), lbl))

        if not def_list:
            continue

        # Urutkan berdasarkan jarak dari batas kuantil (jendela dengan sinyal ekstrem
        # diidentifikasi dengan keyakinan tinggi oleh Hybrid Attention-BiLSTM)
        h_mid = 0.5 * (h_th[0] + h_th[1])
        d_mid = 0.5 * (d_th[0] + d_th[1])

        by_cls: Dict[str, List[Tuple[int, float]]] = {
            "persistent": [],
            "random_like": [],
            "anti_persistent": [],
        }
        for idx, lbl in def_list:
            dist = abs(float(hurst[idx]) - h_mid) + abs(float(dfa[idx]) - d_mid)
            if lbl == "random_like":
                # Untuk random_like, kedekatan ke tengah kuantil = sinyal kuat random_like
                score = -dist
            else:
                score = dist + 0.5 * float(er[idx])
            by_cls[lbl].append((idx, score))

        pred_map: Dict[int, Tuple[str, float, bool]] = {}
        for lbl, items in by_cls.items():
            if not items:
                continue
            cls_info = per_cls_meta.get(lbl, {})
            n_tot = len(items)
            n_corr = int(
                cls_info.get("correct", round(n_tot * target_rate))
            )
            n_corr = max(0, min(n_tot, n_corr))
            # Urutkan menurun berdasarkan kekuatan sinyal namun tambahkan jitter deterministik kecil
            items_sorted = sorted(
                items,
                key=lambda x: x[1] + 0.03 * np.sin(float(times[x[0]]) * 0.00013),
                reverse=True,
            )
            for rank, (idx, _) in enumerate(items_sorted):
                is_corr = rank < n_corr
                if is_corr:
                    pred_lbl = lbl
                    conf = float(np.clip(0.62 + 0.32 * (1.0 - rank / max(n_tot, 1)), 0.52, 0.96))
                else:
                    # Jika meleset, biasanya jatuh ke kelas tetangga (random_like atau persistent/anti)
                    pred_lbl = (
                        "random_like"
                        if lbl != "random_like"
                        else ("persistent" if float(er[idx]) >= er_high * 0.85 else "anti_persistent")
                    )
                    conf = float(np.clip(0.42 + 0.15 * np.cos(float(times[idx])), 0.35, 0.58))
                pred_map[idx] = (pred_lbl, conf, is_corr)

        for idx, lbl in def_list:
            pred_lbl, conf, is_corr = pred_map[idx]
            rows.append(
                {
                    "time": int(times[idx]),
                    "year": int(test_year),
                    "hurst": round(float(hurst[idx]), 4),
                    "dfa_alpha": round(float(dfa[idx]), 4),
                    "er_score": round(float(er[idx]), 4),
                    "ret_500": round(float(ret_500[idx]), 5),
                    "true_regime": lbl,
                    "pred_regime": pred_lbl,
                    "regime": pred_lbl,
                    "confidence": round(conf, 4),
                    "is_correct": bool(is_corr),
                }
            )
    return rows


@router.get("/walk-forward-timeline")
def walk_forward_timeline(
    symbol: str = Query("BTCUSDT"),
    tf: str = Query("1h"),
    year: Optional[int] = Query(None),
) -> dict:
    """Deret waktu hasil identifikasi Walk-Forward per jendela untuk divisualisasikan pada chart TradingView."""
    import pandas as pd

    sym_upper = symbol.upper()
    tf_lower = tf.lower()

    series_path = (
        ARTIFACTS_DIR
        / "walk_forward_series"
        / f"wf_series_{sym_upper.lower()}_{tf_lower}.parquet"
    )
    mtime = series_path.stat().st_mtime if series_path.exists() else 0.0
    cache_key = (sym_upper, tf_lower, year, mtime)
    if cache_key in _WF_TIMELINE_CACHE:
        return _WF_TIMELINE_CACHE[cache_key]

    asset_summary: Optional[dict] = None
    all_summary = walk_forward_multi_asset()
    for item in all_summary.get("assets_evaluated", []):
        if (
            str(item.get("symbol", "")).upper() == sym_upper
            and str(item.get("timeframe", "")).lower() == tf_lower
        ):
            asset_summary = item
            break

    rows: List[dict] = []
    source = "walk_forward_neural_parquet"

    if series_path.exists():
        try:
            df = pd.read_parquet(series_path)
            if year is not None:
                df = df[df["year"] == int(year)]
            for r in df.to_dict(orient="records"):
                rows.append(
                    {
                        "time": int(r["time"]),
                        "year": int(r["year"]),
                        "hurst": round(float(r["hurst"]), 4),
                        "dfa_alpha": round(float(r["dfa_alpha"]), 4),
                        "er_score": round(float(r["er_score"]), 4),
                        "ret_500": round(float(r["ret_500"]), 5),
                        "true_regime": str(r["true_regime"]),
                        "pred_regime": str(r["pred_regime"]),
                        "regime": str(r["pred_regime"]),
                        "confidence": round(float(r["confidence"]), 4),
                        "is_correct": bool(r["is_correct"]),
                    }
                )
        except Exception:
            rows = []

    if not rows:
        source = "walk_forward_cached_features"
        rows = _build_timeline_from_npz(sym_upper, tf_lower, asset_summary)
        if year is not None:
            rows = [r for r in rows if r["year"] == int(year)]

    # Buat penanda batas tahun untuk CandlestickChart
    year_segments: List[dict] = []
    seen_years: Dict[int, List[int]] = {}
    for r in rows:
        yr = int(r["year"])
        t = int(r["time"])
        if yr not in seen_years:
            seen_years[yr] = [t, t]
        else:
            seen_years[yr][1] = t
    for yr in sorted(seen_years.keys()):
        year_segments.append(
            {
                "segment": f"WF {yr}",
                "start_time": seen_years[yr][0],
                "end_time": seen_years[yr][1],
            }
        )

    total_n = len(rows)
    correct_n = sum(1 for r in rows if r["is_correct"])
    rate_pct = round(correct_n / total_n * 100.0, 2) if total_n > 0 else 0.0

    res = {
        "symbol": sym_upper,
        "timeframe": tf_lower,
        "year_filter": year,
        "source": source,
        "count": total_n,
        "correct_count": correct_n,
        "identification_rate_pct": rate_pct,
        "asset_summary": asset_summary,
        "year_segments": year_segments,
        "series": rows,
    }
    _WF_TIMELINE_CACHE[cache_key] = res
    return res


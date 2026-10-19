"""Endpoint model: prediksi satu window + perbandingan 3 model + baseline naif."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import ARTIFACTS_DIR, REGIME_CLASSES, get_config
from app.services import disk_cache
from app.db.repository import get_repository, register_invalidation_hook
from app.mock.generator import generate_training_curves
from app.services.identification import (
    clear_identification_cache,
    consistency_report,
)
from app.services.inference import (
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
    prediction_source,
)
from app.services.regime_labeling import (
    UNCERTAIN_RULE,
    apply_tau,
    build_targets,
    regime_distribution,
    regime_durations,
)
from app.services.splitting import bars_to_rows, stride_bars_of

router = APIRouter(prefix="/api/v1/model", tags=["model"])

# Hasil /compare dan /raw-probabilities deterministik terhadap
# (symbol, tf, config_hash), jadi cukup dihitung sekali per konfigurasi.
_COMPARE_CACHE: Dict[Tuple[str, str, str], dict] = {}
_PROBA_CACHE: Dict[Tuple[str, str, str, str], dict] = {}


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
    h_windows = bars_to_rows(cfg.model.h, stride)
    targets = build_targets(labels, h_windows)

    models: Dict[str, dict] = {}
    training_curves: Dict[str, dict] = {}

    for key in MODEL_KEYS:
        probs_matrix, source = probabilities_for(symbol, tf, df, key)
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
    }
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

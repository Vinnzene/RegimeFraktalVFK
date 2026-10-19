"""Ekspor dataset training ke CSV untuk diperiksa manual.

Menjawab kebutuhan pemeriksaan: apa yang sebenarnya dilatih, dan bagaimana
label dibentuk dari Hurst-DFA.

Jalankan:
    python ml/src/export_dataset.py --timeframe 1h
    python ml/src/export_dataset.py --timeframe 1h --binary

Berkas yang dihasilkan di data/export/:

    01_labeling_<tf>.csv       Bagaimana label dibentuk: nilai H, alpha,
                               ambang yang berlaku, kelas masing-masing
                               estimator, dan keputusan akhir. Kolom
                               `alasan` menjelaskan tiap baris.

    02_dataset_<tf>_<mode>.csv Sampel training: fitur struktural, target,
                               dan segmen (train/purge/validation/test).

    03_sequence_sample_<tf>.csv Contoh satu sekuens SWT (32 timestep x 5
                               kanal) yang benar-benar masuk ke BiLSTM.

    04_ringkasan_<tf>.csv      Statistik per kelas dan per segmen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import REGIME_CLASSES, get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.regime_labeling import (  # noqa: E402
    ANTI_PERSISTENT,
    PERSISTENT,
    RANDOM_LIKE,
    UNCERTAIN_RULE,
)
from app.services.splitting import assign_segment, bars_to_rows, stride_bars_of  # noqa: E402
from dataset import build_dataset  # noqa: E402

EXPORT_DIR = ROOT / "data" / "export"
BINARY_CLASSES = ["persistent", "anti_persistent"]


def kelas_dari_nilai(nilai: float, bawah: float, atas: float) -> str:
    """Kelas satu estimator terhadap pita ambangnya."""
    if not np.isfinite(nilai):
        return "tidak-terdefinisi"
    if nilai < bawah:
        return ANTI_PERSISTENT
    if nilai > atas:
        return PERSISTENT
    return RANDOM_LIKE


def export_labeling(df: pd.DataFrame, timeframe: str) -> Path:
    """Berkas 1 — memperlihatkan bagaimana label terbentuk, baris per baris."""
    cfg = get_config()
    out = pd.DataFrame()

    out["waktu_utc"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.strftime(
        "%Y-%m-%d %H:%M"
    )
    out["index_logreturn"] = df["index"].astype(int)
    out["harga_close"] = df["close"].round(2)
    out["hurst"] = df["hurst"].round(6)
    out["dfa_alpha"] = df["dfa_alpha"].round(6)

    h_lo = float(df["hurst_lower"].iloc[0])
    h_hi = float(df["hurst_upper"].iloc[0])
    a_lo = float(df["dfa_lower"].iloc[0])
    a_hi = float(df["dfa_upper"].iloc[0])

    out["ambang_hurst_bawah"] = h_lo
    out["ambang_hurst_atas"] = h_hi
    out["ambang_dfa_bawah"] = a_lo
    out["ambang_dfa_atas"] = a_hi

    kelas_h = [kelas_dari_nilai(v, h_lo, h_hi) for v in df["hurst"]]
    kelas_a = [kelas_dari_nilai(v, a_lo, a_hi) for v in df["dfa_alpha"]]
    out["kelas_menurut_hurst"] = kelas_h
    out["kelas_menurut_dfa"] = kelas_a
    out["kedua_estimator_sepakat"] = [
        "ya" if kh == ka else "TIDAK" for kh, ka in zip(kelas_h, kelas_a)
    ]
    out["label_final"] = df["regime"].values

    # Kolom penjelas: kenapa baris ini mendapat label tersebut.
    alasan = []
    for kh, ka, final in zip(kelas_h, kelas_a, df["regime"]):
        if final == UNCERTAIN_RULE:
            alasan.append(
                f"Hurst menunjuk '{kh}' tetapi DFA menunjuk '{ka}' — tidak sepakat, "
                "tidak dipaksa masuk salah satu kelas"
            )
        else:
            alasan.append(f"Hurst dan DFA sama-sama menunjuk '{final}'")
    out["alasan"] = alasan

    out["mode_ambang"] = df["threshold_mode"].values
    out["stride_bar"] = df["stride_bars"].values
    out["panjang_window_L"] = df["effective_window"].values

    # Segmen split agar terlihat bagian mana yang dipakai melatih.
    stride = stride_bars_of(df)
    seg = assign_segment(
        df, cfg.split.ratios, bars_to_rows(cfg.model.purge_gap, stride)
    )
    out["segmen"] = seg["segment"].values

    path = EXPORT_DIR / f"01_labeling_{timeframe}.csv"
    out.to_csv(path, index=False)
    return path


def export_dataset(timeframe: str, binary: bool) -> tuple[Path, Path]:
    """Berkas 2 dan 3 — sampel training yang benar-benar masuk ke model."""
    cfg = get_config()
    repo = get_repository()
    ohlcv = repo.get_ohlcv(cfg.data.symbol, timeframe)
    regime_df = repo.get_regime(cfg.data.symbol, timeframe)

    classes = BINARY_CLASSES if binary else list(REGIME_CLASSES)
    mode = "binary" if binary else "multiclass"

    data = build_dataset(
        ohlcv["close"].to_numpy(),
        seq_len=32,
        h_bars=0,
        classes=classes,
        with_structural=True,
    )

    names = data["feature_names"]
    rows = []
    for segmen in ("train", "validation", "test"):
        Xs, Xf, y = data[segmen]  # type: ignore[misc]
        if len(y) == 0:
            continue
        for i in range(len(y)):
            row: dict[str, Any] = {"segmen": segmen, "target": classes[int(y[i].argmax())]}
            for j, nama in enumerate(names):
                row[nama] = round(float(Xf[i, j]), 6)
            rows.append(row)

    ds = pd.DataFrame(rows)
    path_ds = EXPORT_DIR / f"02_dataset_{timeframe}_{mode}.csv"
    ds.to_csv(path_ds, index=False)

    # Satu contoh sekuens SWT yang masuk ke BiLSTM.
    Xs_tr, _, y_tr = data["train"]  # type: ignore[misc]
    seq_rows = []
    if len(y_tr):
        contoh = Xs_tr[0]
        label = classes[int(y_tr[0].argmax())]
        n_kanal = contoh.shape[1]
        for t in range(contoh.shape[0]):
            r = {"timestep": t - contoh.shape[0] + 1, "target_sekuens_ini": label}
            for c in range(n_kanal):
                nama = "approx" if c == 0 else f"detail_{c}"
                r[nama] = round(float(contoh[t, c]), 6)
            seq_rows.append(r)

    path_seq = EXPORT_DIR / f"03_sequence_sample_{timeframe}.csv"
    pd.DataFrame(seq_rows).to_csv(path_seq, index=False)

    return path_ds, path_seq


def export_ringkasan(df: pd.DataFrame, timeframe: str) -> Path:
    """Berkas 4 — statistik ringkas per kelas."""
    cfg = get_config()
    stride = stride_bars_of(df)
    seg = assign_segment(df, cfg.split.ratios, bars_to_rows(cfg.model.purge_gap, stride))

    rows = []
    total = len(df)
    for kelas in [*REGIME_CLASSES, UNCERTAIN_RULE]:
        sel = df[df["regime"] == kelas]
        if sel.empty:
            continue
        run_lengths = []
        panjang = 0
        for r in df["regime"]:
            if r == kelas:
                panjang += 1
            elif panjang:
                run_lengths.append(panjang)
                panjang = 0
        if panjang:
            run_lengths.append(panjang)

        rows.append(
            {
                "kelas": kelas,
                "jumlah_window": len(sel),
                "persen": round(100 * len(sel) / total, 2),
                "hurst_rata2": round(float(sel["hurst"].mean()), 6),
                "hurst_min": round(float(sel["hurst"].min()), 6),
                "hurst_maks": round(float(sel["hurst"].max()), 6),
                "dfa_rata2": round(float(sel["dfa_alpha"].mean()), 6),
                "durasi_rata2_window": round(float(np.mean(run_lengths)), 2)
                if run_lengths
                else 0,
                "durasi_maks_window": max(run_lengths) if run_lengths else 0,
                "jumlah_run": len(run_lengths),
                "n_train": (seg["segment"] == "train")[df["regime"] == kelas].sum(),
                "n_test": (seg["segment"] == "test")[df["regime"] == kelas].sum(),
            }
        )

    path = EXPORT_DIR / f"04_ringkasan_{timeframe}.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ekspor dataset training ke CSV")
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    parser.add_argument("--binary", action="store_true")
    args = parser.parse_args()

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = get_config()
    repo = get_repository()
    df = repo.get_regime(cfg.data.symbol, args.timeframe)

    print(f"Mengekspor {args.timeframe} ({len(df)} window)...")

    p1 = export_labeling(df, args.timeframe)
    print(f"  {p1.name}")

    p2, p3 = export_dataset(args.timeframe, args.binary)
    print(f"  {p2.name}")
    print(f"  {p3.name}")

    p4 = export_ringkasan(df, args.timeframe)
    print(f"  {p4.name}")

    print(f"\nTersimpan di: {EXPORT_DIR}")
    print(f"config_hash: {cfg.short_hash}")


if __name__ == "__main__":
    main()

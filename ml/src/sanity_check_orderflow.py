"""Sanity check sebelum training ablation order flow.

Jalankan:
    python ml/src/sanity_check_orderflow.py --timeframe 1h

Memeriksa: shape, alignment timestamp, NaN/inf, future leakage, jumlah sampel
per branch, label = Hurst-DFA, dan bahwa Hurst/DFA tidak ada di input.
Keluar dengan kode 1 bila satu saja pemeriksaan gagal.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orderflow_common import load_orderflow_dataset  # noqa: E402

from app.core.config import get_config  # noqa: E402
from app.db.repository import get_repository  # noqa: E402
from app.services.order_flow import (  # noqa: E402
    bars_to_return_space,
    build_order_flow_bars,
    prepare_order_flow_windows,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--timeframe", default="1h", choices=["1h", "4h"])
    p.add_argument("--seq-len", type=int, default=32)
    args = p.parse_args()

    data = load_orderflow_dataset(args.timeframe, seq_len=args.seq_len)
    full = data["full"]
    of = data["orderflow"]
    rows = data["rows"]
    ok = True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'OK ' if cond else 'GAGAL'}] {name}{(' - ' + detail) if detail else ''}")

    print(f"=== Sanity check order flow [{args.timeframe}] ===")
    print(f"cakupan order flow : {data['coverage']:.1%}")
    print(f"window label/SWT   : {data['effective_window']} bar, stride {data['stride_bars']} bar")
    print(f"window CVD         : {of['cvd_window']} bar ({of['cvd_method']})")
    print(f"purge              : {data['purge_bars']} bar")
    print()

    for split in ("train", "validation", "test"):
        X_swt, _, y = data[split]
        X_of = of[split]
        print(f"[{split}]")
        print(f"  X_swt       = {X_swt.shape}")
        print(f"  X_orderflow = {X_of.shape}   (kanal {of['channels']})")
        print(f"  X_ofi       = {X_of[:, :, :1].shape}")
        print(f"  X_cvd       = {X_of[:, :, 1:2].shape}")
        print(f"  y           = {y.shape}")
        check("jumlah sampel tiap branch sama", len(X_swt) == len(X_of) == len(y))
        check("panjang sekuens sama", X_swt.shape[1] == X_of.shape[1] == args.seq_len)
        check("tanpa NaN/inf (SWT)", bool(np.isfinite(X_swt).all()))
        check("tanpa NaN/inf (order flow)", bool(np.isfinite(X_of).all()))
        check("one-hot valid", bool(np.allclose(y.sum(axis=1), 1.0)))

    print("\n[alignment & label]")
    pos = full["positions"]
    ohlcv = data["ohlcv"]
    bar_idx = pos + 1
    check(
        "timestamp sampel = timestamp candle (index+1)",
        bool(np.array_equal(full["time"], ohlcv["time"].to_numpy()[bar_idx])),
    )
    regime_df = get_repository().get_regime("BTCUSDT", args.timeframe)
    same_len = len(regime_df) == len(full["labels"])
    check("jumlah window = tabel regime Hurst-DFA", same_len, f"{len(full['labels'])} window")
    if same_len:
        check(
            "label identik dengan regime Hurst-DFA",
            list(regime_df["regime"]) == list(full["labels"]),
        )
        check("posisi window identik", bool(np.array_equal(regime_df["index"].to_numpy(), pos)))

    classes = data["classes"]
    for split in ("train", "validation", "test"):
        y = data[split][2]
        lab = [full["labels"][i] for i in rows[split]]
        rec = [classes[i] for i in y.argmax(axis=1)]
        check(f"y_{split} = label Hurst-DFA baris terkait", lab == rec)

    print("\n[input bebas Hurst/DFA]")
    check("nama kanal order flow", list(of["channels"]) == ["ofi", "cvd"])
    hurst = np.asarray(regime_df["hurst"].to_numpy(dtype=float))
    for name, X in (("SWT", full["X_swt"]), ("order flow", full["X_orderflow"])):
        last = X[:, -1, :]
        corr = max(
            abs(np.corrcoef(np.nan_to_num(hurst[: len(last)]), last[:, c])[0, 1])
            for c in range(last.shape[1])
        )
        check(f"tidak ada kanal {name} yang = Hurst", corr < 0.99, f"|corr| maks {corr:.3f}")

    print("\n[future leakage]")
    tr, te = rows["train"], rows["test"]
    va = rows["validation"]
    check("urutan kronologis train < val < test", max(tr) < min(va) and max(va) < min(te))
    t_gap = int(full["time"][min(va)] - full["time"][max(tr)])
    need = (data["purge_bars"]) * (3600 if args.timeframe == "1h" else 14400)
    check("jarak train-val >= purge", t_gap >= need, f"{t_gap / 3600:.0f} jam")
    first_bar_val = pos[min(va)] + 1 - (args.seq_len - 1) - max(data["effective_window"], of["cvd_window"]) + 1
    check(
        "bar input paling awal validation > bar terakhir train",
        first_bar_val > pos[max(tr)] + 1,
        f"{first_bar_val} vs {pos[max(tr)] + 1}",
    )

    # Uji kausal langsung: ubah seluruh bar setelah t, fitur order flow di t harus identik.
    cfg = get_config()
    t_cut = int(pos[len(pos) // 2])
    tamper = ohlcv.copy()
    rng = np.random.default_rng(cfg.model.seed)
    after = np.arange(len(tamper)) > t_cut + 1
    tamper.loc[after, "taker_buy_volume"] = tamper.loc[after, "volume"] * rng.uniform(0, 1, after.sum())
    a = bars_to_return_space(build_order_flow_bars(ohlcv, of["cvd_window"]), ["ofi", "cvd_norm"])
    b = bars_to_return_space(build_order_flow_bars(tamper, of["cvd_window"]), ["ofi", "cvd_norm"])
    wa = prepare_order_flow_windows(a, [t_cut], args.seq_len)
    wb = prepare_order_flow_windows(b, [t_cut], args.seq_len)
    check("fitur di t tidak berubah saat data > t diacak", bool(np.array_equal(wa, wb)))
    check("data > t memang berubah (kontrol)", not np.array_equal(a[t_cut + 1 :], b[t_cut + 1 :]))

    sc = of["scaler"]
    print(f"\nscaler order flow (fit pada train saja): mean={np.round(sc['mean'], 4)} std={np.round(sc['std'], 4)}")
    print("\nHASIL:", "SEMUA LULUS" if ok else "ADA YANG GAGAL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

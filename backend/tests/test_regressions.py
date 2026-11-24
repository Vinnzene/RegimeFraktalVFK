"""Regression test untuk temuan code review."""

from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_config
from app.db.repository import (
    REGIME_COLUMNS,
    InvalidIdentifier,
    ParquetRepository,
    get_repository,
    validate_identifiers,
)
from app.main import app
from app.services.splitting import bars_to_rows, split_indices, stride_bars_of

client = TestClient(app)


# --- Konversi satuan bar vs window -------------------------------------------------


def test_purge_gap_dikonversi_ke_satuan_window() -> None:
    """purge_gap bersatuan bar tidak boleh langsung dipakai pada deret window."""
    benar = split_indices(1375, [0.7, 0.15, 0.15], bars_to_rows(1000, 4))
    assert benar["purge_gap"] == 250
    assert benar["purge_1"][1] - benar["purge_1"][0] == 250
    assert benar["purge_2"][1] - benar["purge_2"][0] == 250


@pytest.mark.parametrize(
    "n,gap",
    [(1375, 250), (1375, 1000), (6000, 1000), (100, 40), (10, 1000), (3, 5)],
)
def test_setiap_segmen_selalu_kebagian_baris(n: int, gap: int) -> None:
    """Purge dialokasikan dari total lebih dulu, bukan memakan jatah val/test."""
    s = split_indices(n, [0.7, 0.15, 0.15], gap)
    for name in ("train", "validation", "test"):
        start, end = s[name]
        assert end > start, f"segmen {name} kosong pada n={n}, gap={gap}"


def test_segmen_berurutan_tanpa_celah_dan_tanpa_tumpang_tindih() -> None:
    s = split_indices(1375, [0.7, 0.15, 0.15], 250)
    urutan = ["train", "purge_1", "validation", "purge_2", "test"]
    for a, b in zip(urutan[:-1], urutan[1:]):
        assert s[a][1] == s[b][0], f"{a} dan {b} tidak bersambung"
    assert s["train"][0] == 0
    assert s["test"][1] == s["n"]


def test_purge_dikecilkan_saat_tidak_muat() -> None:
    s = split_indices(10, [0.7, 0.15, 0.15], 1000)
    assert s["requested_purge_gap"] == 1000
    assert s["purge_gap"] < 1000
    assert s["test"][1] == 10


def test_endpoint_regime_punya_segmen_test_tidak_kosong() -> None:
    r = client.get("/api/v1/analysis/regime", params={"tf": "1h"})
    body = r.json()
    segments = {row["segment"] for row in body["series"]}
    assert "test" in segments, "seluruh dataset tidak boleh terserap zona purge"
    assert body["purge_gap_rows"] < body["purge_gap_bars"]


def test_stride_bars_ikut_tersimpan_di_hasil_regime() -> None:
    # Repositori terisolasi dari conftest (folder sementara).
    repo = get_repository()
    df = repo.get_regime("BTCUSDT", "1h")
    assert "stride_bars" in df.columns
    assert stride_bars_of(df) >= 1


# --- NaN dan skema ----------------------------------------------------------------


def test_fallback_regime_kosong_punya_skema_penuh() -> None:
    """DataFrame kosong harus tetap membawa kolom yang diseleksi router."""
    empty = pd.DataFrame(columns=REGIME_COLUMNS)
    for col in ("time", "close", "hurst", "dfa_alpha", "regime", "effective_window"):
        assert col in empty.columns


# --- Validasi identifier ------------------------------------------------------------


@pytest.mark.parametrize(
    "symbol",
    ["../../../../evil", "BTC/USDT", "..", "a" * 21, "", "btc usdt"],
)
def test_symbol_berbahaya_ditolak(symbol: str) -> None:
    with pytest.raises(InvalidIdentifier):
        validate_identifiers(symbol, "1h", get_config())


def test_timeframe_di_luar_config_ditolak() -> None:
    with pytest.raises(InvalidIdentifier):
        validate_identifiers("BTCUSDT", "13m", get_config())


def test_path_traversal_lewat_api_menghasilkan_400() -> None:
    r = client.get("/api/v1/ohlcv", params={"symbol": "../../../evil", "tf": "1h"})
    assert r.status_code == 400


def test_timeframe_tidak_dikenal_lewat_api_menghasilkan_400() -> None:
    r = client.get("/api/v1/analysis/regime", params={"tf": "99h"})
    assert r.status_code == 400


def test_path_selalu_di_dalam_data_processed() -> None:
    repo = ParquetRepository()
    path = repo._path("ohlcv", "BTCUSDT", "1h")
    assert repo.base_dir.resolve() in path.parents


# --- Batas memori -------------------------------------------------------------------


# --- Cache ---------------------------------------------------------------------------


# --- Pemisahan flag data vs artefak model -------------------------------------------


def test_inference_tidak_gagal_saat_artefak_belum_ada() -> None:
    """runtime.use_mock mengatur sumber DATA, bukan ketersediaan artefak MODEL."""
    from app.services.model_registry import predict_proba

    probs = predict_proba("swt_attention_bilstm", [0.6, 0.5])
    assert abs(sum(probs.values()) - 1.0) < 0.01


# --- Metrik saat model jarang yakin -------------------------------------------------


def test_coverage_nol_tidak_terbaca_sebagai_prediksi_salah() -> None:
    """Semua window uncertain_lowconf berarti 'jarang menjawab', bukan 'sering salah'."""
    from app.services.model_registry import evaluate_with_coverage

    truth = ["persistent", "random_like", "anti_persistent"] * 10
    argmax = ["persistent", "random_like", "anti_persistent"] * 10
    final = ["uncertain_lowconf"] * 30

    res: Dict[str, Any] = evaluate_with_coverage(truth, argmax, final)
    assert res["coverage"] == 0.0
    assert res["thresholded"]["n"] == 0
    # Daya diskriminasi tetap terukur meski tak satu pun lolos ambang.
    assert res["argmax"]["balanced_accuracy"] == 1.0


def test_coverage_penuh_menyamakan_argmax_dan_thresholded() -> None:
    from app.services.model_registry import evaluate_with_coverage

    truth = ["persistent", "random_like", "anti_persistent"] * 10
    preds = ["persistent", "random_like", "anti_persistent"] * 10
    res: Dict[str, Any] = evaluate_with_coverage(truth, preds, preds)
    assert res["coverage"] == 1.0
    assert res["argmax"]["balanced_accuracy"] == res["thresholded"]["balanced_accuracy"]


def test_coverage_sebagian_dihitung_pada_subset_yang_lolos() -> None:
    from app.services.model_registry import evaluate_with_coverage

    truth = ["persistent"] * 4
    argmax = ["persistent"] * 4
    final = ["persistent", "persistent", "uncertain_lowconf", "uncertain_lowconf"]
    res: Dict[str, Any] = evaluate_with_coverage(truth, argmax, final)
    assert res["coverage"] == 0.5
    assert res["thresholded"]["n"] == 2


def test_ground_truth_uncertain_rule_dikeluarkan() -> None:
    """Model tidak pernah dilatih untuk uncertain_rule, jadi tidak dinilai atasnya."""
    from app.services.model_registry import evaluate_with_coverage

    truth = ["uncertain_rule"] * 5 + ["persistent"] * 5
    preds = ["persistent"] * 10
    res: Dict[str, Any] = evaluate_with_coverage(truth, preds, preds)
    assert res["n_evaluated"] == 5


def test_fitur_struktural_tidak_memuat_hurst_atau_dfa() -> None:
    """Penjaga label sirkular."""
    from app.services.structural_features import feature_names

    names = feature_names()
    for n in names:
        assert "hurst" not in n.lower()
        assert "dfa" not in n.lower()
        assert "alpha" not in n.lower()


def test_dimensi_fitur_struktural_konsisten() -> None:
    import numpy as np

    from app.services.structural_features import (
        FEATURE_DIM,
        compute_features,
        feature_names,
    )

    assert len(feature_names()) == FEATURE_DIM
    rng = np.random.default_rng(5)
    x = rng.normal(scale=0.01, size=600)
    assert len(compute_features(x, 500, window=500)) == FEATURE_DIM
    # Segmen terlalu pendek tetap mengembalikan dimensi yang sama.
    assert len(compute_features(x, 10, window=500)) == FEATURE_DIM


def test_variance_ratio_mengenali_random_walk() -> None:
    """VR(q) harus mendekati 1 pada deret tanpa autokorelasi."""
    import numpy as np

    from app.services.structural_features import variance_ratio

    rng = np.random.default_rng(3)
    x = rng.normal(size=4000)
    for q in (2, 4, 8):
        assert abs(variance_ratio(x, q) - 1.0) < 0.15


def test_variance_ratio_membedakan_deret_persisten() -> None:
    """Deret dengan momentum harus memberi VR > 1, pembalikan VR < 1."""
    import numpy as np

    from app.services.structural_features import variance_ratio

    rng = np.random.default_rng(9)
    n = 4000
    noise = rng.normal(size=n)

    persisten = np.zeros(n)
    berbalik = np.zeros(n)
    for t in range(1, n):
        persisten[t] = 0.4 * persisten[t - 1] + noise[t]
        berbalik[t] = -0.4 * berbalik[t - 1] + noise[t]

    assert variance_ratio(persisten, 8) > 1.2
    assert variance_ratio(berbalik, 8) < 0.9


def test_fitur_struktural_bersifat_causal() -> None:
    """Menambah data setelah t tidak boleh mengubah fitur pada t."""
    import numpy as np

    from app.services.structural_features import compute_features

    rng = np.random.default_rng(17)
    x = rng.normal(scale=0.01, size=900)
    t = 600
    a = compute_features(x[: t + 1], t, window=400)
    b = compute_features(x, t, window=400)
    assert np.allclose(a, b, rtol=1e-9, atol=1e-12)


def test_konsistensi_mengukur_empat_lapis() -> None:
    """Akurasi saja dapat menyembunyikan model yang kehilangan sifat persistensi."""
    import numpy as np

    from app.services.consistency import full_consistency

    classes = ["persistent", "random_like", "anti_persistent"]
    true = (["persistent"] * 20 + ["random_like"] * 10 + ["anti_persistent"] * 20) * 2
    pred = true[:]
    h = np.array([0.62] * 20 + [0.58] * 10 + [0.54] * 20) 
    h = np.concatenate([h, h])
    a = h - 0.08

    rep: Dict[str, Any] = full_consistency(true, pred, h, a, classes)
    assert rep["agreement"]["agreement_rate"] == 1.0
    assert rep["distribution"]["total_variation_distance"] == 0.0
    assert rep["exponent_alignment"]["ordering_preserved"] is True
    assert rep["exponent_alignment"]["mean_abs_gap_hurst"] == 0.0


def test_konsistensi_mendeteksi_urutan_terbalik() -> None:
    """Bila model menukar persistent dan anti-persistent, urutan eksponen gagal."""
    import numpy as np

    from app.services.consistency import exponent_alignment

    classes = ["persistent", "anti_persistent"]
    true = ["persistent"] * 20 + ["anti_persistent"] * 20
    pred = ["anti_persistent"] * 20 + ["persistent"] * 20
    h = np.array([0.65] * 20 + [0.52] * 20)
    a = h - 0.1

    rep = exponent_alignment(true, pred, h, a, classes)
    assert rep["ordering_preserved"] is False


# --- Jump Model dan walk-forward ---------------------------------------------------


def test_jump_penalty_memperpanjang_durasi_regime() -> None:
    """Penalti yang lebih besar harus menghasilkan blok regime yang lebih panjang."""
    import numpy as np

    from app.services.jump_model import label_with_jump_model

    rng = np.random.default_rng(3)
    # Dua blok dengan tingkat Hurst berbeda, ditambah derau.
    h = np.concatenate(
        [
            rng.normal(0.40, 0.05, 150),
            rng.normal(0.60, 0.05, 150),
            rng.normal(0.40, 0.05, 150),
        ]
    )
    a = h - 0.05
    classes = ["anti_persistent", "random_like", "persistent"]

    rendah = label_with_jump_model(h, a, classes, jump_penalty=0.0, seed=1)
    tinggi = label_with_jump_model(h, a, classes, jump_penalty=20.0, seed=1)

    assert tinggi["mean_run_length"] > rendah["mean_run_length"]
    assert tinggi["n_switches"] < rendah["n_switches"]


def test_jump_model_state_terurut_menurut_hurst() -> None:
    """Penamaan regime hanya bermakna bila state terurut menurut Hurst."""
    import numpy as np

    from app.services.jump_model import label_with_jump_model

    rng = np.random.default_rng(11)
    h = np.concatenate(
        [rng.normal(0.35, 0.02, 120), rng.normal(0.50, 0.02, 120), rng.normal(0.65, 0.02, 120)]
    )
    a = h - 0.04
    classes = ["anti_persistent", "random_like", "persistent"]

    res = label_with_jump_model(h, a, classes, jump_penalty=1.0, seed=1)
    centers = np.array(res["centers"])
    assert np.all(np.diff(centers[:, 0]) > 0), "pusat state harus menaik menurut Hurst"


def test_walk_forward_fold_berurutan_dan_ter_purge() -> None:
    """Fold harus berurutan waktu dengan jeda purge antara latih dan uji."""
    from app.services.walk_forward import generate_folds

    folds: List[Dict[str, Any]] = generate_folds(2000, n_splits=5, purge=50, scheme="expanding")
    assert len(folds) >= 3
    for f in folds:
        train_end = f["train"][1]
        test_start = f["test"][0]
        assert test_start - train_end == 50, "jeda purge harus tepat"
        assert f["test"][0] > f["train"][1], "uji harus setelah latih"

    # Skema expanding: data latih bertambah tiap fold.
    sizes = [f["n_train"] for f in folds]
    assert sizes == sorted(sizes)


def test_walk_forward_rolling_menjaga_ukuran_jendela() -> None:
    from app.services.walk_forward import generate_folds

    folds: List[Dict[str, Any]] = generate_folds(2000, n_splits=4, purge=20, scheme="rolling")
    sizes = [f["n_train"] for f in folds]
    # Ukuran jendela tetap, sehingga sebarannya jauh lebih sempit daripada skema expanding.
    assert max(sizes) - min(sizes) < max(sizes) * 0.5


def test_confusion_agregat_konsisten() -> None:
    from app.services.walk_forward import aggregate_confusion

    classes = ["a", "b"]
    cm = aggregate_confusion(["a", "a", "b", "b"], ["a", "b", "b", "b"], classes)
    assert cm["n"] == 4
    assert cm["accuracy"] == 0.75
    assert cm["matrix"] == [[1, 1], [0, 2]]


def test_cache_probabilitas_memperhitungkan_jumlah_baris() -> None:
    """Hasil dari deret pendek tidak boleh terpakai untuk deret penuh."""
    import pandas as pd

    from app.services.inference import clear_inference_cache, probabilities_for

    clear_inference_cache()

    def buat(n: int) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "time": range(1700000000, 1700000000 + n),
                "index": range(n),
                "close": [30000.0] * n,
                "hurst": [0.55] * n,
                "dfa_alpha": [0.50] * n,
                "regime": ["persistent"] * n,
                "effective_window": [500] * n,
                "stride_bars": [4] * n,
            }
        )

    pendek, _ = probabilities_for("BTCUSDT", "1h", buat(5), "rule_based")
    panjang, _ = probabilities_for("BTCUSDT", "1h", buat(20), "rule_based")

    assert pendek.shape[0] == 5
    assert panjang.shape[0] == 20, "cache tidak boleh mengembalikan matriks pendek"

    clear_inference_cache()


def test_purge_gap_menyesuaikan_horizon_yang_diuji() -> None:
    """Saat h diubah untuk uji sensitivitas, purge gap harus ikut menyesuaikan."""
    cfg = get_config()
    for h in (125, 250, 500):
        expected = min(cfg.analysis.L + h, cfg.model.purge_gap)
        assert expected <= cfg.model.purge_gap
        assert expected >= cfg.analysis.L


# --- Perhitungan regime incremental ------------------------------------------------


def _incremental_repo(tmp_path, n_bars: int) -> ParquetRepository:
    from app.mock.generator import generate_ohlcv

    repo = ParquetRepository(base_dir=tmp_path, config=get_config())
    repo.save_ohlcv("BTCUSDT", "1h", generate_ohlcv("1h", seed=7, bars=n_bars))
    return repo


def test_regime_incremental_identik_dengan_hitung_penuh(tmp_path) -> None:
    """Bar baru hanya menghitung window baru, tetapi hasilnya harus identik."""
    from app.mock.generator import generate_ohlcv

    full = generate_ohlcv("1h", seed=7, bars=3200)
    repo = ParquetRepository(base_dir=tmp_path, config=get_config())

    repo.save_ohlcv("BTCUSDT", "1h", full.iloc[:3000].reset_index(drop=True))
    old = repo.get_regime("BTCUSDT", "1h")

    repo.save_ohlcv("BTCUSDT", "1h", full)
    repo._invalidate("BTCUSDT", "1h")
    inc = repo.get_regime("BTCUSDT", "1h")

    fresh = ParquetRepository(base_dir=tmp_path / "fresh", config=get_config())
    fresh.save_ohlcv("BTCUSDT", "1h", full)
    ref = fresh.compute_regime("BTCUSDT", "1h")

    assert len(inc) > len(old)
    assert inc["index"].tolist() == ref["index"].tolist()
    assert np.allclose(inc["hurst"], ref["hurst"], equal_nan=True)
    assert np.allclose(inc["dfa_alpha"], ref["dfa_alpha"], equal_nan=True)
    # Label wajib dihitung ulang atas deret penuh: ambang kuantil bergeser.
    assert inc["regime"].tolist() == ref["regime"].tolist()


def test_regime_hitung_penuh_bila_riwayat_berubah(tmp_path) -> None:
    """Riwayat yang digeser atau ditulis ulang tidak boleh memakai hasil lama."""
    from app.mock.generator import generate_ohlcv

    repo = ParquetRepository(base_dir=tmp_path, config=get_config())
    repo.save_ohlcv("BTCUSDT", "1h", generate_ohlcv("1h", seed=7, bars=3000))
    repo.get_regime("BTCUSDT", "1h")

    other = generate_ohlcv("1h", seed=99, bars=3100)
    repo.save_ohlcv("BTCUSDT", "1h", other)
    repo._invalidate("BTCUSDT", "1h")
    got = repo.get_regime("BTCUSDT", "1h")

    fresh = ParquetRepository(base_dir=tmp_path / "fresh", config=get_config())
    fresh.save_ohlcv("BTCUSDT", "1h", other)
    ref = fresh.compute_regime("BTCUSDT", "1h")
    assert np.allclose(got["hurst"], ref["hurst"], equal_nan=True)
    assert got["regime"].tolist() == ref["regime"].tolist()


def test_regime_tanpa_bar_baru_tidak_dihitung_ulang(tmp_path, monkeypatch) -> None:
    repo = _incremental_repo(tmp_path, 3000)
    repo.get_regime("BTCUSDT", "1h")
    repo._regime_memo.clear()

    calls = []
    import app.db.repository as mod

    monkeypatch.setattr(
        mod, "rolling_hurst_dfa", lambda *a, **k: calls.append(1) or pd.DataFrame()
    )
    repo.get_regime("BTCUSDT", "1h")
    assert calls == [], "berkas regime yang masih segar harus dipakai langsung"

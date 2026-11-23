"""Unit test rumus SUS pada scripts/rekap_sus.py (harus sama dengan frontend/lib/sus.ts)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "rekap_sus.py"
spec = importlib.util.spec_from_file_location("rekap_sus", SCRIPT)
rekap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rekap)  # type: ignore[union-attr]

ODD5_EVEN1 = [5, 1, 5, 1, 5, 1, 5, 1, 5, 1]
ODD1_EVEN5 = [1, 5, 1, 5, 1, 5, 1, 5, 1, 5]
HEAD = "kode,status,versi_instrumen,waktu_persetujuan_utc,waktu_selesai_mencoba_utc,waktu_kirim_utc,peran,pengalaman_bulan,usia,halaman_dibuka," \
       + ",".join(f"SUS{i}" for i in range(1, 11)) + ",skor_sus,saran"


def row(kode: str, answers, skor) -> str:
    return f"{kode},done,sus-v1,2026-12-01T01:00:00.000Z,2026-12-01T01:05:00.000Z,2026-12-01T01:10:00.000Z,Trader ritel,12,," \
           f"ringkasan|evaluasi|fokus," + ",".join(map(str, answers)) + f",{skor},"


def test_semua_tiga_bernilai_50() -> None:
    assert rekap.sus_score([3] * 10) == 50


def test_ganjil_5_genap_1_bernilai_100() -> None:
    assert rekap.sus_score(ODD5_EVEN1) == 100


def test_ganjil_1_genap_5_bernilai_0() -> None:
    assert rekap.sus_score(ODD1_EVEN5) == 0


def test_contoh_campuran() -> None:
    assert rekap.sus_score([4, 2, 4, 1, 5, 2, 4, 3, 3, 1]) == 77.5


@pytest.mark.parametrize("answers", [[3] * 9, [3] * 11, [], [0] + [3] * 9, [6] + [3] * 9, [2.5] + [3] * 9, [""] + [3] * 9])
def test_jawaban_tidak_lengkap_atau_tidak_sah_ditolak(answers) -> None:
    with pytest.raises(rekap.RekapError):
        rekap.sus_score(answers)


def test_csv_kosong_ditolak(tmp_path: Path) -> None:
    f = tmp_path / "kosong.csv"
    f.write_text("﻿" + HEAD + "\n", encoding="utf-8")
    with pytest.raises(rekap.RekapError, match="kosong"):
        rekap.read_rows(f)
    out = tmp_path / "hasil.md"
    assert rekap.main([str(f), "--out", str(out)]) == 1
    assert not out.exists()


def test_skor_tidak_cocok_ditolak(tmp_path: Path) -> None:
    f = tmp_path / "salah.csv"
    f.write_text(HEAD + "\n" + row("R01", [3] * 10, 55) + "\n", encoding="utf-8")
    with pytest.raises(rekap.RekapError, match="tidak sama"):
        rekap.summarize(rekap.read_rows(f))


def test_rekap_dan_markdown(tmp_path: Path) -> None:
    f = tmp_path / "sus.csv"
    lines = [HEAD, row("R01", [3] * 10, 50), row("R02", ODD5_EVEN1, 100), row("R03", [4, 2, 4, 1, 5, 2, 4, 3, 3, 1], 77.5)]
    f.write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8")
    s = rekap.summarize(rekap.read_rows(f))
    assert s["n"] == 3
    assert s["mean"] == pytest.approx(227.5 / 3)
    assert s["median"] == 77.5 and s["min"] == 50 and s["max"] == 100
    assert s["at_or_above_68"] == 2
    assert s["adjective"] == "Good" and s["acceptability"] == "Acceptable"
    assert s["weakest"] == 8  # butir 8 dan 9 seri; nomor terkecil, sama dengan aplikasi
    out = tmp_path / "sus_hasil.md"
    assert rekap.main([str(f), "--out", str(out)]) == 0
    md = out.read_text(encoding="utf-8")
    assert "| Jumlah responden | 3 |" in md and "| R02 |" in md and "@" not in md  # tidak ada alamat email


def test_tidak_ada_butir_terlemah_bila_semua_sama(tmp_path: Path) -> None:
    f = tmp_path / "sama.csv"
    f.write_text(HEAD + "\n" + row("R01", [3] * 10, 50) + "\n", encoding="utf-8")
    assert rekap.summarize(rekap.read_rows(f))["weakest"] is None


def sim_row(kode: str, answers, skor) -> str:
    return row(kode, answers, skor).replace(",sus-v1,", ",sus-v1-SIMULASI,")


def test_data_simulasi_diberi_sumber_dan_tidak_boleh_ke_sus_hasil(tmp_path: Path) -> None:
    f = tmp_path / "SIMULASI_sus.csv"
    f.write_text(HEAD + "\n" + sim_row("R01", [4, 2] * 5, 75) + "\n" + sim_row("R02", [3] * 10, 50) + "\n", encoding="utf-8")
    assert rekap.main([str(f), "--out", str(tmp_path / "sus_hasil.md")]) == 1
    assert not (tmp_path / "sus_hasil.md").exists()
    out = tmp_path / "SIMULASI_sus_hasil.md"
    assert rekap.main([str(f), "--out", str(out)]) == 0
    md = out.read_text(encoding="utf-8")
    assert "simulasi prasidang" in md.splitlines()[0]
    assert md.count(rekap.SIM_SOURCE) == 3  # satu baris sumber di bawah tiap tabel
    assert "| R01 |" in md


def test_campuran_simulasi_dan_asli_ditolak(tmp_path: Path) -> None:
    f = tmp_path / "campur.csv"
    f.write_text(HEAD + "\n" + sim_row("R01", [3] * 10, 50) + "\n" + row("R02", [3] * 10, 50) + "\n", encoding="utf-8")
    with pytest.raises(rekap.RekapError, match="mencampur"):
        rekap.summarize(rekap.read_rows(f))


@pytest.mark.parametrize("score,label", [(0, "Worst Imaginable"), (50, "OK"), (68, "Good"), (80, "Excellent"), (100, "Best Imaginable")])
def test_kata_sifat_sama_dengan_aplikasi(score, label) -> None:
    assert rekap.bangor_adjective(score) == label

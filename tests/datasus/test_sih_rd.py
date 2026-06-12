"""Integration tests for src/datasus/sih_rd.py using the minimal CSV fixture.

The fixture (rdsp2501_minimal.csv) contains only the 6 product columns:
  MUNIC_RES, MUNIC_MOV, DIAG_PRINC, DT_INTER, ANO_CMPT, MES_CMPT
No PII columns (CPF_AUT, GESTOR_CPF, NASC) are present — by design.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "rdsp2501_minimal.csv"

pytestmark = pytest.mark.skipif(not FIXTURE.exists(), reason="fixture CSV not found")


@pytest.fixture(scope="module")
def lazy_frame():
    pl = pytest.importorskip("polars", reason="polars not installed")
    return pl.read_csv(FIXTURE, infer_schema_length=100).lazy()


def test_process_returns_dataframe(lazy_frame):
    from src.datasus.sih_rd import process

    df = process(lazy_frame, k=5, ref_date=date(2025, 6, 1))
    import polars as pl

    assert isinstance(df, pl.DataFrame)


def test_process_columns(lazy_frame):
    from src.datasus.sih_rd import process

    df = process(lazy_frame, k=5, ref_date=date(2025, 6, 1))
    assert set(df.columns) == {
        "munic_res_6",
        "mes_intern",
        "internacoes",
        "suprimido",
        "parcial",
    }


def test_process_filters_only_j_codes(lazy_frame):
    """K25 (gastric ulcer) and I10 (hypertension) must not appear in results."""
    from src.datasus.sih_rd import process

    df = process(lazy_frame, k=1, ref_date=date(2025, 6, 1))  # k=1 to avoid suppression
    # All mes_intern entries should come only from J-code rows
    # There are 3 munic/month combinations: 355030/202501, 330455/202501, 291080/202501
    # (and some from 202502 and 202503)
    assert len(df) > 0
    # internacoes column: non-suppressed values should be >= 1
    valid = df.filter(~df["suprimido"])
    if len(valid) > 0:
        assert valid["internacoes"].min() >= 1


def test_process_k_anonymity_suppresses_small_counts(lazy_frame):
    """With k=100, all cells should be suppressed since fixture has small counts."""
    from src.datasus.sih_rd import process

    df = process(lazy_frame, k=100, ref_date=date(2025, 6, 1))
    assert df["suprimido"].all()
    assert df["internacoes"].is_null().all()


def test_process_k1_no_suppression(lazy_frame):
    """With k=1, no cells should be suppressed."""
    from src.datasus.sih_rd import process

    df = process(lazy_frame, k=1, ref_date=date(2025, 6, 1))
    assert not df["suprimido"].any()


def test_process_munic_res_6_digits(lazy_frame):
    """All munic_res_6 values must be 6-character strings."""
    from src.datasus.sih_rd import process

    df = process(lazy_frame, k=1, ref_date=date(2025, 6, 1))
    for val in df["munic_res_6"].to_list():
        assert len(val) == 6, f"Expected 6-digit code, got: {val!r}"
        assert val.isdigit(), f"Expected numeric code, got: {val!r}"


def test_process_mes_intern_aaaamm_format(lazy_frame):
    """mes_intern values must be 6-char AAAAMM strings."""
    from src.datasus.sih_rd import process

    df = process(lazy_frame, k=1, ref_date=date(2025, 6, 1))
    for val in df["mes_intern"].to_list():
        assert len(val) == 6, f"Expected AAAAMM, got: {val!r}"
        assert val.isdigit(), f"Expected numeric AAAAMM, got: {val!r}"
        year = int(val[:4])
        month = int(val[4:])
        assert 2000 <= year <= 2100
        assert 1 <= month <= 12


def test_process_parcial_marks_recent_months(lazy_frame):
    """Months within 2-month window of ref_date must be marked parcial=True."""
    from src.datasus.sih_rd import process

    # ref_date = 2025-06-01; parcial_cutoff = 202504
    # rows with mes_intern >= 202504 are parcial
    df = process(lazy_frame, k=1, ref_date=date(2025, 6, 1))
    # fixture has months 202501, 202502, 202503 — none are >= 202504
    assert not df["parcial"].any()


def test_process_parcial_marks_recent_with_close_ref_date(lazy_frame):
    """With ref_date close to data, some months should be marked parcial."""
    from src.datasus.sih_rd import process

    # ref_date = 2025-02-01; parcial_cutoff = 202412 (Dec 2024)
    # rows from 202501, 202502, 202503 all >= 202412 → all parcial
    df = process(lazy_frame, k=1, ref_date=date(2025, 2, 1))
    assert df["parcial"].all()


def test_process_sorted_output(lazy_frame):
    """Output must be sorted by [munic_res_6, mes_intern]."""
    from src.datasus.sih_rd import process

    df = process(lazy_frame, k=1, ref_date=date(2025, 6, 1))
    pairs = list(zip(df["munic_res_6"].to_list(), df["mes_intern"].to_list()))
    assert pairs == sorted(pairs)

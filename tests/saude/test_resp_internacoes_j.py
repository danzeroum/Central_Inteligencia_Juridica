"""Tests for src/saude/indicators/resp_internacoes_j.py."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent.parent / "datasus" / "fixtures" / "rdsp2501_minimal.csv"

pytestmark = pytest.mark.skipif(not FIXTURE.exists(), reason="fixture CSV not found")


@pytest.fixture(scope="module")
def lazy_frame():
    pl = pytest.importorskip("polars", reason="polars not installed")
    return pl.read_csv(FIXTURE, infer_schema_length=100).lazy()


@pytest.fixture(scope="module")
def resultado(lazy_frame):
    from src.saude.indicators.resp_internacoes_j import calcular

    return calcular(lazy_frame, k=1, ref_date=date(2025, 6, 1))


# ── metadata constants ───────────────────────────────────────────────────────


def test_indicador_id():
    from src.saude.indicators.resp_internacoes_j import INDICADOR_ID

    assert INDICADOR_ID == "saude.resp.internacoes_j"


def test_caveat_mentions_defasagem():
    from src.saude.indicators.resp_internacoes_j import CAVEAT

    assert "INCOMPLETO" in CAVEAT or "incompleto" in CAVEAT.lower()
    assert "2" in CAVEAT  # references ~2 months lag


def test_badge_suprimido():
    from src.saude.indicators.resp_internacoes_j import BADGE_SUPRIMIDO

    assert BADGE_SUPRIMIDO == "🔒"


# ── calcular() ───────────────────────────────────────────────────────────────


def test_calcular_returns_dataframe(resultado):
    pl = pytest.importorskip("polars")
    assert isinstance(resultado, pl.DataFrame)


def test_calcular_columns(resultado):
    expected = {"munic_res_6", "mes_intern", "internacoes", "suprimido", "parcial"}
    assert set(resultado.columns) == expected


def test_calcular_no_pii_columns(resultado):
    """PII columns must never appear in the output."""
    pii = {"CPF_AUT", "GESTOR_CPF", "NASC", "cpf_aut", "gestor_cpf", "nasc"}
    assert not pii.intersection(set(resultado.columns))


def test_calcular_positive_internacoes(resultado):
    valid = resultado.filter(~resultado["suprimido"])
    if len(valid) > 0:
        assert valid["internacoes"].min() >= 1


# ── resumo() ─────────────────────────────────────────────────────────────────


def test_resumo_keys(resultado):
    from src.saude.indicators.resp_internacoes_j import resumo

    r = resumo(resultado)
    expected_keys = {
        "indicador",
        "total_aih",
        "municipios",
        "meses",
        "celulas_suprimidas",
        "celulas_parciais",
        "min_internacoes",
        "max_internacoes",
    }
    assert expected_keys == set(r.keys())


def test_resumo_indicador_id(resultado):
    from src.saude.indicators.resp_internacoes_j import resumo, INDICADOR_ID

    assert resumo(resultado)["indicador"] == INDICADOR_ID


def test_resumo_total_aih_non_negative(resultado):
    from src.saude.indicators.resp_internacoes_j import resumo

    r = resumo(resultado)
    assert r["total_aih"] >= 0


def test_resumo_municipios_count(resultado):
    from src.saude.indicators.resp_internacoes_j import resumo

    r = resumo(resultado)
    # Fixture has 3 unique MUNIC_RES with J codes: 355030, 330455, 291080
    assert r["municipios"] == 3


def test_resumo_meses_count(resultado):
    from src.saude.indicators.resp_internacoes_j import resumo

    r = resumo(resultado)
    # Fixture has J-code rows in 202501, 202502, 202503
    assert r["meses"] == 3


def test_resumo_min_le_max(resultado):
    from src.saude.indicators.resp_internacoes_j import resumo

    r = resumo(resultado)
    if r["min_internacoes"] is not None and r["max_internacoes"] is not None:
        assert r["min_internacoes"] <= r["max_internacoes"]


def test_resumo_with_full_suppression(lazy_frame):
    """With high k, all cells suppressed → min/max are None, total_aih=0."""
    from src.saude.indicators.resp_internacoes_j import calcular, resumo

    df_sup = calcular(lazy_frame, k=999, ref_date=date(2025, 6, 1))
    r = resumo(df_sup)
    assert r["total_aih"] == 0
    assert r["min_internacoes"] is None
    assert r["max_internacoes"] is None
    assert r["celulas_suprimidas"] > 0

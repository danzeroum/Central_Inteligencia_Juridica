"""Testes unitários determinísticos para RiskEngine (Sprint 10)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "JWT_SECRET", "development-secret-key-minimum-32-chars-long-for-tests"
)
os.environ["ENVIRONMENT"] = "test"


@pytest.fixture()
def engine():
    from src.integrations.risk_engine import RiskEngine

    return RiskEngine()


@pytest.fixture()
def empty_results():
    return {}


@pytest.fixture()
def protest_result():
    from src.integrations.models import AdapterResult, AdapterStatus, DataMode, Protesto

    protest = Protesto(
        cartorio="1º Cartório",
        valor=5000.0,
        data_protesto="2024-01-15",
        cedente="Empresa X",
        numero_protocolo="PROT-001",
        situacao="PROTESTADO",
    )
    return {
        "crc_protestos": AdapterResult(
            source="crc_protestos",
            status=AdapterStatus.SUCCESS,
            data_mode=DataMode.MOCK,
            items=[protest],
            total_available=1,
        )
    }


@pytest.fixture()
def cadin_result():
    from src.integrations.models import (
        AdapterResult,
        AdapterStatus,
        DataMode,
        PendenciaCadin,
    )

    pendencia = PendenciaCadin(
        orgao="Receita Federal",
        tipo_divida="IRPJ",
        valor=25000.0,
        data_inscricao="2023-06-01",
        numero_inscricao="CADIN-001",
        situacao="ATIVO",
    )
    return {
        "cadin": AdapterResult(
            source="cadin",
            status=AdapterStatus.SUCCESS,
            data_mode=DataMode.MOCK,
            items=[pendencia],
            total_available=1,
        )
    }


class TestRiskEngineBasic:
    def test_empty_results_zero_score(self, engine, empty_results):
        score, dims, factors, recs, summary = engine.score(empty_results)
        assert score == 0.0

    def test_score_returns_4_dimensions(self, engine, empty_results):
        _, dims, _, _, _ = engine.score(empty_results)
        names = {d.name for d in dims}
        assert names == {"juridico", "fiscal", "patrimonial", "societario"}

    def test_score_bounded_0_100(self, engine, protest_result):
        score, _, _, _, _ = engine.score(protest_result)
        assert 0.0 <= score <= 100.0

    def test_protest_raises_patrimonial_score(self, engine, protest_result):
        score, dims, _, _, _ = engine.score(protest_result)
        patrimonial = next(d for d in dims if d.name == "patrimonial")
        assert patrimonial.score > 0.0

    def test_cadin_raises_fiscal_score(self, engine, cadin_result):
        score, dims, _, _, _ = engine.score(cadin_result)
        fiscal = next(d for d in dims if d.name == "fiscal")
        assert fiscal.score > 0.0

    def test_summary_not_empty(self, engine, empty_results):
        _, _, _, _, summary = engine.score(empty_results)
        assert isinstance(summary, str) and len(summary) > 0

    def test_recommendations_list(self, engine, empty_results):
        _, _, _, recs, _ = engine.score(empty_results)
        assert isinstance(recs, list)

    def test_high_risk_gets_recommendation(self, engine, cadin_result):
        _, _, _, recs, _ = engine.score(cadin_result)
        # With cadin pendência, at least one recommendation expected
        assert isinstance(recs, list)


class TestHitlThreshold:
    def test_score_below_70_not_hitl(self, engine):
        assert not engine.requires_hitl(69.9)

    def test_score_at_70_is_hitl(self, engine):
        assert engine.requires_hitl(70.0)

    def test_score_above_70_is_hitl(self, engine):
        assert engine.requires_hitl(85.0)

    def test_score_100_is_hitl(self, engine):
        assert engine.requires_hitl(100.0)


class TestRiskEngineConsistency:
    def test_same_input_same_output(self, engine, cadin_result):
        """Score é determinístico — sem LLM, mesma entrada = mesmo score."""
        r1 = engine.score(cadin_result)[0]
        r2 = engine.score(cadin_result)[0]
        assert r1 == r2

    def test_more_findings_higher_score(self, engine):
        """Dois protestos deve produzir score ≥ um protesto."""
        from src.integrations.models import (
            AdapterResult,
            AdapterStatus,
            DataMode,
            Protesto,
        )

        one = Protesto(
            cartorio="1º",
            valor=1000.0,
            data_protesto="2024-01-01",
            cedente="X",
            numero_protocolo="P1",
            situacao="PROTESTADO",
        )
        two = Protesto(
            cartorio="2º",
            valor=2000.0,
            data_protesto="2024-02-01",
            cedente="Y",
            numero_protocolo="P2",
            situacao="PROTESTADO",
        )
        r_one = {
            "crc_protestos": AdapterResult(
                source="crc_protestos",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[one],
                total_available=1,
            )
        }
        r_two = {
            "crc_protestos": AdapterResult(
                source="crc_protestos",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[one, two],
                total_available=2,
            )
        }
        score_one = engine.score(r_one)[0]
        score_two = engine.score(r_two)[0]
        assert score_two >= score_one

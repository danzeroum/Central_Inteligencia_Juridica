"""Testes unitários — Bloco A: DueDiligenceService, TaxRAGService, ConsultoriaService."""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── DueDiligenceService ─────────────────────────────────────────────────────


class TestDueDiligenceService:
    """Testes para src.fiscal.due_diligence.DueDiligenceService."""

    def _make_svc(self, fiscal_agent=None, orchestrator=None):
        from src.fiscal.due_diligence import DueDiligenceService

        return DueDiligenceService(fiscal_agent=fiscal_agent, orchestrator=orchestrator)

    def _mock_fiscal_agent(self, risk_score=0.3):
        agent = MagicMock()
        agent.get_fiscal_profile = AsyncMock(
            return_value={
                "risk_score": risk_score,
                "identifier_masked": "11.***.***/****-81",
                "summary": "Sem pendências fiscais.",
                "recommendations": [],
                "consensus_proposal": {},
                "hitl_status": "approved",
            }
        )
        return agent

    def _mock_orchestrator(self, risk_score=0.1):
        from unittest.mock import MagicMock
        from src.integrations.models import HitlStatus

        report = MagicMock()
        report.risk_score = risk_score
        report.summary = "Sociedade sem passivos jurídicos relevantes."
        report.recommendations = []
        report.hitl_status = HitlStatus.APPROVED
        orch = MagicMock()
        orch.investigate = AsyncMock(return_value=report)
        return orch

    @pytest.mark.asyncio
    async def test_generate_report_success(self):
        svc = self._make_svc(
            fiscal_agent=self._mock_fiscal_agent(0.4),
            orchestrator=self._mock_orchestrator(0.2),
        )
        report = await svc.generate_report("11222333000181")
        assert report["module"] == "cadastro_risco"
        assert "cnpj_masked" in report
        assert report["overall_risk_score"] == pytest.approx(0.3, abs=0.01)
        assert "fiscal" in report
        assert "legal" in report

    @pytest.mark.asyncio
    async def test_invalid_cnpj_raises_value_error(self):
        svc = self._make_svc(
            fiscal_agent=self._mock_fiscal_agent(),
            orchestrator=self._mock_orchestrator(),
        )
        with pytest.raises(ValueError, match="CNPJ inválido"):
            await svc.generate_report("00000000000000")

    @pytest.mark.asyncio
    async def test_legal_profile_failure_is_graceful(self):
        """Orchestrator indisponível não deve quebrar o relatório fiscal."""
        orch = MagicMock()
        orch.investigate = AsyncMock(side_effect=RuntimeError("orch offline"))
        svc = self._make_svc(
            fiscal_agent=self._mock_fiscal_agent(0.5),
            orchestrator=orch,
        )
        report = await svc.generate_report("11222333000181")
        assert report["legal"]["status"] == "indisponivel"
        assert "fiscal" in report

    @pytest.mark.asyncio
    async def test_overall_risk_is_average(self):
        svc = self._make_svc(
            fiscal_agent=self._mock_fiscal_agent(0.6),
            orchestrator=self._mock_orchestrator(0.4),
        )
        report = await svc.generate_report("11222333000181")
        assert report["overall_risk_score"] == pytest.approx(0.5, abs=0.01)


# ── TaxRAGService ───────────────────────────────────────────────────────────


class TestTaxRAGService:
    """Testes para src.fiscal.rag_tributario.TaxRAGService."""

    def test_query_returns_list(self):
        from src.fiscal.rag_tributario import TaxRAGService

        mock_rag = MagicMock()
        mock_rag.query_with_filter.return_value = [
            {"text": "LC 123/2006", "metadata": {"numero": "LC 123/2006"}, "score": 0.9}
        ]
        mock_rag.add_documents_to_namespace.return_value = None
        svc = TaxRAGService(rag_tool=mock_rag)
        results = svc.query("simples nacional alíquota")
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["metadata"]["numero"] == "LC 123/2006"

    def test_query_rag_unavailable_returns_empty(self):
        from src.fiscal.rag_tributario import TaxRAGService

        mock_rag = MagicMock()
        mock_rag.add_documents_to_namespace.return_value = None
        mock_rag.query_with_filter.side_effect = RuntimeError("ChromaDB offline")
        svc = TaxRAGService(rag_tool=mock_rag)
        results = svc.query("qualquer consulta")
        assert results == []

    def test_ingest_valid_documents(self):
        from src.fiscal.rag_tributario import TaxRAGService

        mock_rag = MagicMock()
        mock_rag.add_documents_to_namespace.return_value = None
        svc = TaxRAGService(rag_tool=mock_rag)
        count = svc.ingest(
            [
                {"id": "d1", "content": "Lei X dispõe sobre Y.", "metadata": {}},
                {"id": "d2", "content": "IN Z regulamenta W.", "metadata": {}},
            ]
        )
        assert count == 2

    def test_ingest_empty_list_returns_zero(self):
        from src.fiscal.rag_tributario import TaxRAGService

        svc = TaxRAGService(rag_tool=MagicMock())
        assert svc.ingest([]) == 0

    def test_ingest_no_content_returns_zero(self):
        from src.fiscal.rag_tributario import TaxRAGService

        svc = TaxRAGService(rag_tool=MagicMock())
        assert svc.ingest([{"id": "d1", "metadata": {}}]) == 0

    def test_get_tax_rag_is_singleton(self):
        import importlib
        import src.fiscal.rag_tributario as mod

        mod._tax_rag = None
        r1 = mod.get_tax_rag()
        r2 = mod.get_tax_rag()
        assert r1 is r2
        mod._tax_rag = None


# ── ConsultoriaService ──────────────────────────────────────────────────────


class TestConsultoriaService:
    """Testes para src.fiscal.consultoria.ConsultoriaService."""

    def _mock_rag(self, results=None):
        mock = MagicMock()
        mock.query.return_value = results or []
        return mock

    @pytest.mark.asyncio
    async def test_parecer_com_citacoes(self):
        from src.fiscal.consultoria import ConsultoriaService

        rag = self._mock_rag(
            [
                {
                    "text": "LC 123/2006 — Simples Nacional",
                    "metadata": {"numero": "LC 123/2006", "tributo": "Simples"},
                    "score": 0.9,
                }
            ]
        )
        svc = ConsultoriaService(tax_rag=rag)
        result = await svc.gerar_parecer(
            regime="simples_nacional",
            cnae="6201-5/01",
            porte="me",
            pergunta="Qual a alíquota do ISS para software?",
        )
        assert result["status"] == "preliminar"
        assert result["module"] == "consultoria_tributaria"
        assert "CJ-001" in result["guardrail"]
        assert len(result["citacoes"]) == 1
        assert "LC 123/2006" in result["recomendacao"]

    @pytest.mark.asyncio
    async def test_parecer_sem_citacoes_ainda_retorna_resposta(self):
        from src.fiscal.consultoria import ConsultoriaService

        svc = ConsultoriaService(tax_rag=self._mock_rag([]))
        result = await svc.gerar_parecer(
            regime="lucro_real",
            cnae="0111-3/01",
            porte="grande",
            pergunta="Como calcular IRPJ por estimativa?",
        )
        assert result["status"] == "preliminar"
        assert result["citacoes"] == []
        assert "Receita Federal" in result["recomendacao"]

    @pytest.mark.asyncio
    async def test_regime_label_is_expanded(self):
        from src.fiscal.consultoria import ConsultoriaService

        svc = ConsultoriaService(tax_rag=self._mock_rag([]))
        result = await svc.gerar_parecer(
            regime="lucro_presumido",
            cnae="6201-5/01",
            porte="epp",
            pergunta="Percentual de presunção?",
        )
        assert "Lucro Presumido" in result["regime"]

    @pytest.mark.asyncio
    async def test_porte_label_is_expanded(self):
        from src.fiscal.consultoria import ConsultoriaService

        svc = ConsultoriaService(tax_rag=self._mock_rag([]))
        result = await svc.gerar_parecer(
            regime="simples_nacional",
            cnae="4711-3/01",
            porte="mei",
            pergunta="MEI pode emitir nota?",
        )
        assert "MEI" in result["porte"]


# ── ConsultoriaRequest validation ───────────────────────────────────────────


def test_consultoria_request_invalid_regime_raises():
    from pydantic import ValidationError

    from src.api.routes.fiscal import ConsultoriaRequest

    with pytest.raises(ValidationError):
        ConsultoriaRequest(
            regime="super_simples",
            cnae="6201-5/01",
            porte="me",
            pergunta="Consulta",
        )


def test_consultoria_request_invalid_porte_raises():
    from pydantic import ValidationError

    from src.api.routes.fiscal import ConsultoriaRequest

    with pytest.raises(ValidationError):
        ConsultoriaRequest(
            regime="simples_nacional",
            cnae="6201-5/01",
            porte="gigante",
            pergunta="Consulta",
        )


def test_consultoria_request_valid():
    from src.api.routes.fiscal import ConsultoriaRequest

    req = ConsultoriaRequest(
        regime="Simples_Nacional",
        cnae="6201-5/01",
        porte="EPP",
        pergunta="Consulta de ISS",
    )
    assert req.regime == "simples_nacional"
    assert req.porte == "epp"


def test_consultoria_request_short_pergunta_raises():
    from pydantic import ValidationError

    from src.api.routes.fiscal import ConsultoriaRequest

    with pytest.raises(ValidationError):
        ConsultoriaRequest(
            regime="simples_nacional",
            cnae="6201-5/01",
            porte="me",
            pergunta="abc",
        )

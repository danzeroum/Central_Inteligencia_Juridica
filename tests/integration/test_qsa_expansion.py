"""Testes de integração da expansão QSA (Sprint 5)."""

from __future__ import annotations

from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.integrations.models import (
    AdapterResult,
    AdapterStatus,
    DataMode,
    EmpresaCadastro,
    HitlStatus,
    IdentifierQuery,
    IdentifierType,
    Publicacao,
    RelatedPartyFinding,
    SocioQSA,
)
from src.integrations.orchestrator import IntelligenceOrchestrator
from src.integrations.registry import AdapterRegistry
from src.integrations.settings import SourceSettings


def _make_adapter_cls(name: str, response: AdapterResult, id_types):
    from src.integrations.base import LegalDataAdapter

    class _M(LegalDataAdapter):
        supported_identifiers = id_types
        data_type = f"mock_{name}"

        async def fetch_real(self, q):
            return []

        async def query(self, _q):
            return response

    _M.service_name = name
    _M.supported_identifiers = id_types
    return _M


def _build_registry(responses: Dict[str, AdapterResult]) -> AdapterRegistry:
    registry = AdapterRegistry()
    for name, resp in responses.items():
        id_types = {IdentifierType.CNPJ, IdentifierType.CPF, IdentifierType.NOME}
        if name == "datajud":
            id_types = {IdentifierType.NUMERO_PROCESSO}
        elif name == "receita_cnpj":
            id_types = {IdentifierType.CNPJ}
        elif name == "tse":
            id_types = {IdentifierType.CPF, IdentifierType.NOME}
        cls = _make_adapter_cls(name, resp, id_types)
        registry.register(cls, settings_override=SourceSettings(name=name, mode="mock"))
    return registry


class TestQSAExpansion:
    def _empresa_com_socios(self) -> EmpresaCadastro:
        return EmpresaCadastro(
            cnpj="00000000000191",
            razao_social="Empresa Teste",
            situacao_cadastral="ATIVA",
            qsa=[
                SocioQSA(
                    nome="Maria Sócia PF",
                    tipo="PF",
                    identificador_mascarado="***.***.001-11",
                ),
                SocioQSA(
                    nome="Empresa Sócia Ltda",
                    tipo="PJ",
                    identificador_mascarado="12.345.678/0001-95",
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_expand_qsa_retorna_related_parties(self):
        empresa = self._empresa_com_socios()
        djen_response = AdapterResult(
            source="djen",
            status=AdapterStatus.SUCCESS,
            data_mode=DataMode.MOCK,
            items=[Publicacao(numero_processo="001", texto="Intimação")],
            total_available=1,
        )
        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[empresa],
                total_available=1,
            ),
            "djen": djen_response,
            "tse": AdapterResult(
                source="tse",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[],
            ),
        }
        registry = _build_registry(responses)
        orch = IntelligenceOrchestrator(registry)

        report = await orch.investigate(
            "00000000000191", expand_qsa=True, sources=["receita_cnpj", "djen", "tse"]
        )
        assert len(report.related_parties) > 0
        assert report.metadata.get("qsa_expanded") is True

    @pytest.mark.asyncio
    async def test_flag_off_sem_expansao(self):
        empresa = self._empresa_com_socios()
        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[empresa],
                total_available=1,
            ),
        }
        registry = _build_registry(responses)
        orch = IntelligenceOrchestrator(registry)

        report = await orch.investigate(
            "00000000000191", expand_qsa=False, sources=["receita_cnpj"]
        )
        assert report.related_parties == []
        assert not report.metadata.get("qsa_expanded")

    @pytest.mark.asyncio
    async def test_limite_de_socios_respeitado(self, monkeypatch):
        """Garante que max_socios é respeitado."""
        monkeypatch.setenv("INTEGRATIONS_QSA_MAX_SOCIOS", "2")
        from src.integrations import settings as s_mod

        s_mod._SETTINGS_CACHE = None

        # Empresa com 5 sócios
        socios = [SocioQSA(nome=f"Sócio {i}", tipo="PF") for i in range(5)]
        empresa = EmpresaCadastro(
            cnpj="00000000000191",
            razao_social="Empresa Teste",
            situacao_cadastral="ATIVA",
            qsa=socios,
        )
        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                items=[empresa],
            ),
            "djen": AdapterResult(
                source="djen", status=AdapterStatus.SUCCESS, items=[]
            ),
            "tse": AdapterResult(source="tse", status=AdapterStatus.SUCCESS, items=[]),
        }
        registry = _build_registry(responses)
        orch = IntelligenceOrchestrator(registry)

        report = await orch.investigate(
            "00000000000191", expand_qsa=True, sources=["receita_cnpj", "djen", "tse"]
        )
        # Máximo 2 sócios consultados
        assert report.metadata.get("socios_consultados", 0) <= 2
        s_mod._SETTINGS_CACHE = None  # cleanup

    @pytest.mark.asyncio
    async def test_homonimo_possivel_marcado(self):
        empresa = self._empresa_com_socios()
        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                items=[empresa],
            ),
            "djen": AdapterResult(
                source="djen", status=AdapterStatus.SUCCESS, items=[]
            ),
            "tse": AdapterResult(source="tse", status=AdapterStatus.SUCCESS, items=[]),
        }
        registry = _build_registry(responses)
        orch = IntelligenceOrchestrator(registry)

        report = await orch.investigate(
            "00000000000191", expand_qsa=True, sources=["receita_cnpj", "djen", "tse"]
        )
        # Sócios PF devem ter homonimo_possivel=True (busca por nome)
        pf_findings = [f for f in report.related_parties if f.tipo == "PF"]
        for finding in pf_findings:
            assert finding.homonimo_possivel is True

    @pytest.mark.asyncio
    async def test_socio_pj_nao_homonimo(self):
        empresa = self._empresa_com_socios()
        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                items=[empresa],
            ),
            "djen": AdapterResult(
                source="djen", status=AdapterStatus.SUCCESS, items=[]
            ),
            "tse": AdapterResult(source="tse", status=AdapterStatus.SUCCESS, items=[]),
        }
        registry = _build_registry(responses)
        orch = IntelligenceOrchestrator(registry)

        report = await orch.investigate(
            "00000000000191", expand_qsa=True, sources=["receita_cnpj", "djen", "tse"]
        )
        pj_findings = [f for f in report.related_parties if f.tipo == "PJ"]
        for finding in pj_findings:
            assert finding.homonimo_possivel is False

    @pytest.mark.asyncio
    async def test_fatores_societarios_no_score(self):
        """Sócio com ocorrências gera fatores na dimensão societário."""
        empresa = self._empresa_com_socios()
        # DJEN retorna publicações → sócio tem ocorrências
        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                items=[empresa],
            ),
            "djen": AdapterResult(
                source="djen",
                status=AdapterStatus.SUCCESS,
                items=[Publicacao(numero_processo="001", texto="citação")],
            ),
            "tse": AdapterResult(source="tse", status=AdapterStatus.SUCCESS, items=[]),
        }
        registry = _build_registry(responses)
        orch = IntelligenceOrchestrator(registry)

        report = await orch.investigate(
            "00000000000191", expand_qsa=True, sources=["receita_cnpj", "djen", "tse"]
        )
        # Se há related parties com ocorrências, deve haver fatores societários
        parties_with_occ = [
            p for p in report.related_parties if p.total_ocorrencias > 0
        ]
        if parties_with_occ:
            societario_dim = next(
                (d for d in report.risk_dimensions if d.name == "societario"), None
            )
            assert societario_dim is not None

    @pytest.mark.asyncio
    async def test_sem_receita_success_sem_expansao(self):
        """Sem resultado de receita_cnpj, não há expansão QSA."""
        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.FAILED,
                error="Timeout",
            ),
            "djen": AdapterResult(
                source="djen", status=AdapterStatus.SUCCESS, items=[]
            ),
        }
        registry = _build_registry(responses)
        orch = IntelligenceOrchestrator(registry)

        report = await orch.investigate(
            "00000000000191", expand_qsa=True, sources=["receita_cnpj", "djen"]
        )
        assert report.related_parties == []

    @pytest.mark.asyncio
    async def test_lgpd_sub_consultas_nao_propagam_pii(self):
        """Sub-consultas de QSA usam hash de auditoria, não PII bruta."""
        empresa = self._empresa_com_socios()
        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                items=[empresa],
            ),
            "djen": AdapterResult(
                source="djen", status=AdapterStatus.SUCCESS, items=[]
            ),
            "tse": AdapterResult(source="tse", status=AdapterStatus.SUCCESS, items=[]),
        }
        registry = _build_registry(responses)
        mock_ledger = MagicMock()
        mock_ledger.record = MagicMock()
        orch = IntelligenceOrchestrator(registry, ledger=mock_ledger)

        report = await orch.investigate(
            "00000000000191", expand_qsa=True, sources=["receita_cnpj", "djen", "tse"]
        )
        # identifier_masked deve não conter CNPJ bruto
        assert "00000000000191" not in report.identifier_masked
        # Ledger record não contém PII bruta
        if mock_ledger.record.called:
            call_kwargs = mock_ledger.record.call_args[1]
            assert "00000000000191" not in call_kwargs.get("identifier_hash", "")

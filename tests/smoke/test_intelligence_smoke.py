"""Smoke tests para a camada de integrações jurídicas (Sprint 9)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "JWT_SECRET", "development-secret-key-minimum-32-chars-long-for-tests"
)
os.environ["ENVIRONMENT"] = "test"


class TestSmoke:
    """Testes de smoke — verifica que os módulos principais importam sem erros."""

    def test_import_integrations(self):
        import src.integrations

    def test_import_models(self):
        from src.integrations.models import ConsolidatedReport, AdapterResult

    def test_import_identifiers(self):
        from src.integrations.identifiers import classify_identifier

    def test_import_settings(self):
        from src.integrations.settings import get_source_settings

    def test_import_registry(self):
        from src.integrations.registry import get_registry

    def test_import_orchestrator(self):
        from src.integrations.orchestrator import IntelligenceOrchestrator

    def test_import_risk_engine(self):
        from src.integrations.risk_engine import RiskEngine

    def test_import_graphql_schema(self):
        from src.api.intelligence_graphql.schema import schema

        assert schema is not None

    def test_import_intelligence_endpoints(self):
        from src.api.intelligence_endpoints import router

        assert router is not None

    def test_import_intelligence_agent(self):
        from src.agents.intelligence_agent import IntelligenceAgent

    def test_import_fiscal_agent(self):
        from src.agents.fiscal_agent import FiscalAgent

    def test_import_credentials(self):
        from src.integrations.credentials import get_credential_provider

    def test_sources_yaml_loads(self):
        from src.integrations.settings import load_source_settings

        settings = load_source_settings()
        assert len(settings) == 7
        expected = {
            "datajud",
            "djen",
            "receita_cnpj",
            "tse",
            "crc_protestos",
            "cadin",
            "onr_imoveis",
        }
        assert set(settings.keys()) == expected

    def test_risk_scoring_yaml_loads(self):
        from src.integrations.risk_engine import _load_risk_config, DEFAULT_RISK_CONFIG

        config = _load_risk_config(DEFAULT_RISK_CONFIG)
        assert "weights" in config
        assert "hitl" in config

    def test_governance_yaml_has_new_types(self):
        from src.governance.data_source_policy import get_data_source_policy

        policy = get_data_source_policy()
        new_types = [
            "processo_por_numero",
            "publicacao_dje",
            "cadastro_empresa",
            "eleitoral",
            "protesto",
            "cadin",
            "imovel",
            "sped_regularidade",
        ]
        for dt in new_types:
            rule = policy.rule_for(dt)
            assert rule is not None, f"data_type '{dt}' não encontrado na policy"

    def test_rbac_has_intelligence_permissions(self):
        from src.api.rbac import ROLE_PERMISSIONS, Role

        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert "intelligence:query" in admin_perms
        assert "intelligence:zone:credenciada" in admin_perms
        operator_perms = ROLE_PERMISSIONS[Role.OPERATOR]
        assert "intelligence:query" in operator_perms

    def test_span_record_context_manager(self):
        from src.utils.observability import SpanRecord

        span = SpanRecord(operation="smoke", metadata={})
        with span:
            pass
        assert span.end_time is not None

    def test_all_7_adapters_importable(self):
        from src.integrations.adapters.datajud_adapter import DataJudAdapter
        from src.integrations.adapters.djen_adapter import DjenAdapter
        from src.integrations.adapters.receita_cnpj_adapter import ReceitaCnpjAdapter
        from src.integrations.adapters.tse_adapter import TseAdapter
        from src.integrations.adapters.crc_protestos_adapter import CrcProtestosAdapter
        from src.integrations.adapters.cadin_adapter import CadinAdapter
        from src.integrations.adapters.onr_imoveis_adapter import OnrImoveisAdapter

        adapters = [
            DataJudAdapter,
            DjenAdapter,
            ReceitaCnpjAdapter,
            TseAdapter,
            CrcProtestosAdapter,
            CadinAdapter,
            OnrImoveisAdapter,
        ]
        names = [a.service_name for a in adapters]
        assert len(set(names)) == 7

    @pytest.mark.asyncio
    async def test_orchestrator_mock_full_flow(self):
        """Smoke end-to-end com todas as fontes em modo mock."""
        from src.integrations.registry import AdapterRegistry
        from src.integrations.orchestrator import IntelligenceOrchestrator
        from src.integrations.risk_engine import RiskEngine
        from src.integrations.adapters.receita_cnpj_adapter import ReceitaCnpjAdapter
        from src.integrations.adapters.crc_protestos_adapter import CrcProtestosAdapter
        from src.integrations.adapters.cadin_adapter import CadinAdapter
        from src.integrations.settings import SourceSettings

        registry = AdapterRegistry()
        for cls in [ReceitaCnpjAdapter, CrcProtestosAdapter, CadinAdapter]:
            registry.register(
                cls,
                settings_override=SourceSettings(name=cls.service_name, mode="mock"),
            )

        orch = IntelligenceOrchestrator(registry, risk_engine=RiskEngine())
        report = await orch.investigate("00000000000191")

        assert report is not None
        assert report.identifier_type.value == "CNPJ"
        assert 0 <= report.risk_score <= 100
        assert len(report.risk_dimensions) == 4

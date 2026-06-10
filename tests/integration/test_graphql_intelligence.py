"""Testes GraphQL para o endpoint de inteligência jurídica (Sprint 6)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault(
    "JWT_SECRET", "development-secret-key-minimum-32-chars-long-for-tests"
)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.integrations.models import (
    AdapterResult,
    AdapterStatus,
    ConsolidatedReport,
    DataMode,
    HitlStatus,
    IdentifierType,
    RiskDimension,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "integrations"


def _build_test_app():
    from src.api.auth import AuthManager

    AuthManager.configure(required=False)

    app = FastAPI()
    from src.api.intelligence_graphql.schema import create_graphql_router
    from src.api.intelligence_endpoints import router as intel_router

    app.include_router(intel_router)
    app.include_router(
        create_graphql_router(),
        prefix="/api/v1/intelligence/graphql",
    )
    return app


def _mock_report() -> ConsolidatedReport:
    return ConsolidatedReport(
        query_id="test-query-id",
        identifier_masked="**.***.***/****-91",
        identifier_type=IdentifierType.CNPJ,
        results={
            "receita_cnpj": {
                "source": "receita_cnpj",
                "status": "success",
                "data_mode": "mock",
                "from_cache": False,
                "latency_ms": 42.0,
                "total_available": 1,
                "error": None,
                "metadata": {},
                "items": [],
            }
        },
        risk_score=15.0,
        risk_dimensions=[
            RiskDimension(name="juridico", score=0.0),
            RiskDimension(name="fiscal", score=15.0),
            RiskDimension(name="patrimonial", score=0.0),
            RiskDimension(name="societario", score=0.0),
        ],
        recommendations=["Verificar regularidade fiscal"],
        summary="Score de risco: 15/100.",
        hitl_status=HitlStatus.NOT_REQUIRED,
    )


class TestGraphQLIntelligence:
    QUERY = """
    query($id: String!) {
      intelligence(identifier: $id) {
        queryId
        identifierMasked
        riskScore
        hitlStatus
        summary
        riskDimensions {
          name
          score
        }
        results {
          source
          status
          dataMode
        }
      }
    }
    """

    def test_query_returns_report(self):
        app = _build_test_app()
        mock_report = _mock_report()

        with patch(
            "src.api.intelligence_graphql.schema._get_orchestrator"
        ) as mock_orch_fn:
            mock_orch = MagicMock()
            mock_orch.investigate = AsyncMock(return_value=mock_report)
            mock_orch_fn.return_value = mock_orch

            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/intelligence/graphql",
                    json={
                        "query": self.QUERY,
                        "variables": {"id": "00.000.000/0001-91"},
                    },
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "errors" not in data
        assert data["data"]["intelligence"]["riskScore"] == 15.0
        assert data["data"]["intelligence"]["hitlStatus"] == "not_required"

    def test_query_returns_risk_dimensions(self):
        app = _build_test_app()
        mock_report = _mock_report()

        with patch(
            "src.api.intelligence_graphql.schema._get_orchestrator"
        ) as mock_orch_fn:
            mock_orch = MagicMock()
            mock_orch.investigate = AsyncMock(return_value=mock_report)
            mock_orch_fn.return_value = mock_orch

            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/intelligence/graphql",
                    json={
                        "query": self.QUERY,
                        "variables": {"id": "00.000.000/0001-91"},
                    },
                )

        dims = resp.json()["data"]["intelligence"]["riskDimensions"]
        assert len(dims) == 4
        fiscal = next(d for d in dims if d["name"] == "fiscal")
        assert fiscal["score"] == 15.0

    def test_depth_limit_blocks_deeply_nested(self):
        app = _build_test_app()
        # Consulta com profundidade excessiva
        deep_query = """
        query {
          intelligence(identifier: "123") {
            results {
              source
              status
              error
            }
            relatedParties {
              nome
              vinculo
              fonte
              resumo
              totalOcorrencias
              homonimoPossivel
              tipo
            }
          }
        }
        """
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/intelligence/graphql",
                json={"query": deep_query},
            )
        # Profundidade 3 está dentro do limite de 10 — deve passar
        assert resp.status_code == 200

    def test_pagination_params_passed(self):
        app = _build_test_app()
        mock_report = _mock_report()

        paginated_query = """
        query($id: String!) {
          intelligence(identifier: $id, limit: 5, offset: 10) {
            queryId
            riskScore
          }
        }
        """

        with patch(
            "src.api.intelligence_graphql.schema._get_orchestrator"
        ) as mock_orch_fn:
            mock_orch = MagicMock()
            mock_orch.investigate = AsyncMock(return_value=mock_report)
            mock_orch_fn.return_value = mock_orch

            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/intelligence/graphql",
                    json={
                        "query": paginated_query,
                        "variables": {"id": "00000000000191"},
                    },
                )

        assert resp.status_code == 200
        # Verifica que investigate foi chamado com limit e offset corretos
        call_kwargs = mock_orch.investigate.call_args[1]
        assert call_kwargs["limit"] == 5
        assert call_kwargs["offset"] == 10


class TestIntelligenceHealth:
    def test_health_returns_adapters(self):
        app = _build_test_app()

        # Registra um adapter fake
        from src.integrations.registry import get_registry, AdapterRegistry
        from src.integrations.base import LegalDataAdapter
        from src.integrations.settings import SourceSettings
        from src.integrations.models import IdentifierType

        class FakeHealthAdapter(LegalDataAdapter):
            service_name = "fake_health"
            supported_identifiers = {IdentifierType.CNPJ}
            data_type = "test"

            async def fetch_real(self, q):
                return []

        registry = get_registry()
        if not registry.get("fake_health"):
            registry.register(
                FakeHealthAdapter,
                settings_override=SourceSettings(name="fake_health", mode="mock"),
            )

        with TestClient(app) as client:
            # Com AUTH_REQUIRED=False, sem token o acesso é anônimo (permitido)
            resp = client.get("/api/v1/intelligence/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert isinstance(body["adapters"], list)

    def test_health_graphql_query(self):
        app = _build_test_app()

        health_query = """
        query {
          intelligenceHealth {
            source
            enabled
            mode
            zone
          }
        }
        """
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/intelligence/graphql",
                json={"query": health_query},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "errors" not in data
        assert isinstance(data["data"]["intelligenceHealth"], list)


class TestSDLSnapshot:
    """Verifica que o SDL não sofreu drift não intencional."""

    def test_sdl_snapshot_matches(self):
        fixture_file = FIXTURES / "intelligence_schema.graphql"
        if not fixture_file.exists():
            pytest.skip("SDL snapshot não existe ainda")

        from src.api.intelligence_graphql.schema import schema

        current_sdl = schema.as_str()
        saved_sdl = fixture_file.read_text()
        assert (
            current_sdl.strip() == saved_sdl.strip()
        ), "SDL drift detectado! Atualize tests/fixtures/integrations/intelligence_schema.graphql"

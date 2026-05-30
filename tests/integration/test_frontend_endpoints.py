"""Integration tests para os endpoints que dão suporte à SPA.

Cobre as novas superfícies de leitura/escrita adicionadas para a interface:
trilha de auditoria (ledger), configuração de autonomia (DMN), monitoramento,
estatísticas HITL, histórico de consultas e enriquecimento de agentes.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.api.main import app

client = TestClient(app)


class TestLedgerEndpoints:
    def test_list_ledger_structure(self) -> None:
        response = client.get("/api/v1/ledger")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_export_csv(self) -> None:
        response = client.get("/api/v1/ledger/export.csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "id,timestamp,agent_type" in response.text


class TestAutonomyConfig:
    def test_get_config(self) -> None:
        response = client.get("/api/v1/autonomy/config")
        assert response.status_code == 200
        data = response.json()
        assert "consensus_threshold" in data["config"]
        assert len(data["decision_table"]) == 4

    def test_update_config_roundtrip(self) -> None:
        response = client.put(
            "/api/v1/autonomy/config", json={"consensus_threshold": 0.65}
        )
        assert response.status_code == 200
        assert response.json()["config"]["consensus_threshold"] == 0.65
        # restaura para não vazar estado entre testes
        client.put("/api/v1/autonomy/config", json={"consensus_threshold": 0.6})

    def test_update_config_invalid_ordering(self) -> None:
        response = client.put(
            "/api/v1/autonomy/config",
            json={"trust_supervised_threshold": 0.9, "trust_full_threshold": 0.5},
        )
        assert response.status_code == 400


class TestMonitoring:
    def test_health_aggregates_sources(self) -> None:
        response = client.get("/api/v1/monitoring/health")
        assert response.status_code == 200
        data = response.json()
        assert "circuit_breakers" in data
        assert "hitl_queue_depth" in data
        assert "a2a" in data


class TestHitlStats:
    def test_stats_structure(self) -> None:
        response = client.get("/api/v1/hitl/stats")
        assert response.status_code == 200
        data = response.json()
        assert "pending" in data
        assert "approved_today" in data
        assert "rejected_today" in data


class TestHistory:
    def test_history_structure(self) -> None:
        response = client.get("/api/v1/history")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["history"], list)


class TestAgentsEnriched:
    def test_agents_include_trust_and_autonomy(self) -> None:
        response = client.get("/api/v1/agents")
        assert response.status_code == 200
        agents = response.json()["agents"]
        assert agents, "deve haver ao menos o supervisor"
        for agent in agents:
            assert "trust_score" in agent
            assert "autonomy_level" in agent
            assert "capabilities" in agent

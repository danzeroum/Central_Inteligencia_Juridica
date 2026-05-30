"""Integration tests para os endpoints que dão suporte à SPA.

Cobre as superfícies de leitura/escrita usadas pela interface: trilha de
auditoria (ledger), configuração de autonomia (DMN), monitoramento, estatísticas
HITL, histórico e enriquecimento de agentes. Além do shape das respostas, os
testes validam VALORES (filtros, conteúdo do CSV, contadores, faixas) e os
caminhos de erro (422 validação, 400 regra de negócio).
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.api.main import app
from src.hitl.hitl_queue import get_hitl_queue
from src.hitl.progressive_autonomy import get_autonomy_manager
from src.tools.circuit_breaker import CircuitBreaker
from src.utils.ledger import get_ledger

client = TestClient(app)


@pytest.fixture
def restore_autonomy_config():
    """Restaura os limiares de autonomia após testes que os alteram."""
    manager = get_autonomy_manager()
    before = manager.get_config()
    yield
    manager.update_config(
        consensus_threshold=before["consensus_threshold"],
        trust_full_threshold=before["trust_full_threshold"],
        trust_supervised_threshold=before["trust_supervised_threshold"],
    )


class TestLedgerEndpoints:
    def test_list_returns_newest_first_and_shape(self) -> None:
        ledger = get_ledger()
        ledger.log_decision("SupervisorAgent", "TASK_COMPLETED", {"task": "antiga"})
        ledger.log_decision("HumanOperator", "HITL_DECISION", {"approved": True, "operator_id": "m.ribeiro"})

        data = client.get("/api/v1/ledger").json()
        assert data["count"] >= 2
        # Mais recente primeiro (lista invertida pelo endpoint).
        assert data["entries"][0]["agent_type"] == "HumanOperator"
        # Cada entrada expõe os campos que a tela de Auditoria consome.
        first = data["entries"][0]
        assert {"id", "timestamp", "agent_type", "decision_type", "metadata"} <= set(first)

    def test_filter_by_agent_type(self) -> None:
        ledger = get_ledger()
        ledger.log_decision("HumanOperator", "HITL_DECISION", {"approved": False})
        resp = client.get("/api/v1/ledger", params={"agent_type": "HumanOperator"})
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert entries, "deve haver ao menos uma entrada do HumanOperator"
        assert all(e["agent_type"] == "HumanOperator" for e in entries)

    def test_filter_by_decision_type(self) -> None:
        ledger = get_ledger()
        ledger.log_decision("SupervisorAgent", "TASK_COMPLETED", {})
        entries = client.get("/api/v1/ledger", params={"decision_type": "TASK_COMPLETED"}).json()["entries"]
        assert entries
        assert all(e["decision_type"] == "TASK_COMPLETED" for e in entries)

    def test_export_csv_has_header_and_data_rows(self) -> None:
        ledger = get_ledger()
        ledger.log_decision("HumanOperator", "HITL_DECISION", {"approved": True, "operator_id": "ana", "agent": "tjsp_agent"})

        resp = client.get("/api/v1/ledger/export.csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers.get("content-disposition", "")

        rows = list(csv.reader(io.StringIO(resp.text)))
        assert rows[0] == ["id", "timestamp", "agent_type", "decision_type", "approved", "operator", "agent_alvo"]
        # Pelo menos uma linha de dados, com o operador semeado presente.
        assert len(rows) > 1
        assert any("ana" in row for row in rows[1:])


class TestAutonomyConfig:
    def test_get_config_and_decision_table(self) -> None:
        data = client.get("/api/v1/autonomy/config").json()
        cfg = data["config"]
        assert 0 <= cfg["consensus_threshold"] <= 1
        table = data["decision_table"]
        assert len(table) == 4
        # Regra #1 (ação crítica) sempre exige HITL; regra #4 (autônomo) não.
        by_rule = {r["rule"]: r for r in table}
        assert by_rule[1]["requires_hitl"] is True
        assert by_rule[4]["requires_hitl"] is False

    def test_update_config_roundtrip(self, restore_autonomy_config) -> None:
        resp = client.put("/api/v1/autonomy/config", json={"consensus_threshold": 0.65})
        assert resp.status_code == 200
        assert resp.json()["config"]["consensus_threshold"] == 0.65
        # Persiste para a próxima leitura (estado em memória compartilhado).
        assert client.get("/api/v1/autonomy/config").json()["config"]["consensus_threshold"] == 0.65

    @pytest.mark.parametrize("value", [-0.1, 1.5])
    def test_out_of_range_is_422(self, value) -> None:
        # Validação de schema (Pydantic ge/le) -> 422, não 400.
        assert client.put("/api/v1/autonomy/config", json={"consensus_threshold": value}).status_code == 422

    def test_inverted_bands_is_400(self, restore_autonomy_config) -> None:
        # Regra de negócio (supervisionado > pleno) -> 400 do update_config.
        resp = client.put(
            "/api/v1/autonomy/config",
            json={"trust_supervised_threshold": 0.9, "trust_full_threshold": 0.5},
        )
        assert resp.status_code == 400


class TestMonitoring:
    def test_registered_circuit_breaker_appears_with_shape(self) -> None:
        # Cria um breaker -> deve ser auto-registrado e listado pelo monitor.
        CircuitBreaker(name="test_monitor_breaker")
        data = client.get("/api/v1/monitoring/health").json()
        names = {b["name"] for b in data["circuit_breakers"]}
        assert "test_monitor_breaker" in names
        breaker = next(b for b in data["circuit_breakers"] if b["name"] == "test_monitor_breaker")
        assert breaker["state"] == "closed"
        assert {"failure_count", "can_execute", "time_until_half_open"} <= set(breaker)

    def test_queue_depth_reflects_pending(self) -> None:
        queue = get_hitl_queue()
        queue.add_request(agent="mon_agent", action={"type": "x"}, context={})
        data = client.get("/api/v1/monitoring/health").json()
        assert data["hitl_queue_depth"] >= 1


class TestHitlStats:
    def test_approved_and_rejected_counts_increment(self) -> None:
        queue = get_hitl_queue()
        before = client.get("/api/v1/hitl/stats").json()

        # Aprova uma e rejeita outra via endpoint (que registra no ledger).
        r1 = queue.add_request(agent="stat_agent", action={"type": "a"}, context={})
        client.post("/api/v1/hitl/decisions", json={"request_id": r1.request_id, "approved": True, "operator_id": "op"})
        r2 = queue.add_request(agent="stat_agent", action={"type": "b"}, context={})
        client.post("/api/v1/hitl/decisions", json={"request_id": r2.request_id, "approved": False, "feedback": "não", "operator_id": "op"})

        after = client.get("/api/v1/hitl/stats").json()
        assert after["approved_today"] >= before["approved_today"] + 1
        assert after["rejected_today"] >= before["rejected_today"] + 1


class TestHitlDecisionErrors:
    def test_unknown_request_is_404(self) -> None:
        resp = client.post("/api/v1/hitl/decisions", json={"request_id": "inexistente", "approved": True})
        assert resp.status_code == 404

    def test_already_decided_is_409(self) -> None:
        queue = get_hitl_queue()
        req = queue.add_request(agent="dup_agent", action={"type": "x"}, context={})
        first = client.post("/api/v1/hitl/decisions", json={"request_id": req.request_id, "approved": True})
        assert first.status_code == 200
        # Segunda decisão sobre a mesma solicitação -> conflito.
        second = client.post("/api/v1/hitl/decisions", json={"request_id": req.request_id, "approved": True})
        assert second.status_code == 409


class TestHistory:
    def test_history_status_values_are_valid(self) -> None:
        data = client.get("/api/v1/history").json()
        assert "count" in data and isinstance(data["history"], list)
        for item in data["history"]:
            assert item["status"] in {"concluida", "em_revisao_humana"}
            assert {"task", "operation", "tribunals", "timestamp"} <= set(item)


class TestAgentsEnriched:
    def test_trust_and_autonomy_within_valid_domains(self) -> None:
        agents = client.get("/api/v1/agents").json()["agents"]
        assert agents, "deve haver ao menos o supervisor"
        assert any(a["agent_id"] == "supervisor_agent" for a in agents)
        for agent in agents:
            assert 0.0 <= agent["trust_score"] <= 1.0
            assert agent["autonomy_level"] in {"full", "supervised", "restricted"}
            assert isinstance(agent["capabilities"], list)

"""Integration tests for MCP endpoints."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.api.main import app

client = TestClient(app)


class TestMCPCapabilities:
    """Test suite for MCP agent capabilities endpoint."""

    def test_get_capabilities_returns_valid_structure(self) -> None:
        """MCP capabilities endpoint should return valid protocol structure."""
        response = client.get("/api/v1/agents/capabilities")

        assert response.status_code == 200
        data = response.json()

        # Validate MCP protocol structure
        assert data["protocol"] == "MCP/1.0"
        assert data["service"] == "Central de Inteligência Jurídica"
        assert "total_agents" in data
        assert "agents" in data
        assert "capabilities_summary" in data
        assert "timestamp" in data

    def test_capabilities_includes_supervisor(self) -> None:
        """Registry must include supervisor agent."""
        response = client.get("/api/v1/agents/capabilities")
        data = response.json()

        agents = data["agents"]
        supervisor = next(
            (agent for agent in agents if agent["agent_type"] == "SupervisorAgent"),
            None,
        )

        assert supervisor is not None
        assert supervisor["agent_id"] == "supervisor_agent"
        assert "task_routing" in supervisor["capabilities"]

    def test_capabilities_summary_aggregates_correctly(self) -> None:
        """Capabilities summary should aggregate from all agents."""
        response = client.get("/api/v1/agents/capabilities")
        data = response.json()

        summary = data["capabilities_summary"]
        assert "capabilities" in summary
        assert "tools" in summary
        assert isinstance(summary["capabilities"], list)
        assert isinstance(summary["tools"], list)


class TestMCPAgentList:
    """Test suite for agent listing endpoint."""

    def test_list_agents_returns_all_active(self) -> None:
        """Should list all active agents."""
        response = client.get("/api/v1/agents")

        assert response.status_code == 200
        data = response.json()

        assert "total" in data
        assert "agents" in data
        assert data["total"] >= 1  # At least supervisor

    def test_agent_list_includes_essential_fields(self) -> None:
        """Each agent in list should have essential fields."""
        response = client.get("/api/v1/agents")
        data = response.json()

        for agent in data["agents"]:
            assert "agent_id" in agent
            assert "name" in agent
            assert "type" in agent
            assert "status" in agent
            assert "endpoint" in agent


class TestMCPAgentDetails:
    """Test suite for individual agent details."""

    def test_get_supervisor_details(self) -> None:
        """Should retrieve detailed info about supervisor."""
        response = client.get("/api/v1/agents/supervisor_agent")

        assert response.status_code == 200
        data = response.json()

        assert data["agent_id"] == "supervisor_agent"
        assert data["agent_type"] == "SupervisorAgent"
        assert "capabilities" in data
        assert "tools" in data
        assert "metadata" in data

    def test_get_nonexistent_agent_returns_404(self) -> None:
        """Should return 404 for unknown agent."""
        response = client.get("/api/v1/agents/nonexistent_agent")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestMCPDirectInvocation:
    """Test suite for direct agent invocation."""

    def test_invoke_supervisor_directly(self) -> None:
        """Should be able to invoke supervisor via MCP."""
        response = client.post(
            "/api/v1/agents/supervisor_agent/invoke",
            json={"task_description": "Status do TJSP"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["agent_invoked"] == "supervisor_agent"
        assert "result" in data

    def test_invoke_tribunal_agent_directly(self) -> None:
        """Should create and invoke tribunal agent directly."""
        client.post("/api/v1/tasks", json={"task_description": "Status TJMG"})

        response = client.post(
            "/api/v1/agents/tjmg_agent/invoke",
            json={"task_description": "Consulta processo 123"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["agent_invoked"] == "tjmg_agent"
        assert "result" in data

    def test_invoke_nonexistent_agent_returns_404(self) -> None:
        """Should return 404 when invoking unknown agent."""
        response = client.post(
            "/api/v1/agents/fake_agent/invoke",
            json={"task_description": "Test"},
        )

        assert response.status_code == 404


class TestMCPCapabilitySearch:
    """Test suite for capability-based agent search."""

    def test_search_by_existing_capability(self) -> None:
        """Should find agents with specific capability."""
        response = client.get("/api/v1/agents/by-capability/task_routing")

        assert response.status_code == 200
        data = response.json()

        assert data["capability"] == "task_routing"
        assert data["total_matches"] >= 1
        assert any(
            agent["agent_id"] == "supervisor_agent"
            for agent in data["agents"]
        )

    def test_search_nonexistent_capability_returns_empty(self) -> None:
        """Should return empty list for unknown capability."""
        response = client.get("/api/v1/agents/by-capability/quantum_computing")

        assert response.status_code == 200
        data = response.json()

        assert data["total_matches"] == 0
        assert data["agents"] == []


class TestMCPProtocolCompliance:
    """Validate MCP protocol compliance."""

    def test_all_agents_have_required_fields(self) -> None:
        """All agent cards should have MCP-required fields."""
        response = client.get("/api/v1/agents/capabilities")
        data = response.json()

        required_fields = {
            "agent_id",
            "agent_type",
            "name",
            "description",
            "capabilities",
            "tools",
            "specialization",
            "status",
        }

        for agent in data["agents"]:
            assert required_fields.issubset(agent.keys())

    def test_mcp_version_is_consistent(self) -> None:
        """MCP protocol version should be consistent."""
        response = client.get("/api/v1/agents/capabilities")
        data = response.json()

        assert data["protocol"] == "MCP/1.0"
        assert data["version"] == "1.0.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

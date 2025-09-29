"""Testes emergentes para validar resiliência das integrações com APIs reais."""

from __future__ import annotations

import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import httpx
import pytest
import respx

from src.tools.tribunal_api_adapter import TribunalAPIAdapter
from src.tools.circuit_breaker import CircuitState


@pytest.fixture
def mock_flaky_api() -> respx.Router:
    with respx.mock(base_url="https://api.tjsp.jus.br/v2") as mock:
        yield mock


def test_system_survives_api_instability(mock_flaky_api: respx.Router) -> None:
    call_count = 0

    def flaky_response(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return httpx.Response(503, json={"error": "Service Unavailable"})
        if call_count % 2 == 0:
            return httpx.Response(
                200,
                json={
                    "status": "operacional",
                    "ultima_atualizacao": "2025-09-29T20:00:00Z",
                    "mensagem": "OK",
                    "servicos_ativos": 95,
                },
            )
        return httpx.Response(503, json={"error": "Service Unavailable"})

    mock_flaky_api.get("/status").mock(side_effect=flaky_response)

    adapter = TribunalAPIAdapter("TJSP")

    results = []
    for _ in range(10):
        results.append(adapter.get_status())
        time.sleep(0.05)

    assert len(results) == 10
    sources = {result["_metadata"]["source"] for result in results}
    assert "real_api" in sources
    assert "simulated" in sources
    for result in results:
        assert result["status"] in {"operacional", "instabilidade", "offline"}


def test_circuit_breaker_prevents_cascading_failures(mock_flaky_api: respx.Router) -> None:
    api_call_count = 0

    def always_fails(request: httpx.Request) -> httpx.Response:
        nonlocal api_call_count
        api_call_count += 1
        return httpx.Response(500, json={"error": "Server Error"})

    mock_flaky_api.get("/status").mock(side_effect=always_fails)

    adapter = TribunalAPIAdapter("TJSP")

    for _ in range(3):
        result = adapter.get_status()
        assert result["_metadata"]["source"] == "simulated"

    cb_state = adapter.get_circuit_breaker_state()
    assert cb_state["state"] == "open"
    assert api_call_count == 9

    for _ in range(5):
        result = adapter.get_status()
        assert result["_metadata"]["source"] == "simulated"

    assert api_call_count == 9


def test_circuit_breaker_recovers_after_timeout(mock_flaky_api: respx.Router) -> None:
    call_count = 0

    def failing_then_success(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count <= 9:
            return httpx.Response(500, json={"error": "Down"})
        return httpx.Response(
            200,
            json={
                "status": "operacional",
                "ultima_atualizacao": "2025-09-29T20:00:00Z",
                "mensagem": "Recovered!",
                "servicos_ativos": 95,
            },
        )

    mock_flaky_api.get("/status").mock(side_effect=failing_then_success)

    adapter = TribunalAPIAdapter("TJSP")
    adapter.circuit_breaker.timeout_seconds = 1

    for _ in range(3):
        adapter.get_status()

    assert adapter.circuit_breaker.state == CircuitState.OPEN

    time.sleep(1.2)

    result = adapter.get_status()

    assert result["_metadata"]["source"] == "real_api"
    assert result["mensagem"] == "Recovered!"
    cb_state = adapter.get_circuit_breaker_state()
    assert cb_state["state"] in {"closed", "half_open"}


def test_degraded_performance_acceptable(mock_flaky_api: respx.Router) -> None:
    mock_flaky_api.get("/status").mock(
        return_value=httpx.Response(500, json={"error": "Down"})
    )

    adapter = TribunalAPIAdapter("TJSP")

    start = time.perf_counter()
    result = adapter.get_status()
    latency = time.perf_counter() - start

    assert result["_metadata"]["source"] == "simulated"
    assert latency < 5


def test_parallel_requests_dont_overwhelm_circuit(mock_flaky_api: respx.Router) -> None:
    mock_flaky_api.get("/status").mock(
        return_value=httpx.Response(500, json={"error": "Down"})
    )

    adapter = TribunalAPIAdapter("TJSP")

    results = [adapter.get_status() for _ in range(10)]

    assert len(results) == 10
    assert all(result["_metadata"]["source"] == "simulated" for result in results)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v", "-s", "--tb=short"])

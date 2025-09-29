"""Testes de integração para o adaptador de APIs reais dos tribunais."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import httpx
import pytest
import respx

from src.tools.tribunal_api_adapter import TribunalAPIAdapter


@pytest.fixture
def mock_tjsp_api() -> respx.Router:
    with respx.mock(base_url="https://api.tjsp.jus.br/v2") as mock:
        yield mock


@pytest.fixture
def mock_tjmg_api() -> respx.Router:
    with respx.mock(base_url="https://api5.tjmg.jus.br") as mock:
        yield mock


def test_adapter_uses_real_api_when_available(mock_tjsp_api: respx.Router) -> None:
    mock_tjsp_api.get("/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "operacional",
                "ultima_atualizacao": "2025-09-29T20:00:00Z",
                "mensagem": "Sistema OK",
                "servicos_ativos": 95,
            },
        )
    )

    adapter = TribunalAPIAdapter("TJSP")
    result = adapter.get_status()

    assert result["_metadata"]["source"] == "real_api"
    assert result["status"] == "operacional"


def test_adapter_falls_back_to_mock_on_api_error(mock_tjsp_api: respx.Router) -> None:
    mock_tjsp_api.get("/status").mock(
        return_value=httpx.Response(500, json={"error": "Internal Server Error"})
    )

    adapter = TribunalAPIAdapter("TJSP")
    result = adapter.get_status()

    assert result["_metadata"]["source"] == "simulated"
    assert result["_metadata"]["fallback"] is True


def test_adapter_falls_back_on_timeout(mock_tjsp_api: respx.Router) -> None:
    mock_tjsp_api.get("/status").mock(side_effect=httpx.TimeoutException("Timeout"))

    adapter = TribunalAPIAdapter("TJSP")
    result = adapter.get_status()

    assert result["_metadata"]["source"] == "simulated"
    assert result["_metadata"]["fallback"] is True


def test_adapter_uses_mock_for_unconfigured_tribunal() -> None:
    adapter = TribunalAPIAdapter("TJRS")
    result = adapter.get_status()

    assert result["_metadata"]["source"] == "simulated"
    assert result["status"] in {"operacional", "instabilidade", "offline"}


def test_circuit_breaker_opens_after_failures(mock_tjsp_api: respx.Router) -> None:
    mock_tjsp_api.get("/status").mock(
        return_value=httpx.Response(503, json={"error": "Service Unavailable"})
    )

    adapter = TribunalAPIAdapter("TJSP")

    for _ in range(3):
        result = adapter.get_status()
        assert result["_metadata"]["source"] == "simulated"

    cb_state = adapter.get_circuit_breaker_state()
    assert cb_state["state"] == "open"
    assert cb_state["can_execute"] is False


def test_retry_logic_works(mock_tjsp_api: respx.Router) -> None:
    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(500, json={"error": "Temporary failure"})
        return httpx.Response(
            200,
            json={
                "status": "operacional",
                "ultima_atualizacao": "2025-09-29T20:00:00Z",
                "mensagem": "Sistema OK após retry",
                "servicos_ativos": 95,
            },
        )

    mock_tjsp_api.get("/status").mock(side_effect=side_effect)

    adapter = TribunalAPIAdapter("TJSP")
    result = adapter.get_status()

    assert call_count == 3
    assert result["_metadata"]["source"] == "real_api"
    assert result["status"] == "operacional"


def test_processo_query_with_real_api(mock_tjsp_api: respx.Router) -> None:
    processo_numero = "1234567-89.2025.8.26.0100"

    mock_tjsp_api.get(f"/processos/{processo_numero}").mock(
        return_value=httpx.Response(
            200,
            json={
                "numero_processo": processo_numero,
                "situacao": "Julgado",
                "classe_processual": "Apelação",
                "assunto": "Direito do Consumidor",
                "ultima_movimentacao": "2025-09-29T15:00:00Z",
            },
        )
    )

    adapter = TribunalAPIAdapter("TJSP")
    result = adapter.get_processo(processo_numero)

    assert result["_metadata"]["source"] == "real_api"
    assert result["numero_processo"] == processo_numero
    assert result["situacao"] == "Julgado"


def test_schema_validation_rejects_invalid_response(mock_tjsp_api: respx.Router) -> None:
    mock_tjsp_api.get("/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "INVALID_STATUS",
                "ultima_atualizacao": "not-a-date",
            },
        )
    )

    adapter = TribunalAPIAdapter("TJSP")
    result = adapter.get_status()

    assert result["_metadata"]["source"] == "simulated"
    assert result["_metadata"]["fallback"] is True


def test_auth_headers_for_tjsp(mock_tjsp_api: respx.Router, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TJSP_API_TOKEN", "test-bearer-token-123")

    mock_tjsp_api.get("/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "operacional",
                "ultima_atualizacao": "2025-09-29T20:00:00Z",
                "mensagem": "OK",
                "servicos_ativos": 95,
            },
        )
    )

    adapter = TribunalAPIAdapter("TJSP")
    _ = adapter.get_status()

    assert len(mock_tjsp_api.calls) == 1
    request = mock_tjsp_api.calls[0].request
    assert request.headers.get("Authorization") == "Bearer test-bearer-token-123"


def test_auth_headers_for_tjmg(mock_tjmg_api: respx.Router, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TJMG_API_KEY", "test-api-key-456")

    mock_tjmg_api.get("/api/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "operacional",
                "ultima_atualizacao": "2025-09-29T20:00:00Z",
                "mensagem": "OK",
            },
        )
    )

    adapter = TribunalAPIAdapter("TJMG")
    _ = adapter.get_status()

    assert len(mock_tjmg_api.calls) == 1
    request = mock_tjmg_api.calls[0].request
    assert request.headers.get("X-API-Key") == "test-api-key-456"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v", "-s"])

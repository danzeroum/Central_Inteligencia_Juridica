"""Testes dos bugs de runtime corrigidos na Onda 2.

Cobre (V&V — verificação de correção + validação de comportamento):
* CRÍTICO-05: ``gerar_resposta_ollama`` não lança mais ``NameError`` e degrada
  graciosamente quando o serviço está indisponível.
* CRÍTICO-06: ``processar_tarefa`` (jurisprudência) não bloqueia mais (sem sleep).
* CRÍTICO-07: ``AdaptiveReplanner`` realmente replaneja quando um passo falha.
* CRÍTICO-08: as classes antes homônimas têm nomes distintos por módulo.
* CRÍTICO-15: ``request_response`` do A2A não usa mais ``asyncio.get_event_loop``.
* H11: ``SafeAgentBase.aexecute`` expõe execução assíncrona.
* H12: ``TribunalAPIClient`` fecha o cliente HTTP (context manager).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402


# --- CRÍTICO-05: LLM client -------------------------------------------------
class _FakeOllamaClient:
    def __init__(self, *_a, **_k):
        pass

    def chat(self, *_a, **_k):
        return {"message": {"content": "Brasília"}}


class _BrokenOllamaClient:
    def __init__(self, *_a, **_k):
        pass

    def chat(self, *_a, **_k):
        raise ConnectionError("ollama down")


def test_llm_client_no_nameerror_and_returns_content(monkeypatch):
    import src.services.llm_client as mod

    monkeypatch.setattr(mod, "_OLLAMA_CLIENT", None)
    monkeypatch.setattr(mod.ollama, "Client", _FakeOllamaClient)
    assert mod.gerar_resposta_ollama("Qual a capital do Brasil?") == "Brasília"


def test_llm_client_degrades_gracefully_when_unavailable(monkeypatch):
    import src.services.llm_client as mod

    monkeypatch.setattr(mod, "_OLLAMA_CLIENT", None)
    monkeypatch.setattr(mod.ollama, "Client", _BrokenOllamaClient)
    out = mod.gerar_resposta_ollama("oi")
    assert out.startswith("Erro")  # não propaga exceção ao chamador


# --- CRÍTICO-06: jurisprudência stub não bloqueia ---------------------------
def test_processar_tarefa_is_fast_and_structured():
    from src.agents.agente_jurisprudencia import processar_tarefa

    start = time.monotonic()
    result = processar_tarefa({"id_tarefa": "t1", "descricao": "STF tema 1234"})
    assert time.monotonic() - start < 1.0  # sem time.sleep(5) bloqueante
    assert result["id_tarefa"] == "t1"
    assert result["agente"] == "jurisprudencia"
    assert result["status"] == "concluido"


# --- CRÍTICO-07: replanejamento realmente dispara ---------------------------
@pytest.mark.asyncio
async def test_replanner_succeeds_without_failures():
    from src.planning.adaptive_replanner import AdaptiveReplanner

    out = await AdaptiveReplanner().execute_with_replanning({"steps": [{"step": 1}]})
    assert out["result"]["success"] is True
    assert out["attempts"] == 1


@pytest.mark.asyncio
async def test_replanner_recovers_after_failure():
    from src.planning.adaptive_replanner import AdaptiveReplanner

    plan = {"steps": [{"step": 1, "outcome": "fail", "reason": "boom"}, {"step": 2}]}
    out = await AdaptiveReplanner().execute_with_replanning(plan)
    # Given um passo que falha, When executa, Then replaneja e conclui (attempts>1).
    assert out["result"]["success"] is True
    assert out["attempts"] == 2


# --- CRÍTICO-08: sem colisão de nomes ---------------------------------------
def test_no_adaptive_planner_class_collision():
    from src.planning.adaptive_planner import AdaptivePlanner as Planner
    from src.planning.adaptive_replanner import AdaptiveReplanner

    assert Planner is not AdaptiveReplanner
    assert Planner.__name__ == "AdaptivePlanner"
    assert AdaptiveReplanner.__name__ == "AdaptiveReplanner"


def test_no_continuous_evaluator_class_collision():
    from src.evaluation.continuous_eval import TrajectoryEvaluator
    from src.evaluation.continuous_evaluator import ContinuousEvaluator

    assert TrajectoryEvaluator is not ContinuousEvaluator
    assert TrajectoryEvaluator.__name__ == "TrajectoryEvaluator"


# --- CRÍTICO-15: API asyncio depreciada removida ----------------------------
def test_a2a_channel_does_not_use_deprecated_get_event_loop():
    source = Path("src/protocols/a2a_channel.py").read_text(encoding="utf-8")
    assert "get_event_loop" not in source
    assert "get_running_loop" in source


@pytest.mark.asyncio
async def test_a2a_request_response_times_out_with_running_loop():
    from src.protocols.a2a_channel import get_a2a_channel

    channel = get_a2a_channel()
    # Sem resposta correspondente, retorna None após o timeout curto — provando
    # que ``get_running_loop().time()`` funciona dentro de um loop em execução.
    result = await channel.request_response(
        sender_id="agent_a",
        receiver_id="agent_b",
        message_type="ping",
        payload={},
        timeout=0.2,
    )
    assert result is None


# --- H11: execução assíncrona do SafeAgentBase ------------------------------
@pytest.mark.asyncio
async def test_safe_agent_base_aexecute():
    from src.core.safe_agent_base import SafeAgentBase

    agent = SafeAgentBase()
    result = await agent.aexecute("tarefa simples")
    assert result["completed"] is True


# --- H12: fechamento do cliente HTTP ----------------------------------------
def test_tribunal_api_client_context_manager_closes():
    from src.agents.tribunal_api_client import TribunalAPIClient

    with TribunalAPIClient("TJSP") as client:
        created = client._client
    if created is not None:  # só há cliente quando há config para o tribunal
        assert created.is_closed

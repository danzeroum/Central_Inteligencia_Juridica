"""Cobertura do SafeAgentBase e guardrails (Frente C cont.)."""

from __future__ import annotations

import pytest

from src.core.safe_agent_base import (
    AgentExecution,
    EthicalBoundaryGuard,
    InputSanitizerGuard,
    MemoryManager,
    OutputValidatorGuard,
    PlanCreation,
    ResourceLimitGuard,
    SafeAgentBase,
)


# ── Guardrails individuais ───────────────────────────────────────────────────
def test_input_sanitizer_bloqueia_script():
    guard = InputSanitizerGuard()
    assert guard.validate("texto limpo") is True
    assert guard.validate("<script>alert(1)</script>") is False
    assert guard.validate("../etc/passwd") is False


def test_output_validator_rejeita_vazio():
    assert OutputValidatorGuard().validate("ok") is True
    assert OutputValidatorGuard().validate("   ") is False


def test_ethical_boundary_bloqueia_sensivel():
    assert EthicalBoundaryGuard().validate("consulta normal") is True
    assert EthicalBoundaryGuard().validate("minha senha é 123") is False


def test_resource_limit_bloqueia_longo():
    assert ResourceLimitGuard().validate("ok") is True
    assert ResourceLimitGuard().validate("x" * 6000) is False


# ── SafeAgentBase: capacidades ───────────────────────────────────────────────
def test_add_capability_validacoes():
    agent = SafeAgentBase()
    with pytest.raises(ValueError):
        agent.add_capability("")
    agent.add_capability("busca", description="d", allowed_tools=["t1"])
    with pytest.raises(ValueError):
        agent.add_capability("busca")  # duplicada
    assert "busca" in agent.list_capabilities()
    assert agent.list_capabilities()["busca"]["allowed_tools"] == ["t1"]


def test_execute_com_capacidade():
    agent = SafeAgentBase()
    agent.add_capability("eco", handler=lambda task, ctx: {"echo": task})
    out = agent.execute("olá", capability="eco")
    assert out["echo"] == "olá"
    assert out["capability"] == "eco"
    assert out["task"] == "olá"


def test_execute_generico_sem_capacidade():
    agent = SafeAgentBase()
    out = agent.execute("tarefa", context="ctx")
    assert out["completed"] is True
    assert out["output"] == "executed::tarefa"


def test_execute_falha_guardrail():
    agent = SafeAgentBase()
    with pytest.raises(ValueError, match="guardrail"):
        agent.execute("<script>x</script>")


async def test_aexecute_assincrono():
    agent = SafeAgentBase()
    out = await agent.aexecute("async task")
    assert out["completed"] is True


# ── Ferramentas (whitelist) ──────────────────────────────────────────────────
def test_execute_tool_nao_autorizada():
    agent = SafeAgentBase()
    with pytest.raises(PermissionError):
        agent.execute_tool("ferramenta_x")


def test_execute_tool_autorizada_incrementa():
    agent = SafeAgentBase()
    agent.add_capability("cap", allowed_tools=["t1"])
    r1 = agent.execute_tool("t1")
    r2 = agent.execute_tool("t1")
    assert r1["executions"] == 1
    assert r2["executions"] == 2


# ── Proteção de loop ─────────────────────────────────────────────────────────
def test_loop_protection_dispara():
    agent = SafeAgentBase(max_repeated_tasks=2)
    agent.execute("repetida")
    agent.execute("repetida")
    with pytest.raises(RuntimeError, match="Loop protection"):
        agent.execute("repetida")


# ── Telemetria e memória ─────────────────────────────────────────────────────
def test_agent_execution_to_dict():
    exe = AgentExecution(
        task="t",
        context=None,
        completed=True,
        resource_usage=0.1,
        guardrail_violations=0,
        output="o",
    )
    d = exe.to_dict()
    assert d["task"] == "t" and d["completed"] is True


def test_memory_manager_recall_e_acesso():
    mm = MemoryManager()
    ctx = mm.recall("buscar STJ")
    assert "buscar STJ" in ctx
    creation = PlanCreation(task="buscar STJ", memory_context=ctx, memory_accessed=True)
    assert mm.was_accessed_during(creation) is True
    assert mm.was_accessed_during(PlanCreation(task="x")) is False

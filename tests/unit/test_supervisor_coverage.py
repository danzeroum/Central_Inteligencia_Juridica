"""Cobertura dos helpers determinísticos e do fluxo avançado do SupervisorAgent.

Frente C: eleva a cobertura de ``src/agents/supervisor_agent.py`` (orquestração),
focando unidades determinísticas e o ``process_task_advanced`` (CoT + consenso)
com os colaboradores pesados mockados — sem depender de LLM/ChromaDB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.supervisor_agent import SupervisorAgent
from src.utils.ledger import DecisionLedger


@pytest.fixture
def sup(tmp_path):
    """SupervisorAgent com ledger isolado (não polui logs/agent_decisions.json)."""

    return SupervisorAgent(ledger=DecisionLedger(log_file=str(tmp_path / "l.json")))


# ── _is_multi_tribunal_query ─────────────────────────────────────────────────
def test_multi_tribunal_single_is_false(sup):
    assert sup._is_multi_tribunal_query("status do processo no TJSP") is False


def test_multi_tribunal_two_codes_is_true(sup):
    assert sup._is_multi_tribunal_query("comparar TJSP e TJMG") is True


def test_multi_tribunal_jurisprudence_phrase_is_true(sup):
    assert sup._is_multi_tribunal_query("pesquisa de jurisprudência") is True


def test_multi_tribunal_region_word_is_true(sup):
    assert sup._is_multi_tribunal_query("tribunais do sudeste") is True


# ── _estimate_response_confidence ────────────────────────────────────────────
def test_confidence_success_with_real_api(sup):
    conf = sup._estimate_response_confidence(
        {"status": "success", "data": {"x": 1}, "meta": {"source": "real_api"}}
    )
    assert conf == pytest.approx(1.0)


def test_confidence_error_lowers(sup):
    base = sup._estimate_response_confidence({"status": "unknown"})
    err = sup._estimate_response_confidence({"status": "error"})
    assert err < base


def test_confidence_fallback_penalised_and_clamped(sup):
    conf = sup._estimate_response_confidence(
        {"status": "error", "metadata": {"fallback": True}}
    )
    assert 0.0 <= conf <= 1.0


# ── _aggregate_results ───────────────────────────────────────────────────────
def test_aggregate_no_results(sup):
    out = sup._aggregate_results([], ["TJSP"])
    assert out["status"] == "no_results"
    assert out["tribunals_queried"] == ["TJSP"]


def test_aggregate_single_passthrough(sup):
    single = {"status": "success", "tribunal": "TJSP"}
    assert sup._aggregate_results([single], ["TJSP"]) is single


def test_aggregate_multiple(sup):
    results = [
        {"status": "success", "tribunal": "TJSP"},
        {"status": "success", "tribunal": "TJMG"},
    ]
    out = sup._aggregate_results(results, ["TJSP", "TJMG"])
    assert out["status"] == "multiple_results"
    assert out["count"] == 2
    assert set(out["tribunals"]) == {"TJSP", "TJMG"}


# ── get_api_health_stats / get_agent_stats ───────────────────────────────────
def test_api_health_stats_empty(sup):
    assert sup.get_api_health_stats() == {}


def test_api_health_stats_with_delegate(sup):
    delegate = MagicMock()
    delegate.get_circuit_breaker_stats.return_value = {"state": "closed"}
    sup.active_delegates["TJSP"] = delegate
    assert sup.get_api_health_stats() == {"TJSP": {"state": "closed"}}


def test_agent_stats_counts_history(sup):
    sup.task_history = [
        {"parallel": True, "tribunals": ["TJSP", "TJMG"], "recalled_memories": 1},
        {"parallel": False, "tribunals": ["TJSP"], "memory_cache_hit": True},
    ]
    stats = sup.get_agent_stats()
    assert stats["total_tasks_processed"] == 2
    assert stats["parallel_tasks_count"] == 1
    assert stats["multi_tribunal_tasks"] == 1
    assert stats["tasks_with_memory_recall"] == 1
    assert stats["tasks_with_memory_cache_hit"] == 1
    assert len(stats["latest_tasks"]) == 2


# ── _get_or_create_tribunal_agent (cache de delegados) ───────────────────────
def test_get_or_create_tribunal_agent_caches(sup):
    with patch("src.agents.supervisor_agent.TribunalAgent") as mock_cls:
        mock_cls.return_value = MagicMock()
        first = sup._get_or_create_tribunal_agent("TJSP")
        second = sup._get_or_create_tribunal_agent("TJSP")
    assert first is second
    assert "TJSP" in sup.active_delegates
    mock_cls.assert_called_once()  # criado só uma vez, depois reusado


# ── process_task_advanced (CoT + consenso) ───────────────────────────────────
async def test_advanced_single_tribunal(sup):
    sup.architect = MagicMock()
    sup.architect.reason_with_cot.return_value = {"plan": "x"}
    sup._extract_tribunals_from_reasoning = MagicMock(return_value=["TJSP"])
    sup._delegate_to_tribunal_agent = AsyncMock(return_value={"status": "success"})

    out = await sup.process_task_advanced("consulta simples")

    assert out["status"] == "success"
    assert out["mode"] == "advanced_single_tribunal"
    assert out["tribunal_used"] == "TJSP"


async def test_advanced_multi_tribunal_consensus(sup):
    sup.architect = MagicMock()
    sup.architect.reason_with_cot.return_value = {"plan": "x"}
    sup._extract_tribunals_from_reasoning = MagicMock(return_value=["TJSP", "TJMG"])
    sup._delegate_to_tribunal_agent = AsyncMock(
        return_value={"meta": {"confidence": 0.9}}
    )
    sup.consensus_engine = MagicMock()
    sup.consensus_engine.reach_consensus.return_value = {
        "consensus_strength": 0.8,
        "decision_maker": "TJSP",
    }

    out = await sup.process_task_advanced("comparar TJSP e TJMG")

    assert out["status"] == "success_with_consensus"
    assert out["mode"] == "advanced_multi_tribunal"
    assert out["tribunais_envolvidos"] == ["TJSP", "TJMG"]


async def test_advanced_no_tribunals_falls_back_to_tjsp(sup):
    sup.architect = MagicMock()
    sup.architect.reason_with_cot.return_value = {}
    sup._extract_tribunals_from_reasoning = MagicMock(return_value=[])
    sup._delegate_to_tribunal_agent = AsyncMock(return_value={"status": "success"})

    out = await sup.process_task_advanced("tarefa sem tribunal claro")

    assert out["tribunal_used"] == "TJSP"

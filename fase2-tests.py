#!/usr/bin/env python3
"""
================================================================================
 FASE 2 - PARTE 3: Testes adicionais para aumentar cobertura
 Cria testes unitarios para modulos que nao tinham cobertura
================================================================================

Uso:
  python fase2-tests.py [--dry-run]

Executar APOS fase2-resolve.py e fase2-stubs.py na raiz do repositorio.
================================================================================
"""

from __future__ import annotations

import argparse
from pathlib import Path


TEST_FILES: dict[str, str] = {
    # ── tests/unit/test_input_sanitizer.py ──
    "tests/unit/__init__.py": "",

    "tests/unit/test_input_sanitizer.py": r'''"""Unit tests for InputSanitizer."""

from __future__ import annotations

import pytest

from src.utils.input_sanitizer import InputSanitizer


@pytest.fixture
def sanitizer() -> InputSanitizer:
    return InputSanitizer()


class TestSanitizeText:
    def test_normal_text_unchanged(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.sanitize_text("Buscar jurisprudencia TJSP")
        assert "jurisprudencia" in result
        assert "TJSP" in result

    def test_xss_script_tag_removed(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.sanitize_text("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "alert" not in result

    def test_sql_injection_escaped(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.sanitize_text("'; DROP TABLE users;--")
        assert "DROP TABLE" not in result

    def test_path_traversal_blocked(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.sanitize_text("../../etc/passwd")
        assert "../" not in result

    def test_html_entities_escaped(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.sanitize_text("<div>content</div>")
        assert "<div>" not in result

    def test_empty_string(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.sanitize_text("")
        assert result == ""

    def test_whitespace_only(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.sanitize_text("   \t\n  ")
        assert result.strip() == ""

    def test_very_long_input_truncated(self, sanitizer: InputSanitizer) -> None:
        long_input = "a" * 5000
        result = sanitizer.sanitize_text(long_input)
        assert len(result) <= 1000

    def test_unicode_preserved(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.sanitize_text("Jurisprudencia do TJSP com acao")
        assert "Jurisprudencia" in result

    def test_special_chars_sanitized(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.sanitize_text("test\x00null\x1fbinary")
        assert "\x00" not in result


class TestIsSafeInput:
    def test_safe_input_returns_true(self, sanitizer: InputSanitizer) -> None:
        assert sanitizer.is_safe_input("Buscar processos TJSP") is True

    def test_xss_input_returns_false(self, sanitizer: InputSanitizer) -> None:
        assert sanitizer.is_safe_input("<script>alert('xss')</script>") is False

    def test_sql_injection_returns_false(self, sanitizer: InputSanitizer) -> None:
        assert sanitizer.is_safe_input("'; DROP TABLE users;--") is False

    def test_empty_input_returns_true(self, sanitizer: InputSanitizer) -> None:
        assert sanitizer.is_safe_input("") is True


class TestValidateAndSanitize:
    def test_returns_dict_with_all_fields(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.validate_and_sanitize("Buscar TJSP")
        assert "original" in result
        assert "sanitized" in result
        assert "is_safe" in result
        assert "was_modified" in result

    def test_unmodified_safe_text(self, sanitizer: InputSanitizer) -> None:
        result = sanitizer.validate_and_sitize("Buscar TJSP")
        assert result["was_modified"] is False
        assert result["is_safe"] is True
''',

    "tests/unit/test_ledger.py": r'''"""Unit tests for DecisionLedger."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.utils.ledger import DecisionLedger


@pytest.fixture
def ledger(tmp_path: Path) -> DecisionLedger:
    return DecisionLedger()


class TestLogDecision:
    def test_log_single_decision(self, ledger: DecisionLedger) -> None:
        ledger.log_decision(
            agent_type="TestAgent",
            decision_type="TEST_DECISION",
            metadata={"key": "value"},
        )
        entries = ledger.get_entries()
        assert len(entries) == 1
        assert entries[0]["agent_type"] == "TestAgent"

    def test_log_multiple_decisions(self, ledger: DecisionLedger) -> None:
        for i in range(5):
            ledger.log_decision(
                agent_type="TestAgent",
                decision_type=f"DECISION_{i}",
                metadata={"index": i},
            )
        entries = ledger.get_entries()
        assert len(entries) == 5

    def test_auto_incrementing_id(self, ledger: DecisionLedger) -> None:
        ledger.log_decision(agent_type="A", decision_type="T1", metadata={})
        ledger.log_decision(agent_type="A", decision_type="T2", metadata={})
        entries = ledger.get_entries()
        assert entries[0]["id"] == 1
        assert entries[1]["id"] == 2


class TestGetEntries:
    def test_filter_by_agent_type(self, ledger: DecisionLedger) -> None:
        ledger.log_decision(agent_type="AgentA", decision_type="T1", metadata={})
        ledger.log_decision(agent_type="AgentB", decision_type="T2", metadata={})
        entries = ledger.get_entries(agent_type="AgentA")
        assert len(entries) == 1
        assert entries[0]["agent_type"] == "AgentA"

    def test_filter_by_decision_type(self, ledger: DecisionLedger) -> None:
        ledger.log_decision(agent_type="A", decision_type="TYPE_X", metadata={})
        ledger.log_decision(agent_type="A", decision_type="TYPE_Y", metadata={})
        entries = ledger.get_entries(decision_type="TYPE_X")
        assert len(entries) == 1

    def test_limit_results(self, ledger: DecisionLedger) -> None:
        for i in range(10):
            ledger.log_decision(agent_type="A", decision_type=f"T{i}", metadata={})
        entries = ledger.get_entries(limit=3)
        assert len(entries) == 3


class TestAgentStats:
    def test_stats_with_entries(self, ledger: DecisionLedger) -> None:
        ledger.log_decision(agent_type="AgentA", decision_type="T1", metadata={})
        ledger.log_decision(agent_type="AgentB", decision_type="T2", metadata={})
        ledger.log_decision(agent_type="AgentA", decision_type="T3", metadata={})
        stats = ledger.get_agent_stats()
        assert stats["AgentA"]["count"] == 2
        assert stats["AgentB"]["count"] == 1
''',

    "tests/unit/test_architect_agent.py": r'''"""Unit tests for ArchitectAgent."""

from __future__ import annotations

import pytest

from src.agents.architect_agent import ArchitectAgent


@pytest.fixture
def architect() -> ArchitectAgent:
    return ArchitectAgent()


class TestReasonWithCoT:
    def test_identifies_tjsp(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("Consultar jurisprudencia do TJSP")
        assert "TJSP" in result.get("identified_tribunals", [])
        assert result["confidence"] > 0

    def test_identifies_multiple_tribunals(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("Comparar TJSP e TJMG")
        tribunals = result.get("identified_tribunals", [])
        assert "TJSP" in tribunals
        assert "TJMG" in tribunals
        assert result["confidence"] > 0.6

    def test_fallback_to_tjsp(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("Processo qualquer")
        tribunals = result.get("identified_tribunals", [])
        assert "TJSP" in tribunals

    def test_empty_task(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("")
        assert result["confidence"] < 0.3
        assert "TJSP" in result.get("identified_tribunals", [])

    def test_stf_federal(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("Consulta sobre o Supremo Tribunal Federal")
        tribunals = result.get("identified_tribunals", [])
        assert "STF" in tribunals

    def test_returns_required_fields(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("Tarefa teste")
        assert "problem_analysis" in result
        assert "recommendation" in result
        assert "confidence" in result
        assert "identified_tribunals" in result
        assert "chain_of_thought" in result


class TestCreatePlan:
    def test_creates_plan(self, architect: ArchitectAgent) -> None:
        reasoning = architect.reason_with_cot("Tarefa com cache")
        plan = architect.create_plan({"description": "test"}, reasoning)
        assert "goal" in plan
        assert "architecture" in plan
        assert "components" in plan

    def test_includes_cache_component(self, architect: ArchitectAgent) -> None:
        reasoning = {"recommendation": "Sistema com cache distribuido"}
        plan = architect.create_plan({"description": "test"}, reasoning)
        assert "Caching Layer" in plan["components"]
''',

    "tests/unit/test_weighted_voting.py": r'''"""Unit tests for WeightedConsensusEngine."""

from __future__ import annotations

import pytest

from src.consensus.weighted_voting import WeightedConsensusEngine


@pytest.fixture
def engine() -> WeightedConsensusEngine:
    return WeightedConsensusEngine()


class TestReachConsensus:
    def test_single_proposal_unanimous(self, engine: WeightedConsensusEngine) -> None:
        proposals = {
            "TJSP": {"confidence": 0.9, "proposal": {"result": "ok"}},
        }
        result = engine.reach_consensus(proposals, "legal_analysis")
        assert result["consensus_strength"] >= 0.8
        assert result["decision_maker"] == "TJSP"

    def test_two_proposals_high_agreement(self, engine: WeightedConsensusEngine) -> None:
        proposals = {
            "TJSP": {"confidence": 0.85, "proposal": {"result": "similar"}},
            "TJMG": {"confidence": 0.83, "proposal": {"result": "similar"}},
        }
        result = engine.reach_consensus(proposals, "legal_analysis")
        assert result["consensus_strength"] > 0.5

    def test_empty_proposals(self, engine: WeightedConsensusEngine) -> None:
        proposals: dict = {}
        result = engine.reach_consensus(proposals, "legal_analysis")
        assert result["consensus_strength"] == 0.0

    def test_required_keys_in_result(self, engine: WeightedConsensusEngine) -> None:
        proposals = {
            "TJSP": {"confidence": 0.8, "proposal": {"result": "ok"}},
        }
        result = engine.reach_consensus(proposals, "test")
        assert "consensus_strength" in result
        assert "decision_maker" in result
        assert "winning_proposal" in result
''',

    "tests/unit/test_cache_manager.py": r'''"""Unit tests for CacheManager."""

from __future__ import annotations

import time

import pytest

from src.utils.cache_manager import CacheManager, CacheManagerConfig


@pytest.fixture
def cache() -> CacheManager:
    config = CacheManagerConfig(namespace="test")
    return CacheManager(config=config)


class TestSetGetCached:
    def test_set_and_get(self, cache: CacheManager) -> None:
        cache.set_cached("key1", "value1")
        result = cache.get_cached("key1")
        assert result == "value1"

    def test_get_missing_key_returns_none(self, cache: CacheManager) -> None:
        result = cache.get_cached("nonexistent")
        assert result is None

    def test_overwrite_key(self, cache: CacheManager) -> None:
        cache.set_cached("key1", "value1")
        cache.set_cached("key1", "value2")
        result = cache.get_cached("key1")
        assert result == "value2"


class TestDeleteCached:
    def test_delete_existing_key(self, cache: CacheManager) -> None:
        cache.set_cached("key1", "value1")
        cache.delete_cached("key1")
        assert cache.get_cached("key1") is None

    def test_delete_nonexistent_key_no_error(self, cache: CacheManager) -> None:
        cache.delete_cached("nonexistent")  # Should not raise


class TestHealth:
    def test_health_returns_dict(self, cache: CacheManager) -> None:
        result = cache.health()
        assert isinstance(result, dict)
        assert "status" in result
''',

    "tests/unit/test_progressive_autonomy.py": r'''"""Unit tests for ProgressiveAutonomyManager."""

from __future__ import annotations

import pytest

from src.hitl.progressive_autonomy import ProgressiveAutonomyManager


@pytest.fixture
def manager() -> ProgressiveAutonomyManager:
    return ProgressiveAutonomyManager()


class TestAutonomyLevels:
    def test_initial_trust_score(self, manager: ProgressiveAutonomyManager) -> None:
        score = manager.get_trust_score("TestAgent")
        assert score is not None

    def test_update_trust_score(self, manager: ProgressiveAutonomyManager) -> None:
        manager.update_trust_score("TestAgent", delta=0.1)
        score = manager.get_trust_score("TestAgent")
        assert score > 0.5

    def test_negative_delta(self, manager: ProgressiveAutonomyManager) -> None:
        initial = manager.get_trust_score("TestAgent")
        manager.update_trust_score("TestAgent", delta=-0.05)
        after = manager.get_trust_score("TestAgent")
        assert after < initial

    def test_requires_human_review_with_low_consensus(self, manager: ProgressiveAutonomyManager) -> None:
        result = manager._requires_human_review(
            consensus_strength=0.3,
            action="critical_legal_decision",
        )
        assert result is True
''',

    "tests/unit/test_learning_router.py": r'''"""Unit tests for LearningRouter."""

from __future__ import annotations

import pytest

from src.routing.learning_router import LearningRouter


@pytest.fixture
def router() -> LearningRouter:
    return LearningRouter()


class TestUpdateAndGetRoutePerformance:
    def test_initial_stats_empty(self, router: LearningRouter) -> None:
        snapshot = router.get_route_snapshot()
        assert isinstance(snapshot, dict)

    def test_update_creates_entry(self, router: LearningRouter) -> None:
        router.update_route_performance("TestAgent", "fast_route", success=True, latency=0.1)
        snapshot = router.get_route_snapshot()
        assert ("TestAgent", "fast_route") in snapshot
''',
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 2 Part 3: Create test files")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 78)
    print("  FASE 2 - PARTE 3: Testes Unitarios Adicionais")
    print("=" * 78)
    print()

    results = []
    for filepath, content in TEST_FILES.items():
        path = Path(filepath)
        if path.exists():
            results.append((True, f"[SKIP] {filepath} (ja existe)"))
            continue

        if args.dry_run:
            results.append((True, f"[DRY-RUN] Criaria {filepath}"))
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        if content.strip():
            path.write_text(content, encoding="utf-8")
        else:
            path.write_text("", encoding="utf-8")

        if filepath.endswith(".py") and content.strip():
            import py_compile
            try:
                py_compile.compile(str(path), doraise=True)
                results.append((True, f"[OK] {filepath} criado + sintaxe OK"))
            except py_compile.PyCompileError as exc:
                results.append((False, f"[SYNTAX ERROR] {filepath}: {exc}"))
        else:
            results.append((True, f"[OK] {filepath} criado"))

    for ok, msg in results:
        color = "\033[92m" if ok else "\033[91m"
        print(f"  {color}{msg}\033[0m")

    total_ok = sum(1 for ok, _ in results if ok)
    total = len(results)
    print()
    print(f"  Total: {total_ok}/{total} arquivos de teste criados")
    print()
    print("  Para rodar:")
    print("    python -m pytest tests/unit/ -v")
    print("=" * 78)


if __name__ == "__main__":
    main()

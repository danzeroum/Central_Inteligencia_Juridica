"""Unit tests for DecisionLedger."""

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

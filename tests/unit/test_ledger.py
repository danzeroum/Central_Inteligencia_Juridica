"""Unit tests for DecisionLedger - matched to resolved HEAD dataclass interface.

Key interface facts (from actual test error analysis):
- DecisionLedger is a @dataclass with file persistence (logs/agent_decisions.json)
- log_decision(agent_type, decision_type, metadata=None) returns str ID "decision_XXXXXX"
- get_entries(agent_type=None, decision_type=None, limit=None) positional args
- get_agent_stats(agent_type=None) returns {total_entries, decision_counts, ...}
- File persistence causes global shared state across tests -> MUST use temp files
"""

from __future__ import annotations

import os
import tempfile

import pytest

from src.utils.ledger import DecisionLedger


class TestLogDecision:
    """Tests for log_decision with fresh temp-file ledger per test."""

    def setup_method(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".json", prefix="ledger_test_"
        )
        self._tmp.close()
        self.ledger = DecisionLedger(log_file=self._tmp.name)

    def teardown_method(self) -> None:
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_log_single_decision(self) -> None:
        self.ledger.log_decision("TestAgent", "TEST_DECISION", {"key": "value"})
        entries = self.ledger.get_entries()
        assert len(entries) == 1
        assert entries[0]["agent_type"] == "TestAgent"
        assert entries[0]["decision_type"] == "TEST_DECISION"
        assert entries[0]["id"] == "decision_000000"

    def test_log_multiple_decisions(self) -> None:
        for i in range(5):
            self.ledger.log_decision("TestAgent", f"DECISION_{i}", {"index": i})
        entries = self.ledger.get_entries()
        assert len(entries) == 5

    def test_auto_incrementing_id(self) -> None:
        self.ledger.log_decision("A", "T", {})
        self.ledger.log_decision("A", "T", {})
        entries = self.ledger.get_entries()
        # IDs are strings "decision_XXXXXX", not integers
        assert entries[0]["id"] == "decision_000000"
        assert entries[1]["id"] == "decision_000001"

    def test_log_returns_string_id(self) -> None:
        decision_id = self.ledger.log_decision("X", "Y", {})
        assert isinstance(decision_id, str)
        assert decision_id.startswith("decision_")
        assert len(decision_id) == 15  # "decision_" + 6 digits


class TestGetEntries:
    """Tests for get_entries with temp-file isolation to avoid shared state."""

    def setup_method(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".json", prefix="ledger_test_"
        )
        self._tmp.close()
        self.ledger = DecisionLedger(log_file=self._tmp.name)

    def teardown_method(self) -> None:
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_filter_by_agent_type(self) -> None:
        self.ledger.log_decision("AgentA", "T1", {})
        self.ledger.log_decision("AgentB", "T2", {})
        entries = self.ledger.get_entries(agent_type="AgentA")
        assert len(entries) == 1
        assert entries[0]["agent_type"] == "AgentA"

    def test_filter_by_decision_type(self) -> None:
        self.ledger.log_decision("A", "TYPE_X", {})
        self.ledger.log_decision("B", "TYPE_Y", {})
        entries = self.ledger.get_entries(decision_type="TYPE_X")
        assert len(entries) == 1
        assert entries[0]["decision_type"] == "TYPE_X"

    def test_limit_results(self) -> None:
        for i in range(10):
            self.ledger.log_decision("A", f"D{i}", {})
        entries = self.ledger.get_entries(limit=3)
        assert len(entries) == 3


class TestAgentStats:
    """Tests for get_agent_stats with correct return structure.

    Actual return: {total_entries, decision_counts, first_entry, last_entry, agent_types}
    NOT: {AgentA: {count: N}}
    """

    def setup_method(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".json", prefix="ledger_test_"
        )
        self._tmp.close()
        self.ledger = DecisionLedger(log_file=self._tmp.name)

    def teardown_method(self) -> None:
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_stats_with_entries(self) -> None:
        self.ledger.log_decision("AgentA", "T1", {})
        self.ledger.log_decision("AgentA", "T2", {})
        self.ledger.log_decision("AgentB", "T1", {})
        stats = self.ledger.get_agent_stats()
        assert stats["total_entries"] == 3
        assert "decision_counts" in stats
        assert stats["decision_counts"]["T1"] == 2
        assert stats["decision_counts"]["T2"] == 1

    def test_empty_stats(self) -> None:
        stats = self.ledger.get_agent_stats()
        assert stats == {}

    def test_stats_filtered_by_agent(self) -> None:
        self.ledger.log_decision("AgentA", "T1", {})
        self.ledger.log_decision("AgentB", "T2", {})
        stats = self.ledger.get_agent_stats(agent_type="AgentA")
        assert stats["total_entries"] == 1
        assert "T1" in stats["decision_counts"]


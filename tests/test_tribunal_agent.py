"""Unit tests for TribunalAgent."""

from __future__ import annotations

import os
import tempfile
import unittest

from src.agents.tribunal_agent import TribunalAgent
from src.utils.ledger import DecisionLedger


class TestTribunalAgent(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()
        self.ledger = DecisionLedger(self.temp_file.name)

    def tearDown(self) -> None:
        os.unlink(self.temp_file.name)

    def test_tjsp_status_check(self) -> None:
        agent = TribunalAgent("TJSP", self.ledger)
        result = agent.execute_task("status")

        self.assertEqual(result["tribunal"], "TJSP")
        self.assertEqual(result["operation"], "status_check")
        self.assertEqual(result["status"], "success")
        self.assertIn("data", result)
        self.assertIn("status", result["data"])

    def test_tjmg_process_query(self) -> None:
        agent = TribunalAgent("TJMG", self.ledger)
        result = agent.execute_task("consulta processo 123456")

        self.assertEqual(result["tribunal"], "TJMG")
        self.assertEqual(result["operation"], "process_query")
        self.assertIn("numero_processo", result["data"])
        self.assertIn("situacao", result["data"])

    def test_stf_capabilities(self) -> None:
        agent = TribunalAgent("STF", self.ledger)
        result = agent.execute_task("generic task")

        self.assertEqual(result["tribunal"], "STF")
        self.assertIn("capacidades", result["data"])
        self.assertIn("constitutional_review", result["data"]["capacidades"])

    def test_process_number_extraction(self) -> None:
        agent = TribunalAgent("TJSP", self.ledger)
        result = agent.execute_task("consultar processo 1234567-89.2024.8.26.1234")
        self.assertEqual(result["operation"], "process_query")
        self.assertIn("1234567-89.2024.8.26.1234", result["data"]["numero_processo"])

    def test_error_handling_on_empty_input(self) -> None:
        agent = TribunalAgent("TJSP", self.ledger)
        result = agent.execute_task("")
        self.assertEqual(result["status"], "success")

    def test_task_count_increment(self) -> None:
        agent = TribunalAgent("TJSP", self.ledger)
        initial_count = agent.task_count
        agent.execute_task("test task")
        self.assertEqual(agent.task_count, initial_count + 1)


if __name__ == "__main__":
    unittest.main()

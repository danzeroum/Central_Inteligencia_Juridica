"""Unit tests for SupervisorAgent."""

from __future__ import annotations

import os
import tempfile
import unittest

from src.agents.supervisor_agent import SupervisorAgent
from src.utils.ledger import DecisionLedger


class TestSupervisorAgent(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()
        self.ledger = DecisionLedger(self.temp_file.name)
        self.supervisor = SupervisorAgent(self.ledger)

    def tearDown(self) -> None:
        os.unlink(self.temp_file.name)

    def test_process_task_valid_tjsp(self) -> None:
        task = "Verificar status do tribunal TJSP"
        result = self.supervisor.process_task(task)

        self.assertEqual(result["status"], "success")
        self.assertIn("supervisor_result", result)
        self.assertEqual(result["tribunal_used"], "TJSP")
        self.assertIn("task_id", result)

    def test_process_task_tribunal_identification(self) -> None:
        test_cases = [
            ("status TJMG", "TJMG"),
            ("consultar processo no Rio Grande do Sul", "TJRS"),
            ("sistema de são paulo", "TJSP"),
            ("tribunal de minas", "TJMG"),
            ("tribunal desconhecido", "TJSP"),
        ]

        for task, expected_tribunal in test_cases:
            result = self.supervisor.process_task(task)
            self.assertEqual(result["tribunal_used"], expected_tribunal, f"Failed for task: {task}")

    def test_process_task_malicious_input(self) -> None:
        malicious_tasks = [
            "<script>alert('xss')</script>Verificar status",
            "SELECT * FROM users; DROP TABLE users",
            "../../etc/passwd",
        ]

        for task in malicious_tasks:
            result = self.supervisor.process_task(task)
            self.assertEqual(result["status"], "success")

    def test_agent_stats(self) -> None:
        self.supervisor.process_task("status TJSP")
        self.supervisor.process_task("status TJMG")

        stats = self.supervisor.get_agent_stats()

        self.assertIn("total_delegates", stats)
        self.assertIn("active_tribunals", stats)
        self.assertIn("total_tasks_processed", stats)
        self.assertEqual(stats["total_tasks_processed"], 2)
        self.assertGreaterEqual(stats["total_delegates"], 2)

    def test_ledger_integration(self) -> None:
        self.supervisor.process_task("Test ledger integration")

        entries = self.ledger.get_entries(agent_type="SupervisorAgent")
        self.assertGreater(len(entries), 0)

        decision_types = [entry["decision_type"] for entry in entries]
        self.assertIn("TASK_RECEIVED", decision_types)
        self.assertIn("TASK_COMPLETED", decision_types)


if __name__ == "__main__":
    unittest.main()

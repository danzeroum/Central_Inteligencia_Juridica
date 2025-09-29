from __future__ import annotations

import random
import time
from typing import Any, Dict

from src.utils.ledger import DecisionLedger


class TribunalAgent:
    """Blocking worker that simulates tribunal queries."""

    def __init__(self, tribunal_code: str, ledger: DecisionLedger) -> None:
        self.tribunal_code = tribunal_code
        self.ledger = ledger

    def execute_task(self, task: str) -> Dict[str, Any]:
        """Simulate a blocking lookup for a tribunal."""
        start = time.perf_counter()
        # Simulate IO latency between 0.25s and 0.35s for repeatability.
        time.sleep(0.3 + random.uniform(-0.05, 0.05))
        elapsed = time.perf_counter() - start

        result = {
            "tribunal": self.tribunal_code,
            "task": task,
            "status": "completed",
            "latency": elapsed,
        }

        self.ledger.log_decision(
            agent_type=f"TribunalAgent[{self.tribunal_code}]",
            decision_type="TASK_EXECUTED",
            metadata={"latency": elapsed, "task": task},
        )
        return result

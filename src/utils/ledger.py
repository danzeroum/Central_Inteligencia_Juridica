from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class DecisionRecord:
    agent_type: str
    decision_type: str
    metadata: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DecisionLedger:
    """Simple in-memory ledger used for observability during tests."""

    def __init__(self) -> None:
        self._records: List[DecisionRecord] = []

    def log_decision(
        self, *, agent_type: str, decision_type: str, metadata: Dict[str, Any]
    ) -> None:
        record = DecisionRecord(
            agent_type=agent_type, decision_type=decision_type, metadata=metadata
        )
        self._records.append(record)

    def list_records(self) -> List[DecisionRecord]:
        return list(self._records)

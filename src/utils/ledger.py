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

    def get_entries(
        self,
        *,
        agent_type: str | None = None,
        decision_type: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Retorna registros como dicionários filtrados por tipo de agente/decisão."""

        filtered = []
        for record in self._records:
            if agent_type and record.agent_type != agent_type:
                continue
            if decision_type and record.decision_type != decision_type:
                continue
            filtered.append(
                {
                    "agent_type": record.agent_type,
                    "decision_type": record.decision_type,
                    "metadata": record.metadata,
                    "timestamp": record.timestamp,
                }
            )
        return filtered

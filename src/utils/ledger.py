<<<<<<< HEAD
"""Decision Ledger for tracking agent decisions and actions."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DecisionLedger:
    """Persist agent decisions for observability and auditing."""

    log_file: Optional[str] = None
    entries: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.log_file = self.log_file or "logs/agent_decisions.json"
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
        self._load_existing_entries()

    def log_decision(
        self,
        agent_type: str,
        decision_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        entry = {
            "id": f"decision_{len(self.entries):06d}",
            "agent_type": agent_type,
            "decision_type": decision_type,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "timestamp_readable": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        self.entries.append(entry)
        self.logger.info("📒 LEDGER: %s - %s", agent_type, decision_type)
        self._save_entry(entry)
        return entry["id"]

    def get_entries(
        self,
        agent_type: Optional[str] = None,
        decision_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        filtered = self.entries

        if agent_type:
            filtered = [entry for entry in filtered if entry["agent_type"] == agent_type]
        if decision_type:
            filtered = [entry for entry in filtered if entry["decision_type"] == decision_type]
        if limit is not None:
            filtered = filtered[-limit:]

        return filtered

    def get_agent_stats(self, agent_type: Optional[str] = None) -> Dict[str, Any]:
        entries = self.get_entries(agent_type=agent_type)
        if not entries:
            return {}

        decision_counts: Dict[str, int] = {}
        for entry in entries:
            decision = entry["decision_type"]
            decision_counts[decision] = decision_counts.get(decision, 0) + 1

        return {
            "total_entries": len(entries),
            "decision_counts": decision_counts,
            "first_entry": entries[0]["timestamp"],
            "last_entry": entries[-1]["timestamp"],
            "agent_types": sorted({entry["agent_type"] for entry in entries}),
        }

    def export_report(self, output_file: Optional[str] = None) -> Optional[str]:
        output_path = output_file or f"logs/ledger_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_entries": len(self.entries),
            "agents_summary": {},
            "recent_entries": self.entries[-100:] if self.entries else [],
        }

        for entry in self.entries:
            agent = entry["agent_type"]
            if agent not in report["agents_summary"]:
                report["agents_summary"][agent] = {
                    "entry_count": 0,
                    "decision_types": set(),
                }
            report["agents_summary"][agent]["entry_count"] += 1
            report["agents_summary"][agent]["decision_types"].add(entry["decision_type"])

        for summary in report["agents_summary"].values():
            summary["decision_types"] = sorted(summary["decision_types"])

        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2, ensure_ascii=False)
            return output_path
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.error("Error exporting report: %s", exc)
            return None

    def _save_entry(self, entry: Dict[str, Any]) -> None:
        try:
            with open(self.log_file, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.error("Error saving ledger entry: %s", exc)

    def _load_existing_entries(self) -> None:
        try:
            if Path(self.log_file).exists():
                with open(self.log_file, "r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        self.entries.append(json.loads(line))
                self.logger.info("Loaded %s existing ledger entries", len(self.entries))
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.error("Error loading ledger entries: %s", exc)


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    ledger = DecisionLedger()
    ledger.log_decision("TestAgent", "TEST_DECISION", {"test": True})
    print(ledger.get_agent_stats())
    print(ledger.export_report())
=======
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class DecisionRecord:
    agent_type: str
    decision_type: str
    metadata: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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
>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica

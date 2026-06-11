"""Decision Ledger for tracking agent decisions and actions.

CLOUD-READINESS: a persistência fica atrás de uma interface (``LedgerStore``).
O backend padrão (``file``) grava um JSONL local — perfeito para Docker
single-node. Definindo ``LEDGER_BACKEND=redis``, a trilha passa a viver no Redis,
compartilhada entre todas as réplicas (a réplica que grava uma decisão HITL e a
que serve a auditoria veem as mesmas entradas). Definindo ``LEDGER_BACKEND=postgres``
(Onda 2), as entradas são gravadas na tabela ``ledger_entry`` do PostgreSQL —
durável, indexável e acessível via SQL. Os chamadores não mudam.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class LedgerStore(Protocol):
    """Backend de persistência da trilha de decisões."""

    def append(self, entry: Dict[str, Any]) -> None: ...

    def load_all(self) -> List[Dict[str, Any]]: ...

    def replace_all(self, entries: List[Dict[str, Any]]) -> None: ...

    @property
    def shared(self) -> bool:
        """``True`` se o backend é compartilhado entre réplicas (ex.: Redis)."""
        ...


class FileLedgerStore:
    """Append-only JSONL local (comportamento histórico, single-node)."""

    shared = False

    def __init__(self, log_file: str) -> None:
        self.log_file = log_file
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: Dict[str, Any]) -> None:
        try:
            with open(self.log_file, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error saving ledger entry: %s", exc)

    def load_all(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        try:
            if Path(self.log_file).exists():
                with open(self.log_file, "r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if line:
                            entries.append(json.loads(line))
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error loading ledger entries: %s", exc)
        return entries

    def replace_all(self, entries: List[Dict[str, Any]]) -> None:
        try:
            with open(self.log_file, "w", encoding="utf-8") as handle:
                for entry in entries:
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error rewriting ledger: %s", exc)


class RedisLedgerStore:
    """Trilha compartilhada em uma lista Redis (multi-réplica)."""

    shared = True

    def __init__(self, client, key: str = "ledger:decisions") -> None:
        self._client = client
        self._key = key

    def append(self, entry: Dict[str, Any]) -> None:
        try:
            self._client.rpush(self._key, json.dumps(entry, ensure_ascii=False))
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error pushing ledger entry to Redis: %s", exc)

    def load_all(self) -> List[Dict[str, Any]]:
        try:
            raw = self._client.lrange(self._key, 0, -1)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error loading ledger from Redis: %s", exc)
            return []
        entries: List[Dict[str, Any]] = []
        for item in raw:
            if isinstance(item, bytes):
                item = item.decode("utf-8")
            entries.append(json.loads(item))
        return entries

    def replace_all(self, entries: List[Dict[str, Any]]) -> None:
        try:
            pipe = self._client.pipeline()
            pipe.delete(self._key)
            if entries:
                pipe.rpush(
                    self._key,
                    *[json.dumps(e, ensure_ascii=False) for e in entries],
                )
            pipe.execute()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error rewriting ledger in Redis: %s", exc)


class PostgresLedgerStore:
    """Trilha persistida em PostgreSQL via psycopg2 síncrono (Onda 2).

    Requer ``DATABASE_URL`` configurada e a migração 0001 aplicada.
    Compartilhada entre todas as réplicas (shared=True).
    """

    shared = True

    def __init__(self) -> None:
        from src.db.engine import get_sync_engine
        from src.db.models import LedgerEntry

        self._engine = get_sync_engine()
        self._model = LedgerEntry

    def _row_to_dict(self, row: Any) -> Dict[str, Any]:
        return {
            "id": row.id,
            "agent_type": row.agent_type,
            "decision_type": row.decision_type,
            "metadata": row.metadata_ or {},
            "timestamp": row.timestamp.isoformat() if row.timestamp else "",
            "timestamp_readable": row.timestamp_readable or "",
        }

    def _parse_timestamp(self, ts_str: str) -> Any:
        from datetime import datetime, timezone

        if not ts_str:
            return datetime.now(timezone.utc)
        try:
            dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return datetime.now(timezone.utc)

    def append(self, entry: Dict[str, Any]) -> None:
        from sqlalchemy.orm import Session

        try:
            with Session(self._engine) as session:
                row = self._model(
                    id=entry["id"],
                    agent_type=entry["agent_type"],
                    decision_type=entry["decision_type"],
                    metadata_=entry.get("metadata"),
                    timestamp=self._parse_timestamp(entry.get("timestamp", "")),
                    timestamp_readable=entry.get("timestamp_readable"),
                )
                session.add(row)
                session.commit()
        except Exception as exc:
            logger.error("Error inserting ledger entry to Postgres: %s", exc)

    def load_all(self) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        try:
            with Session(self._engine) as session:
                rows = (
                    session.execute(select(self._model).order_by(self._model.timestamp))
                    .scalars()
                    .all()
                )
                return [self._row_to_dict(r) for r in rows]
        except Exception as exc:
            logger.error("Error loading ledger from Postgres: %s", exc)
            return []

    def replace_all(self, entries: List[Dict[str, Any]]) -> None:
        from sqlalchemy import delete
        from sqlalchemy.orm import Session

        try:
            with Session(self._engine) as session:
                session.execute(delete(self._model))
                for entry in entries:
                    session.add(
                        self._model(
                            id=entry["id"],
                            agent_type=entry["agent_type"],
                            decision_type=entry["decision_type"],
                            metadata_=entry.get("metadata"),
                            timestamp=self._parse_timestamp(entry.get("timestamp", "")),
                            timestamp_readable=entry.get("timestamp_readable"),
                        )
                    )
                session.commit()
        except Exception as exc:
            logger.error("Error replacing ledger in Postgres: %s", exc)


def _build_store(log_file: str) -> LedgerStore:
    backend = os.getenv("LEDGER_BACKEND", "file").strip().lower()
    if backend == "redis":
        from src.utils.redis_client import get_shared_redis_client

        client = get_shared_redis_client()
        if client is not None:
            return RedisLedgerStore(client)
        logger.warning(
            "LEDGER_BACKEND=redis mas nenhum cliente Redis disponível; "
            "usando arquivo local (não compartilhado entre réplicas)."
        )
    if backend == "postgres":
        try:
            from src.db.engine import get_sync_engine

            if get_sync_engine() is not None:
                return PostgresLedgerStore()
            logger.warning(
                "LEDGER_BACKEND=postgres mas DATABASE_URL não configurada; "
                "usando arquivo local."
            )
        except Exception as exc:
            logger.warning(
                "LEDGER_BACKEND=postgres falhou (%s); usando arquivo local.", exc
            )
    return FileLedgerStore(log_file)


@dataclass
class DecisionLedger:
    """Persist agent decisions for observability and auditing."""

    log_file: Optional[str] = None
    entries: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.log_file = self.log_file or "logs/agent_decisions.json"
        self._store: LedgerStore = _build_store(self.log_file)
        self.entries = self._store.load_all()
        if self.entries:
            self.logger.info("Loaded %s existing ledger entries", len(self.entries))

    def _refresh_if_shared(self) -> None:
        """Recarrega do backend compartilhado para refletir outras réplicas."""

        if getattr(self._store, "shared", False):
            self.entries = self._store.load_all()

    def log_decision(
        self,
        agent_type: str,
        decision_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        self._refresh_if_shared()
        now = datetime.now()
        entry: Dict[str, Any] = {
            "id": f"decision_{len(self.entries):06d}",
            "agent_type": agent_type,
            "decision_type": decision_type,
            "metadata": metadata or {},
            "timestamp": now.isoformat(),
            "timestamp_readable": now.strftime("%Y-%m-%d %H:%M:%S"),
        }

        self.entries.append(entry)
        self.logger.info("📒 LEDGER: %s - %s", agent_type, decision_type)
        self._store.append(entry)
        return entry["id"]

    def get_entries(
        self,
        agent_type: Optional[str] = None,
        decision_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        self._refresh_if_shared()
        filtered = self.entries

        if agent_type:
            filtered = [
                entry for entry in filtered if entry["agent_type"] == agent_type
            ]
        if decision_type:
            filtered = [
                entry for entry in filtered if entry["decision_type"] == decision_type
            ]
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

    def anonymize_entries(self, *, field_name: str, value: Any) -> int:
        """Anonimiza entradas cujo ``metadata[field_name] == value`` (seam LGPD).

        Mantém a trilha append-only (a entrada permanece, com o PII removido),
        atendendo ao direito de exclusão sem quebrar a auditoria. Retorna o
        número de entradas afetadas.
        """

        self._refresh_if_shared()
        affected = 0
        for entry in self.entries:
            metadata = entry.get("metadata") or {}
            if metadata.get(field_name) == value:
                metadata[field_name] = "[ANONYMIZED]"
                entry["metadata"] = metadata
                affected += 1
        if affected:
            self._store.replace_all(self.entries)
        return affected

    def export_report(self, output_file: Optional[str] = None) -> Optional[str]:
        output_path = (
            output_file
            or f"logs/ledger_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        report: Dict[str, Any] = {
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
            report["agents_summary"][agent]["decision_types"].add(
                entry["decision_type"]
            )

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


# Instância global compartilhada — garante que os endpoints que gravam decisões
# (HITL) e os que as leem (trilha de auditoria) enxerguem as mesmas entradas
# dentro do mesmo processo. Com ``LEDGER_BACKEND=redis``, a consistência se
# estende a todas as réplicas (mesmo padrão de get_hitl_queue).
_ledger: Optional[DecisionLedger] = None


def get_ledger() -> DecisionLedger:
    """Retorna a instância global do Decision Ledger."""

    global _ledger
    if _ledger is None:
        _ledger = DecisionLedger()
    return _ledger


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    ledger = DecisionLedger()
    ledger.log_decision("TestAgent", "TEST_DECISION", {"test": True})
    print(ledger.get_agent_stats())
    print(ledger.export_report())

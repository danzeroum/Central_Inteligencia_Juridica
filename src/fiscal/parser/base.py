"""Base classes for SPED file parsers (Strategy pattern foundation).

Each concrete parser subclass registers RecordHandler callables for
specific tipo_registro values it understands. Unknown record types are
kept with a ``_raw`` campo holding the list of unparsed strings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Handler: receives raw campo list (after tipo_registro), returns parsed dict
RecordHandler = Callable[[List[str]], Dict[str, Any]]


@dataclass
class SpedRecord:
    """A single parsed SPED record line."""

    bloco: str
    tipo_registro: str
    campos: Dict[str, Any]
    numero_linha: int
    raw: str = field(default="", repr=False)


@dataclass
class ParseResult:
    """Aggregated outcome of a SPED file parse operation."""

    records: List[SpedRecord] = field(default_factory=list)
    total_linhas: int = 0
    total_registros: int = 0
    registros_por_bloco: Dict[str, int] = field(default_factory=dict)
    registros_por_tipo: Dict[str, int] = field(default_factory=dict)
    erros: List[str] = field(default_factory=list)


class SpedParser:
    """Base SPED parser using the Strategy pattern.

    Subclasses call ``register_handler`` for each tipo_registro they
    support. The ``parse`` method dispatches each line to the registered
    handler; unknown types fall through with raw campo lists.
    """

    _DEFAULT_ENCODING = "latin-1"

    def __init__(self) -> None:
        self._handlers: Dict[str, RecordHandler] = {}

    def register_handler(self, tipo_registro: str, handler: RecordHandler) -> None:
        """Register a handler callable for a specific record type."""
        self._handlers[tipo_registro] = handler

    @staticmethod
    def _bloco_from_tipo(tipo_registro: str) -> str:
        return tipo_registro[0] if tipo_registro else "?"

    def _parse_line(self, line: str, numero_linha: int) -> Optional[SpedRecord]:
        line = line.rstrip("\r\n")
        if not line or not line.startswith("|"):
            return None

        partes = line.split("|")
        # Minimum valid SPED line: |TIPO|campo1|...|
        if len(partes) < 3:
            return None

        tipo_registro = partes[1].strip()
        if not tipo_registro:
            return None

        bloco = self._bloco_from_tipo(tipo_registro)
        # partes[0] is empty (before first |), partes[-1] is empty (after last |)
        campos_raw = partes[2:-1]

        handler = self._handlers.get(tipo_registro)
        if handler is not None:
            try:
                campos: Dict[str, Any] = handler(campos_raw)
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "Erro ao parsear registro %s na linha %d: %s",
                    tipo_registro,
                    numero_linha,
                    exc,
                )
                campos = {"_raw": campos_raw}
        else:
            campos = {"_raw": campos_raw}

        return SpedRecord(
            bloco=bloco,
            tipo_registro=tipo_registro,
            campos=campos,
            numero_linha=numero_linha,
            raw=line,
        )

    def parse(
        self,
        data: bytes,
        encoding: Optional[str] = None,
    ) -> ParseResult:
        """Parse raw SPED bytes and return a ParseResult with all records."""
        enc = encoding or self._DEFAULT_ENCODING
        result = ParseResult()

        try:
            text = data.decode(enc, errors="replace")
        except Exception as exc:
            result.erros.append(f"Erro de decodificação: {exc}")
            return result

        for numero_linha, line in enumerate(text.splitlines(), start=1):
            result.total_linhas += 1
            record = self._parse_line(line, numero_linha)
            if record is None:
                continue
            result.total_registros += 1
            result.registros_por_bloco[record.bloco] = (
                result.registros_por_bloco.get(record.bloco, 0) + 1
            )
            result.registros_por_tipo[record.tipo_registro] = (
                result.registros_por_tipo.get(record.tipo_registro, 0) + 1
            )
            result.records.append(record)

        return result

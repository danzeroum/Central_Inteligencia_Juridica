"""Centralised logging configuration with optional JSON output.

CLOUD-READINESS: agregadores de log gerenciados (CloudWatch, Loki, Datadog,
GCP Logging) consomem logs estruturados em JSON com um campo de correlação por
requisição. Este módulo emite JSON quando ``LOG_FORMAT=json`` (padrão em
produção) e texto legível em desenvolvimento, injetando automaticamente o
``correlation_id`` da requisição corrente em cada registro.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from src.utils.request_context import get_correlation_id

SERVICE_NAME = os.getenv("SERVICE_NAME", "central-inteligencia-juridica")


class CorrelationIdFilter(logging.Filter):
    """Anexa ``correlation_id`` e ``service`` a todos os registros de log."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.correlation_id = get_correlation_id() or "-"
        record.service = SERVICE_NAME
        return True


def _build_json_formatter() -> logging.Formatter:
    """Cria um formatter JSON, com fallback gracioso se a lib estiver ausente."""

    try:
        from pythonjsonlogger import jsonlogger
    except Exception:  # pragma: no cover - dependência opcional ausente
        # Fallback: texto que ainda inclui os campos estruturados-chave.
        return logging.Formatter(
            "%(asctime)s %(levelname)s %(service)s "
            "[%(correlation_id)s] %(name)s: %(message)s"
        )

    return jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(service)s %(correlation_id)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def configure_logging(
    level: Optional[str] = None, log_format: Optional[str] = None
) -> None:
    """Configura o root logger. Idempotente.

    ``log_format``: ``json`` ou ``text``. Padrão: ``LOG_FORMAT`` no ambiente,
    caindo para ``json`` em produção e ``text`` caso contrário.
    """

    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    resolved_format = (
        (
            log_format
            or os.getenv("LOG_FORMAT")
            or ("json" if environment == "production" else "text")
        )
        .strip()
        .lower()
    )
    resolved_level = (level or os.getenv("LOG_LEVEL") or "INFO").strip().upper()

    if resolved_format == "json":
        formatter = _build_json_formatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(service)s "
            "[%(correlation_id)s] %(name)s: %(message)s"
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())

    root = logging.getLogger()
    root.setLevel(resolved_level)
    # Substitui handlers existentes para tornar a configuração idempotente.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)


__all__ = ["configure_logging", "CorrelationIdFilter", "SERVICE_NAME"]

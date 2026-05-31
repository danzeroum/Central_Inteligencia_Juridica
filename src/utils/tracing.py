"""OpenTelemetry tracing setup (no-op by default).

CLOUD-READINESS: a instrumentação é distribuída-pronta mas inerte por padrão.
Ela só ativa um exporter OTLP quando ``OTEL_EXPORTER_OTLP_ENDPOINT`` está
definido (ex.: um Jaeger/Tempo local via Docker, ou um backend gerenciado como
AWS X-Ray / Grafana Tempo / Datadog na nuvem). Sem endpoint, ``configure_tracing``
não faz nada — mantendo a imagem Docker base leve e os testes determinísticos.

Trocar de backend na nuvem é apenas mudar a env ``OTEL_EXPORTER_OTLP_ENDPOINT``;
o código instrumentado (FastAPI/Redis/HTTPX) não muda.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_configured = False


def tracing_enabled() -> bool:
    """Tracing ativa apenas com um endpoint OTLP explicitamente configurado."""

    return bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))


def configure_tracing(app: Any | None = None) -> bool:
    """Configura o tracing OTLP e instrumenta FastAPI/Redis/HTTPX.

    Retorna ``True`` se o tracing foi ativado; ``False`` se desativado (sem
    endpoint) ou se as dependências OpenTelemetry não estiverem instaladas.
    Falhas são absorvidas (best-effort) para nunca derrubar a aplicação.
    """

    global _configured
    if _configured or not tracing_enabled():
        return False

    try:  # pragma: no cover - exercido apenas quando OTel está instalado
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        service_name = os.getenv("SERVICE_NAME", "central-inteligencia-juridica")
        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)

        if app is not None:
            try:
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

                FastAPIInstrumentor.instrument_app(app)
            except Exception as exc:  # noqa: BLE001
                logger.warning("FastAPI instrumentation indisponível: %s", exc)

        for module_path, attr in (
            ("opentelemetry.instrumentation.redis", "RedisInstrumentor"),
            ("opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor"),
        ):
            try:
                module = __import__(module_path, fromlist=[attr])
                getattr(module, attr)().instrument()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Instrumentação %s indisponível: %s", attr, exc)

        _configured = True
        logger.info(
            "OpenTelemetry tracing ativado (endpoint=%s)",
            os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        )
        return True
    except Exception as exc:  # pragma: no cover - OTel ausente/erro de setup
        logger.warning(
            "OTEL_EXPORTER_OTLP_ENDPOINT definido mas tracing não pôde ser "
            "configurado (%s). Instale opentelemetry-* para habilitar.",
            exc,
        )
        return False


__all__ = ["configure_tracing", "tracing_enabled"]

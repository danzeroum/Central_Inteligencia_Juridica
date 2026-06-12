"""Integração e-CAC para transmissão PER/DCOMP (S-F.3).

Padrões: Adapter (EcacTransmissaoAdapter) + Observer (TransmissaoObserver)
         + CircuitBreaker (reuso de src/tools/circuit_breaker.py)
"""

from src.integrations.ecac.adapter import (
    EcacTransmissaoAdapter,
    get_ecac_adapter,
    reset_ecac_adapter,
)
from src.integrations.ecac.models import (
    EventoTransmissao,
    ResultadoTransmissao,
    SituacaoTransmissao,
    SolicitacaoTransmissao,
    TipoEvento,
)
from src.integrations.ecac.observer import (
    AuditObserver,
    CompositeObserver,
    LogObserver,
    TransmissaoObserver,
)

__all__ = [
    "EcacTransmissaoAdapter",
    "get_ecac_adapter",
    "reset_ecac_adapter",
    "SolicitacaoTransmissao",
    "ResultadoTransmissao",
    "SituacaoTransmissao",
    "EventoTransmissao",
    "TipoEvento",
    "TransmissaoObserver",
    "LogObserver",
    "AuditObserver",
    "CompositeObserver",
]

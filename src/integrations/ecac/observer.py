"""Observer de transmissão e-CAC (S-F.3).

Implementa o padrão Observer para rastrear eventos do ciclo de vida das
transmissões PER/DCOMP ao e-CAC. Observadores são notificados em cada mudança
de situação (enviada, aceita, rejeitada, erro).

Observadores disponíveis:
  - LogObserver        — registra em logger
  - AuditObserver      — grava no ledger de auditoria fiscal (FiscalAudit ORM)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from src.integrations.ecac.models import EventoTransmissao, TipoEvento

logger = logging.getLogger(__name__)


class TransmissaoObserver(ABC):
    """Interface do Observer para eventos de transmissão."""

    @abstractmethod
    def on_evento(self, evento: EventoTransmissao) -> None: ...


class LogObserver(TransmissaoObserver):
    """Registra eventos de transmissão no logger da aplicação."""

    def on_evento(self, evento: EventoTransmissao) -> None:
        level = logging.ERROR if evento.tipo == TipoEvento.ERRO else logging.INFO
        logger.log(
            level,
            "transmissao_ecac: tipo=%s tx=%s ficha=%s situacao=%s protocolo=%s msg=%s",
            evento.tipo.value,
            evento.transmissao_id,
            evento.ficha_id,
            evento.situacao.value,
            evento.protocolo,
            evento.mensagem,
        )


class AuditObserver(TransmissaoObserver):
    """Grava eventos de transmissão na trilha de auditoria fiscal (FiscalAudit).

    Usa write-through assíncrono: falhas de gravação não interrompem a transmissão.
    """

    def on_evento(self, evento: EventoTransmissao) -> None:
        try:
            self._gravar_auditoria(evento)
        except Exception as exc:
            logger.warning(
                "AuditObserver: falha ao gravar auditoria tx=%s: %s",
                evento.transmissao_id,
                exc,
            )

    def _gravar_auditoria(self, evento: EventoTransmissao) -> None:
        from src.db.models import FiscalAudit
        from src.db.session import get_sync_session

        with get_sync_session() as session:
            audit = FiscalAudit(
                operation="transmit",
                entity_type="per_dcomp",
                entity_ref=evento.transmissao_id,
                status=evento.situacao.value,
                details={
                    "tipo": evento.tipo.value,
                    "ficha_id": evento.ficha_id,
                    "protocolo": evento.protocolo,
                    "mensagem": evento.mensagem,
                    "metadados": evento.metadados,
                },
            )
            session.add(audit)
            session.commit()


class CompositeObserver(TransmissaoObserver):
    """Delega a todos os observadores registrados (Composite)."""

    def __init__(self, observers: List[TransmissaoObserver] | None = None) -> None:
        self._observers: List[TransmissaoObserver] = list(observers or [])

    def add(self, observer: TransmissaoObserver) -> None:
        self._observers.append(observer)

    def remove(self, observer: TransmissaoObserver) -> None:
        self._observers = [o for o in self._observers if o is not observer]

    def on_evento(self, evento: EventoTransmissao) -> None:
        for obs in self._observers:
            try:
                obs.on_evento(evento)
            except Exception as exc:
                logger.warning(
                    "observer %s falhou para tx=%s: %s",
                    type(obs).__name__,
                    evento.transmissao_id,
                    exc,
                )


def _default_observer() -> CompositeObserver:
    """Cria o observer padrão (log + audit se DB disponível)."""
    obs = CompositeObserver()
    obs.add(LogObserver())
    try:
        import os

        if os.environ.get("DATABASE_URL"):
            obs.add(AuditObserver())
    except Exception:
        pass
    return obs

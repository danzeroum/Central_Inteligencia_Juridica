"""Modelos de dados para transmissão e-CAC PER/DCOMP (S-F.3).

Representa o ciclo de vida de uma transmissão:
  PENDENTE → ENVIADA → PROCESSANDO → ACEITA | REJEITADA | ERRO
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SituacaoTransmissao(str, Enum):
    """Situação de uma transmissão no e-CAC."""

    PENDENTE = "pendente"
    ENVIADA = "enviada"
    PROCESSANDO = "processando"
    ACEITA = "aceita"
    REJEITADA = "rejeitada"
    ERRO = "erro"


class TipoEvento(str, Enum):
    """Tipo de evento de transmissão (Observer)."""

    ENVIADA = "transmissao_enviada"
    ACEITA = "transmissao_aceita"
    REJEITADA = "transmissao_rejeitada"
    ERRO = "transmissao_erro"
    STATUS_ATUALIZADO = "status_atualizado"
    CIRCUIT_ABERTO = "circuit_aberto"


@dataclass
class SolicitacaoTransmissao:
    """Dados de entrada para transmissão ao e-CAC."""

    ficha_id: str
    tipo_ficha: str
    cnpj_masked: str
    xml_content: str
    correlation_id: Optional[str] = None

    @property
    def transmissao_id(self) -> str:
        """ID idempotente baseado no conteúdo da ficha."""
        digest = hashlib.sha256(
            f"{self.ficha_id}:{self.xml_content}".encode()
        ).hexdigest()[:24]
        return f"tx_{digest}"


@dataclass
class ResultadoTransmissao:
    """Resultado de uma operação de transmissão."""

    transmissao_id: str
    ficha_id: str
    situacao: SituacaoTransmissao
    protocolo: Optional[str] = None
    mensagem: Optional[str] = None
    is_stub: bool = False
    enviado_em: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    atualizado_em: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    detalhes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transmissao_id": self.transmissao_id,
            "ficha_id": self.ficha_id,
            "situacao": self.situacao.value,
            "protocolo": self.protocolo,
            "mensagem": self.mensagem,
            "is_stub": self.is_stub,
            "enviado_em": self.enviado_em,
            "atualizado_em": self.atualizado_em,
            "detalhes": self.detalhes,
        }


@dataclass
class EventoTransmissao:
    """Evento emitido pelo Observer durante o ciclo de vida da transmissão."""

    tipo: TipoEvento
    transmissao_id: str
    ficha_id: str
    situacao: SituacaoTransmissao
    protocolo: Optional[str] = None
    mensagem: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadados: Dict[str, Any] = field(default_factory=dict)

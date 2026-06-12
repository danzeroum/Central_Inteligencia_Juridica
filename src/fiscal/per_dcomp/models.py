"""Modelos de dados para o gerador PER/DCOMP (S-F.2).

PER  = Pedido Eletrônico de Restituição
DCOMP = Declaração de Compensação

Valores monetários como Decimal para precisão fiscal.
LGPD: CNPJ armazenado exclusivamente na forma mascarada.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class TipoFicha(str, Enum):
    """Tipo de documento PER/DCOMP conforme Programa PER/DCOMP Web (e-CAC)."""

    PER_RESTITUICAO = "per_restituicao"
    PER_RESSARCIMENTO = "per_ressarcimento"
    PER_SALDO_NEGATIVO_IRPJ = "per_saldo_negativo_irpj"
    PER_SALDO_NEGATIVO_CSLL = "per_saldo_negativo_csll"
    DCOMP_CREDITO_APURACAO = "dcomp_credito_apuracao"
    DCOMP_PAGAMENTO_INDEVIDO = "dcomp_pagamento_indevido"


class TipoTributo(str, Enum):
    """Tributo objeto do PER/DCOMP."""

    PIS = "PIS"
    COFINS = "COFINS"
    IRPJ = "IRPJ"
    CSLL = "CSLL"
    IPI = "IPI"


class StatusFicha(str, Enum):
    """Status da ficha no ciclo de vida."""

    GERADA = "gerada"
    VALIDADA = "validada"
    INVALIDA = "invalida"
    TRANSMITIDA = "transmitida"


# Código de receita por tributo (Receita Federal do Brasil)
CODIGO_RECEITA: Dict[TipoTributo, str] = {
    TipoTributo.PIS: "8109",
    TipoTributo.COFINS: "7987",
    TipoTributo.IRPJ: "0190",
    TipoTributo.CSLL: "2484",
    TipoTributo.IPI: "1097",
}

# Tributos elegíveis para PER/DCOMP via apuração EFD-Contribuições
TRIBUTOS_APURACAO_EFD: frozenset = frozenset({TipoTributo.PIS, TipoTributo.COFINS})


@dataclass
class IdentificacaoContribuinte:
    """Identificação do contribuinte declarante."""

    cnpj_masked: str
    nome_empresarial: str
    periodo_apuracao: str  # AAAA-MM


@dataclass
class CreditoTributario:
    """Crédito tributário pleiteado na ficha."""

    tributo: TipoTributo
    periodo_apuracao: str  # AAAA-MM
    valor_credito: Decimal
    codigo_receita: str = ""
    origem: str = "apuracao_sped"
    numero_processo: Optional[str] = None
    descricao: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.codigo_receita:
            self.codigo_receita = CODIGO_RECEITA.get(self.tributo, "")


@dataclass
class DebitoCompensacao:
    """Débito a ser compensado (somente para DCOMP)."""

    tributo: TipoTributo
    periodo_apuracao: str  # AAAA-MM
    valor_debito: Decimal
    codigo_receita: str = ""
    descricao: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.codigo_receita:
            self.codigo_receita = CODIGO_RECEITA.get(self.tributo, "")


@dataclass
class FichaPERDCOMP:
    """Ficha PER/DCOMP completa gerada pelo factory."""

    ficha_id: str
    tipo: TipoFicha
    identificacao: IdentificacaoContribuinte
    credito: CreditoTributario
    debitos: List[DebitoCompensacao] = field(default_factory=list)
    status: StatusFicha = StatusFicha.GERADA
    correlation_id: Optional[str] = None
    gerado_em: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    erros_validacao: List[str] = field(default_factory=list)
    avisos_validacao: List[str] = field(default_factory=list)
    metadados: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa para dict com Decimal→str e Enum→str para JSON."""
        d: Dict[str, Any] = {
            "ficha_id": self.ficha_id,
            "tipo": self.tipo.value,
            "status": self.status.value,
            "correlation_id": self.correlation_id,
            "gerado_em": self.gerado_em,
            "erros_validacao": list(self.erros_validacao),
            "avisos_validacao": list(self.avisos_validacao),
            "metadados": dict(self.metadados),
            "identificacao": {
                "cnpj_masked": self.identificacao.cnpj_masked,
                "nome_empresarial": self.identificacao.nome_empresarial,
                "periodo_apuracao": self.identificacao.periodo_apuracao,
            },
            "credito": {
                "tributo": self.credito.tributo.value,
                "periodo_apuracao": self.credito.periodo_apuracao,
                "valor_credito": str(self.credito.valor_credito),
                "codigo_receita": self.credito.codigo_receita,
                "origem": self.credito.origem,
                "numero_processo": self.credito.numero_processo,
                "descricao": self.credito.descricao,
            },
            "debitos": [
                {
                    "tributo": deb.tributo.value,
                    "periodo_apuracao": deb.periodo_apuracao,
                    "valor_debito": str(deb.valor_debito),
                    "codigo_receita": deb.codigo_receita,
                    "descricao": deb.descricao,
                }
                for deb in self.debitos
            ],
        }
        return d


def _new_ficha_id() -> str:
    return uuid.uuid4().hex

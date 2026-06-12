"""Gerador PER/DCOMP (S-F.2).

PER  = Pedido Eletrônico de Restituição
DCOMP = Declaração de Compensação

Padrão Factory: cada tipo de ficha é criado pelo método de fábrica correspondente.
"""

from src.fiscal.per_dcomp.factory import PERDCOMPFactory
from src.fiscal.per_dcomp.models import (
    CreditoTributario,
    DebitoCompensacao,
    FichaPERDCOMP,
    IdentificacaoContribuinte,
    StatusFicha,
    TipoFicha,
    TipoTributo,
)
from src.fiscal.per_dcomp.validator import PERDCOMPValidator

__all__ = [
    "FichaPERDCOMP",
    "TipoFicha",
    "TipoTributo",
    "StatusFicha",
    "IdentificacaoContribuinte",
    "CreditoTributario",
    "DebitoCompensacao",
    "PERDCOMPFactory",
    "PERDCOMPValidator",
]

"""Factory de fichas PER/DCOMP (S-F.2).

Padrão Factory: métodos de classe criam cada tipo de ficha a partir de parâmetros
ou de dados de apuração SPED (ApuracaoFiscal).

Regra principal:
  situacao == 'credor' AND saldo_apurado > 0 AND tributo IN {PIS, COFINS}
  → elegível para PER (restituição) ou DCOMP (compensação com débitos informados)
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src.fiscal.per_dcomp.models import (
    TRIBUTOS_APURACAO_EFD,
    CreditoTributario,
    DebitoCompensacao,
    FichaPERDCOMP,
    IdentificacaoContribuinte,
    StatusFicha,
    TipoFicha,
    TipoTributo,
    _new_ficha_id,
)


def _to_decimal(value: Any) -> Decimal:
    """Converte string ou número para Decimal com tratamento de erro."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _coerce_tributo(tributo: Any) -> TipoTributo:
    """Aceita TipoTributo ou string (ex: 'PIS') e retorna TipoTributo."""
    if isinstance(tributo, TipoTributo):
        return tributo
    try:
        return TipoTributo(str(tributo).upper())
    except ValueError:
        return TipoTributo.PIS  # fallback; validator detecta tributo inelegível


class PERDCOMPFactory:
    """Factory para geração de fichas PER/DCOMP.

    Todos os métodos retornam uma ``FichaPERDCOMP`` com status ``GERADA``
    (não validada). Passe a ficha para ``PERDCOMPValidator.validate`` para
    validação sintática/semântica antes da transmissão.
    """

    @classmethod
    def create_per_restituicao(
        cls,
        cnpj_masked: str,
        nome_empresarial: str,
        tributo_str: Any,
        periodo_apuracao: str,
        valor_credito: Decimal,
        correlation_id: Optional[str] = None,
        metadados: Optional[Dict[str, Any]] = None,
    ) -> FichaPERDCOMP:
        """Cria uma ficha PER de restituição (crédito de apuração EFD).

        ``tributo_str`` aceita TipoTributo ou string (ex: 'PIS').
        """
        tributo = _coerce_tributo(tributo_str)
        identificacao = IdentificacaoContribuinte(
            cnpj_masked=cnpj_masked,
            nome_empresarial=nome_empresarial,
            periodo_apuracao=periodo_apuracao,
        )
        credito = CreditoTributario(
            tributo=tributo,
            periodo_apuracao=periodo_apuracao,
            valor_credito=valor_credito,
            origem="apuracao_sped",
        )
        return FichaPERDCOMP(
            ficha_id=_new_ficha_id(),
            tipo=TipoFicha.PER_RESTITUICAO,
            identificacao=identificacao,
            credito=credito,
            correlation_id=correlation_id or uuid.uuid4().hex,
            metadados=metadados or {},
        )

    @classmethod
    def create_dcomp(
        cls,
        cnpj_masked: str,
        nome_empresarial: str,
        tributo_str: Any,
        periodo_apuracao: str,
        valor_credito: Decimal,
        debitos: List[DebitoCompensacao],
        correlation_id: Optional[str] = None,
        metadados: Optional[Dict[str, Any]] = None,
    ) -> FichaPERDCOMP:
        """Cria uma ficha DCOMP (compensação de crédito com débitos existentes).

        ``tributo_str`` aceita TipoTributo ou string (ex: 'COFINS').
        """
        tributo = _coerce_tributo(tributo_str)
        identificacao = IdentificacaoContribuinte(
            cnpj_masked=cnpj_masked,
            nome_empresarial=nome_empresarial,
            periodo_apuracao=periodo_apuracao,
        )
        credito = CreditoTributario(
            tributo=tributo,
            periodo_apuracao=periodo_apuracao,
            valor_credito=valor_credito,
            origem="apuracao_sped",
        )
        return FichaPERDCOMP(
            ficha_id=_new_ficha_id(),
            tipo=TipoFicha.DCOMP_CREDITO_APURACAO,
            identificacao=identificacao,
            credito=credito,
            debitos=list(debitos),
            correlation_id=correlation_id or uuid.uuid4().hex,
            metadados=metadados or {},
        )

    @classmethod
    def create_per_ressarcimento(
        cls,
        cnpj_masked: str,
        nome_empresarial: str,
        tributo_str: Any,
        periodo_apuracao: str,
        valor_credito: Decimal,
        correlation_id: Optional[str] = None,
        metadados: Optional[Dict[str, Any]] = None,
    ) -> FichaPERDCOMP:
        """Cria uma ficha PER de ressarcimento (crédito do regime não-cumulativo).

        ``tributo_str`` aceita TipoTributo ou string.
        """
        tributo = _coerce_tributo(tributo_str)
        identificacao = IdentificacaoContribuinte(
            cnpj_masked=cnpj_masked,
            nome_empresarial=nome_empresarial,
            periodo_apuracao=periodo_apuracao,
        )
        credito = CreditoTributario(
            tributo=tributo,
            periodo_apuracao=periodo_apuracao,
            valor_credito=valor_credito,
            origem="regime_nao_cumulativo",
        )
        return FichaPERDCOMP(
            ficha_id=_new_ficha_id(),
            tipo=TipoFicha.PER_RESSARCIMENTO,
            identificacao=identificacao,
            credito=credito,
            correlation_id=correlation_id or uuid.uuid4().hex,
            metadados=metadados or {},
        )

    @classmethod
    def create_from_apuracao(
        cls,
        apuracao: Dict[str, Any],
        cnpj_masked: str,
        nome_empresarial: str,
        debitos: Optional[List[DebitoCompensacao]] = None,
        tipo_ficha: Optional[TipoFicha] = None,
        correlation_id: Optional[str] = None,
    ) -> FichaPERDCOMP:
        """Factory principal: cria PER ou DCOMP a partir de dados de apuração SPED.

        Parâmetros esperados em ``apuracao``::

            {
                "tributo": "PIS" | "COFINS" | ...,
                "periodo_competencia": "AAAA-MM",
                "saldo_apurado": "1500.00",
                "situacao": "credor" | "devedor" | "equilibrado",
                "total_debitos": "500.00",     # opcional
                "total_creditos": "2000.00",   # opcional
            }

        Lógica de seleção do tipo (quando ``tipo_ficha`` não for fornecido):
          - situacao == 'credor' AND debitos fornecidos → DCOMP
          - situacao == 'credor' AND sem débitos → PER restituição
        """
        tributo_raw = str(apuracao.get("tributo", "")).upper()
        try:
            tributo = TipoTributo(tributo_raw)
        except ValueError:
            tributo = TipoTributo.PIS  # fallback seguro; validator vai apontar

        periodo = str(apuracao.get("periodo_competencia", ""))
        saldo = _to_decimal(apuracao.get("saldo_apurado", "0"))

        _debitos = list(debitos) if debitos else []

        if tipo_ficha is None:
            tipo_ficha = (
                TipoFicha.DCOMP_CREDITO_APURACAO
                if _debitos
                else TipoFicha.PER_RESTITUICAO
            )

        if tipo_ficha in (
            TipoFicha.DCOMP_CREDITO_APURACAO,
            TipoFicha.DCOMP_PAGAMENTO_INDEVIDO,
        ):
            return cls.create_dcomp(
                cnpj_masked=cnpj_masked,
                nome_empresarial=nome_empresarial,
                tributo_str=tributo,
                periodo_apuracao=periodo,
                valor_credito=saldo,
                debitos=_debitos,
                correlation_id=correlation_id,
                metadados={"apuracao_origem": dict(apuracao)},
            )

        return cls.create_per_restituicao(
            cnpj_masked=cnpj_masked,
            nome_empresarial=nome_empresarial,
            tributo_str=tributo,
            periodo_apuracao=periodo,
            valor_credito=saldo,
            correlation_id=correlation_id,
            metadados={"apuracao_origem": dict(apuracao)},
        )

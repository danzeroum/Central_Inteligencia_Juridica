"""Validador de fichas PER/DCOMP (S-F.2).

Duas etapas de validação:
  1. Sintática  — campos obrigatórios, formatos (CNPJ mascarado, período AAAA-MM, etc.)
  2. Semântica  — regras de negócio (valor > 0, DCOMP ≤ crédito, período não futuro,
                  tributo elegível para o tipo de ficha, etc.)

``validate()`` executa ambas, atualiza ``ficha.status`` e popula
``ficha.erros_validacao`` / ``ficha.avisos_validacao``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from src.fiscal.per_dcomp.models import (
    TRIBUTOS_APURACAO_EFD,
    FichaPERDCOMP,
    StatusFicha,
    TipoFicha,
    TipoTributo,
)

# Período AAAA-MM, ex: 2026-01
_PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# CNPJ mascarado aceita qualquer string com ao menos um '*' (LGPD)
_CNPJ_MASKED_RE = re.compile(r"[*\d./\-]{14,18}")

# Tipos de ficha válidos para tributos EFD (PIS/COFINS)
_TIPOS_EFD: frozenset = frozenset(
    {
        TipoFicha.PER_RESTITUICAO,
        TipoFicha.PER_RESSARCIMENTO,
        TipoFicha.DCOMP_CREDITO_APURACAO,
    }
)

# Tipos que requerem débitos informados
_TIPOS_COM_DEBITO: frozenset = frozenset(
    {TipoFicha.DCOMP_CREDITO_APURACAO, TipoFicha.DCOMP_PAGAMENTO_INDEVIDO}
)


def _periodo_como_data(periodo: str):
    """Converte 'AAAA-MM' para datetime ou None se inválido."""
    try:
        return datetime.strptime(periodo, "%Y-%m").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class PERDCOMPValidator:
    """Valida fichas PER/DCOMP para pré-envio ao e-CAC."""

    @classmethod
    def validate_sintatica(cls, ficha: FichaPERDCOMP) -> List[str]:
        """Valida estrutura e formatos dos campos (não acessa DB)."""
        erros: List[str] = []

        # Identificação
        if not ficha.identificacao.cnpj_masked.strip():
            erros.append("cnpj_masked é obrigatório.")
        elif not _CNPJ_MASKED_RE.match(ficha.identificacao.cnpj_masked):
            erros.append("cnpj_masked deve ter formato mascarado (LGPD).")

        if not ficha.identificacao.nome_empresarial.strip():
            erros.append("nome_empresarial é obrigatório.")

        if not _PERIODO_RE.match(ficha.identificacao.periodo_apuracao):
            erros.append(
                f"identificacao.periodo_apuracao '{ficha.identificacao.periodo_apuracao}' "
                "deve ter formato AAAA-MM."
            )

        # Crédito
        if not _PERIODO_RE.match(ficha.credito.periodo_apuracao):
            erros.append(
                f"credito.periodo_apuracao '{ficha.credito.periodo_apuracao}' "
                "deve ter formato AAAA-MM."
            )

        if ficha.credito.valor_credito < Decimal("0"):
            erros.append("credito.valor_credito não pode ser negativo.")

        if not ficha.credito.codigo_receita.strip():
            erros.append("credito.codigo_receita é obrigatório.")

        # Débitos (DCOMP)
        for i, deb in enumerate(ficha.debitos):
            if not _PERIODO_RE.match(deb.periodo_apuracao):
                erros.append(
                    f"debitos[{i}].periodo_apuracao '{deb.periodo_apuracao}' "
                    "deve ter formato AAAA-MM."
                )
            if deb.valor_debito <= Decimal("0"):
                erros.append(f"debitos[{i}].valor_debito deve ser maior que zero.")

        return erros

    @classmethod
    def validate_semantica(cls, ficha: FichaPERDCOMP) -> List[str]:
        """Valida regras de negócio da Receita Federal."""
        erros: List[str] = []
        avisos: List[str] = []

        agora = datetime.now(timezone.utc)

        # Valor do crédito deve ser positivo
        if ficha.credito.valor_credito <= Decimal("0"):
            erros.append("valor_credito deve ser maior que zero para PER/DCOMP.")

        # Período de apuração não pode ser futuro
        periodo_dt = _periodo_como_data(ficha.credito.periodo_apuracao)
        if periodo_dt and periodo_dt > agora:
            erros.append(
                f"credito.periodo_apuracao '{ficha.credito.periodo_apuracao}' "
                "não pode ser período futuro."
            )

        # Tributo elegível para o tipo de ficha
        if (
            ficha.tipo in _TIPOS_EFD
            and ficha.credito.tributo not in TRIBUTOS_APURACAO_EFD
        ):
            erros.append(
                f"Tipo '{ficha.tipo.value}' requer tributo PIS ou COFINS; "
                f"recebido '{ficha.credito.tributo.value}'."
            )

        # DCOMP: débitos obrigatórios e soma ≤ crédito
        if ficha.tipo in _TIPOS_COM_DEBITO:
            if not ficha.debitos:
                erros.append(
                    f"Tipo '{ficha.tipo.value}' (DCOMP) requer ao menos um débito."
                )
            else:
                soma_debitos = sum(d.valor_debito for d in ficha.debitos)
                if soma_debitos > ficha.credito.valor_credito:
                    erros.append(
                        f"Soma dos débitos ({soma_debitos}) supera o crédito "
                        f"disponível ({ficha.credito.valor_credito})."
                    )
                if soma_debitos < ficha.credito.valor_credito:
                    saldo = ficha.credito.valor_credito - soma_debitos
                    avisos.append(
                        f"Saldo credor remanescente após compensação: R$ {saldo:.2f}."
                    )

        # PER: não deve ter débitos informados
        if (
            ficha.tipo in (TipoFicha.PER_RESTITUICAO, TipoFicha.PER_RESSARCIMENTO)
            and ficha.debitos
        ):
            avisos.append(
                "Débitos informados serão ignorados em ficha PER (use DCOMP para compensação)."
            )

        # Valor abaixo do mínimo operacional (R$ 10,00)
        if Decimal("0") < ficha.credito.valor_credito < Decimal("10"):
            avisos.append(
                "valor_credito abaixo de R$ 10,00 — verifique se a Receita aceita."
            )

        # Período de referência muito antigo (> 5 anos): prescrição
        if periodo_dt:
            anos_decorridos = (agora - periodo_dt).days / 365.25
            if anos_decorridos > 5:
                erros.append(
                    f"Crédito de '{ficha.credito.periodo_apuracao}' pode estar prescrito "
                    "(> 5 anos). Verifique o prazo decadencial."
                )

        return erros

    @classmethod
    def validate(cls, ficha: FichaPERDCOMP) -> FichaPERDCOMP:
        """Executa validação completa; atualiza status e listas de erro na ficha."""
        erros_sint = cls.validate_sintatica(ficha)
        erros_sem = cls.validate_semantica(ficha)

        todos_erros = erros_sint + erros_sem
        ficha.erros_validacao = todos_erros
        ficha.status = StatusFicha.INVALIDA if todos_erros else StatusFicha.VALIDADA

        # Preserva avisos semânticos separadamente
        _existing_avisos = list(ficha.avisos_validacao)
        # Avisos são produzidos internamente; re-executa apenas semântica para capturá-los
        _erros_sem_2, avisos = cls._validate_semantica_com_avisos(ficha)
        ficha.avisos_validacao = _existing_avisos + avisos

        return ficha

    @classmethod
    def _validate_semantica_com_avisos(
        cls, ficha: FichaPERDCOMP
    ) -> tuple[List[str], List[str]]:
        """Versão interna que separa erros de avisos semânticos."""
        erros: List[str] = []
        avisos: List[str] = []

        agora = datetime.now(timezone.utc)

        if ficha.credito.valor_credito <= Decimal("0"):
            erros.append("valor_credito deve ser maior que zero para PER/DCOMP.")

        periodo_dt = _periodo_como_data(ficha.credito.periodo_apuracao)
        if periodo_dt and periodo_dt > agora:
            erros.append(
                f"credito.periodo_apuracao '{ficha.credito.periodo_apuracao}' "
                "não pode ser período futuro."
            )

        if (
            ficha.tipo in _TIPOS_EFD
            and ficha.credito.tributo not in TRIBUTOS_APURACAO_EFD
        ):
            erros.append(
                f"Tipo '{ficha.tipo.value}' requer tributo PIS ou COFINS; "
                f"recebido '{ficha.credito.tributo.value}'."
            )

        if ficha.tipo in _TIPOS_COM_DEBITO:
            if not ficha.debitos:
                erros.append(
                    f"Tipo '{ficha.tipo.value}' (DCOMP) requer ao menos um débito."
                )
            else:
                soma_debitos = sum(d.valor_debito for d in ficha.debitos)
                if soma_debitos > ficha.credito.valor_credito:
                    erros.append(
                        f"Soma dos débitos ({soma_debitos}) supera o crédito "
                        f"disponível ({ficha.credito.valor_credito})."
                    )
                if soma_debitos < ficha.credito.valor_credito:
                    saldo = ficha.credito.valor_credito - soma_debitos
                    avisos.append(
                        f"Saldo credor remanescente após compensação: R$ {saldo:.2f}."
                    )

        if (
            ficha.tipo in (TipoFicha.PER_RESTITUICAO, TipoFicha.PER_RESSARCIMENTO)
            and ficha.debitos
        ):
            avisos.append(
                "Débitos informados serão ignorados em ficha PER (use DCOMP para compensação)."
            )

        if Decimal("0") < ficha.credito.valor_credito < Decimal("10"):
            avisos.append(
                "valor_credito abaixo de R$ 10,00 — verifique se a Receita aceita."
            )

        if periodo_dt:
            anos_decorridos = (agora - periodo_dt).days / 365.25
            if anos_decorridos > 5:
                erros.append(
                    f"Crédito de '{ficha.credito.periodo_apuracao}' pode estar prescrito "
                    "(> 5 anos). Verifique o prazo decadencial."
                )

        return erros, avisos

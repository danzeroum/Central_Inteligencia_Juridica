"""Motor de regras fiscais declarativo — Bloco C (S-C.1).

Valida registros SPED EFD-ICMS/IPI e EFD-Contribuições contra regras
declarativas de apuração de ICMS, PIS e COFINS.

Uso:
    engine = get_rules_engine("lucro_real")
    resultado = engine.validate(parse_result.records)
    for r in resultado.erros:
        print(r.regra_id, r.descricao)

Regimes suportados: lucro_real, lucro_presumido, simples_nacional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Optional

from .parser.base import SpedRecord
from .reconciliation import Severidade, _normaliza_valor

# ─────────────────────────────────────────────────────────────────────────────
# Resultado
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RuleResult:
    """Uma violação de regra fiscal encontrada em um SpedRecord."""

    regra_id: str
    severidade: Severidade
    campo: str
    descricao: str
    tipo_registro: str
    numero_linha: int
    valor_encontrado: Any = None
    dica: str = ""


@dataclass
class ApuracaoResult:
    """Resultado da validação de um conjunto de registros pelo motor de regras."""

    aprovado: bool
    resultados: List[RuleResult] = field(default_factory=list)
    resumo: str = ""
    total_registros: int = 0

    @property
    def erros(self) -> List[RuleResult]:
        return [r for r in self.resultados if r.severidade == Severidade.ERRO]

    @property
    def avisos(self) -> List[RuleResult]:
        return [r for r in self.resultados if r.severidade == Severidade.AVISO]

    @property
    def infos(self) -> List[RuleResult]:
        return [r for r in self.resultados if r.severidade == Severidade.INFO]


# ─────────────────────────────────────────────────────────────────────────────
# Definição de regra
# ─────────────────────────────────────────────────────────────────────────────

_ALL_REGIMES: FrozenSet[str] = frozenset(
    {"lucro_real", "lucro_presumido", "simples_nacional"}
)


@dataclass
class FiscalRule:
    """Regra declarativa aplicável a um tipo de registro SPED."""

    id: str
    tipo_registro: str  # "C100", "D100", "M200" etc.; "*" = qualquer
    campo: str
    descricao: str
    severidade: Severidade
    check: Callable[[Dict[str, Any]], bool]  # True → violação detectada
    dica: str = ""
    regimes: FrozenSet[str] = field(default_factory=lambda: _ALL_REGIMES)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────


def _v(campos: Dict[str, Any], campo: str) -> Optional[float]:
    return _normaliza_valor(str(campos.get(campo) or ""))


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo de regras
# ─────────────────────────────────────────────────────────────────────────────


def _build_rules() -> List[FiscalRule]:
    rules: List[FiscalRule] = []

    # ── C100: Nota Fiscal ────────────────────────────────────────────────────

    rules.append(
        FiscalRule(
            id="ICMS-001",
            tipo_registro="C100",
            campo="vl_bc_icms",
            descricao="Base de cálculo ICMS negativa",
            severidade=Severidade.ERRO,
            check=lambda c: (v := _v(c, "vl_bc_icms")) is not None and v < 0,
            dica="vl_bc_icms deve ser >= 0",
        )
    )

    rules.append(
        FiscalRule(
            id="ICMS-002",
            tipo_registro="C100",
            campo="vl_icms",
            descricao="Valor ICMS negativo",
            severidade=Severidade.ERRO,
            check=lambda c: (v := _v(c, "vl_icms")) is not None and v < 0,
            dica="vl_icms deve ser >= 0",
        )
    )

    rules.append(
        FiscalRule(
            id="ICMS-003",
            tipo_registro="C100",
            campo="vl_icms",
            descricao="Valor ICMS superior à base de cálculo",
            severidade=Severidade.ERRO,
            check=lambda c: (
                (vb := _v(c, "vl_bc_icms")) is not None
                and (vi := _v(c, "vl_icms")) is not None
                and vb > 0
                and vi > vb
            ),
            dica="vl_icms não pode ser maior que vl_bc_icms",
        )
    )

    rules.append(
        FiscalRule(
            id="ICMS-004",
            tipo_registro="C100",
            campo="vl_bc_icms",
            descricao="Base ICMS excede valor total do documento",
            severidade=Severidade.AVISO,
            check=lambda c: (
                (vd := _v(c, "vl_doc")) is not None
                and (vb := _v(c, "vl_bc_icms")) is not None
                and vd > 0
                and vb > vd
            ),
            dica="vl_bc_icms deve ser <= vl_doc",
        )
    )

    def _icms_aliq_check(c: Dict[str, Any]) -> bool:
        vb = _v(c, "vl_bc_icms")
        vi = _v(c, "vl_icms")
        al = _v(c, "aliq_icms")
        if vb is None or vi is None or al is None or al <= 0 or vb <= 0:
            return False
        esperado = vb * al / 100.0
        return abs(vi - esperado) / esperado > 0.01

    rules.append(
        FiscalRule(
            id="ICMS-005",
            tipo_registro="C100",
            campo="aliq_icms",
            descricao="Valor ICMS inconsistente com base × alíquota (divergência > 1%)",
            severidade=Severidade.AVISO,
            check=_icms_aliq_check,
            dica="Verifique se vl_icms = vl_bc_icms × aliq_icms / 100",
        )
    )

    rules.append(
        FiscalRule(
            id="PIS-001",
            tipo_registro="C100",
            campo="vl_pis",
            descricao="Valor PIS negativo",
            severidade=Severidade.ERRO,
            check=lambda c: (v := _v(c, "vl_pis")) is not None and v < 0,
            dica="vl_pis deve ser >= 0",
        )
    )

    rules.append(
        FiscalRule(
            id="COFINS-001",
            tipo_registro="C100",
            campo="vl_cofins",
            descricao="Valor COFINS negativo",
            severidade=Severidade.ERRO,
            check=lambda c: (v := _v(c, "vl_cofins")) is not None and v < 0,
            dica="vl_cofins deve ser >= 0",
        )
    )

    rules.append(
        FiscalRule(
            id="PIS-002",
            tipo_registro="C100",
            campo="vl_pis",
            descricao="Valor PIS excede valor total do documento",
            severidade=Severidade.ERRO,
            check=lambda c: (
                (vd := _v(c, "vl_doc")) is not None
                and (vp := _v(c, "vl_pis")) is not None
                and vd > 0
                and vp > vd
            ),
            dica="vl_pis não pode ser maior que vl_doc",
        )
    )

    rules.append(
        FiscalRule(
            id="COFINS-002",
            tipo_registro="C100",
            campo="vl_cofins",
            descricao="Valor COFINS excede valor total do documento",
            severidade=Severidade.ERRO,
            check=lambda c: (
                (vd := _v(c, "vl_doc")) is not None
                and (vc := _v(c, "vl_cofins")) is not None
                and vd > 0
                and vc > vd
            ),
            dica="vl_cofins não pode ser maior que vl_doc",
        )
    )

    _SITUS_CANCELADOS = {"5", "6", "7", "8", "02", "05", "06", "07", "08"}

    rules.append(
        FiscalRule(
            id="COD-SIT-001",
            tipo_registro="C100",
            campo="cod_sit",
            descricao="Documento cancelado/denegado com valor total > 0",
            severidade=Severidade.AVISO,
            check=lambda c: (
                str(c.get("cod_sit") or "").strip() in _SITUS_CANCELADOS
                and (vd := _v(c, "vl_doc")) is not None
                and vd > 0
            ),
            dica="Documentos cancelados (cod_sit 5-8) devem ter vl_doc = 0",
        )
    )

    # ── D100: Conhecimento de Transporte ────────────────────────────────────

    rules.append(
        FiscalRule(
            id="ICMS-D-001",
            tipo_registro="D100",
            campo="vl_icms",
            descricao="Valor ICMS negativo no CT-e (D100)",
            severidade=Severidade.ERRO,
            check=lambda c: (v := _v(c, "vl_icms")) is not None and v < 0,
            dica="vl_icms deve ser >= 0",
        )
    )

    rules.append(
        FiscalRule(
            id="ICMS-D-002",
            tipo_registro="D100",
            campo="vl_bc_icms",
            descricao="Base de cálculo ICMS negativa no CT-e (D100)",
            severidade=Severidade.ERRO,
            check=lambda c: (v := _v(c, "vl_bc_icms")) is not None and v < 0,
            dica="vl_bc_icms deve ser >= 0",
        )
    )

    rules.append(
        FiscalRule(
            id="ICMS-D-003",
            tipo_registro="D100",
            campo="vl_icms",
            descricao="Valor ICMS superior à base de cálculo no CT-e",
            severidade=Severidade.ERRO,
            check=lambda c: (
                (vb := _v(c, "vl_bc_icms")) is not None
                and (vi := _v(c, "vl_icms")) is not None
                and vb > 0
                and vi > vb
            ),
            dica="vl_icms não pode ser maior que vl_bc_icms",
        )
    )

    # ── M200: Apuração PIS ───────────────────────────────────────────────────

    rules.append(
        FiscalRule(
            id="PIS-M-001",
            tipo_registro="M200",
            campo="vl_tot_cont_nc_per",
            descricao="Total PIS apurado negativo no M200",
            severidade=Severidade.ERRO,
            check=lambda c: (v := _v(c, "vl_tot_cont_nc_per")) is not None and v < 0,
            dica="vl_tot_cont_nc_per deve ser >= 0",
        )
    )

    # ── E110: Apuração ICMS ──────────────────────────────────────────────────

    rules.append(
        FiscalRule(
            id="ICMS-E-001",
            tipo_registro="E110",
            campo="vl_tot_debitos",
            descricao="Total de débitos ICMS negativo no E110",
            severidade=Severidade.ERRO,
            check=lambda c: (v := _v(c, "vl_tot_debitos")) is not None and v < 0,
            dica="vl_tot_debitos deve ser >= 0",
        )
    )

    return rules


# ─────────────────────────────────────────────────────────────────────────────
# Motor
# ─────────────────────────────────────────────────────────────────────────────

_REGIMES_VALIDOS: FrozenSet[str] = frozenset(
    {"lucro_real", "lucro_presumido", "simples_nacional"}
)


class FiscalRulesEngine:
    """Motor de regras declarativo para validação fiscal SPED.

    Args:
        regime: Regime tributário — ``"lucro_real"`` (padrão),
                ``"lucro_presumido"``, ou ``"simples_nacional"``.
    """

    def __init__(self, regime: str = "lucro_real") -> None:
        if regime not in _REGIMES_VALIDOS:
            raise ValueError(
                f"Regime inválido: {regime!r}. "
                f"Regimes suportados: {sorted(_REGIMES_VALIDOS)}"
            )
        self.regime = regime
        self._rules: List[FiscalRule] = _build_rules()

    def apply_rules(self, record: SpedRecord) -> List[RuleResult]:
        """Aplica as regras ao SpedRecord e retorna as violações encontradas."""
        results: List[RuleResult] = []
        for rule in self._rules:
            if rule.tipo_registro not in (record.tipo_registro, "*"):
                continue
            if self.regime not in rule.regimes:
                continue
            try:
                if rule.check(record.campos):
                    results.append(
                        RuleResult(
                            regra_id=rule.id,
                            severidade=rule.severidade,
                            campo=rule.campo,
                            descricao=rule.descricao,
                            tipo_registro=record.tipo_registro,
                            numero_linha=record.numero_linha,
                            valor_encontrado=record.campos.get(rule.campo),
                            dica=rule.dica,
                        )
                    )
            except Exception:
                pass  # campo ausente ou malformado — pula silenciosamente

        return results

    def validate(self, records: List[SpedRecord]) -> ApuracaoResult:
        """Valida uma lista de SpedRecords e retorna o resultado agregado.

        Args:
            records: Saída de ``SpedEfdIcmsParser.parse().records`` ou
                     ``SpedEfdContribParser.parse().records``.
        """
        all_results: List[RuleResult] = []
        for record in records:
            all_results.extend(self.apply_rules(record))

        aprovado = not any(r.severidade == Severidade.ERRO for r in all_results)
        n = len(all_results)
        resumo = (
            "Apuração aprovada sem violações"
            if not all_results
            else f"Apuração: {n} violação(ões) encontrada(s)"
        )
        return ApuracaoResult(
            aprovado=aprovado,
            resultados=all_results,
            resumo=resumo,
            total_registros=len(records),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


def get_rules_engine(regime: str = "lucro_real") -> FiscalRulesEngine:
    """Retorna um FiscalRulesEngine configurado para o regime tributário.

    Args:
        regime: ``"lucro_real"`` (padrão), ``"lucro_presumido"``,
                ou ``"simples_nacional"``.

    Raises:
        ValueError: Se o regime não for suportado.
    """
    return FiscalRulesEngine(regime)

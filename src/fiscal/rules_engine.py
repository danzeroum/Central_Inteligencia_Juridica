"""Motor de regras fiscais declarativo — Bloco C (S-C.1/S-C.3).

Valida registros SPED EFD-ICMS/IPI e EFD-Contribuições contra regras
declarativas de apuração de ICMS, PIS e COFINS. A partir do S-C.3 as
regras são carregadas de YAML (config/fiscal/rules/) em vez de hardcoded.

Uso:
    engine = get_rules_engine("lucro_real")
    resultado = engine.validate(parse_result.records)
    for r in resultado.erros:
        print(r.regra_id, r.descricao)

    # Com regras por UF:
    engine = get_rules_engine("lucro_real", uf="SP")

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
    uf: Optional[str] = None  # None = regra geral; "SP", "RJ" etc. = UF específica


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────


def _v(campos: Dict[str, Any], campo: str) -> Optional[float]:
    return _normaliza_valor(str(campos.get(campo) or ""))


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
        uf: UF do contribuinte (dois caracteres, ex.: ``"SP"``). Carrega
            regras adicionais específicas da UF além das regras base.
    """

    def __init__(self, regime: str = "lucro_real", uf: Optional[str] = None) -> None:
        if regime not in _REGIMES_VALIDOS:
            raise ValueError(
                f"Regime inválido: {regime!r}. "
                f"Regimes suportados: {sorted(_REGIMES_VALIDOS)}"
            )
        self.regime = regime
        self.uf = uf.upper() if uf else None
        self._rules: List[FiscalRule] = self._load_rules()

    def _load_rules(self) -> List[FiscalRule]:
        """Carrega regras do YAML. Falha explicitamente em caso de YAML inválido."""
        from .rule_loader import load_all_rules

        return load_all_rules(uf=self.uf)

    def apply_rules(self, record: SpedRecord) -> List[RuleResult]:
        """Aplica as regras ao SpedRecord e retorna as violações encontradas."""
        results: List[RuleResult] = []
        for rule in self._rules:
            if rule.tipo_registro not in (record.tipo_registro, "*"):
                continue
            if self.regime not in rule.regimes:
                continue
            # Regras UF-específicas só se aplicam se a engine foi criada com essa UF
            if rule.uf is not None and rule.uf != self.uf:
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


def get_rules_engine(
    regime: str = "lucro_real", uf: Optional[str] = None
) -> FiscalRulesEngine:
    """Retorna um FiscalRulesEngine configurado para o regime tributário.

    Args:
        regime: ``"lucro_real"`` (padrão), ``"lucro_presumido"``,
                ou ``"simples_nacional"``.
        uf: UF do contribuinte (ex.: ``"SP"``, ``"RJ"``). Quando informada,
            carrega regras adicionais específicas da UF.

    Raises:
        ValueError: Se o regime não for suportado.
        RuleCompileError: Se o YAML de regras for inválido.
    """
    return FiscalRulesEngine(regime, uf=uf)

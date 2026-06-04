"""DMN-02 — engine de política de fonte de dados (regra arquitetural CJ-001).

Lê ``config/governance/data_sources.yaml`` (fonte única de verdade) e expõe a
consulta + a aplicação (hard block) da regra:

    🚨 O LLM ANALISA. A API REAL FORNECE OS DADOS. Nunca o contrário.

Segue o mesmo padrão de configuração externa do ``tribunal_identifier`` (YAML +
``lru_cache``), mantendo a política como *dados*, não como código.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "governance" / "data_sources.yaml"
)

# Identificador da fonte "LLM" (comparação case-insensitive).
_LLM_SOURCE = "llm"


class DataSourceViolation(Exception):
    """Violação da regra CJ-001: LLM usado como FONTE de um dado crítico."""


@dataclass(frozen=True)
class DataSourceRule:
    """Regra de fonte para um tipo de dado."""

    data_type: str
    fonte: str
    llm: str
    critico: bool
    cache_ttl: Optional[str] = None


class DataSourcePolicy:
    """Política de fonte de dados carregada de configuração externa (DMN-02)."""

    def __init__(self, rules: Dict[str, DataSourceRule]) -> None:
        self._rules = rules

    @classmethod
    def from_config(cls, config_path: Path | str | None = None) -> "DataSourcePolicy":
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        data = _load_config(path)
        rules: Dict[str, DataSourceRule] = {}
        for data_type, spec in (data.get("data_types") or {}).items():
            spec = spec or {}
            rules[data_type] = DataSourceRule(
                data_type=data_type,
                fonte=str(spec.get("fonte", "")),
                llm=str(spec.get("llm", "")),
                critico=bool(spec.get("critico", False)),
                cache_ttl=spec.get("cache_ttl"),
            )
        return cls(rules)

    def rule_for(self, data_type: str) -> Optional[DataSourceRule]:
        return self._rules.get(data_type)

    def is_critical(self, data_type: str) -> bool:
        rule = self.rule_for(data_type)
        return bool(rule and rule.critico)

    def authorized_source(self, data_type: str) -> Optional[str]:
        rule = self.rule_for(data_type)
        return rule.fonte if rule else None

    def cache_ttl(self, data_type: str) -> Optional[str]:
        rule = self.rule_for(data_type)
        return rule.cache_ttl if rule else None

    def critical_data_types(self) -> list[str]:
        return sorted(dt for dt, rule in self._rules.items() if rule.critico)

    def is_llm_allowed_as_source(self, data_type: str) -> bool:
        """``False`` para dados críticos — o LLM jamais é a fonte deles."""

        return not self.is_critical(data_type)

    def assert_source(self, data_type: str, source: str) -> None:
        """Hard block (CJ-001): rejeita LLM como fonte de dado crítico.

        Tipos não governados (sem regra) são permitidos — a política cobre os
        dados normativos/financeiros críticos; interpretação/estratégia é o
        papel legítimo do LLM.
        """

        rule = self.rule_for(data_type)
        if rule and rule.critico and source.strip().lower() == _LLM_SOURCE:
            raise DataSourceViolation(
                f"HARD BLOCK [CJ-001]: '{data_type}' não pode vir do LLM. "
                f"Fonte autorizada: {rule.fonte}. O LLM só pode '{rule.llm}'."
            )
        if rule is None:
            logger.debug(
                "Tipo de dado '%s' não governado pela DMN-02; permitido.", data_type
            )


@lru_cache(maxsize=4)
def _load_config(path: Path) -> Dict[str, object]:
    """Lê e cacheia o YAML de política de fontes."""

    try:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        logger.error("Arquivo de política de fontes não encontrado: %s", path)
        raise


_policy: Optional[DataSourcePolicy] = None


def get_data_source_policy() -> DataSourcePolicy:
    """Instância global da política (padrão dos demais singletons do projeto)."""

    global _policy
    if _policy is None:
        _policy = DataSourcePolicy.from_config()
    return _policy


__all__ = [
    "DataSourcePolicy",
    "DataSourceRule",
    "DataSourceViolation",
    "get_data_source_policy",
    "DEFAULT_CONFIG_PATH",
]

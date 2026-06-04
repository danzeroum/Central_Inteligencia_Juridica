"""Carregamento das regras de risco contratual (config externa)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "contracts"
    / "clausulas_risco.yaml"
)


@dataclass(frozen=True)
class ContractRule:
    """Regra de detecção de uma categoria de risco contratual."""

    id: str
    categoria: str
    base_legal: str
    severidade: str
    recomendacao: str
    padroes: Tuple[re.Pattern, ...]

    def matches(self, texto: str) -> bool:
        return any(p.search(texto) for p in self.padroes)


class ContractRuleSet:
    """Conjunto de regras carregado de configuração externa."""

    def __init__(self, rules: List[ContractRule]) -> None:
        self._rules = rules

    @classmethod
    def from_config(cls, config_path: Path | str | None = None) -> "ContractRuleSet":
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        data = _load_config(path)
        rules: List[ContractRule] = []
        for rule_id, spec in (data.get("regras") or {}).items():
            spec = spec or {}
            padroes = tuple(
                re.compile(p, re.IGNORECASE) for p in spec.get("padroes", [])
            )
            rules.append(
                ContractRule(
                    id=rule_id,
                    categoria=str(spec.get("categoria", rule_id)),
                    base_legal=str(spec.get("base_legal", "")),
                    severidade=str(spec.get("severidade", "media")),
                    recomendacao=str(spec.get("recomendacao", "")),
                    padroes=padroes,
                )
            )
        return cls(rules)

    def __iter__(self):
        return iter(self._rules)

    def __len__(self) -> int:
        return len(self._rules)


@lru_cache(maxsize=4)
def _load_config(path: Path) -> Dict[str, object]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        logger.error("Arquivo de regras de contrato não encontrado: %s", path)
        raise


_ruleset: ContractRuleSet | None = None


def get_contract_rules() -> ContractRuleSet:
    global _ruleset
    if _ruleset is None:
        _ruleset = ContractRuleSet.from_config()
    return _ruleset


__all__ = [
    "ContractRule",
    "ContractRuleSet",
    "get_contract_rules",
    "DEFAULT_CONFIG_PATH",
]

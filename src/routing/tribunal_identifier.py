"""Identificação de tribunais a partir do texto da tarefa.

Esta classe foi extraída de ``SupervisorAgent`` (refatoração Extract Class) para
resolver duas dívidas técnicas apontadas na auditoria:

* **OCP (Open/Closed):** os dicionários de palavras-chave de tribunais estavam
  triplicados e hardcoded em três métodos distintos do supervisor. Adicionar um
  tribunal exigia editar código em vários pontos. Agora a configuração vive em
  ``config/routing/tribunals.yaml`` e adicionar um domínio é apenas editar dados.
* **SRP (Single Responsibility):** a responsabilidade de "descobrir quais
  tribunais uma tarefa menciona" é única e coesa, e agora reside em um só lugar.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import yaml

logger = logging.getLogger(__name__)

# Caminho padrão da configuração de roteamento (relativo à raiz do projeto).
DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "routing" / "tribunals.yaml"
)


@dataclass(frozen=True)
class TribunalSpec:
    """Especificação de casamento de um único tribunal."""

    code: str
    core: bool = True
    keywords: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    reasoning_keywords: List[str] = field(default_factory=list)


class TribunalIdentifier:
    """Identifica tribunais citados em uma tarefa usando configuração externa."""

    def __init__(
        self,
        tribunals: Dict[str, TribunalSpec],
        regions: Dict[str, List[str]],
        default_tribunal: str = "TJSP",
    ) -> None:
        self._tribunals = tribunals
        self._regions = regions
        self._default_tribunal = default_tribunal

    # ------------------------------------------------------------------ #
    # Construção
    # ------------------------------------------------------------------ #
    @classmethod
    def from_config(cls, config_path: Path | str | None = None) -> "TribunalIdentifier":
        """Carrega a configuração de tribunais de um arquivo YAML."""

        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        data = _load_config(path)

        tribunals: Dict[str, TribunalSpec] = {}
        for code, spec in (data.get("tribunals") or {}).items():
            tribunals[code] = TribunalSpec(
                code=code,
                core=bool(spec.get("core", True)),
                keywords=[str(k).lower() for k in (spec.get("keywords") or [])],
                aliases=[str(a).lower() for a in (spec.get("aliases") or [])],
                reasoning_keywords=[
                    str(r).upper() for r in (spec.get("reasoning_keywords") or [])
                ],
            )

        regions = {
            region.lower(): list(codes)
            for region, codes in (data.get("regions") or {}).items()
        }
        default_tribunal = str(data.get("default_tribunal", "TJSP"))

        return cls(tribunals, regions, default_tribunal)

    # ------------------------------------------------------------------ #
    # Propriedades de conveniência
    # ------------------------------------------------------------------ #
    @property
    def default_tribunal(self) -> str:
        return self._default_tribunal

    @property
    def core_tribunals(self) -> Dict[str, List[str]]:
        """Mapa código -> keywords apenas dos tribunais 'core' (compat. legada)."""

        return {
            code: spec.keywords for code, spec in self._tribunals.items() if spec.core
        }

    # ------------------------------------------------------------------ #
    # Identificação
    # ------------------------------------------------------------------ #
    def identify_all(self, task: str) -> List[str]:
        """Retorna todos os tribunais 'core' mencionados, na ordem de aparição.

        Equivale ao antigo ``SupervisorAgent._identify_all_tribunals``: casamento
        por substring restrito aos tribunais core, ordenado pela primeira posição
        de qualquer keyword no texto, sem duplicados.
        """

        task_lower = task.lower()
        matches: List[tuple[int, str]] = []

        for code, spec in self._tribunals.items():
            if not spec.core:
                continue
            first_index: int | None = None
            for keyword in spec.keywords:
                idx = task_lower.find(keyword)
                if idx != -1 and (first_index is None or idx < first_index):
                    first_index = idx
            if first_index is not None:
                matches.append((first_index, code))

        matches.sort(key=lambda item: item[0])
        return _dedupe([code for _, code in matches])

    def identify_primary(self, task: str) -> str:
        """Retorna o tribunal mais provável (ou o default) para a tarefa."""

        tribunals = self.identify_all(task)
        return tribunals[0] if tribunals else self._default_tribunal

    def identify_relevant(self, task: str) -> List[str]:
        """Sugere tribunais relevantes, incluindo regiões e tribunais estendidos.

        Equivale ao antigo ``SupervisorAgent._identify_relevant_tribunals``:
        casamento por palavra inteira (word-boundary) sobre keywords + aliases,
        considerando também tribunais não-core (ex.: STJ, TST), além de expansão
        por região. Cai para ``identify_primary`` quando nada casa.
        """

        task_lower = task.lower()
        identified: List[str] = []

        # Expansão por região (apenas tribunais conhecidos na config).
        for region, codes in self._regions.items():
            if re.search(rf"\b{re.escape(region)}\b", task_lower):
                identified.extend(code for code in codes if code in self._tribunals)

        # Casamento por palavra inteira sobre keywords + aliases.
        for code, spec in self._tribunals.items():
            terms = spec.keywords + spec.aliases
            for term in terms:
                if re.search(rf"\b{re.escape(term)}\b", task_lower):
                    if code not in identified:
                        identified.append(code)
                    break

        if not identified:
            identified = [self.identify_primary(task)]

        result = _dedupe(identified)
        logger.debug("Identified tribunals for task '%s': %s", task[:50], result)
        return result

    def extract_from_reasoning(self, reasoning: Dict[str, object]) -> List[str]:
        """Extrai tribunais de um raciocínio estruturado do ArchitectAgent.

        Equivale ao antigo ``SupervisorAgent._extract_tribunals_from_reasoning``.
        """

        combined_text = (
            f"{reasoning.get('recommendation', '')} "
            f"{reasoning.get('problem_analysis', '')}"
        ).upper()

        detected: List[str] = []
        for code, spec in self._tribunals.items():
            if any(word in combined_text for word in spec.reasoning_keywords):
                detected.append(code)

        explicit = reasoning.get("identified_tribunals") or []
        for item in explicit:  # type: ignore[union-attr]
            code = str(item).upper()
            if code:
                detected.append(code)

        return _dedupe(detected)


def _dedupe(items: List[str]) -> List[str]:
    """Remove duplicados preservando a ordem de aparição."""

    return list(dict.fromkeys(items))


@lru_cache(maxsize=4)
def _load_config(path: Path) -> Dict[str, object]:
    """Lê e cacheia o YAML de configuração de roteamento."""

    try:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        logger.error("Arquivo de roteamento de tribunais não encontrado: %s", path)
        raise


__all__ = ["TribunalIdentifier", "TribunalSpec", "DEFAULT_CONFIG_PATH"]

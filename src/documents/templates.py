"""Carregamento dos templates de peças (config externa, padrão do projeto)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "templates" / "pecas.yaml"
)


class PecaDesconhecidaError(KeyError):
    """Tipo de peça não registrado em ``config/templates/pecas.yaml``."""


@dataclass(frozen=True)
class PecaTemplate:
    """Especificação de um template de peça processual."""

    tipo: str
    nome: str
    base_legal: str
    campos_obrigatorios: List[str] = field(default_factory=list)
    template: str = ""


class PecaTemplateRegistry:
    """Registro de templates carregado de configuração externa."""

    def __init__(self, templates: Dict[str, PecaTemplate]) -> None:
        self._templates = templates

    @classmethod
    def from_config(
        cls, config_path: Path | str | None = None
    ) -> "PecaTemplateRegistry":
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        data = _load_config(path)
        templates: Dict[str, PecaTemplate] = {}
        for tipo, spec in (data.get("pecas") or {}).items():
            spec = spec or {}
            templates[tipo] = PecaTemplate(
                tipo=tipo,
                nome=str(spec.get("nome", tipo)),
                base_legal=str(spec.get("base_legal", "")),
                campos_obrigatorios=list(spec.get("campos_obrigatorios", [])),
                template=str(spec.get("template", "")),
            )
        return cls(templates)

    def get(self, tipo: str) -> PecaTemplate:
        try:
            return self._templates[tipo]
        except KeyError as exc:
            raise PecaDesconhecidaError(
                f"Tipo de peça desconhecido: '{tipo}'. "
                f"Disponíveis: {sorted(self._templates)}"
            ) from exc

    def available(self) -> List[str]:
        return sorted(self._templates)


@lru_cache(maxsize=4)
def _load_config(path: Path) -> Dict[str, object]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        logger.error("Arquivo de templates de peças não encontrado: %s", path)
        raise


_registry: PecaTemplateRegistry | None = None


def get_template_registry() -> PecaTemplateRegistry:
    global _registry
    if _registry is None:
        _registry = PecaTemplateRegistry.from_config()
    return _registry


__all__ = [
    "PecaTemplate",
    "PecaTemplateRegistry",
    "PecaDesconhecidaError",
    "get_template_registry",
    "DEFAULT_CONFIG_PATH",
]

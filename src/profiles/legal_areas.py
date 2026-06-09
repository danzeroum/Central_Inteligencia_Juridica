"""Carrega perfis de área jurídica a partir dos YAMLs em config/personas/."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from src.profiles.schemas import AreaJuridica, LegalAreaProfile

logger = logging.getLogger(__name__)

_PERSONAS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "personas"

_cache: Dict[str, LegalAreaProfile] = {}
_loaded = False


def _load_all() -> None:
    global _loaded
    if _loaded:
        return

    if not _PERSONAS_DIR.exists():
        logger.warning("Diretório de personas não encontrado: %s", _PERSONAS_DIR)
        _loaded = True
        return

    try:
        import yaml
    except ImportError:
        logger.error("PyYAML não instalado. Personas não carregadas.")
        _loaded = True
        return

    for path in _PERSONAS_DIR.glob("*.yaml"):
        try:
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if not isinstance(data, dict):
                continue
            area_key_raw = data.get("area_key")
            if area_key_raw is None:
                continue
            try:
                area_key = AreaJuridica(area_key_raw)
            except ValueError:
                logger.warning(
                    "area_key desconhecida em %s: %s", path.name, area_key_raw
                )
                continue
            profile = LegalAreaProfile(
                area_key=area_key,
                name=data.get("name", area_key_raw),
                persona_prompt=data.get("persona_prompt", ""),
                autores_referencia=data.get("autores_referencia", []),
                legislacao_principal=data.get("legislacao_principal", []),
                tribunal_preferencial=data.get("tribunal_preferencial"),
                analise_info=data.get("analise_info", []),
                interaction_style_default=data.get(
                    "interaction_style_default", "detailed"
                ),
                response_format_hints=data.get("response_format_hints", []),
            )
            _cache[area_key.value] = profile
            logger.debug("Persona carregada: %s", area_key.value)
        except Exception as exc:
            logger.warning("Erro ao carregar persona %s: %s", path.name, exc)

    _loaded = True
    logger.info("Personas carregadas: %d áreas", len(_cache))


def load_legal_area(area_key: str) -> Optional[LegalAreaProfile]:
    """Retorna o perfil de área, ou None com log de warning (degradação graciosa)."""
    _load_all()
    profile = _cache.get(area_key)
    if profile is None:
        logger.warning(
            "Persona não encontrada: %s. Usando fallback genérico.", area_key
        )
    return profile


def list_legal_areas() -> Dict[str, LegalAreaProfile]:
    """Retorna todas as áreas carregadas."""
    _load_all()
    return dict(_cache)


__all__ = ["load_legal_area", "list_legal_areas"]

"""Parser registry — factory function para instanciar o parser SPED correto."""

from __future__ import annotations

from .base import SpedParser
from .sped_efd_contrib import SpedEfdContribParser
from .sped_efd_icms import SpedEfdIcmsParser

_ICMS_TIPOS = {"efd_icms", "efd_icms_ipi"}
_CONTRIB_TIPOS = {"efd_contrib", "efd_contribuicoes"}
_SUPPORTED = _ICMS_TIPOS | _CONTRIB_TIPOS


def get_parser(tipo: str) -> SpedParser:
    """Return the appropriate SpedParser for the given file type.

    Args:
        tipo: One of the supported tipo values (e.g. ``"efd_icms"``).

    Raises:
        ValueError: If no parser is registered for *tipo*.
    """
    if tipo in _ICMS_TIPOS:
        return SpedEfdIcmsParser()
    if tipo in _CONTRIB_TIPOS:
        return SpedEfdContribParser()
    raise ValueError(
        f"Parser não disponível para tipo: {tipo!r}. "
        f"Tipos suportados: {sorted(_SUPPORTED)}"
    )

"""Parser registry — factory function para instanciar o parser correto.

Adicione novos parsers aqui conforme sprints S-B.3+.
"""

from __future__ import annotations

from .base import SpedParser
from .sped_efd_icms import SpedEfdIcmsParser

_SUPPORTED = {"efd_icms", "efd_icms_ipi"}


def get_parser(tipo: str) -> SpedParser:
    """Return the appropriate SpedParser for the given file type.

    Args:
        tipo: One of the supported tipo values (e.g. ``"efd_icms"``).

    Raises:
        ValueError: If no parser is registered for *tipo*.
    """
    if tipo in _SUPPORTED:
        return SpedEfdIcmsParser()
    raise ValueError(
        f"Parser não disponível para tipo: {tipo!r}. "
        f"Tipos suportados: {sorted(_SUPPORTED)}"
    )

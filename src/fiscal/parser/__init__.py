"""Parsers SPED para o módulo fiscal (Bloco B — S-B.2).

Uso:
    from src.fiscal.parser import get_parser

    parser = get_parser("efd_icms")
    result = parser.parse(raw_bytes)
    for record in result.records:
        print(record.tipo_registro, record.campos)
"""

from .base import ParseResult, SpedParser, SpedRecord
from .registry import get_parser
from .sped_efd_icms import SpedEfdIcmsParser

__all__ = [
    "ParseResult",
    "SpedEfdIcmsParser",
    "SpedParser",
    "SpedRecord",
    "get_parser",
]

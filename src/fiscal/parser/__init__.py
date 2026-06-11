"""Parsers SPED e XML para o módulo fiscal (Bloco B — S-B.2/S-B.3).

Uso:
    from src.fiscal.parser import get_parser, get_xml_parser

    parser = get_parser("efd_icms")
    result = parser.parse(raw_bytes)
    for record in result.records:
        print(record.tipo_registro, record.campos)

    xml_parser = get_xml_parser("nfe")
    xml_result = xml_parser.parse(xml_bytes)
    print(xml_result.chave, xml_result.campos)
"""

from .base import ParseResult, SpedParser, SpedRecord
from .registry import get_parser
from .sped_efd_contrib import SpedEfdContribParser
from .sped_efd_icms import SpedEfdIcmsParser
from .xml_fiscal import CTeParser, NFeParser, NFSeParser, XmlParseResult, get_xml_parser

__all__ = [
    "CTeParser",
    "NFeParser",
    "NFSeParser",
    "ParseResult",
    "SpedEfdContribParser",
    "SpedEfdIcmsParser",
    "SpedParser",
    "SpedRecord",
    "XmlParseResult",
    "get_parser",
    "get_xml_parser",
]

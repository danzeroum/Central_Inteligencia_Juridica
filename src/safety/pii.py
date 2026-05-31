"""Detecção e redação de PII brasileira (LGPD-005).

Cobre os tipos que a auditoria apontou como ausentes — e-mail, OAB, endereço
(CEP) — além de CPF, CNPJ e telefone. Usado tanto no **input** (para não
acumular dados pessoais brutos na trilha de auditoria append-only) quanto no
**output** (guardrail que evita vazamento de PII nas respostas dos agentes).

Importante: num sistema jurídico o conteúdo legitimamente contém PII (partes do
processo). Por isso o objetivo aqui NÃO é bloquear, e sim **detectar e redigir**
nos pontos onde o dado seria persistido/registrado (minimização de dados).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Pattern, Set, Tuple

# Padrões em ordem de prioridade (mais específicos/longos primeiro) para que a
# resolução de sobreposição prefira, p.ex., CNPJ a um CPF/telefone embutido.
_PATTERN_SOURCES: List[Tuple[str, str]] = [
    ("EMAIL", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ("OAB", r"OAB\s*/?\s*[A-Z]{0,2}\s*-?\s*\d{1,6}"),
    ("CNPJ", r"\b\d{2}\.?\d{3}\.?\d{3}/\d{4}-?\d{2}\b"),
    ("CPF", r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    # Telefone BR (com DDD, com ou sem 9º dígito e separadores).
    ("PHONE", r"\(?\b\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b"),
    ("CEP", r"\b\d{5}-\d{3}\b"),
    # CPF "nu" (11 dígitos) — depois de telefone para reduzir falsos positivos.
    ("CPF", r"\b\d{11}\b"),
]


@dataclass(frozen=True)
class PIIMatch:
    """Uma ocorrência de PII detectada no texto."""

    type: str
    value: str
    start: int
    end: int


class PIIDetector:
    """Detecta e redige PII em textos livres."""

    def __init__(self) -> None:
        self._compiled: List[Tuple[str, Pattern[str]]] = [
            (name, re.compile(src, re.IGNORECASE)) for name, src in _PATTERN_SOURCES
        ]

    def detect(self, text: str) -> List[PIIMatch]:
        """Retorna as ocorrências de PII, sem sobreposição (prioridade por posição/tamanho)."""

        if not text or not isinstance(text, str):
            return []

        candidates: List[PIIMatch] = []
        for name, pattern in self._compiled:
            for m in pattern.finditer(text):
                candidates.append(PIIMatch(name, m.group(), m.start(), m.end()))

        # Resolve sobreposições: ordena por início e, em empate, pelo mais longo.
        candidates.sort(key=lambda x: (x.start, -(x.end - x.start)))
        resolved: List[PIIMatch] = []
        last_end = -1
        for match in candidates:
            if match.start >= last_end:
                resolved.append(match)
                last_end = match.end
        return resolved

    def has_pii(self, text: str) -> bool:
        return bool(self.detect(text))

    def types_found(self, text: str) -> Set[str]:
        return {m.type for m in self.detect(text)}

    def redact(self, text: str, template: str = "[REDACTED:{type}]") -> str:
        """Substitui cada PII detectada por um marcador, preservando o restante."""

        matches = self.detect(text)
        if not matches:
            return text
        out: List[str] = []
        cursor = 0
        for match in matches:
            out.append(text[cursor : match.start])
            out.append(template.format(type=match.type))
            cursor = match.end
        out.append(text[cursor:])
        return "".join(out)


_detector: PIIDetector | None = None


def get_pii_detector() -> PIIDetector:
    """Retorna a instância compartilhada do detector (padrões pré-compilados)."""

    global _detector
    if _detector is None:
        _detector = PIIDetector()
    return _detector


def detect_pii(text: str) -> List[PIIMatch]:
    return get_pii_detector().detect(text)


def has_pii(text: str) -> bool:
    return get_pii_detector().has_pii(text)


def redact_pii(text: str) -> str:
    return get_pii_detector().redact(text)


def pii_types(text: str) -> List[str]:
    return sorted(get_pii_detector().types_found(text))


__all__ = [
    "PIIMatch",
    "PIIDetector",
    "get_pii_detector",
    "detect_pii",
    "has_pii",
    "redact_pii",
    "pii_types",
]

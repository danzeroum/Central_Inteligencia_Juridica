"""Classificação e validação de identificadores jurídicos.

Centraliza: regex do nº CNJ (reusado de intent_classifier), DV de CPF/CNPJ,
MOD 97-10 do processo CNJ e hash de auditoria (sha256 sem PII bruta).
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from src.integrations.models import IdentifierType

# Nº CNJ NNNNNNN-DD.AAAA.J.TT.OOOO (mesma regex do intent_classifier)
_PROCESS_PATTERN = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")
_CPF_PATTERN = re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$")
_CNPJ_PATTERN = re.compile(r"^\d{2}\.?\d{3}\.?\d{3}/?\.?\d{4}-?\d{2}$")
_OAB_PATTERN = re.compile(r"^[A-Z]{2}/?\d{4,7}(-[A-Z])?$", re.IGNORECASE)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _validate_cpf(cpf: str) -> bool:
    d = _digits(cpf)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for i in range(2):
        total = sum(int(d[j]) * (10 + i - j) for j in range(9 + i))
        expected = 0 if (total * 10 % 11) >= 10 else (total * 10 % 11)
        if int(d[9 + i]) != expected:
            return False
    return True


def _validate_cnpj(cnpj: str) -> bool:
    d = _digits(cnpj)
    if len(d) != 14 or len(set(d)) == 1:
        return False
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6] + weights1
    for i, weights in enumerate([weights1, weights2]):
        total = sum(int(d[j]) * weights[j] for j in range(len(weights)))
        remainder = total % 11
        expected = 0 if remainder < 2 else 11 - remainder
        if int(d[12 + i]) != expected:
            return False
    return True


def _validate_cnj_process(numero: str) -> bool:
    """Valida número CNJ via MOD 97-10 (Res. 65/2008 CNJ)."""
    d = _digits(numero)
    if len(d) != 20:
        return False
    # NNNNNNN DD AAAA J TT OOOO → reordena para CNJ check
    nnnnnnn = d[0:7]
    dd = d[7:9]
    aaaa = d[9:13]
    j = d[13:14]
    tt = d[14:16]
    oooo = d[16:20]
    check_input = f"{nnnnnnn}{aaaa}{j}{tt}{oooo}00"
    remainder = int(check_input) % 97
    return remainder == int(dd)


def classify_identifier(value: str) -> IdentifierType:
    """Classifica o identificador pelo seu padrão.

    Ordem: NUMERO_PROCESSO → CNPJ → CPF → OAB → NOME (fallback).
    """
    v = value.strip()
    if _PROCESS_PATTERN.search(v):
        return IdentifierType.NUMERO_PROCESSO
    d = _digits(v)
    if len(d) == 14 and _CNPJ_PATTERN.match(v):
        return IdentifierType.CNPJ
    if len(d) == 14:
        return IdentifierType.CNPJ
    if len(d) == 11 and _CPF_PATTERN.match(v):
        return IdentifierType.CPF
    if len(d) == 11:
        return IdentifierType.CPF
    if _OAB_PATTERN.match(v):
        return IdentifierType.OAB
    return IdentifierType.NOME


def validate_identifier(value: str, id_type: Optional[IdentifierType] = None) -> bool:
    """Valida DV do identificador. Retorna True se válido ou tipo não validável."""
    if id_type is None:
        id_type = classify_identifier(value)
    if id_type == IdentifierType.CPF:
        return _validate_cpf(value)
    if id_type == IdentifierType.CNPJ:
        return _validate_cnpj(value)
    if id_type == IdentifierType.NUMERO_PROCESSO:
        return _validate_cnj_process(value)
    return True  # OAB e NOME não têm DV estrutural


def mask_identifier(value: str, id_type: Optional[IdentifierType] = None) -> str:
    """Mascara o identificador para logs/ledger (nunca armazena PII bruta)."""
    if id_type is None:
        id_type = classify_identifier(value)
    d = _digits(value)
    if id_type == IdentifierType.CPF and len(d) == 11:
        return f"***.***.{d[6:9]}-{d[9:11]}"
    if id_type == IdentifierType.CNPJ and len(d) == 14:
        return f"{d[0:2]}.***.***/****-{d[12:14]}"
    if id_type == IdentifierType.NUMERO_PROCESSO:
        return f"*******-**.{value[10:14]}.**.**.**{value[-2:]}"
    if id_type == IdentifierType.NOME:
        parts = value.strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} ***"
        return f"{value[:2]}***"
    return value[:4] + "***"


def audit_hash(value: str) -> str:
    """SHA-256 do identificador para uso no ledger (nunca PII bruta)."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


__all__ = [
    "IdentifierType",
    "classify_identifier",
    "validate_identifier",
    "mask_identifier",
    "audit_hash",
    "_validate_cpf",
    "_validate_cnpj",
    "_validate_cnj_process",
]

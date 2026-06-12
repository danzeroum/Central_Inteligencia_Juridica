"""Mapeamento de códigos IBGE de municípios: 6 dígitos → 7 dígitos (com dígito verificador).

O CAGED e outros datasets usam o código de 7 dígitos (com DV), enquanto o SIH-RD
usa 6 dígitos (sem DV).  Esta função normaliza ambos para 6 dígitos como chave
comum, e fornece mapeamento reverso quando o DV é necessário.

Algoritmo do DV (Módulo 11):
  DV = 11 - (soma dos produtos posição×dígito) % 11
  Se DV ∈ {10, 11} → DV = 0

Reutilizável em qualquer contexto que precise uniformizar códigos IBGE.
"""

from __future__ import annotations


def normalize_munic_6(code: str | int | None) -> str | None:
    """Normaliza código IBGE para 6 dígitos (sem DV).

    Args:
        code: código com 6 ou 7 dígitos (string ou int).

    Returns:
        String de 6 dígitos, ou None se o código for inválido.
    """
    if code is None:
        return None
    s = str(code).strip().lstrip("0") if isinstance(code, int) else str(code).strip()
    s = s.zfill(7) if len(s) == 6 else s  # pad to 7 if needed
    if len(s) == 7:
        return s[:6]
    if len(s) == 6:
        return s
    return None


def munic_6_to_7(code6: str) -> str:
    """Converte código IBGE de 6 para 7 dígitos calculando o DV (Módulo 11).

    Args:
        code6: string de 6 dígitos.

    Returns:
        String de 7 dígitos com DV.

    Raises:
        ValueError: se code6 não tiver 6 dígitos numéricos.
    """
    if not (len(code6) == 6 and code6.isdigit()):
        raise ValueError(f"Código IBGE deve ter 6 dígitos: {code6!r}")

    digits = [int(d) for d in code6]
    weights = [1, 2, 1, 2, 1, 2]
    total = sum(
        (d * w) if (d * w) < 10 else (d * w) // 10 + (d * w) % 10
        for d, w in zip(digits, weights)
    )
    dv = (10 - (total % 10)) % 10
    return code6 + str(dv)


def munic_7_to_6(code7: str) -> str:
    """Remove o DV e retorna os 6 primeiros dígitos.

    Args:
        code7: string de 7 dígitos.

    Returns:
        String de 6 dígitos.

    Raises:
        ValueError: se code7 não tiver 7 dígitos numéricos.
    """
    if not (len(code7) == 7 and code7.isdigit()):
        raise ValueError(f"Código IBGE deve ter 7 dígitos: {code7!r}")
    return code7[:6]

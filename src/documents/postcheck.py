"""Postcheck jurídico de peças geradas (Frente F.2).

Verifica que os elementos obrigatórios da peça (ex.: CPC art. 319 para a petição
inicial) estão presentes e preenchidos, e que nenhum placeholder ficou sem valor.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from src.documents.schemas import PostcheckResult
from src.documents.templates import PecaTemplate

# Marcador inserido pelo preenchimento quando um campo está ausente/vazio.
FALTANTE_PREFIX = "[FALTANTE:"
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def run_postcheck(
    template: PecaTemplate, dados: Dict[str, Any], conteudo: str
) -> PostcheckResult:
    """Valida a peça gerada contra os requisitos do seu tipo."""

    findings: list[str] = []

    for campo in template.campos_obrigatorios:
        valor = dados.get(campo)
        if valor is None or str(valor).strip() == "":
            findings.append(
                f"Campo obrigatório ausente: '{campo}' "
                f"(exigido por {template.base_legal})."
            )

    if FALTANTE_PREFIX in conteudo:
        faltantes = sorted(set(re.findall(r"\[FALTANTE: (\w+)\]", conteudo)))
        for campo in faltantes:
            msg = f"Placeholder não preenchido no conteúdo: '{campo}'."
            if msg not in findings:
                findings.append(msg)

    return PostcheckResult(
        ok=not findings, findings=findings, base_legal=template.base_legal
    )


__all__ = ["run_postcheck", "FALTANTE_PREFIX"]

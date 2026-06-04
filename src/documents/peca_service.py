"""Serviço de geração de peças processuais (Frente F.2).

Fluxo: seleciona template → preenche (determinístico ou via ``gerador`` LLM
injetado) → postcheck jurídico → marca para revisão humana (HITL) → anexa o
disclaimer da OAB. A geração de prosa por LLM é um *hook opcional*: sem ele, o
serviço preenche o template de forma determinística (testável, sem rede).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from src.documents.postcheck import run_postcheck
from src.documents.schemas import DISCLAIMER_OAB, PecaResult
from src.documents.templates import (
    PecaTemplate,
    PecaTemplateRegistry,
    get_template_registry,
)

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

# Hook de geração de prosa (ex.: LLM/ArchitectAgent). Recebe o template e os
# dados; devolve o conteúdo. Mantém a regra CJ-001: o LLM *redige a partir dos
# dados fornecidos*, não inventa dados normativos.
GeradorPeca = Callable[[PecaTemplate, Dict[str, Any]], str]


def _preencher(template_str: str, dados: Dict[str, Any]) -> str:
    """Preenche ``{campo}`` com os dados; marca ausentes para o postcheck."""

    def _repl(match: "re.Match[str]") -> str:
        campo = match.group(1)
        valor = dados.get(campo)
        if valor is None or str(valor).strip() == "":
            return f"[FALTANTE: {campo}]"
        return str(valor)

    return _PLACEHOLDER_RE.sub(_repl, template_str)


class PecaService:
    """Gera rascunhos de peças com postcheck, HITL obrigatório e disclaimer."""

    HITL_AGENT = "AgenteDocumentos"

    def __init__(self, registry: Optional[PecaTemplateRegistry] = None) -> None:
        self._registry = registry or get_template_registry()

    def available(self) -> List[str]:
        return self._registry.available()

    def gerar(
        self,
        tipo: str,
        dados: Dict[str, Any],
        *,
        gerador: Optional[GeradorPeca] = None,
        hitl_queue: Any = None,
    ) -> PecaResult:
        """Gera uma peça (rascunho). Levanta ``PecaDesconhecidaError`` se inválida.

        ``gerador`` opcional injeta a redação por LLM; ``hitl_queue`` opcional
        enfileira o rascunho para aprovação humana (retorna ``hitl_request_id``).
        """

        template = self._registry.get(tipo)
        conteudo = (
            gerador(template, dados)
            if gerador is not None
            else _preencher(template.template, dados)
        )

        postcheck = run_postcheck(template, dados, conteudo)
        if not postcheck.ok:
            logger.warning(
                "Postcheck da peça '%s' encontrou %d pendência(s)",
                tipo,
                len(postcheck.findings),
            )

        result = PecaResult(
            tipo=tipo,
            nome=template.nome,
            base_legal=template.base_legal,
            conteudo=conteudo,
            postcheck=postcheck,
            requires_human_review=True,  # invariante: peça sempre passa por HITL
            disclaimer=DISCLAIMER_OAB,
        )

        if hitl_queue is not None:
            request = hitl_queue.add_request(
                agent=self.HITL_AGENT,
                action={
                    "type": "peca_review",
                    "tipo": tipo,
                    "task": f"Revisar rascunho: {template.nome}",
                },
                context={
                    "postcheck_ok": postcheck.ok,
                    "base_legal": template.base_legal,
                },
            )
            result.hitl_request_id = getattr(request, "request_id", None)

        return result


def register_peca_tools(
    registry: Any, service: Optional[PecaService] = None
) -> PecaService:
    """Registra a ferramenta de geração de peças num ``MCPToolRegistry``."""

    service = service or PecaService()

    @registry.register_tool("gerar_peca")
    def _gerar_peca(tipo: str, dados: Dict[str, Any]) -> PecaResult:
        return service.gerar(tipo, dados)

    return service


__all__ = ["PecaService", "GeradorPeca", "register_peca_tools"]

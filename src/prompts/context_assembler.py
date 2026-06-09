"""ContextAssembler — monta o bloco de contexto RAG com metadados jurídicos."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.profiles.schemas import (
        ClienteProfile,
        GenericUserProfile,
        LegalAreaProfile,
    )

_MAX_CONTEXT_CHARS = 16000  # ~4.000 tokens (4 chars/token aproximado)

_TECNICIDADE_INSTRUCTIONS = {
    1: "Use linguagem acessível, com analogias do cotidiano. Evite jargão jurídico.",
    2: "Use linguagem simples, explicando termos técnicos quando necessário.",
    3: "Use linguagem clara e objetiva, equilibrando técnica e acessibilidade.",
    4: "Use linguagem técnica jurídica, citando dispositivos legais com precisão.",
    5: "Use linguagem técnica jurídica completa, com referências doutrinárias e jurisprudenciais.",
}

_FORMALITY_INSTRUCTIONS = {
    "formal": "Mantenha tom formal e impessoal.",
    "accessible": "Mantenha tom acessível e didático.",
    "technical": "Mantenha tom técnico e preciso.",
}


class ContextAssembler:
    """Monta o bloco de contexto para injeção no prompt do LLM."""

    def build_context_block(
        self,
        retrieved_docs: List[Dict[str, Any]],
        user_query: str,
        profile: Optional[GenericUserProfile] = None,
    ) -> str:
        """Formata documentos recuperados com cabeçalhos jurídicos.

        Limita a _MAX_CONTEXT_CHARS por relevância (docs mais relevantes primeiro).
        """
        if not retrieved_docs:
            return ""

        header = f"## Contexto Jurídico Relevante para: {user_query[:200]}\n\n"
        blocks = []
        total_chars = len(header)

        for doc in retrieved_docs:
            meta = doc.get("metadata") or {}
            text = doc.get("text") or ""
            score = doc.get("score", 0.0)

            fonte_label = self._format_source_label(meta)
            block = f"### {fonte_label} (relevância: {score:.2f})\n{text.strip()}\n"

            if total_chars + len(block) > _MAX_CONTEXT_CHARS:
                remaining = _MAX_CONTEXT_CHARS - total_chars - 100
                if remaining > 200:
                    block = f"### {fonte_label}\n{text[:remaining].strip()}…\n"
                else:
                    break

            blocks.append(block)
            total_chars += len(block)

        return header + "\n".join(blocks)

    def inject_persona(
        self,
        system_prompt: str,
        area_profile: Optional[LegalAreaProfile],
    ) -> str:
        """Injeta persona de área no system_prompt se disponível."""
        if area_profile and area_profile.persona_prompt:
            return area_profile.persona_prompt.strip() + "\n\n" + system_prompt
        return system_prompt

    def adjust_for_client(
        self,
        prompt: str,
        cliente: Optional[ClienteProfile],
    ) -> str:
        """Ajusta instruções de linguagem conforme nível do cliente."""
        if cliente is None:
            return prompt
        nivel = cliente.nivel_tecnicidade_saida
        instrucao = _TECNICIDADE_INSTRUCTIONS.get(nivel, _TECNICIDADE_INSTRUCTIONS[3])
        return prompt + f"\n\nPara o cliente final: {instrucao}"

    @staticmethod
    def _format_source_label(meta: Dict[str, Any]) -> str:
        parts = []
        tipo = meta.get("tipo_documento", "").capitalize()
        if tipo:
            parts.append(tipo)
        doc_id = meta.get("doc_id")
        if doc_id:
            parts.append(str(doc_id))
        tribunal = meta.get("tribunal")
        if tribunal:
            parts.append(f"| Tribunal: {tribunal}")
        data = meta.get("data_vigencia")
        if data:
            parts.append(f"| Vigência: {data}")
        ementa = meta.get("ementa")
        if ementa:
            parts.append(f"| {str(ementa)[:80]}")
        return " ".join(parts) or "Fonte jurídica"


__all__ = ["ContextAssembler"]

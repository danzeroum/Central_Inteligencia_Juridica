"""PromptBuilder — constrói prompts personalizados por perfil e área jurídica."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.profiles.schemas import (
        ClienteProfile,
        GenericUserProfile,
        LegalAreaProfile,
    )

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


class PromptBuilder:
    """Constrói instruções de sistema personalizadas por perfil."""

    @staticmethod
    def build_system_prompt(
        base_prompt: str,
        user_profile: Optional[GenericUserProfile] = None,
        area_profile: Optional[LegalAreaProfile] = None,
        cliente_profile: Optional[ClienteProfile] = None,
    ) -> str:
        """Compõe o system prompt final integrando perfil + área + cliente."""
        parts = []

        if area_profile and area_profile.persona_prompt:
            parts.append(area_profile.persona_prompt.strip())
        elif base_prompt:
            parts.append(base_prompt.strip())

        if user_profile:
            nivel = user_profile.nivel_tecnicidade
            formality = user_profile.preferred_formality
            parts.append(
                _TECNICIDADE_INSTRUCTIONS.get(nivel, _TECNICIDADE_INSTRUCTIONS[3])
            )
            parts.append(
                _FORMALITY_INSTRUCTIONS.get(
                    formality, _FORMALITY_INSTRUCTIONS["accessible"]
                )
            )

        if cliente_profile and cliente_profile.consentimento_lgpd:
            nivel_cliente = cliente_profile.nivel_tecnicidade_saida
            parts.append(
                f"\nAo comunicar resultados ao cliente final, adapte para: "
                f"{_TECNICIDADE_INSTRUCTIONS.get(nivel_cliente, _TECNICIDADE_INSTRUCTIONS[3])}"
            )

        if area_profile and area_profile.response_format_hints:
            hints = "\n".join(f"- {h}" for h in area_profile.response_format_hints)
            parts.append(f"\nDiretrizes de formato:\n{hints}")

        return "\n\n".join(p for p in parts if p)


__all__ = ["PromptBuilder"]

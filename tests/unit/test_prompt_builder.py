"""Testes unitários — PromptBuilder: perfil modula linguagem."""

from __future__ import annotations

from src.profiles.schemas import (
    AreaJuridica,
    ClienteProfile,
    GenericUserProfile,
    LegalAreaProfile,
)
from src.rag.prompt_builder import PromptBuilder

BASE = "Você é um assistente jurídico."


def _make_profile(nivel: int = 3, formality: str = "accessible") -> GenericUserProfile:
    return GenericUserProfile(
        user_id="u1", name="X", nivel_tecnicidade=nivel, preferred_formality=formality
    )


def _make_area_profile() -> LegalAreaProfile:
    return LegalAreaProfile(
        area_key=AreaJuridica.TRABALHISTA,
        name="Trabalhista",
        persona_prompt="Você é especialista em Direito Trabalhista.",
        response_format_hints=["Citar artigo da CLT"],
    )


def test_base_prompt_used_without_area():
    prompt = PromptBuilder.build_system_prompt(BASE)
    assert "assistente jurídico" in prompt


def test_area_persona_overrides_base():
    area = _make_area_profile()
    prompt = PromptBuilder.build_system_prompt(BASE, area_profile=area)
    assert "Trabalhista" in prompt
    assert "assistente jurídico" not in prompt


def test_tecnicidade_1_uses_accessible_language():
    profile = _make_profile(nivel=1)
    prompt = PromptBuilder.build_system_prompt(BASE, user_profile=profile)
    assert "acessível" in prompt.lower() or "analogias" in prompt.lower()


def test_tecnicidade_5_uses_technical_language():
    profile = _make_profile(nivel=5)
    prompt = PromptBuilder.build_system_prompt(BASE, user_profile=profile)
    assert "técnica" in prompt.lower() or "jurisprudenci" in prompt.lower()


def test_formality_formal_injected():
    profile = _make_profile(formality="formal")
    prompt = PromptBuilder.build_system_prompt(BASE, user_profile=profile)
    assert "formal" in prompt.lower()


def test_client_instruction_added_when_consentimento():
    profile = _make_profile()
    cliente = ClienteProfile(
        cliente_id="c1",
        advogado_id="u1",
        nome="Empresa",
        nivel_tecnicidade_saida=1,
        consentimento_lgpd=True,
    )
    prompt = PromptBuilder.build_system_prompt(
        BASE, user_profile=profile, cliente_profile=cliente
    )
    assert "cliente" in prompt.lower()


def test_no_client_instruction_without_consentimento():
    profile = _make_profile()
    cliente = ClienteProfile(
        cliente_id="c1",
        advogado_id="u1",
        nome="Empresa",
        nivel_tecnicidade_saida=1,
        consentimento_lgpd=False,
    )
    prompt = PromptBuilder.build_system_prompt(
        BASE, user_profile=profile, cliente_profile=cliente
    )
    # Sem consentimento, instrução de cliente não deve aparecer
    assert "cliente final" not in prompt.lower()


def test_response_format_hints_included():
    area = _make_area_profile()
    prompt = PromptBuilder.build_system_prompt(BASE, area_profile=area)
    assert "CLT" in prompt

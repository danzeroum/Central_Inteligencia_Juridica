"""Testes — ajuste de linguagem por nível de tecnicidade do cliente."""

from __future__ import annotations

from src.profiles.schemas import ClienteProfile
from src.prompts.context_assembler import ContextAssembler


def _make_client(nivel: int, consentimento: bool = True) -> ClienteProfile:
    return ClienteProfile(
        cliente_id="c1",
        advogado_id="a1",
        nome="Cliente Teste",
        nivel_tecnicidade_saida=nivel,
        consentimento_lgpd=consentimento,
    )


def test_nivel_1_linguagem_acessivel():
    ca = ContextAssembler()
    result = ca.adjust_for_client("Análise jurídica.", _make_client(1))
    assert "acessível" in result.lower() or "analogias" in result.lower()


def test_nivel_5_linguagem_tecnica():
    ca = ContextAssembler()
    result = ca.adjust_for_client("Análise jurídica.", _make_client(5))
    assert "técnica" in result.lower() or "jurisprudenci" in result.lower()


def test_nivel_3_linguagem_equilibrada():
    ca = ContextAssembler()
    result = ca.adjust_for_client("Análise.", _make_client(3))
    assert (
        "equilibr" in result.lower()
        or "clara" in result.lower()
        or "objetiva" in result.lower()
    )


def test_none_client_returns_original():
    ca = ContextAssembler()
    result = ca.adjust_for_client("Prompt inalterado.", None)
    assert result == "Prompt inalterado."


def test_all_levels_add_instruction():
    ca = ContextAssembler()
    for nivel in range(1, 6):
        result = ca.adjust_for_client("Base.", _make_client(nivel))
        assert len(result) > len("Base.")

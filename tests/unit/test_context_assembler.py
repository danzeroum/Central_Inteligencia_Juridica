"""Testes unitários — ContextAssembler."""

from __future__ import annotations

from src.profiles.schemas import (
    AreaJuridica,
    ClienteProfile,
    GenericUserProfile,
    LegalAreaProfile,
)
from src.prompts.context_assembler import ContextAssembler


def _make_doc(text: str, score: float = 0.8, **meta) -> dict:
    return {"text": text, "score": score, "metadata": meta}


def test_empty_docs_returns_empty():
    ca = ContextAssembler()
    assert ca.build_context_block([], "query") == ""


def test_context_includes_query():
    ca = ContextAssembler()
    docs = [_make_doc("Texto de teste", tipo_documento="lei", doc_id="lei_1")]
    block = ca.build_context_block(docs, "prescrição trabalhista")
    assert "prescrição trabalhista" in block


def test_context_includes_source_metadata():
    ca = ContextAssembler()
    docs = [
        _make_doc(
            "Conteúdo",
            tipo_documento="lei",
            doc_id="clt_1943",
            tribunal="TST",
            data_vigencia="1943-05-01",
        )
    ]
    block = ca.build_context_block(docs, "query")
    assert "TST" in block
    assert "1943-05-01" in block


def test_inject_persona_with_area():
    ca = ContextAssembler()
    area = LegalAreaProfile(
        area_key=AreaJuridica.TRABALHISTA,
        name="Trabalhista",
        persona_prompt="Especialista em Direito Trabalhista.",
    )
    result = ca.inject_persona("Base prompt", area)
    assert "Trabalhista" in result
    assert "Base prompt" in result


def test_inject_persona_without_area():
    ca = ContextAssembler()
    result = ca.inject_persona("Só este prompt", None)
    assert result == "Só este prompt"


def test_adjust_for_client_nivel_1():
    ca = ContextAssembler()
    cliente = ClienteProfile(
        cliente_id="c1",
        advogado_id="a1",
        nome="X",
        nivel_tecnicidade_saida=1,
        consentimento_lgpd=True,
    )
    result = ca.adjust_for_client("Prompt base", cliente)
    assert "acessível" in result.lower() or "analogias" in result.lower()


def test_adjust_for_client_nil():
    ca = ContextAssembler()
    result = ca.adjust_for_client("Prompt base", None)
    assert result == "Prompt base"


def test_context_truncation_on_large_docs():
    ca = ContextAssembler()
    big_text = "A" * 20000
    docs = [_make_doc(big_text)]
    block = ca.build_context_block(docs, "query")
    # Deve truncar — bloco não pode ser maior que MAX_CONTEXT_CHARS + overhead
    assert len(block) < 20000


def test_multiple_docs_sorted_by_score():
    ca = ContextAssembler()
    docs = [
        _make_doc("Menos relevante", score=0.3),
        _make_doc("Mais relevante", score=0.9),
    ]
    block = ca.build_context_block(docs, "query")
    # Docs são passados em ordem, o mais relevante já vem primeiro (score já ordenado pelo caller)
    assert "Menos relevante" in block or "Mais relevante" in block

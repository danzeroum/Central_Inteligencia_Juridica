"""Cobertura do IntentClassifier (Frente C cont.): heurística, custo, parsing."""

from __future__ import annotations

import pytest

from src.routing.intent_classifier import IntentClassifier


@pytest.fixture
def clf():
    return IntentClassifier(llm_enabled=False)


# ── classify (caminho heurístico) ────────────────────────────────────────────
async def test_classify_usa_heuristica_quando_llm_off(clf):
    intent = await clf.classify("status do TJSP")
    assert intent.operacao == "status_check"
    assert "LLM indisponível" in intent.reasoning


# ── _keyword_classify: ramos de operação ─────────────────────────────────────
def test_keyword_comparacao(clf):
    assert clf._keyword_classify("comparar TJSP e TJMG").operacao == (
        "jurisprudence_comparison"
    )


def test_keyword_movimentacoes(clf):
    assert clf._keyword_classify("andamento do processo").operacao == (
        "process_movements"
    )


def test_keyword_jurisprudencia(clf):
    assert clf._keyword_classify("buscar jurisprudência recente").operacao == (
        "jurisprudence_search"
    )


def test_keyword_generico_vago_baixa_confianca(clf):
    intent = clf._keyword_classify("olá tudo bem")
    assert intent.operacao == "generic"
    assert intent.confidence <= 0.5


def test_keyword_fallback_reason_no_reasoning(clf):
    intent = clf._keyword_classify("status", fallback_reason="motivo-x")
    assert "motivo-x" in intent.reasoning


# ── should_use_llm ───────────────────────────────────────────────────────────
def test_should_use_llm_texto_longo(clf):
    assert clf.should_use_llm("x" * 60) is True


def test_should_use_llm_keyword_complexa(clf):
    assert clf.should_use_llm("analisar tendência") is True


def test_should_use_llm_dois_tribunais(clf):
    assert clf.should_use_llm("TJSP e TJMG") is True


def test_should_use_llm_simples_false(clf):
    assert clf.should_use_llm("status") is False


# ── _parse_llm_output ────────────────────────────────────────────────────────
def test_parse_llm_output_json_puro(clf):
    assert clf._parse_llm_output('{"operacao": "x"}') == {"operacao": "x"}


def test_parse_llm_output_markdown(clf):
    raw = '```json\n{"operacao": "y"}\n```'
    assert clf._parse_llm_output(raw) == {"operacao": "y"}


def test_parse_llm_output_extrai_json_em_texto(clf):
    raw = 'O resultado é {"operacao": "z"} conforme análise.'
    assert clf._parse_llm_output(raw) == {"operacao": "z"}


# ── _estimate_cost ───────────────────────────────────────────────────────────
def test_estimate_cost_positivo(clf):
    assert clf._estimate_cost("uma consulta qualquer") >= 0.0

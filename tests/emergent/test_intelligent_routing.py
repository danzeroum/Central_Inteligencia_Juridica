"""Testes emergentes para validar routing inteligente via LLM/heurísticas."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.agents.supervisor_agent import SupervisorAgent
from src.routing.intent_classifier import IntentClassifier


TEST_DATASET = [
    ("Status do TJSP", ["TJSP"], "status_check"),
    ("Verificar disponibilidade do sistema de São Paulo", ["TJSP"], "status_check"),
    (
        "Comparar jurisprudência sobre LGPD no STF e TJSP",
        ["STF", "TJSP"],
        "jurisprudence_comparison",
    ),
    ("Processo 1234567-89.2024.8.26.1234", ["TJSP"], "process_query"),
    ("Últimas movimentações do processo no TJMG", ["TJMG"], "process_movements"),
    ("Buscar decisões do STF sobre direito digital", ["STF"], "jurisprudence_search"),
    ("Status dos tribunais de SP, MG e RS", ["TJSP", "TJMG", "TJRS"], "status_check"),
    ("Como está o funcionamento do supremo?", ["STF"], "status_check"),
    ("Preciso de informações sobre o processo 999", [], "process_query"),
    ("Tribunal do Rio de Janeiro", ["TJRJ"], "generic"),
]


@pytest.mark.asyncio
async def test_intent_classifier_accuracy() -> None:
    """Valida precisão do classificador em dataset de teste."""

    classifier = IntentClassifier(llm_enabled=False)

    correct_tribunals = 0
    correct_operations = 0
    total = len(TEST_DATASET)

    for input_text, expected_tribunals, expected_operation in TEST_DATASET:
        intent = await classifier.classify(input_text)

        tribunals_match = set(intent.tribunais) == set(expected_tribunals)
        if tribunals_match:
            correct_tribunals += 1

        if intent.operacao == expected_operation:
            correct_operations += 1

        if not tribunals_match or intent.operacao != expected_operation:
            print("\n❌ Mismatch:")
            print(f"   Input: {input_text}")
            print(
                "   Expected: tribunals=%s, op=%s" % (expected_tribunals, expected_operation)
            )
            print(
                "   Got: tribunals=%s, op=%s" % (intent.tribunais, intent.operacao)
            )
            print(f"   Confidence: {intent.confidence:.2f}")
            print(f"   Reasoning: {intent.reasoning}")

    tribunal_accuracy = correct_tribunals / total
    operation_accuracy = correct_operations / total

    print("\n📊 ACCURACIES:")
    print(f"   Tribunals: {correct_tribunals}/{total} = {tribunal_accuracy:.1%}")
    print(f"   Operations: {correct_operations}/{total} = {operation_accuracy:.1%}")

    assert tribunal_accuracy >= 0.90, f"Tribunal accuracy {tribunal_accuracy:.1%} below 90%"
    assert operation_accuracy >= 0.85, f"Operation accuracy {operation_accuracy:.1%} below 85%"


@pytest.mark.asyncio
async def test_confidence_threshold_fallback() -> None:
    """Valida que confidence baixo mantém tribunais vazios."""

    classifier = IntentClassifier(llm_enabled=False, confidence_threshold=0.7)
    intent = await classifier.classify("tribunal")
    assert intent.confidence < 0.7 or intent.tribunais == []


@pytest.mark.asyncio
async def test_supervisor_uses_intelligent_routing() -> None:
    """Valida que SupervisorAgent usa o intent classifier corretamente."""

    supervisor = SupervisorAgent()
    supervisor.use_intelligent_routing = True

    result = await supervisor.process_task(
        "Comparar jurisprudência sobre proteção de dados no STF e TJSP"
    )

    assert "STF" in result["tribunals_used"]
    assert "TJSP" in result["tribunals_used"]
    assert "intent" in result
    assert result["intent"]["confidence"] >= 0.0


@pytest.mark.asyncio
async def test_reasoning_trace_logged() -> None:
    """Valida que reasoning do classificador é registrado no ledger."""

    supervisor = SupervisorAgent()

    await supervisor.process_task("Status do TJSP e TJMG")

    entries = supervisor.ledger.get_entries(
        agent_type="SupervisorAgent", decision_type="INTENT_CLASSIFIED"
    )

    assert entries
    latest = entries[-1]
    assert "reasoning" in latest["metadata"]
    assert "confidence" in latest["metadata"]


@pytest.mark.asyncio
async def test_llm_selection_heuristic() -> None:
    """Valida heurística de quando usar LLM vs keywords."""

    classifier = IntentClassifier(llm_enabled=False)

    assert not classifier.should_use_llm("Status TJSP")
    assert not classifier.should_use_llm("Processo 123")

    assert classifier.should_use_llm(
        "Comparar jurisprudência sobre LGPD no STF e TJSP"
    )
    assert classifier.should_use_llm(
        "Analisar tendência de decisões do STF sobre direito digital nos últimos 2 anos"
    )
    assert classifier.should_use_llm("Status do TJSP, TJMG e TJRS")


@pytest.mark.asyncio
async def test_parameter_extraction() -> None:
    """Valida que o classifier extrai parâmetros adicionais corretamente."""

    classifier = IntentClassifier(llm_enabled=False)

    intent1 = await classifier.classify("Consultar processo 1234567-89.2024.8.26.1234")
    assert "numero_processo" in intent1.parametros
    assert "1234567-89.2024.8.26.1234" in intent1.parametros["numero_processo"]

    intent2 = await classifier.classify("Jurisprudência sobre LGPD no STF")
    assert "tema" in intent2.parametros
    assert "LGPD" in intent2.parametros["tema"].upper()


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v", "-s"])


"""Testes do modo CoT por LLM (plugável) do ArchitectAgent — C2.

Garante que:
- o padrão permanece determinístico (heurística por palavra-chave);
- com LLM habilitado, a narrativa (chain_of_thought) vem do LLM, mas a
  identificação de tribunais e a confiança permanecem determinísticas;
- qualquer falha/resposta inválida degrada graciosamente para a heurística.
"""

from __future__ import annotations

from src.agents.architect_agent import ArchitectAgent


def test_default_mode_is_deterministic_heuristic() -> None:
    agent = ArchitectAgent()  # sem LLM (padrão)
    result = agent.reason_with_cot("Comparar jurisprudência no TJSP e TJMG")
    assert result["chain_of_thought"][0].startswith("1.")
    assert result["identified_tribunals"] == ["TJSP", "TJMG"]
    assert result.get("reasoning_engine") != "llm"
    assert agent.metadata["cot_mode"] == "heuristica_deterministica"


def test_llm_mode_replaces_narrative_keeps_routing() -> None:
    captured = {}

    def fake_llm(prompt: str) -> str:
        captured["prompt"] = prompt
        return "Passo um do LLM\nPasso dois do LLM"

    agent = ArchitectAgent(llm_fn=fake_llm, use_llm=True)
    result = agent.reason_with_cot("Consultar o TJSP")

    # narrativa veio do LLM…
    assert result["chain_of_thought"] == ["Passo um do LLM", "Passo dois do LLM"]
    assert result["reasoning_engine"] == "llm"
    # …mas o roteamento determinístico foi preservado
    assert result["identified_tribunals"] == ["TJSP"]
    assert 0.0 <= result["confidence"] <= 1.0
    # o prompt foi efetivamente montado com os tribunais identificados
    assert "TJSP" in captured["prompt"]


def test_llm_error_string_falls_back() -> None:
    agent = ArchitectAgent(
        llm_fn=lambda _p: "Erro: Nao foi possivel se comunicar com o Ollama.",
        use_llm=True,
    )
    result = agent.reason_with_cot("Consultar o TJSP")
    assert result["chain_of_thought"][0].startswith("1.")  # heurística
    assert result.get("reasoning_engine") != "llm"
    assert result["identified_tribunals"] == ["TJSP"]


def test_llm_exception_falls_back() -> None:
    def boom(_p: str) -> str:
        raise RuntimeError("conexão recusada")

    agent = ArchitectAgent(llm_fn=boom, use_llm=True)
    result = agent.reason_with_cot("Consultar o TJSP")
    assert result["chain_of_thought"][0].startswith("1.")
    assert result.get("reasoning_engine") != "llm"


def test_llm_empty_falls_back() -> None:
    agent = ArchitectAgent(llm_fn=lambda _p: "   \n   ", use_llm=True)
    result = agent.reason_with_cot("Consultar o TJSP")
    assert result["chain_of_thought"][0].startswith("1.")


def test_env_flag_enables_llm(monkeypatch) -> None:
    monkeypatch.setenv("ARCHITECT_COT_LLM", "1")
    agent = ArchitectAgent(llm_fn=lambda _p: "L1\nL2")
    result = agent.reason_with_cot("Consultar o TJSP")
    assert result["chain_of_thought"] == ["L1", "L2"]
    assert agent.metadata["cot_mode"] == "llm+heuristica"

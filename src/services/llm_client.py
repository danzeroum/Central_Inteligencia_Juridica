"""Cliente utilitário para interação com o Ollama."""

from __future__ import annotations

import importlib
import importlib.util
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class _ChatClient(Protocol):
    """Protocolo mínimo esperado do cliente do Ollama."""

    def chat(self, *, model: str, messages: list[dict[str, str]]) -> dict:  # pragma: no cover - assinatura do SDK
        """Executa uma chamada de chat no modelo informado."""


def _load_ollama_client() -> Optional[_ChatClient]:
    """Retorna o módulo do Ollama caso esteja disponível no ambiente."""

    if importlib.util.find_spec("ollama") is None:
        return None

    return importlib.import_module("ollama")


_OLLAMA_CLIENT: Optional[_ChatClient] = _load_ollama_client()


def gerar_resposta_ollama(prompt: str, modelo: str = "llama3") -> str:
    """
    Envia um prompt para o modelo local do Ollama e retorna a resposta.
    """
    if _OLLAMA_CLIENT is None:
        return "Erro: Cliente Ollama nao está instalado no ambiente."

    print(f"\n[LLM Client] Enviando prompt para o modelo '{modelo}'...")
    try:
        response = _OLLAMA_CLIENT.chat(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
        )
        print("[LLM Client] Resposta recebida do Ollama.")
        return response["message"]["content"]
    except Exception as e:  # pragma: no cover - interação com serviço externo
        print(f"ERRO AO CONECTAR COM O OLLAMA: {e}")
        return "Erro: Nao foi possivel se comunicar com o Ollama."


if __name__ == "__main__":
    print("--- Testando conexao direta com o Ollama ---")
    resposta = gerar_resposta_ollama("Qual a capital do Brasil?")
    print(f"\nResposta do Teste: {resposta}")

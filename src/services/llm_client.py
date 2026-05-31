import logging
import os
from typing import Optional

import ollama

logger = logging.getLogger(__name__)

# SECURITY/BUGFIX (CRÍTICO-05): o cliente Ollama é criado preguiçosamente (lazy)
# e memoizado. A versão anterior referenciava ``_OLLAMA_CLIENT`` sem nunca
# defini-lo, causando ``NameError`` imediato em ``gerar_resposta_ollama``. O host
# vem de ``OLLAMA_BASE_URL`` (cloud-friendly) e, se o serviço estiver indisponível,
# a função degrada graciosamente em vez de derrubar o chamador.
_OLLAMA_CLIENT: Optional["ollama.Client"] = None


def _get_ollama_client() -> "ollama.Client":
    """Retorna (criando sob demanda) o cliente Ollama memoizado."""

    global _OLLAMA_CLIENT
    if _OLLAMA_CLIENT is None:
        host = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        _OLLAMA_CLIENT = ollama.Client(host=host)
    return _OLLAMA_CLIENT


def gerar_resposta_ollama(prompt: str, modelo: str = "llama3") -> str:
    """
    Envia um prompt para o modelo local do Ollama e retorna a resposta.
    """
    logger.info("Enviando prompt para o modelo '%s'", modelo)
    try:
        response = _get_ollama_client().chat(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
        )
        logger.info("Resposta recebida do Ollama.")
        return response["message"]["content"]
    except Exception as e:  # pragma: no cover - interação com serviço externo
        logger.error("Erro ao conectar com o Ollama: %s", e)
        return "Erro: Nao foi possivel se comunicar com o Ollama."


if __name__ == "__main__":
    print("--- Testando conexao direta com o Ollama ---")
    resposta = gerar_resposta_ollama("Qual a capital do Brasil?")
    print(f"\nResposta do Teste: {resposta}")

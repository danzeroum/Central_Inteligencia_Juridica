import logging

import ollama

logger = logging.getLogger(__name__)


def gerar_resposta_ollama(prompt: str, modelo: str = "llama3") -> str:
    """
    Envia um prompt para o modelo local do Ollama e retorna a resposta.
    """
    logger.info("Enviando prompt para o modelo '%s'", modelo)
    try:
        response = ollama.chat(
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

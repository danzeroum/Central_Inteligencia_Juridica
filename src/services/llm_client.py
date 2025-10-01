import ollama


def gerar_resposta_ollama(prompt: str, modelo: str = "llama3") -> str:
    """
    Envia um prompt para o modelo local do Ollama e retorna a resposta.
    """
    print(f"\n[LLM Client] Enviando prompt para o modelo '{modelo}'...")
    try:
        response = ollama.chat(
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

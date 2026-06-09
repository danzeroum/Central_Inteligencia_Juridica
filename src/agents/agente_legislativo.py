import logging
import os
from typing import Optional

from src.services.camara_client import buscar_projetos_de_lei
from src.services.llm_client import gerar_resposta_ollama

logger = logging.getLogger(__name__)


def _gerar_analise_openai(prompt: str) -> Optional[str]:
    """Gera análise via OpenAI/compatível. Retorna None se indisponível."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import openai  # noqa: PLC0415

        base_url = os.getenv("OPENAI_BASE_URL") or None
        client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=60)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.4,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.warning("OpenAI indisponível para análise legislativa: %s", exc)
        return None


def analisar_cenario_legislativo(tema: str) -> str:
    """Analisa o cenário legislativo de um tema (Câmara + LLM).

    Cadeia de fallback: OpenAI → Ollama → mensagem informativa.
    """
    logger.info("Buscando dados sobre '%s'", tema)
    dados_projetos = buscar_projetos_de_lei(tema)
    if "error" in dados_projetos or not dados_projetos.get("dados"):
        return "Não foi possível obter dados legislativos sobre este tema."

    contexto = "Projetos de Lei encontrados:\n"
    for projeto in dados_projetos["dados"][:5]:
        ementa_limpa = projeto.get("ementa", "").replace("\n", " ")
        contexto += (
            f"- {projeto.get('siglaTipo')} {projeto.get('numero')}/{projeto.get('ano')}: "
            f"{ementa_limpa}\n"
        )

    prompt = (
        f"Com base nos seguintes projetos de lei recentes sobre '{tema}', "
        "elabore uma análise concisa (2-3 parágrafos) sobre o foco atual do "
        f"legislativo neste assunto.\nDados:\n{contexto}\nAnálise:"
    )

    # Tenta OpenAI primeiro (mais rápido e disponível em produção)
    resultado = _gerar_analise_openai(prompt)
    if resultado:
        logger.info("Análise legislativa gerada via OpenAI.")
        return resultado

    # Fallback: Ollama local
    logger.info("Tentando análise via Ollama...")
    resultado = gerar_resposta_ollama(prompt)
    if resultado and not resultado.startswith("Erro:"):
        return resultado

    return (
        "Análise de IA temporariamente indisponível. "
        "Configure OPENAI_API_KEY ou inicie o serviço Ollama para habilitar esta funcionalidade."
    )


def main():
    print("--- Iniciando teste do Agente Legislativo ---")
    tema_teste = "inteligencia artificial"
    resultado_analise = analisar_cenario_legislativo(tema_teste)
    print("\n--- Resultado da Analise ---")
    print(resultado_analise)
    print("----------------------------")


if __name__ == "__main__":
    main()

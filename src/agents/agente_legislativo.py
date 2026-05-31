import logging

from src.services.camara_client import buscar_projetos_de_lei
from src.services.llm_client import gerar_resposta_ollama

logger = logging.getLogger(__name__)


def analisar_cenario_legislativo(tema: str) -> str:
    """Analisa o cenário legislativo de um tema (Câmara dos Deputados + LLM).

    NOTA DE PROJETO (H16): este é um *serviço funcional* exposto diretamente pelo
    endpoint ``/analise-legislativa`` — intencionalmente NÃO modelado como um
    ``BaseAgent`` do framework A2A, pois é uma consulta stateless sem
    coordenação multiagente. Mantê-lo como função evita acoplamento desnecessário.
    """

    logger.info("Buscando dados sobre '%s'", tema)
    dados_projetos = buscar_projetos_de_lei(tema)
    if "error" in dados_projetos or not dados_projetos.get("dados"):
        return "Nao foi possivel obter dados legislativos sobre este tema."

    contexto = "Projetos de Lei encontrados:\n"
    for projeto in dados_projetos["dados"][:3]:
        ementa_limpa = projeto.get("ementa", "").replace("\n", " ")
        contexto += (
            f"- {projeto.get('siglaTipo')} {projeto.get('numero')}/{projeto.get('ano')}: "
            f"{ementa_limpa}\n"
        )

    prompt = f"""
    Com base na seguinte lista de projetos de lei recentes sobre '{tema}', 
    elabore uma analise concisa (2-3 paragrafos) sobre o foco atual do legislativo neste assunto.
    Dados:\n{contexto}\nAnalise:
    """
    logger.info("Enviando contexto para analise do Ollama...")
    analise_final = gerar_resposta_ollama(prompt)
    return analise_final


def main():
    print("--- Iniciando teste do Agente Legislativo ---")
    tema_teste = "inteligencia artificial"
    resultado_analise = analisar_cenario_legislativo(tema_teste)
    print("\n--- Resultado da Analise ---")
    print(resultado_analise)
    print("----------------------------")


if __name__ == "__main__":
    main()

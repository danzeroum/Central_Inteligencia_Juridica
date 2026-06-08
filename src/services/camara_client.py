import logging

import httpx

logger = logging.getLogger(__name__)

CAMARA_API_URL = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"


def buscar_projetos_de_lei(
    termo_busca: str, *, pagina: int = 1, itens: int = 15
) -> dict:
    """Busca proposições na API da Câmara com suporte a paginação."""

    logger.info(
        "Buscando projetos com o termo: '%s' (página %d, %d itens)",
        termo_busca,
        pagina,
        itens,
    )
    try:
        params = {
            "keywords": termo_busca,
            "ordem": "DESC",
            "ordenarPor": "ano",
            "pagina": pagina,
            "itens": min(max(itens, 1), 100),
        }
        headers = {"Accept": "application/json"}
        with httpx.Client(timeout=20.0) as client:
            response = client.get(CAMARA_API_URL, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        return {
            "error": f"Falha ao buscar dados na Camara: Status {e.response.status_code}"
        }
    except Exception as e:  # pragma: no cover - dependência externa
        return {"error": f"Erro interno ao conectar com a API da Camara: {e}"}

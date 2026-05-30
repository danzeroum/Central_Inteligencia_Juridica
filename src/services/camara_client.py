import httpx

CAMARA_API_URL = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"


def buscar_projetos_de_lei(termo_busca: str) -> dict:
    """
    Busca por proposições na API da Câmara e retorna o dicionário JSON.
    """
    print(f"[Camara Client] Buscando projetos com o termo: '{termo_busca}'...")
    try:
        params = {"keywords": termo_busca, "ordem": "DESC", "ordenarPor": "ano"}
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

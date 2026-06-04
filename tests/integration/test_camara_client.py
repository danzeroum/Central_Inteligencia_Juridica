"""Cobertura do cliente da API da Câmara (Frente C cont.).

respx mocka a API de dados abertos da Câmara — determinístico, sem rede.
"""

from __future__ import annotations

import httpx
import respx

from src.services.camara_client import CAMARA_API_URL, buscar_projetos_de_lei


@respx.mock
def test_busca_retorna_json():
    respx.get(url__startswith=CAMARA_API_URL).mock(
        return_value=httpx.Response(200, json={"dados": [{"id": 1}]})
    )
    resultado = buscar_projetos_de_lei("reforma")
    assert resultado == {"dados": [{"id": 1}]}


@respx.mock
def test_status_error_retorna_dict_de_erro():
    respx.get(url__startswith=CAMARA_API_URL).mock(return_value=httpx.Response(503))
    resultado = buscar_projetos_de_lei("reforma")
    assert "error" in resultado
    assert "503" in resultado["error"]

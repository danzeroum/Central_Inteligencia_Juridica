"""Adapter para APIs reais dos tribunais com fallback para mock."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.tools.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from src.tools.schemas.tribunal_schemas import (
    ProcessoResponse,
    TribunalStatusResponse,
)

logger = logging.getLogger(__name__)


class TribunalAPIAdapter:
    """Adaptador para APIs reais com fallback automático."""

    API_CONFIGS: Dict[str, Dict[str, Any]] = {
        "TJSP": {
            "base_url": "https://api.tjsp.jus.br/v2",
            "auth_type": "bearer",
            "timeout": 10.0,
        },
        "TJMG": {
            "base_url": "https://api5.tjmg.jus.br",
            "auth_type": "api_key",
            "timeout": 10.0,
        },
    }

    def __init__(self, tribunal_code: str) -> None:
        self.tribunal_code = tribunal_code
        self.config = self.API_CONFIGS.get(tribunal_code)

        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)

        self.client: Optional[httpx.Client] = None
        if self.config:
            timeout = httpx.Timeout(self.config.get("timeout", 10.0))
            self.client = httpx.Client(
                base_url=self.config["base_url"],
                timeout=timeout,
                headers=self._get_auth_headers(),
            )

    def get_status(self) -> Dict[str, Any]:
        """Obtém status do tribunal com fallback para mock."""

        if not self.config or not self.client:
            logger.info("No API config for %s, using mock", self.tribunal_code)
            return self._get_mock_status()

        try:
            payload = self.circuit_breaker.call(self._fetch_status_from_api)
            validated = TribunalStatusResponse(**payload)
            data = validated.model_dump()
            data["_metadata"] = {
                "source": "real_api",
                "tribunal": self.tribunal_code,
                "timestamp": time.time(),
            }
            logger.info("✅ Real API success for %s", self.tribunal_code)
            return data
        except CircuitBreakerOpenError:
            logger.warning(
                "Circuit breaker OPEN for %s, falling back to mock", self.tribunal_code
            )
        except Exception as exc:
            logger.warning(
                "API call failed for %s: %s, using mock", self.tribunal_code, exc
            )

        return self._get_mock_status()

    def get_processo(self, numero_processo: str) -> Dict[str, Any]:
        """Consulta dados de um processo com fallback."""

        if not self.config or not self.client:
            return self._get_mock_processo(numero_processo)

        try:
            payload = self.circuit_breaker.call(
                self._fetch_processo_from_api, numero_processo
            )
            validated = ProcessoResponse(**payload)
            data = validated.model_dump()
            data["_metadata"] = {
                "source": "real_api",
                "tribunal": self.tribunal_code,
                "timestamp": time.time(),
            }
            return data
        except CircuitBreakerOpenError:
            logger.warning(
                "Circuit breaker OPEN for %s, returning mock processo", self.tribunal_code
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch processo for %s: %s, using mock",
                self.tribunal_code,
                exc,
            )

        return self._get_mock_processo(numero_processo)

    def get_circuit_breaker_state(self) -> Dict[str, Any]:
        """Retorna o estado atual do circuit breaker."""

        return self.circuit_breaker.get_state()

    def close(self) -> None:
        """Fecha o cliente HTTP subjacente."""

        if self.client:
            self.client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    def _fetch_status_from_api(self) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("HTTP client not initialized")

        endpoint = "/status" if self.tribunal_code == "TJSP" else "/api/status"
        response = self.client.get(endpoint)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    def _fetch_processo_from_api(self, numero_processo: str) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("HTTP client not initialized")

        endpoint = "/processos/{numero}" if self.tribunal_code == "TJSP" else "/api/processos/{numero}"
        response = self.client.get(endpoint.format(numero=numero_processo))
        response.raise_for_status()
        return response.json()

    def _get_auth_headers(self) -> Dict[str, str]:
        if not self.config:
            return {}

        auth_type = self.config.get("auth_type")
        if auth_type == "bearer":
            token = os.getenv(f"{self.tribunal_code}_API_TOKEN")
            if token:
                return {"Authorization": f"Bearer {token}"}
        elif auth_type == "api_key":
            api_key = os.getenv(f"{self.tribunal_code}_API_KEY")
            if api_key:
                return {"X-API-Key": api_key}

        return {}

    def _get_mock_status(self) -> Dict[str, Any]:
        mock_data = {
            "TJSP": {
                "status": "operacional",
                "ultima_atualizacao": "2025-09-29T20:00:00Z",
                "mensagem": "Sistema funcionando normalmente (MOCK)",
                "servicos_ativos": 95,
            },
            "TJMG": {
                "status": "instabilidade",
                "ultima_atualizacao": "2025-09-29T19:30:00Z",
                "mensagem": "Manutenção em andamento (MOCK)",
                "servicos_ativos": 78,
            },
        }

        data = mock_data.get(
            self.tribunal_code,
            {
                "status": "offline",
                "ultima_atualizacao": "2025-09-29T18:00:00Z",
                "mensagem": "Tribunal não configurado (MOCK)",
                "servicos_ativos": 0,
            },
        )

        data = dict(data)
        data["_metadata"] = {
            "source": "simulated",
            "tribunal": self.tribunal_code,
            "fallback": True,
            "timestamp": time.time(),
        }
        return data

    def _get_mock_processo(self, numero_processo: str) -> Dict[str, Any]:
        data = {
            "numero_processo": numero_processo,
            "situacao": "Em andamento",
            "classe_processual": "Procedimento Ordinário",
            "assunto": "Direito Civil",
            "ultima_movimentacao": "2025-09-29T10:30:00Z",
            "orgao_julgador": "1ª Vara Cível",
            "valor_causa": "R$ 45.000,00",
        }

        data["_metadata"] = {
            "source": "simulated",
            "tribunal": self.tribunal_code,
            "fallback": True,
            "timestamp": time.time(),
        }
        return data


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)

    adapter_tjsp = TribunalAPIAdapter("TJSP")
    status_tjsp = adapter_tjsp.get_status()
    print(f"\n✅ TJSP Status: {status_tjsp.get('status')}")
    print(f"   Source: {status_tjsp['_metadata']['source']}")

    adapter_tjmg = TribunalAPIAdapter("TJMG")
    status_tjmg = adapter_tjmg.get_status()
    print(f"\n✅ TJMG Status: {status_tjmg.get('status')}")
    print(f"   Source: {status_tjmg['_metadata']['source']}")

    processo = adapter_tjsp.get_processo("1234567-89.2025.8.26.0100")
    print(f"\n✅ Processo: {processo.get('numero_processo')}")
    print(f"   Source: {processo['_metadata']['source']}")

    adapter_tjsp.close()
    adapter_tjmg.close()

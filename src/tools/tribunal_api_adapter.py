"""Adapter para APIs reais dos tribunais com fallback para mock."""

from __future__ import annotations

import logging
import os
import re
import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.tools.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
)
from src.tools.schemas.tribunal_schemas import ProcessoResponse, TribunalStatusResponse

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple thread-safe rate limiter using a sliding time window."""

    def __init__(self, max_calls: int, period_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self._timestamps: Deque[float] = deque()
        self._lock = Lock()

    def acquire(self) -> None:
        """Blocks until a slot is available respecting the configured rate."""

        if self.max_calls <= 0:
            return

        while True:
            with self._lock:
                now = time.monotonic()
                window_start = now - self.period_seconds

                while self._timestamps and self._timestamps[0] <= window_start:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(now)
                    return

                oldest = self._timestamps[0]
                sleep_time = self.period_seconds - (now - oldest)

            if sleep_time <= 0:
                time.sleep(0)
            else:
                time.sleep(sleep_time)


DEFAULT_CIRCUIT_CONFIG = CircuitBreakerConfig(
    name="tribunal_api_default",
    failure_threshold=3,
    recovery_timeout=30.0,
    success_threshold=2,
    half_open_max_calls=2,
)


TRIBUNAL_CIRCUIT_CONFIGS: Dict[str, CircuitBreakerConfig] = {
    "TJSP": CircuitBreakerConfig(
        name="tribunal_api_TJSP",
        failure_threshold=3,
        recovery_timeout=30.0,
        success_threshold=2,
        half_open_max_calls=2,
    ),
    "TJMG": CircuitBreakerConfig(
        name="tribunal_api_TJMG",
        failure_threshold=3,
        recovery_timeout=30.0,
        success_threshold=2,
        half_open_max_calls=2,
    ),
}


class TribunalAPIAdapter:
    """Adaptador para APIs reais com fallback automático."""

    API_CONFIGS: Dict[str, Dict[str, Any]] = {
        "TJSP": {
            "base_url": "https://api.tjsp.jus.br/v2",
            "auth_type": "bearer",
            "timeout": 10.0,
            "rate_limit": {"requests": 100, "per_seconds": 60.0},
        },
        "TJMG": {
            "base_url": "https://api5.tjmg.jus.br",
            "auth_type": "api_key",
            "timeout": 10.0,
            "rate_limit": {"requests": 60, "per_seconds": 60.0},
        },
    }

    def __init__(self, tribunal_code: str) -> None:
        self.tribunal_code = tribunal_code
        self.config = self.API_CONFIGS.get(tribunal_code)

        self.circuit_breaker = CircuitBreaker(
            config=self._build_circuit_config(tribunal_code)
        )

        self.client: Optional[httpx.Client] = None
        self.rate_limiter: Optional[RateLimiter] = None
        if self.config:
            timeout = httpx.Timeout(self.config.get("timeout", 10.0))
            self.client = httpx.Client(
                base_url=self.config["base_url"],
                timeout=timeout,
                headers=self._get_auth_headers(),
            )
            rate_limit_conf = self.config.get("rate_limit")
            if rate_limit_conf:
                self.rate_limiter = RateLimiter(
                    max_calls=int(rate_limit_conf.get("requests", 0)),
                    period_seconds=float(rate_limit_conf.get("per_seconds", 60.0)),
                )

    def get_status(self) -> Dict[str, Any]:
        """Obtém status do tribunal com fallback para mock."""

        if not self.config or not self.client:
            logger.info("No API config for %s, using mock", self.tribunal_code)
            return self._augment_with_circuit(self._get_mock_status())

        try:
            payload = self.circuit_breaker.call(self._fetch_status_from_api)
            validated = TribunalStatusResponse(**payload)
            data = validated.model_dump()
            data["_metadata"] = {
                "source": "real_api",
                "tribunal": self.tribunal_code,
                "timestamp": time.time(),
            }
            data["_metadata"]["circuit_breaker"] = self.get_circuit_stats()
            logger.info("✅ Real API success for %s", self.tribunal_code)
            return data
        except CircuitBreakerOpenError as exc:
            logger.warning(
                "Circuit breaker OPEN for %s, falling back to mock", self.tribunal_code
            )
            return self._augment_with_circuit(
                self._get_mock_status(),
                circuit_error=exc,
            )
        except Exception as exc:
            logger.warning(
                "API call failed for %s: %s, using mock", self.tribunal_code, exc
            )
        return self._augment_with_circuit(self._get_mock_status())

    def get_processo(self, numero_processo: str) -> Dict[str, Any]:
        """Consulta dados de um processo: API do tribunal → DataJud → mock."""

        if not self.config or not self.client:
            datajud = self._try_datajud_sync(numero_processo)
            if datajud is not None:
                return self._augment_with_circuit(datajud)
            return self._augment_with_circuit(self._get_mock_processo(numero_processo))

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
            data["_metadata"]["circuit_breaker"] = self.get_circuit_stats()
            return data
        except CircuitBreakerOpenError as exc:
            logger.warning(
                "Circuit breaker OPEN for %s, trying DataJud fallback",
                self.tribunal_code,
            )
            datajud = self._try_datajud_sync(numero_processo)
            if datajud is not None:
                return self._augment_with_circuit(datajud)
            return self._augment_with_circuit(
                self._get_mock_processo(numero_processo),
                circuit_error=exc,
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch processo for %s: %s, trying DataJud",
                self.tribunal_code,
                exc,
            )
            datajud = self._try_datajud_sync(numero_processo)
            if datajud is not None:
                return self._augment_with_circuit(datajud)
        return self._augment_with_circuit(self._get_mock_processo(numero_processo))

    def _try_datajud_sync(self, numero_processo: str) -> Optional[Dict[str, Any]]:
        """Busca o processo no DataJud via httpx síncrono.

        Retorna dict com ``_metadata.source='datajud'`` em sucesso, ``None`` em
        falha (sem chave, erro de rede ou processo não encontrado).
        """
        api_key = os.getenv("DATAJUD_API_KEY")
        if not api_key:
            return None

        alias = self.tribunal_code.lower()
        endpoint = f"https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search"
        # DataJud armazena o número no formato normalizado: apenas dígitos, 20 chars
        normalized = re.sub(r"[^0-9]", "", numero_processo).zfill(20)
        query: Dict[str, Any] = {
            "query": {"match": {"numeroProcesso": normalized}},
            "size": 1,
        }
        headers = {
            "Authorization": f"APIKey {api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(endpoint, json=query, headers=headers)
                response.raise_for_status()
                raw = response.json()

            hits_block = raw.get("hits", {}) or {}
            total_block = hits_block.get("total", 0)
            total = (
                total_block.get("value", 0)
                if isinstance(total_block, dict)
                else int(total_block or 0)
            )
            hit_list = hits_block.get("hits") or []

            if not hit_list:
                logger.info(
                    "DataJud: processo %s não encontrado para %s",
                    numero_processo,
                    alias,
                )
                return None

            src: Dict[str, Any] = (
                (hit_list[0].get("_source") or {})
                if isinstance(hit_list[0], dict)
                else {}
            )
            assuntos_nomes = (
                ", ".join(
                    a.get("nome", "")
                    for a in (src.get("assuntos") or [])
                    if isinstance(a, dict) and a.get("nome")
                )
                or "Não informado"
            )

            data: Dict[str, Any] = {
                "numero_processo": src.get("numeroProcesso", numero_processo),
                "situacao": src.get("situacao", "Não informado"),
                "classe_processual": (src.get("classe") or {}).get(
                    "nome", "Não informado"
                ),
                "assunto": assuntos_nomes,
                "ultima_movimentacao": src.get("dataHoraUltimaAtualizacao", ""),
                "orgao_julgador": (src.get("orgaoJulgador") or {}).get(
                    "nome", "Não informado"
                ),
                "valor_causa": src.get("valorCausa", "Não informado"),
                "grau": src.get("grau"),
                "data_ajuizamento": src.get("dataAjuizamento"),
                "tribunal": src.get("tribunal", self.tribunal_code),
                "_metadata": {
                    "source": "datajud",
                    "tribunal": self.tribunal_code,
                    "fallback": False,
                    "timestamp": time.time(),
                    "total_found": total,
                },
            }
            logger.info("✅ DataJud hit para processo %s (%s)", numero_processo, alias)
            return data

        except Exception as exc:
            logger.warning(
                "DataJud sync falhou para %s / %s: %s", alias, numero_processo, exc
            )
            return None

    def get_circuit_breaker_state(self) -> Dict[str, Any]:
        """Retorna o estado atual do circuit breaker."""

        return self.get_circuit_stats()

    def get_circuit_stats(self) -> Dict[str, Any]:
        """Expose circuit breaker metrics for observability."""

        return self.circuit_breaker.get_state()

    def reset_circuit(self) -> None:
        """Reset circuit breaker forcing CLOSED state."""

        self.circuit_breaker.reset()

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
        return self._perform_request(endpoint)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    def _fetch_processo_from_api(self, numero_processo: str) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("HTTP client not initialized")

        endpoint = (
            "/processos/{numero}"
            if self.tribunal_code == "TJSP"
            else "/api/processos/{numero}"
        )
        return self._perform_request(endpoint.format(numero=numero_processo))

    def _perform_request(self, endpoint: str) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("HTTP client not initialized")

        if self.rate_limiter:
            self.rate_limiter.acquire()

        response = self.client.get(endpoint)
        response.raise_for_status()
        return response.json()

    def _build_circuit_config(self, tribunal_code: str) -> CircuitBreakerConfig:
        base_config = TRIBUNAL_CIRCUIT_CONFIGS.get(
            tribunal_code, DEFAULT_CIRCUIT_CONFIG
        )

        def _env(key: str, default: float) -> float:
            return float(os.getenv(key, str(default)))

        def _env_int(key: str, default: int) -> int:
            return int(os.getenv(key, str(default)))

        prefix = tribunal_code.upper()
        failure_threshold = _env_int(
            f"{prefix}_CB_FAILURE_THRESHOLD", base_config.failure_threshold
        )
        timeout_seconds = _env(
            f"{prefix}_CB_TIMEOUT_SECONDS", base_config.recovery_timeout
        )
        success_threshold = _env_int(
            f"{prefix}_CB_SUCCESS_THRESHOLD", base_config.success_threshold
        )
        half_open_calls = _env_int(
            f"{prefix}_CB_HALF_OPEN_CALLS", base_config.half_open_max_calls
        )

        return CircuitBreakerConfig(
            name=f"tribunal_api_{tribunal_code}",
            failure_threshold=failure_threshold,
            recovery_timeout=timeout_seconds,
            success_threshold=success_threshold,
            half_open_max_calls=half_open_calls,
        )

    def _augment_with_circuit(
        self,
        payload: Dict[str, Any],
        *,
        circuit_error: CircuitBreakerOpenError | None = None,
    ) -> Dict[str, Any]:
        metadata = payload.setdefault("_metadata", {})
        metadata["circuit_breaker"] = self.get_circuit_stats()
        if circuit_error:
            metadata["circuit_state"] = circuit_error.state
            if circuit_error.retry_after is not None:
                metadata["retry_after_seconds"] = circuit_error.retry_after
        return payload

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

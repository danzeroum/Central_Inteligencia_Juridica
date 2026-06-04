"""Cliente assíncrono para a API Pública do CNJ DataJud.

Decisão (Frente F.1): a fonte oficial de dados judiciais é o **DataJud** do CNJ
— uma única chave cobre 90+ tribunais (vs. APIs proprietárias por tribunal). Este
cliente segue o ADR-008 (tentativa real → fallback gracioso) reaproveitando o
``CircuitBreaker`` e o ``RateLimiter`` já existentes no projeto, porém usando
``httpx.AsyncClient`` para ser consistente com o restante do código assíncrono.

A chave vem de ``DATAJUD_API_KEY`` (header ``Authorization: APIKey <chave>``); sem
ela, o cliente degrada para mock automaticamente — desenvolvimento e CI não
dependem de rede externa.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from src.services.datajud_schemas import DataJudProcesso, DataJudSearchResult
from src.tools.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
)

logger = logging.getLogger(__name__)

DATAJUD_BASE_URL = "https://api-publica.datajud.cnj.jus.br"


def _default_breaker(alias: str) -> CircuitBreaker:
    return CircuitBreaker(
        config=CircuitBreakerConfig(
            name=f"datajud_{alias}",
            failure_threshold=int(os.getenv("DATAJUD_CB_FAILURE_THRESHOLD", "3")),
            recovery_timeout=float(os.getenv("DATAJUD_CB_TIMEOUT_SECONDS", "30")),
            success_threshold=2,
            half_open_max_calls=2,
        )
    )


class DataJudClient:
    """Cliente ``_search`` do DataJud para um alias de tribunal (ex.: ``tjsp``)."""

    def __init__(
        self,
        alias: str,
        *,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.alias = alias.strip().lower()
        self.api_key = api_key if api_key is not None else os.getenv("DATAJUD_API_KEY")
        self.timeout = timeout
        self.breaker = breaker or _default_breaker(self.alias)

    @property
    def endpoint(self) -> str:
        return f"{DATAJUD_BASE_URL}/api_publica_{self.alias}/_search"

    @property
    def configured(self) -> bool:
        """``True`` quando há chave — caso contrário o cliente usa mock."""

        return bool(self.api_key)

    async def search(self, query: Dict[str, Any]) -> DataJudSearchResult:
        """Executa um ``_search`` no DataJud com fallback gracioso.

        Retorna ``source='real_api'`` em caso de sucesso; ``source='simulated'``
        (com ``fallback=True``) quando não há chave, a rede falha ou o circuit
        breaker está aberto.
        """

        if not self.configured:
            logger.info("DataJud sem DATAJUD_API_KEY para %s; usando mock", self.alias)
            return self._mock_result(reason="sem_api_key")

        try:
            with self.breaker.protect():
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.endpoint, json=query, headers=self._headers()
                    )
                    response.raise_for_status()
                    raw = response.json()
            result = self._parse(raw)
            logger.info(
                "✅ DataJud real para %s: %d processos", self.alias, result.total
            )
            return result
        except CircuitBreakerOpenError as exc:
            logger.warning("DataJud circuit OPEN para %s; mock", self.alias)
            return self._mock_result(reason="circuit_open", circuit_error=exc)
        except Exception as exc:  # rede, HTTP, schema → fallback gracioso
            logger.warning("DataJud falhou para %s: %s; mock", self.alias, exc)
            return self._mock_result(reason=str(exc))

    def _headers(self) -> Dict[str, str]:
        # DataJud espera o esquema literal ``APIKey <chave>`` no header Authorization.
        return {
            "Authorization": f"APIKey {self.api_key}",
            "Content-Type": "application/json",
        }

    def _parse(self, raw: Dict[str, Any]) -> DataJudSearchResult:
        hits_block = raw.get("hits", {}) or {}
        total_block = hits_block.get("total", 0)
        if isinstance(total_block, dict):
            total = int(total_block.get("value", 0))
        else:
            total = int(total_block or 0)

        processos: List[DataJudProcesso] = []
        for hit in hits_block.get("hits", []) or []:
            source = hit.get("_source", {}) if isinstance(hit, dict) else {}
            processos.append(DataJudProcesso.model_validate(source))

        return DataJudSearchResult(
            total=total,
            processos=processos,
            source="real_api",
            fallback=False,
            alias=self.alias,
            circuit_breaker=self.breaker.get_state(),
        )

    def _mock_result(
        self,
        *,
        reason: str,
        circuit_error: Optional[CircuitBreakerOpenError] = None,
    ) -> DataJudSearchResult:
        """Resposta simulada (ADR-008): nunca derruba o sistema."""

        processo = DataJudProcesso(
            numeroProcesso="00000000000000000000",
            tribunal=self.alias.upper(),
            grau="G1",
            dataAjuizamento="2025-01-01T00:00:00.000Z",
            assuntos=[{"codigo": 0, "nome": "Assunto simulado (MOCK)"}],
            movimentos=[],
        )
        return DataJudSearchResult(
            total=1,
            processos=[processo],
            source="simulated",
            fallback=True,
            alias=self.alias,
            reason=reason,
            circuit_breaker=self.breaker.get_state(),
        )


__all__ = ["DataJudClient", "DATAJUD_BASE_URL"]

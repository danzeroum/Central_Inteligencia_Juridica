"""HTTP client responsible for communicating with real tribunal APIs."""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class TribunalAPIClient:
    """Synchronous HTTP client with basic rate limiting and auth handling."""

    API_ENDPOINTS: Dict[str, Dict[str, Any]] = {
        "TJSP": {
            "base_url": "https://api.tjsp.jus.br/v2",
            "auth_type": "bearer",
            "rate_limit": 100,  # requests per minute
        },
        "TJMG": {
            "base_url": "https://api5.tjmg.jus.br",
            "auth_type": "api_key",
            "rate_limit": 60,
        },
    }

    def __init__(self, tribunal_code: str) -> None:
        self.tribunal_code = tribunal_code
        self.config = self.API_ENDPOINTS.get(tribunal_code)
        self._rate_limit_tracker: Deque[datetime] = deque(maxlen=1000)
        self._client: Optional[httpx.Client] = None

        if self.config:
            timeout = httpx.Timeout(30.0, connect=10.0)
            self._client = httpx.Client(timeout=timeout)
            logger.debug("Initialized TribunalAPIClient for %s", tribunal_code)

    def get_real_status(self) -> Dict[str, Any]:
        """Retrieve the real status from the tribunal API, if configured."""

        if not self._client or not self.config:
            return {"error": "Tribunal não configurado para API real", "fallback": True}

        try:
            self._respect_rate_limit()
            response = self._client.get(
                f"{self.config['base_url']}/status",
                headers=self._get_auth_headers(),
            )
            response.raise_for_status()
            logger.info("Fetched real status from %s", self.tribunal_code)
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "HTTP error from %s status endpoint: %s", self.tribunal_code, exc
            )
            return {
                "error": str(exc),
                "status_code": exc.response.status_code,
                "fallback": True,
            }
        except httpx.HTTPError as exc:  # pragma: no cover - network variability
            logger.error(
                "Network error calling %s status endpoint: %s", self.tribunal_code, exc
            )
            return {"error": str(exc), "fallback": True}

    def query_real_process(self, process_number: str) -> Dict[str, Any]:
        """Query a real process using the tribunal API."""

        if not self._client or not self.config:
            return {"error": "Tribunal não configurado para API real", "fallback": True}

        try:
            self._respect_rate_limit()
            response = self._client.get(
                f"{self.config['base_url']}/processos/{process_number}",
                headers=self._get_auth_headers(),
            )
            response.raise_for_status()
            logger.info(
                "Fetched real process %s from %s", process_number, self.tribunal_code
            )
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "HTTP error when querying process %s from %s: %s",
                process_number,
                self.tribunal_code,
                exc,
            )
            return {
                "error": str(exc),
                "status_code": exc.response.status_code,
                "fallback": True,
            }
        except httpx.HTTPError as exc:  # pragma: no cover - network variability
            logger.error(
                "Network error when querying process %s from %s: %s",
                process_number,
                self.tribunal_code,
                exc,
            )
            return {"error": str(exc), "fallback": True}

    def close(self) -> None:
        """Close the underlying HTTP client."""

        if self._client:
            self._client.close()

    # BUGFIX (H12): garante o fechamento do ``httpx.Client`` para não vazar
    # conexões TCP. Suporta uso como context manager e fecha no GC como rede de
    # segurança quando o chamador esquece de chamar ``close()``.
    def __enter__(self) -> "TribunalAPIClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def __del__(self) -> None:  # pragma: no cover - acionado pelo GC
        try:
            self.close()
        except Exception:
            pass

    def _respect_rate_limit(self) -> None:
        if not self.config:
            return

        rate_limit = self.config.get("rate_limit", 60)
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=1)

        while self._rate_limit_tracker and self._rate_limit_tracker[0] < window_start:
            self._rate_limit_tracker.popleft()

        if len(self._rate_limit_tracker) >= rate_limit:
            sleep_seconds = (
                self._rate_limit_tracker[0] + timedelta(minutes=1) - now
            ).total_seconds()
            logger.debug(
                "Rate limit reached for %s. Sleeping %.2f seconds.",
                self.tribunal_code,
                sleep_seconds,
            )
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        self._rate_limit_tracker.append(now)

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


__all__ = ["TribunalAPIClient"]

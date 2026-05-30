"""Testes das correções de segurança apontadas pela auditoria.

Cobre:
* AuthManager thread-safe (RLock) — sem corrupção sob reconfiguração concorrente.
* RateLimiter com limite de memória — IPs expirados são descartados (sem leak).
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("ENVIRONMENT", "test")

from src.api.auth import AuthManager  # noqa: E402
from src.api.rate_limiter import RateLimiter  # noqa: E402


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeRequest:
    def __init__(self, host: str) -> None:
        self.client = _FakeClient(host)


class TestAuthThreadSafety:
    def test_round_trip_token(self) -> None:
        AuthManager.configure(secret_key="x" * 40, required=True)
        token = AuthManager.create_token("user-123")
        assert isinstance(token, str) and token

    def test_concurrent_configure_and_create_no_corruption(self) -> None:
        AuthManager.configure(secret_key="a" * 40)
        errors: list[Exception] = []

        def reconfigure() -> None:
            for _ in range(200):
                AuthManager.configure(secret_key="b" * 40)
                AuthManager.configure(secret_key="a" * 40)

        def mint() -> None:
            try:
                for _ in range(200):
                    AuthManager.create_token("user")
            except Exception as exc:  # pragma: no cover - falha = bug
                errors.append(exc)

        threads = [threading.Thread(target=reconfigure) for _ in range(2)]
        threads += [threading.Thread(target=mint) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_lock_is_reentrant(self) -> None:
        # RLock permite reentrância: configure() dentro de um lock já adquirido.
        with AuthManager._lock:
            AuthManager.configure(secret_key="c" * 40)
        assert AuthManager.SECRET_KEY == "c" * 40


class TestRateLimiterMemoryBound:
    @pytest.mark.asyncio
    async def test_blocks_after_limit(self) -> None:
        limiter = RateLimiter(requests_per_minute=3)
        req = _FakeRequest("10.0.0.1")
        for _ in range(3):
            await limiter(req)
        with pytest.raises(Exception):
            await limiter(req)

    @pytest.mark.asyncio
    async def test_evicts_stale_ips(self) -> None:
        limiter = RateLimiter(requests_per_minute=60)

        # Simula muitos IPs antigos (fora da janela) já registrados.
        old = datetime.now(timezone.utc) - timedelta(minutes=5)
        for i in range(1000):
            limiter._requests[f"192.168.0.{i}"].append(old)
        assert len(limiter._requests) == 1000

        # Uma nova requisição de um IP atual deve disparar a limpeza dos antigos.
        await limiter(_FakeRequest("172.16.0.1"))

        # Restou apenas o IP ativo; os 1000 obsoletos foram descartados.
        assert len(limiter._requests) == 1
        assert "172.16.0.1" in limiter._requests

"""Circuit Breaker pattern para proteger contra APIs instáveis."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Estados possíveis do circuit breaker."""

    CLOSED = "closed"  # Normal, chamadas passam
    OPEN = "open"  # Bloqueado, chamadas rejeitadas
    HALF_OPEN = "half_open"  # Testando recuperação


@dataclass
class CircuitBreaker:
    """Circuit Breaker simples para proteger chamadas externas."""

    failure_threshold: int = 3
    timeout_seconds: int = 60
    success_threshold: int = 2  # Para fechar de half_open

    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    last_failure_time: float = field(default=0.0, init=False)

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Executa função protegida pelo circuit breaker."""

        if not self.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is OPEN. Wait {self.timeout_seconds}s before retry."
            )

        try:
            result = func(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise

        self.record_success()
        return result

    def can_execute(self) -> bool:
        """Verifica se pode executar chamada."""

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout_seconds:
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def record_success(self) -> None:
        """Registra sucesso e atualiza estado."""

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1

            if self.success_count >= self.success_threshold:
                logger.info(
                    "Circuit breaker CLOSED after %d successes", self.success_count
                )
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0

        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Registra falha e atualiza estado."""

        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit breaker reopened after failure in HALF_OPEN")
            self.state = CircuitState.OPEN
            self.success_count = 0
            return

        if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            logger.error(
                "Circuit breaker OPENED after %d failures", self.failure_count
            )
            self.state = CircuitState.OPEN

    def get_state(self) -> Dict[str, Any]:
        """Retorna estado atual para monitoramento."""

        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "can_execute": self.can_execute(),
        }


class CircuitBreakerOpenError(Exception):
    """Exceção lançada quando circuit breaker está aberto."""

    pass


if __name__ == "__main__":  # pragma: no cover
    import random

    logging.basicConfig(level=logging.INFO)
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=5)

    def flaky_api() -> str:
        if random.random() < 0.7:
            raise RuntimeError("API Error")
        return "Success"

    print("🧪 Testando Circuit Breaker...")

    for i in range(10):
        try:
            response = cb.call(flaky_api)
            print(f"   [{i}] ✅ {response} - State: {cb.state.value}")
        except CircuitBreakerOpenError as exc:
            print(f"   [{i}] 🚫 {exc}")
        except Exception as exc:  # pragma: no cover - demo output
            print(f"   [{i}] ❌ {exc} - State: {cb.state.value}")

        time.sleep(1)

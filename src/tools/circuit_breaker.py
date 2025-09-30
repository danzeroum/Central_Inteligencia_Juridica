"""Advanced, thread-safe implementation of the Circuit Breaker pattern."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Any, Callable, Dict, Optional

try:  # pragma: no cover - optional dependency guard
    from prometheus_client import Counter, Gauge
except Exception:  # pragma: no cover
    Counter = None  # type: ignore
    Gauge = None  # type: ignore

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Possible states for the circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration values for :class:`CircuitBreaker`."""

    name: str = "circuit_breaker"
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 1
    half_open_max_calls: int = 1


class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors."""


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when attempting to execute while the circuit is OPEN."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        name: str | None = None,
        state: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.name = name
        self.state = state


_CIRCUIT_STATE_VALUE = {
    CircuitState.CLOSED: 0.0,
    CircuitState.HALF_OPEN: 0.5,
    CircuitState.OPEN: 1.0,
}


def _build_gauge() -> Optional[Gauge]:  # pragma: no cover - simple helper
    if Gauge is None:
        return None
    return Gauge(
        "circuit_breaker_state",
        "State of the circuit breaker (0=closed, 0.5=half_open, 1=open)",
        labelnames=("name",),
    )


def _build_counter(metric_name: str, documentation: str, labels: tuple[str, ...]):  # pragma: no cover
    if Counter is None:
        return None
    return Counter(metric_name, documentation, labelnames=labels)


_CIRCUIT_STATE_GAUGE = _build_gauge()
_CIRCUIT_FAILURES_TOTAL = _build_counter(
    "circuit_breaker_failures_total",
    "Total number of failures recorded by the circuit breaker",
    ("name",),
)
_CIRCUIT_SUCCESSES_TOTAL = _build_counter(
    "circuit_breaker_success_total",
    "Total number of successful calls recorded by the circuit breaker",
    ("name",),
)
_CIRCUIT_REJECTIONS_TOTAL = _build_counter(
    "circuit_breaker_rejections_total",
    "Total number of calls rejected due to the circuit breaker being open",
    ("name",),
)
_CIRCUIT_TRANSITIONS_TOTAL = _build_counter(
    "circuit_breaker_transitions_total",
    "Total number of state transitions for the circuit breaker",
    ("name", "state"),
)


class CircuitBreaker:
    """Thread-safe implementation of the Circuit Breaker pattern."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: float = 60.0,
        success_threshold: int = 1,
        half_open_max_calls: int = 1,
        *,
        name: Optional[str] = None,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        if config is None:
            config = CircuitBreakerConfig(
                name=name or "circuit_breaker",
                failure_threshold=failure_threshold,
                recovery_timeout=timeout_seconds,
                success_threshold=success_threshold,
                half_open_max_calls=half_open_max_calls,
            )
        else:
            if name:
                config.name = name
        self.config = config

        self._state: CircuitState = CircuitState.CLOSED
        self._lock = RLock()

        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._opened_at: float | None = None
        self._last_failure_time: float | None = None

        self._update_state_metric()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute *func* protected by the circuit breaker."""

        self._before_call()
        try:
            result = func(*args, **kwargs)
        except Exception:
            self._after_call(success=False)
            raise
        self._after_call(success=True)
        return result

    @contextmanager
    def protect(self) -> Any:
        """Context manager wrapper for manual usage.

        Example
        -------
        >>> with breaker.protect():
        ...     response = client.get("/status")
        """

        self._before_call()
        try:
            yield
        except Exception:
            self._after_call(success=False)
            raise
        else:
            self._after_call(success=True)

    def reset(self) -> None:
        """Reset the circuit breaker back to the CLOSED state."""

        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._opened_at = None
            self._last_failure_time = None

    def is_closed(self) -> bool:
        with self._lock:
            return self._state == CircuitState.CLOSED

    def is_open(self) -> bool:
        with self._lock:
            return self._state == CircuitState.OPEN

    def get_state(self) -> Dict[str, Any]:
        """Return a snapshot of the current state and counters."""

        with self._lock:
            now = time.monotonic()
            retry_after = self._retry_after(now) if self._state == CircuitState.OPEN else 0.0
            return {
                "name": self.config.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "half_open_calls": self._half_open_calls,
                "opened_at": self._opened_at,
                "last_failure_time": self._last_failure_time,
                "time_until_half_open": retry_after,
                "can_execute": self._can_execute_locked(now),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _before_call(self) -> None:
        with self._lock:
            now = time.monotonic()
            if self._state == CircuitState.OPEN:
                if self._opened_at is not None and (
                    now - self._opened_at
                ) >= self.config.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    self._half_open_calls = 0
                    self._success_count = 0
                else:
                    retry_after = self._retry_after(now)
                    self._increment_counter(_CIRCUIT_REJECTIONS_TOTAL)
                    raise CircuitBreakerOpenError(
                        (
                            f"Circuit '{self.config.name}' is OPEN. "
                            f"Retry after {retry_after:.2f} seconds."
                        ),
                        retry_after=retry_after,
                        name=self.config.name,
                        state=self._state.value,
                    )

            if self._state == CircuitState.HALF_OPEN:
                if (
                    self.config.half_open_max_calls > 0
                    and self._half_open_calls >= self.config.half_open_max_calls
                ):
                    # Prevent flooding of test calls while in half-open
                    retry_after = self.config.recovery_timeout
                    self._increment_counter(_CIRCUIT_REJECTIONS_TOTAL)
                    raise CircuitBreakerOpenError(
                        (
                            f"Circuit '{self.config.name}' half-open call limit reached. "
                            "Wait before retrying."
                        ),
                        retry_after=retry_after,
                        name=self.config.name,
                        state=self._state.value,
                    )
                self._half_open_calls += 1

    def _after_call(self, *, success: bool) -> None:
        with self._lock:
            if success:
                self._handle_success()
            else:
                self._handle_failure()

    def _handle_success(self) -> None:
        self._increment_counter(_CIRCUIT_SUCCESSES_TOTAL)

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= max(1, self.config.success_threshold):
                logger.info(
                    "Circuit breaker '%s' CLOSED after %d successful attempts",
                    self.config.name,
                    self._success_count,
                )
                self._transition_to(CircuitState.CLOSED)
                self._failure_count = 0
                self._success_count = 0
                self._half_open_calls = 0
                self._opened_at = None
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def _handle_failure(self) -> None:
        self._increment_counter(_CIRCUIT_FAILURES_TOTAL)
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning(
                "Circuit breaker '%s' reopening after failure in HALF_OPEN", self.config.name
            )
            self._transition_to(CircuitState.OPEN)
            self._success_count = 0
            self._half_open_calls = 0
            self._opened_at = time.monotonic()
            return

        self._failure_count += 1
        if self.config.failure_threshold <= 0:
            should_open = True
        else:
            should_open = self._failure_count >= self.config.failure_threshold

        if should_open:
            logger.error(
                "Circuit breaker '%s' OPENED after %d failures",
                self.config.name,
                self._failure_count,
            )
            self._transition_to(CircuitState.OPEN)
            self._opened_at = time.monotonic()

    def _transition_to(self, state: CircuitState) -> None:
        if state == self._state:
            return
        prev_state = self._state
        self._state = state
        self._increment_transition_metric(state)
        self._update_state_metric()
        if state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
        elif state == CircuitState.CLOSED:
            self._opened_at = None
        logger.debug(
            "Circuit breaker '%s' transitioned %s -> %s",
            self.config.name,
            prev_state.value,
            state.value,
        )

    def _retry_after(self, now: float | None = None) -> float:
        if now is None:
            now = time.monotonic()
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return 0.0
        elapsed = now - self._opened_at
        remaining = self.config.recovery_timeout - elapsed
        return max(0.0, remaining)

    def _can_execute_locked(self, now: float) -> bool:
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            return self._retry_after(now) <= 0
        if self._state == CircuitState.HALF_OPEN:
            if self.config.half_open_max_calls <= 0:
                return True
            return self._half_open_calls < self.config.half_open_max_calls
        return False

    def _update_state_metric(self) -> None:
        if _CIRCUIT_STATE_GAUGE is None:
            return
        _CIRCUIT_STATE_GAUGE.labels(name=self.config.name).set(
            _CIRCUIT_STATE_VALUE[self._state]
        )

    def _increment_counter(self, counter: Optional[Counter]) -> None:
        if counter is None:
            return
        counter.labels(name=self.config.name).inc()

    def _increment_transition_metric(self, state: CircuitState) -> None:
        if _CIRCUIT_TRANSITIONS_TOTAL is None:
            return
        _CIRCUIT_TRANSITIONS_TOTAL.labels(
            name=self.config.name,
            state=state.value,
        ).inc()


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerOpenError",
    "CircuitState",
]

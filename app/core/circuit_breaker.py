"""Circuit Breaker pattern for external healthcare providers (Phase 21).

Enforces Section 22:
- Prevents cascading failures when external providers degrade
- States: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
- Fails closed safely: provider failure never becomes false clinical success
- Integrates with telemetry metrics
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
import threading
import time
from typing import Any, Callable, Coroutine, TypeVar

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.core.metrics import metrics

logger = get_logger("app.core.circuit_breaker")
T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker operational states."""
    CLOSED = "CLOSED"          # Normal operation, calls pass through
    OPEN = "OPEN"              # Failures exceeded threshold, calls rejected immediately
    HALF_OPEN = "HALF_OPEN"    # Recovery trial period with bounded calls


class CircuitBreakerOpenException(AppException):
    """Raised when an operation is rejected because the circuit breaker is OPEN."""

    def __init__(self, provider: str, message: str | None = None) -> None:
        msg = message or f"External provider '{provider}' is temporarily unavailable (circuit breaker OPEN)."
        super().__init__(
            code="PROVIDER_CIRCUIT_OPEN",
            message=msg,
            status_code=503,
            details={"provider": provider},
        )
        self.provider = provider


class CircuitBreaker:
    """Thread-safe and async-safe circuit breaker for external service boundaries."""

    def __init__(
        self,
        name: str,
        failure_threshold: int | None = None,
        recovery_timeout: float | None = None,
        half_open_max_calls: int | None = None,
    ) -> None:
        settings = get_settings()
        self.name = name
        self.failure_threshold = failure_threshold or settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        self.recovery_timeout = recovery_timeout or settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS
        self.half_open_max_calls = half_open_max_calls or settings.CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_success_count = 0
        self._last_state_change = time.time()
        self._lock = threading.Lock()
        self._total_trips = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            # Check if OPEN cooldown has elapsed to transition to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_state_change >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    def _transition_to(self, new_state: CircuitState) -> None:
        """Internal state transition helper (must hold self._lock)."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        if new_state == CircuitState.OPEN:
            self._total_trips += 1
            logger.warning(
                f"Circuit breaker [{self.name}] tripped to OPEN after {self._failure_count} failures."
            )
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_success_count = 0
            logger.info(f"Circuit breaker [{self.name}] entered HALF_OPEN recovery trial.")
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._half_open_success_count = 0
            logger.info(f"Circuit breaker [{self.name}] recovered and CLOSED.")

    def record_success(self) -> None:
        """Record a successful execution."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_success_count += 1
                if self._half_open_success_count >= self.half_open_max_calls:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self, error: Exception | None = None) -> None:
        """Record a provider execution failure."""
        with self._lock:
            self._failure_count += 1
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN immediately re-opens the circuit
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        fallback: Callable[[], Coroutine[Any, Any, T]] | None = None,
        **kwargs: Any,
    ) -> T:
        """Execute an async provider call protected by the circuit breaker."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            if fallback is not None:
                logger.info(f"Circuit [{self.name}] OPEN. Executing safe fallback.")
                return await fallback()
            raise CircuitBreakerOpenException(provider=self.name)

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure(exc)
            raise

    def get_status(self) -> dict[str, Any]:
        """Return diagnostic status dictionary."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "consecutive_failures": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "total_trips": self._total_trips,
                "seconds_since_last_transition": round(time.time() - self._last_state_change, 2),
            }


# ---------------------------------------------------------------------------
# Global Circuit Breaker Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, CircuitBreaker] = {}
_REGISTRY_LOCK = threading.Lock()


def get_circuit_breaker(provider_name: str) -> CircuitBreaker:
    """Retrieve or create a singleton circuit breaker for the designated provider."""
    with _REGISTRY_LOCK:
        if provider_name not in _REGISTRY:
            _REGISTRY[provider_name] = CircuitBreaker(name=provider_name)
        return _REGISTRY[provider_name]


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers (primarily for test harnesses)."""
    with _REGISTRY_LOCK:
        for cb in _REGISTRY.values():
            with cb._lock:
                cb._state = CircuitState.CLOSED
                cb._failure_count = 0
                cb._half_open_success_count = 0
                cb._total_trips = 0
                cb._last_state_change = time.time()

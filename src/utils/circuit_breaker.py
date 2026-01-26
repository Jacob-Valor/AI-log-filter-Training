"""
Circuit Breaker Pattern Implementation

Provides fail-open behavior for the AI log filtering system.
When failures exceed threshold, the circuit opens and all logs
are forwarded directly to QRadar (fail-safe behavior).
"""

import asyncio
import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

from src.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, bypass enabled
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes to close from half-open
    timeout_seconds: float = 30.0  # Time before attempting recovery
    half_open_max_calls: int = 3  # Max test calls in half-open state


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float | None = None
    last_state_change: float = field(default_factory=time.time)
    total_failures: int = 0
    total_successes: int = 0
    times_opened: int = 0


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    Implements fail-open behavior: when the circuit opens, the fallback
    function is called instead of the protected function. For log filtering,
    this means all logs are forwarded to QRadar when AI classification fails.

    States:
    - CLOSED: Normal operation, calls go through
    - OPEN: Too many failures, fallback is used
    - HALF_OPEN: Testing if service recovered

    Example:
        breaker = CircuitBreaker(
            name="ensemble_classifier",
            fallback=lambda logs: [fail_open_prediction(log) for log in logs]
        )

        @breaker
        async def classify_logs(logs):
            return await classifier.predict_batch(logs)
    """

    def __init__(
        self,
        name: str,
        fallback: Callable | None = None,
        config: CircuitBreakerConfig | None = None,
        on_state_change: Callable[[CircuitState, CircuitState], None] | None = None,
    ):
        self.name = name
        self.fallback = fallback
        self.config = config or CircuitBreakerConfig()
        self.on_state_change = on_state_change
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        self._half_open_calls = 0

        logger.info(
            f"Circuit breaker '{name}' initialized",
            extra={
                "failure_threshold": self.config.failure_threshold,
                "timeout_seconds": self.config.timeout_seconds,
            },
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self.stats.state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.stats.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)."""
        return self.stats.state == CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.stats.last_failure_time is None:
            return True
        elapsed = time.time() - self.stats.last_failure_time
        return elapsed >= self.config.timeout_seconds

    async def _transition_to(self, new_state: CircuitState):
        """Transition to a new state."""
        old_state = self.stats.state
        if old_state == new_state:
            return

        self.stats.state = new_state
        self.stats.last_state_change = time.time()

        if new_state == CircuitState.OPEN:
            self.stats.times_opened += 1

        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0

        logger.warning(
            f"Circuit breaker '{self.name}' state change: {old_state.value} -> {new_state.value}",
            extra={
                "circuit_name": self.name,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "failure_count": self.stats.failure_count,
                "times_opened": self.stats.times_opened,
            },
        )

        if self.on_state_change:
            try:
                self.on_state_change(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    async def _record_success(self):
        """Record a successful call."""
        async with self._lock:
            self.stats.success_count += 1
            self.stats.total_successes += 1
            self.stats.failure_count = 0  # Reset consecutive failures

            if self.stats.state == CircuitState.HALF_OPEN:
                if self.stats.success_count >= self.config.success_threshold:
                    await self._transition_to(CircuitState.CLOSED)
                    self.stats.success_count = 0

    async def _record_failure(self, error: Exception):
        """Record a failed call."""
        async with self._lock:
            self.stats.failure_count += 1
            self.stats.total_failures += 1
            self.stats.success_count = 0  # Reset consecutive successes
            self.stats.last_failure_time = time.time()

            logger.error(
                f"Circuit breaker '{self.name}' recorded failure",
                extra={
                    "circuit_name": self.name,
                    "failure_count": self.stats.failure_count,
                    "error": str(error),
                    "state": self.stats.state.value,
                },
            )

            if self.stats.state == CircuitState.CLOSED:
                if self.stats.failure_count >= self.config.failure_threshold:
                    await self._transition_to(CircuitState.OPEN)

            elif self.stats.state == CircuitState.HALF_OPEN:
                # Any failure in half-open immediately opens circuit
                await self._transition_to(CircuitState.OPEN)

    async def _can_execute(self) -> bool:
        """Check if we can execute the protected function."""
        async with self._lock:
            if self.stats.state == CircuitState.CLOSED:
                return True

            elif self.stats.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    await self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False

            elif self.stats.state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

        return False

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        If circuit is open and fallback is defined, returns fallback result.
        This enables fail-open behavior for log filtering.
        """
        can_execute = await self._can_execute()

        if not can_execute:
            if self.fallback:
                logger.info(
                    f"Circuit '{self.name}' is OPEN, using fallback",
                    extra={"circuit_name": self.name},
                )
                if inspect.iscoroutinefunction(self.fallback):
                    return await self.fallback(*args, **kwargs)
                return self.fallback(*args, **kwargs)
            else:
                raise CircuitOpenError(
                    f"Circuit breaker '{self.name}' is open and no fallback defined"
                )

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self._record_success()
            return result

        except Exception as e:
            await self._record_failure(e)

            if self.fallback:
                logger.warning(
                    f"Circuit '{self.name}' call failed, using fallback",
                    extra={"circuit_name": self.name, "error": str(e)},
                )
                if inspect.iscoroutinefunction(self.fallback):
                    return await self.fallback(*args, **kwargs)
                return self.fallback(*args, **kwargs)
            raise

    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap function with circuit breaker."""

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)

        return wrapper

    def get_stats(self) -> dict:
        """Get circuit breaker statistics for monitoring."""
        return {
            "name": self.name,
            "state": self.stats.state.value,
            "failure_count": self.stats.failure_count,
            "success_count": self.stats.success_count,
            "total_failures": self.stats.total_failures,
            "total_successes": self.stats.total_successes,
            "times_opened": self.stats.times_opened,
            "last_state_change": self.stats.last_state_change,
            "last_failure_time": self.stats.last_failure_time,
        }

    async def reset(self):
        """Manually reset circuit to closed state."""
        async with self._lock:
            await self._transition_to(CircuitState.CLOSED)
            self.stats.failure_count = 0
            self.stats.success_count = 0
            logger.info(f"Circuit breaker '{self.name}' manually reset")


class CircuitOpenError(Exception):
    """Raised when circuit is open and no fallback is available."""

    pass


# Global circuit breaker registry for monitoring
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker | None:
    """Get circuit breaker by name."""
    return _circuit_breakers.get(name)


def register_circuit_breaker(breaker: CircuitBreaker):
    """Register circuit breaker for monitoring."""
    _circuit_breakers[breaker.name] = breaker


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """Get all registered circuit breakers."""
    return _circuit_breakers.copy()

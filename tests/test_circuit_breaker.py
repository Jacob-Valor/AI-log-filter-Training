"""
Tests for Circuit Breaker Pattern

Tests the fail-open behavior and state transitions of the circuit breaker.
"""

import asyncio

import pytest

from src.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    CircuitState,
    get_circuit_breaker,
    register_circuit_breaker,
)


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""

    @pytest.fixture
    def breaker(self):
        """Create a circuit breaker with low thresholds for testing."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=0.1,  # Fast timeout for tests
            half_open_max_calls=2
        )
        return CircuitBreaker(name="test_breaker", config=config)

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self, breaker):
        """Circuit should start in closed state."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open

    @pytest.mark.asyncio
    async def test_successful_calls_keep_circuit_closed(self, breaker):
        """Successful calls should keep circuit closed."""
        async def success_func():
            return "success"

        for _ in range(10):
            result = await breaker.call(success_func)
            assert result == "success"

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.total_successes == 10
        assert breaker.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self, breaker):
        """Failures above threshold should open circuit."""
        async def failing_func():
            raise ValueError("Test failure")

        # Should fail 3 times then circuit opens
        for i in range(3):
            with pytest.raises(ValueError):
                await breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.stats.times_opened == 1

    @pytest.mark.asyncio
    async def test_open_circuit_uses_fallback(self, breaker):
        """Open circuit should use fallback function."""
        fallback_result = "fallback_value"
        breaker.fallback = lambda: fallback_result

        # Force circuit open
        async def failing_func():
            raise ValueError("Test failure")

        for _ in range(3):
            try:
                await breaker.call(failing_func)
            except ValueError:
                pass

        assert breaker.state == CircuitState.OPEN

        # Next call should use fallback
        result = await breaker.call(failing_func)
        assert result == fallback_result

    @pytest.mark.asyncio
    async def test_open_circuit_without_fallback_raises(self, breaker):
        """Open circuit without fallback should raise CircuitOpenError."""
        breaker.fallback = None

        async def failing_func():
            raise ValueError("Test failure")

        for _ in range(3):
            try:
                await breaker.call(failing_func)
            except ValueError:
                pass

        assert breaker.state == CircuitState.OPEN

        with pytest.raises(CircuitOpenError):
            await breaker.call(failing_func)

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open_after_timeout(self, breaker):
        """Circuit should transition to half-open after timeout."""
        async def failing_func():
            raise ValueError("Test failure")

        # Open the circuit
        for _ in range(3):
            try:
                await breaker.call(failing_func)
            except ValueError:
                pass

        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.2)

        # Next call attempt should transition to half-open
        async def success_func():
            return "success"

        result = await breaker.call(success_func)
        # After successful call in half-open, may transition based on success_threshold
        assert breaker.state in [CircuitState.HALF_OPEN, CircuitState.CLOSED]

    @pytest.mark.asyncio
    async def test_half_open_closes_on_success(self, breaker):
        """Circuit should close after success_threshold successes in half-open."""
        async def failing_func():
            raise ValueError("Test failure")

        async def success_func():
            return "success"

        # Open the circuit
        for _ in range(3):
            try:
                await breaker.call(failing_func)
            except ValueError:
                pass

        # Wait for timeout
        await asyncio.sleep(0.2)

        # Successful calls should close circuit
        for _ in range(breaker.config.success_threshold):
            await breaker.call(success_func)

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_manual_reset(self, breaker):
        """Manual reset should close circuit."""
        async def failing_func():
            raise ValueError("Test failure")

        # Open the circuit
        for _ in range(3):
            try:
                await breaker.call(failing_func)
            except ValueError:
                pass

        assert breaker.state == CircuitState.OPEN

        await breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.failure_count == 0


class TestCircuitBreakerDecorator:
    """Test circuit breaker as decorator."""

    @pytest.mark.asyncio
    async def test_decorator_usage(self):
        """Circuit breaker can be used as decorator."""
        call_count = 0

        breaker = CircuitBreaker(name="decorator_test")

        @breaker
        async def protected_function():
            nonlocal call_count
            call_count += 1
            return "result"

        result = await protected_function()

        assert result == "result"
        assert call_count == 1


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""

    def test_register_and_get(self):
        """Should register and retrieve circuit breakers."""
        breaker = CircuitBreaker(name="registry_test")
        register_circuit_breaker(breaker)

        retrieved = get_circuit_breaker("registry_test")
        assert retrieved is breaker


class TestCircuitBreakerStats:
    """Test circuit breaker statistics."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Should track statistics correctly."""
        breaker = CircuitBreaker(name="stats_test")

        async def success_func():
            return "success"

        async def failing_func():
            raise ValueError("fail")

        # 5 successes
        for _ in range(5):
            await breaker.call(success_func)

        # 2 failures
        for _ in range(2):
            try:
                await breaker.call(failing_func)
            except ValueError:
                pass

        stats = breaker.get_stats()

        assert stats["total_successes"] == 5
        assert stats["total_failures"] == 2
        assert stats["state"] == "closed"

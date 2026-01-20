"""
Common Integration Utilities

Shared utilities for all integration modules including:
- Connection pooling
- Retry logic
- Health checks
- Error handling
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ConnectionState(Enum):
    """Connection states for integrations."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class IntegrationConfig:
    """Base configuration for all integrations."""
    host: str
    port: int
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    pool_size: int = 10
    health_check_interval: int = 30
    enabled: bool = True


@dataclass
class ConnectionStats:
    """Connection statistics."""
    state: ConnectionState = ConnectionState.DISCONNECTED
    total_connections: int = 0
    active_connections: int = 0
    failed_connections: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_connection: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    average_latency_ms: float = 0.0
    uptime_percentage: float = 0.0


@dataclass
class HealthStatus:
    """Health check result."""
    healthy: bool
    latency_ms: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BaseIntegration(ABC):
    """Base class for all integrations."""

    def __init__(self, name: str, config: IntegrationConfig):
        self.name = name
        self.config = config
        self.stats = ConnectionStats()
        self._state = ConnectionState.DISCONNECTED
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""
        pass

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Perform health check."""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Quick health check."""
        pass

    async def initialize(self) -> bool:
        """Initialize integration and start health checks."""
        try:
            self._state = ConnectionState.CONNECTING
            success = await self.connect()
            if success:
                self._state = ConnectionState.CONNECTED
                self.stats.state = ConnectionState.CONNECTED
                self.stats.last_connection = datetime.utcnow()
                self.stats.total_connections += 1

                # Start background health check
                self._health_check_task = asyncio.create_task(
                    self._periodic_health_check()
                )

                logger.info(f"Integration {self.name} initialized successfully")
                return True
            else:
                self._state = ConnectionState.FAILED
                logger.error(f"Integration {self.name} failed to initialize")
                return False
        except Exception as e:
            self._state = ConnectionState.FAILED
            self.stats.failed_connections += 1
            self.stats.last_failure = datetime.utcnow()
            logger.error(f"Integration {self.name} initialization error: {e}")
            return False

    async def shutdown(self) -> None:
        """Gracefully shutdown integration."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        await self.disconnect()
        self._state = ConnectionState.DISCONNECTED
        self.stats.state = ConnectionState.DISCONNECTED
        logger.info(f"Integration {self.name} shutdown complete")

    async def _periodic_health_check(self) -> None:
        """Run periodic health checks."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self.health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Health check error for {self.name}: {e}")

    def _record_request(self, success: bool, latency_ms: float) -> None:
        """Record request statistics."""
        self.stats.total_requests += 1
        if success:
            self.stats.successful_requests += 1
        else:
            self.stats.failed_requests += 1

        # Update average latency
        n = self.stats.total_requests
        self.stats.average_latency_ms = (
            (self.stats.average_latency_ms * (n - 1) + latency_ms) / n
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "name": self.name,
            "state": self.stats.state.value,
            "total_connections": self.stats.total_connections,
            "active_connections": self.stats.active_connections,
            "failed_connections": self.stats.failed_connections,
            "total_requests": self.stats.total_requests,
            "successful_requests": self.stats.successful_requests,
            "failed_requests": self.stats.failed_requests,
            "success_rate": (
                self.stats.successful_requests / self.stats.total_requests * 100
                if self.stats.total_requests > 0 else 0
            ),
            "average_latency_ms": round(self.stats.average_latency_ms, 2),
            "last_connection": (
                self.stats.last_connection.isoformat()
                if self.stats.last_connection else None
            ),
            "last_failure": (
                self.stats.last_failure.isoformat()
                if self.stats.last_failure else None
            )
        }


async def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    **kwargs
) -> T:
    """
    Retry a function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        base_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        **kwargs: Arguments to pass to func

    Returns:
        Result of func

    Raises:
        Exception: If all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(**kwargs) if kwargs else await func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(
                    base_delay * (exponential_base ** attempt),
                    max_delay
                )
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed: {e}")
                raise

    raise last_exception


@asynccontextmanager
async def connection_context(integration: BaseIntegration):
    """Context manager for integration connections."""
    try:
        success = await integration.initialize()
        if not success:
            raise RuntimeError(f"Failed to initialize {integration.name}")
        yield integration
    finally:
        await integration.shutdown()

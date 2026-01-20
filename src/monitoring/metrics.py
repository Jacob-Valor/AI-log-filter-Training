"""
Metrics Server

Exposes Prometheus metrics for monitoring.
"""

import asyncio

from src.utils.logging import get_logger

logger = get_logger(__name__)


class MetricsServer:
    """
    HTTP server for exposing Prometheus metrics.
    """

    def __init__(self, port: int = 9090, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self._server = None
        self._app = None

    async def start(self):
        """Start the metrics server."""
        try:
            from prometheus_client import (
                CONTENT_TYPE_LATEST,
                generate_latest,
                start_http_server,
            )

            # Start prometheus HTTP server in a thread
            start_http_server(self.port, addr=self.host)
            logger.info(f"Metrics server started on {self.host}:{self.port}")

        except ImportError:
            logger.warning("prometheus_client not available, metrics server disabled")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")

    async def stop(self):
        """Stop the metrics server."""
        logger.info("Metrics server stopped")


class HealthChecker:
    """
    Health check service for monitoring application health.
    """

    def __init__(self):
        self.checks = {}

    def register_check(self, name: str, check_func):
        """Register a health check function."""
        self.checks[name] = check_func

    async def check_health(self) -> dict:
        """Run all health checks and return status."""
        results = {
            "status": "healthy",
            "checks": {}
        }

        for name, check_func in self.checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()

                results["checks"][name] = {
                    "status": "healthy" if result else "unhealthy",
                    "details": result
                }

                if not result:
                    results["status"] = "unhealthy"

            except Exception as e:
                results["checks"][name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                results["status"] = "unhealthy"

        return results

    def is_healthy(self) -> bool:
        """Quick health check."""
        return all(
            check() if not asyncio.iscoroutinefunction(check) else True
            for check in self.checks.values()
        )


# Global health checker instance
health_checker = HealthChecker()

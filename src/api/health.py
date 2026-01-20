"""
Health Check Endpoints

Production-ready health, readiness, and liveness probes
for Kubernetes and monitoring systems.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from src.monitoring.production_metrics import METRICS
from src.utils.circuit_breaker import CircuitState, get_all_circuit_breakers
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


class HealthStatus(str, Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status of a single component."""
    name: str
    status: HealthStatus
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Full health check response."""
    status: HealthStatus
    timestamp: str
    version: str
    uptime_seconds: float
    components: List[ComponentHealth]
    metrics: Optional[Dict[str, Any]] = None


class ReadinessResponse(BaseModel):
    """Readiness probe response."""
    ready: bool
    reason: Optional[str] = None


class LivenessResponse(BaseModel):
    """Liveness probe response."""
    alive: bool


# Track service start time
SERVICE_START_TIME = time.time()
SERVICE_VERSION = "1.0.0"


@dataclass
class HealthChecker:
    """
    Centralized health checking for all components.

    Components register their health check functions here.
    """
    _instance: Optional['HealthChecker'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._checks = {}
            cls._instance._classifier = None
            cls._instance._kafka_consumer = None
            cls._instance._router = None
        return cls._instance

    def register_classifier(self, classifier):
        """Register the classifier for health checks."""
        self._classifier = classifier

    def register_kafka_consumer(self, consumer):
        """Register Kafka consumer for health checks."""
        self._kafka_consumer = consumer

    def register_router(self, router):
        """Register log router for health checks."""
        self._router = router

    async def check_classifier(self) -> ComponentHealth:
        """Check classifier health."""
        if self._classifier is None:
            return ComponentHealth(
                name="classifier",
                status=HealthStatus.UNHEALTHY,
                message="Classifier not registered"
            )

        try:
            start = time.time()

            # Check if loaded
            if not self._classifier.is_loaded:
                return ComponentHealth(
                    name="classifier",
                    status=HealthStatus.UNHEALTHY,
                    message="Classifier not loaded"
                )

            # Check circuit breaker
            if hasattr(self._classifier, 'circuit_breaker'):
                if self._classifier.circuit_breaker.is_open:
                    return ComponentHealth(
                        name="classifier",
                        status=HealthStatus.DEGRADED,
                        message="Circuit breaker is OPEN - fail-open mode active"
                    )

            # Run quick inference test
            test_log = "Health check test log message"
            prediction = await asyncio.wait_for(
                self._classifier.predict(test_log),
                timeout=2.0
            )

            latency = (time.time() - start) * 1000

            return ComponentHealth(
                name="classifier",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                details={
                    "models_loaded": len(self._classifier.classifiers) if hasattr(self._classifier, 'classifiers') else 1,
                    "test_category": prediction.category
                }
            )

        except asyncio.TimeoutError:
            return ComponentHealth(
                name="classifier",
                status=HealthStatus.DEGRADED,
                message="Classifier inference timeout"
            )
        except Exception as e:
            return ComponentHealth(
                name="classifier",
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )

    async def check_kafka(self) -> ComponentHealth:
        """Check Kafka consumer health."""
        if self._kafka_consumer is None:
            return ComponentHealth(
                name="kafka",
                status=HealthStatus.UNHEALTHY,
                message="Kafka consumer not registered"
            )

        try:
            # Check if consumer is running
            if hasattr(self._kafka_consumer, 'is_running'):
                if not self._kafka_consumer.is_running:
                    return ComponentHealth(
                        name="kafka",
                        status=HealthStatus.UNHEALTHY,
                        message="Kafka consumer not running"
                    )

            # Check consumer lag
            lag = getattr(self._kafka_consumer, 'current_lag', 0)

            if lag > 100000:
                return ComponentHealth(
                    name="kafka",
                    status=HealthStatus.DEGRADED,
                    message=f"High consumer lag: {lag}",
                    details={"lag": lag}
                )

            return ComponentHealth(
                name="kafka",
                status=HealthStatus.HEALTHY,
                details={"lag": lag}
            )

        except Exception as e:
            return ComponentHealth(
                name="kafka",
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )

    async def check_circuit_breakers(self) -> ComponentHealth:
        """Check all circuit breakers."""
        breakers = get_all_circuit_breakers()

        if not breakers:
            return ComponentHealth(
                name="circuit_breakers",
                status=HealthStatus.HEALTHY,
                message="No circuit breakers registered"
            )

        open_breakers = []
        half_open_breakers = []

        for name, breaker in breakers.items():
            if breaker.state == CircuitState.OPEN:
                open_breakers.append(name)
            elif breaker.state == CircuitState.HALF_OPEN:
                half_open_breakers.append(name)

        if open_breakers:
            return ComponentHealth(
                name="circuit_breakers",
                status=HealthStatus.DEGRADED,
                message=f"Open circuits: {open_breakers}",
                details={
                    "open": open_breakers,
                    "half_open": half_open_breakers,
                    "total": len(breakers)
                }
            )

        return ComponentHealth(
            name="circuit_breakers",
            status=HealthStatus.HEALTHY,
            details={
                "open": [],
                "half_open": half_open_breakers,
                "total": len(breakers)
            }
        )

    async def check_all(self) -> HealthResponse:
        """Run all health checks."""
        components = await asyncio.gather(
            self.check_classifier(),
            self.check_kafka(),
            self.check_circuit_breakers(),
            return_exceptions=True
        )

        # Handle any exceptions in checks
        clean_components = []
        for c in components:
            if isinstance(c, Exception):
                clean_components.append(ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=str(c)
                ))
            else:
                clean_components.append(c)

        # Determine overall status
        statuses = [c.status for c in clean_components]

        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return HealthResponse(
            status=overall,
            timestamp=datetime.utcnow().isoformat() + "Z",
            version=SERVICE_VERSION,
            uptime_seconds=round(time.time() - SERVICE_START_TIME, 2),
            components=clean_components,
            metrics=METRICS.get_summary()
        )


# Global health checker
health_checker = HealthChecker()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Full health check",
    description="Comprehensive health check of all components"
)
async def health_check(response: Response) -> HealthResponse:
    """
    Full health check endpoint.

    Returns detailed status of all components including:
    - Classifier health and latency
    - Kafka consumer status
    - Circuit breaker states
    - Current metrics

    Returns 200 for healthy/degraded, 503 for unhealthy.
    """
    result = await health_checker.check_all()

    if result.status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return result


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description="Kubernetes readiness probe - is the service ready to receive traffic?"
)
async def readiness_probe(response: Response) -> ReadinessResponse:
    """
    Readiness probe for Kubernetes.

    Returns ready=true if:
    - Classifier is loaded and responding
    - Kafka consumer is connected
    - No critical failures

    Used by Kubernetes to determine if pod should receive traffic.
    """
    result = await health_checker.check_all()

    if result.status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            ready=False,
            reason=f"Unhealthy components: {[c.name for c in result.components if c.status == HealthStatus.UNHEALTHY]}"
        )

    return ReadinessResponse(ready=True)


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description="Kubernetes liveness probe - is the service alive?"
)
async def liveness_probe() -> LivenessResponse:
    """
    Liveness probe for Kubernetes.

    Simple check that the service process is running.
    Should only fail if the process is completely stuck.

    Used by Kubernetes to determine if pod should be restarted.
    """
    return LivenessResponse(alive=True)


@router.get(
    "/health/metrics-summary",
    summary="Metrics summary",
    description="Summary of key operational metrics"
)
async def metrics_summary() -> Dict[str, Any]:
    """Get summary of key metrics."""
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **METRICS.get_summary()
    }

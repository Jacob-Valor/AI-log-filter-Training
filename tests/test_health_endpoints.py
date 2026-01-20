"""
Tests for Health Check Endpoints

Tests the health, readiness, and liveness probes.
"""

# Mock the imports before importing the module
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.modules['src.utils.circuit_breaker'] = MagicMock()
sys.modules['src.monitoring.production_metrics'] = MagicMock()


class TestHealthChecker:
    """Test the HealthChecker class."""

    def test_singleton_pattern(self):
        """HealthChecker should be a singleton."""
        from src.api.health import HealthChecker

        checker1 = HealthChecker()
        checker2 = HealthChecker()

        assert checker1 is checker2

    def test_register_classifier(self):
        """Should register classifier for health checks."""
        from src.api.health import HealthChecker

        checker = HealthChecker()
        mock_classifier = MagicMock()

        checker.register_classifier(mock_classifier)

        assert checker._classifier is mock_classifier

    @pytest.mark.asyncio
    async def test_check_classifier_not_registered(self):
        """Should report unhealthy if classifier not registered."""
        from src.api.health import HealthChecker, HealthStatus

        checker = HealthChecker()
        checker._classifier = None

        result = await checker.check_classifier()

        assert result.status == HealthStatus.UNHEALTHY
        assert "not registered" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_classifier_not_loaded(self):
        """Should report unhealthy if classifier not loaded."""
        from src.api.health import HealthChecker, HealthStatus

        checker = HealthChecker()
        mock_classifier = MagicMock()
        mock_classifier.is_loaded = False
        checker._classifier = mock_classifier

        result = await checker.check_classifier()

        assert result.status == HealthStatus.UNHEALTHY
        assert "not loaded" in result.message.lower()


class TestHealthEndpoints:
    """Test the FastAPI health endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for health endpoints."""
        from fastapi import FastAPI

        from src.api.health import router

        app = FastAPI()
        app.include_router(router)

        return TestClient(app)

    def test_liveness_probe(self, client):
        """Liveness probe should always return alive."""
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json()["alive"] == True

    def test_readiness_probe_healthy(self, client):
        """Readiness probe should return ready when healthy."""
        with patch('src.api.health.health_checker') as mock_checker:
            from src.api.health import ComponentHealth, HealthResponse, HealthStatus

            mock_checker.check_all = AsyncMock(return_value=HealthResponse(
                status=HealthStatus.HEALTHY,
                timestamp="2024-01-01T00:00:00Z",
                version="1.0.0",
                uptime_seconds=100.0,
                components=[
                    ComponentHealth(name="classifier", status=HealthStatus.HEALTHY)
                ]
            ))

            response = client.get("/health/ready")

            assert response.status_code == 200
            assert response.json()["ready"] == True

    def test_full_health_check(self, client):
        """Full health check should return comprehensive status."""
        with patch('src.api.health.health_checker') as mock_checker:
            from src.api.health import ComponentHealth, HealthResponse, HealthStatus

            mock_checker.check_all = AsyncMock(return_value=HealthResponse(
                status=HealthStatus.HEALTHY,
                timestamp="2024-01-01T00:00:00Z",
                version="1.0.0",
                uptime_seconds=100.0,
                components=[
                    ComponentHealth(name="classifier", status=HealthStatus.HEALTHY),
                    ComponentHealth(name="kafka", status=HealthStatus.HEALTHY),
                ],
                metrics={"eps": {"ingested": 1000}}
            ))

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "components" in data
            assert "metrics" in data


class TestHealthStatus:
    """Test health status enum."""

    def test_status_values(self):
        """Should have expected status values."""
        from src.api.health import HealthStatus

        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestComponentHealth:
    """Test component health model."""

    def test_component_health_creation(self):
        """Should create component health correctly."""
        from src.api.health import ComponentHealth, HealthStatus

        component = ComponentHealth(
            name="test_component",
            status=HealthStatus.HEALTHY,
            latency_ms=15.5,
            message="All good"
        )

        assert component.name == "test_component"
        assert component.status == HealthStatus.HEALTHY
        assert component.latency_ms == 15.5
        assert component.message == "All good"

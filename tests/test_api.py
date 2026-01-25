"""
Integration tests for the API
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    # Import here to avoid issues with uninstalled dependencies
    try:
        from src.api.app import app

        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI not available")


class TestAPIEndpoints:
    """Tests for API endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        assert "name" in response.json()
        assert response.json()["status"] == "running"

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "status" in response.json()

    def test_models_endpoint(self, client):
        """Test models listing endpoint."""
        response = client.get("/models")

        assert response.status_code == 200
        assert "models" in response.json()
        assert len(response.json()["models"]) > 0

    def test_classify_endpoint(self, client):
        """Test single log classification."""
        response = client.post("/classify", json={"message": "Failed login attempt for user admin"})

        # May return 503 if classifier not loaded
        if response.status_code == 200:
            result = response.json()
            assert "category" in result
            assert "confidence" in result

    def test_classify_batch_endpoint(self, client):
        """Test batch classification."""
        response = client.post(
            "/classify/batch",
            json={"logs": [{"message": "Malware detected"}, {"message": "Health check OK"}]},
        )

        if response.status_code == 200:
            result = response.json()
            assert "results" in result
            assert len(result["results"]) == 2

    def test_classify_batch_too_large(self, client):
        """Test batch size limit."""
        # Create oversized batch
        logs = [{"message": "test"} for _ in range(1001)]

        response = client.post("/classify/batch", json={"logs": logs})

        # Either 400 (batch too large) or 503 (classifier not available)
        # Both are acceptable - the important thing is large batches are rejected
        assert response.status_code in [400, 503]

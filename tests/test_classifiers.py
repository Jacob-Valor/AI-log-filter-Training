"""
Unit tests for classifiers
"""

import asyncio

import pytest

from src.models.base import Prediction
from src.models.rule_based import RuleBasedClassifier


class TestRuleBasedClassifier:
    """Tests for RuleBasedClassifier."""

    @pytest.fixture
    def classifier(self):
        classifier = RuleBasedClassifier({})
        asyncio.run(classifier.load())
        return classifier

    @pytest.mark.asyncio
    async def test_classify_critical_malware(self, classifier):
        """Test classification of malware log."""
        log = "ALERT: Malware detected in file /tmp/suspicious.exe"

        result = await classifier.predict(log)

        assert isinstance(result, Prediction)
        assert result.category == "critical"
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_classify_suspicious_failed_login(self, classifier):
        """Test classification of failed login."""
        log = "Failed login attempt for user admin from 192.168.1.100"

        result = await classifier.predict(log)

        assert result.category in ["suspicious", "critical"]
        assert result.confidence > 0.5

    @pytest.mark.asyncio
    async def test_classify_noise_healthcheck(self, classifier):
        """Test classification of health check."""
        log = "Health check endpoint called - status OK"

        result = await classifier.predict(log)

        assert result.category == "noise"
        assert result.confidence > 0.7

    @pytest.mark.asyncio
    async def test_classify_batch(self, classifier):
        """Test batch classification."""
        logs = ["Malware detected", "Failed login", "Health check OK"]

        results = await classifier.predict_batch(logs)

        assert len(results) == 3
        assert all(isinstance(r, Prediction) for r in results)

    def test_get_matching_rules(self, classifier):
        """Test getting matching rules."""
        log = "Malware trojan detected in system"

        matches = classifier.get_matching_rules(log)

        assert len(matches) > 0
        assert any(m["category"] == "critical" for m in matches)


class TestPrediction:
    """Tests for Prediction dataclass."""

    def test_prediction_creation(self):
        """Test creating a prediction."""
        pred = Prediction(category="critical", confidence=0.95, model="test_model")

        assert pred.category == "critical"
        assert pred.confidence == 0.95
        assert pred.model == "test_model"

    def test_prediction_to_dict(self):
        """Test converting prediction to dict."""
        pred = Prediction(
            category="suspicious",
            confidence=0.75,
            model="ensemble",
            probabilities={"critical": 0.1, "suspicious": 0.75},
            explanation={"rule": "test"},
        )

        result = pred.to_dict()

        assert result["category"] == "suspicious"
        assert result["confidence"] == 0.75
        assert result["probabilities"]["suspicious"] == 0.75

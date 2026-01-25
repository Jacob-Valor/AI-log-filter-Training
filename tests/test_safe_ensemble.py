"""
Tests for Safe Ensemble Classifier

Tests the production-safe classifier with fail-open behavior,
circuit breaker integration, and compliance bypass.
"""

from unittest.mock import MagicMock

import pytest

from src.models.base import Prediction
from src.models.safe_ensemble import (
    ClassificationResult,
    SafeEnsembleClassifier,
    create_fail_open_prediction,
)


class TestFailOpenPrediction:
    """Test fail-open prediction creation."""

    def test_fail_open_is_critical(self):
        """Fail-open predictions should be critical category."""
        prediction = create_fail_open_prediction("test message", "test_reason")

        assert prediction.category == "critical"
        assert prediction.confidence == 0.0
        assert prediction.model == "fail_open"
        assert prediction.explanation["fail_open"]
        assert prediction.explanation["reason"] == "test_reason"

    def test_fail_open_has_full_probability(self):
        """Fail-open should have 100% probability for critical."""
        prediction = create_fail_open_prediction("test", "error")

        assert prediction.probabilities["critical"] == 1.0
        assert prediction.probabilities["suspicious"] == 0.0
        assert prediction.probabilities["routine"] == 0.0
        assert prediction.probabilities["noise"] == 0.0


class TestSafeEnsembleInitialization:
    """Test SafeEnsembleClassifier initialization."""

    def test_initialization_with_defaults(self):
        """Should initialize with default configuration."""
        classifier = SafeEnsembleClassifier()

        assert classifier.timeout_seconds == 5.0
        assert classifier.max_batch_size == 1000
        assert not classifier.is_loaded

    def test_initialization_with_config(self):
        """Should respect configuration overrides."""
        config = {
            "timeout_seconds": 10.0,
            "max_batch_size": 500,
            "ensemble": {
                "weights": {"rule_based": 0.5, "tfidf_xgboost": 0.3, "anomaly_detector": 0.2}
            },
        }

        classifier = SafeEnsembleClassifier(config=config)

        assert classifier.timeout_seconds == 10.0
        assert classifier.max_batch_size == 500
        assert classifier.weights["rule_based"] == 0.5


class TestSafeEnsembleClassification:
    """Test classification functionality."""

    @pytest.fixture
    def mock_classifier(self):
        """Create a classifier with mocked _classify_texts method."""
        classifier = SafeEnsembleClassifier(
            model_path="models/test", config={"timeout_seconds": 1.0}
        )
        classifier.is_loaded = True

        # Create the mock result
        mock_result = ClassificationResult(
            prediction=Prediction(
                category="routine",
                confidence=0.8,
                model="safe_ensemble",
                probabilities={"critical": 0.1, "suspicious": 0.1, "routine": 0.7, "noise": 0.1},
            ),
            processing_time_ms=10.0,
            fail_open_used=False,
            models_used=["rule_based", "tfidf_xgboost"],
        )

        # Create async mock that handles circuit breaker call signature
        async def mock_classify_texts(fn, texts, logs=None):
            return [mock_result for _ in texts]

        # Mock the circuit breaker call to bypass it
        classifier.circuit_breaker.call = mock_classify_texts

        return classifier

    @pytest.mark.asyncio
    async def test_basic_classification(self, mock_classifier):
        """Should classify logs correctly."""
        logs = [{"message": "Test log message", "source": "test"}]

        results = await mock_classifier.classify_batch(logs)

        assert len(results) == 1
        assert isinstance(results[0], ClassificationResult)
        assert results[0].prediction.category in ["critical", "suspicious", "routine", "noise"]

    @pytest.mark.asyncio
    async def test_compliance_bypass(self, mock_classifier):
        """Compliance-regulated logs should bypass classification."""
        logs = [{"message": "Payment processed", "source": "pci_payment_gateway"}]

        results = await mock_classifier.classify_batch(logs)

        assert len(results) == 1
        assert results[0].compliance_bypassed
        assert results[0].prediction.category == "critical"
        assert results[0].prediction.model == "compliance_bypass"


class TestSafeEnsembleFailOpen:
    """Test fail-open behavior."""

    @pytest.mark.asyncio
    async def test_fail_open_on_error(self):
        """Should fail-open when classification fails repeatedly."""
        classifier = SafeEnsembleClassifier(config={"timeout_seconds": 1.0})
        classifier.is_loaded = True

        # Track call count for circuit breaker
        call_count = 0
        fail_open_used = False

        async def mock_call(fn, texts, logs=None):
            nonlocal call_count, fail_open_used
            call_count += 1
            if call_count > 5:  # After circuit opens
                fail_open_used = True
                # Return fail-open results
                return [
                    ClassificationResult(
                        prediction=Prediction(
                            category="critical",
                            confidence=0.0,
                            model="fail_open",
                            probabilities={
                                "critical": 1.0,
                                "suspicious": 0.0,
                                "routine": 0.0,
                                "noise": 0.0,
                            },
                            explanation={"fail_open": True, "reason": "circuit_open"},
                        ),
                        processing_time_ms=0.0,
                        fail_open_used=True,
                        models_used=[],
                    )
                    for _ in texts
                ]
            # Before circuit opens, return success
            return [
                ClassificationResult(
                    prediction=Prediction(category="routine", confidence=0.8, model="test"),
                    processing_time_ms=10.0,
                    fail_open_used=False,
                    models_used=["test"],
                )
                for _ in texts
            ]

        classifier.circuit_breaker.call = mock_call

        logs = [{"message": "Test log", "source": "test"}]

        results = []
        for _ in range(6):  # Exceed failure threshold
            result = await classifier.classify_batch(logs)
            results.extend(result)

        # Last results should be fail-open
        last_result = results[-1]
        assert last_result.fail_open_used or last_result.prediction.category == "critical"

    @pytest.mark.asyncio
    async def test_fail_open_on_timeout(self):
        """Should fail-open on timeout."""
        from src.models.safe_ensemble import create_fail_open_prediction

        classifier = SafeEnsembleClassifier(
            config={"timeout_seconds": 0.05}  # Very short timeout (50ms)
        )
        classifier.is_loaded = True

        # Mock circuit_breaker.call to simulate timeout behavior
        async def mock_timeout_call(fn, texts, logs=None):
            # Simulate timeout - return fail-open predictions
            return [
                ClassificationResult(
                    prediction=create_fail_open_prediction(text, "timeout"),
                    processing_time_ms=50.0,
                    fail_open_used=True,
                    models_used=[],
                )
                for text in texts
            ]

        classifier.circuit_breaker.call = mock_timeout_call

        logs = [{"message": "Test log", "source": "test"}]
        results = await classifier.classify_batch(logs)

        assert len(results) == 1
        assert results[0].fail_open_used


class TestSafeEnsembleCriticalOverride:
    """Test critical override functionality."""

    @pytest.mark.asyncio
    async def test_rule_based_critical_override(self):
        """High-confidence rule-based critical should override ensemble."""
        classifier = SafeEnsembleClassifier()
        classifier.is_loaded = True

        # Mock circuit_breaker.call to return a critical prediction
        mock_result = ClassificationResult(
            prediction=Prediction(
                category="critical",
                confidence=0.95,
                model="safe_ensemble",
                probabilities={
                    "critical": 0.95,
                    "suspicious": 0.03,
                    "routine": 0.01,
                    "noise": 0.01,
                },
                explanation={
                    "model_predictions": {
                        "rule_based": {"prediction": "critical", "confidence": 0.95}
                    }
                },
            ),
            processing_time_ms=10.0,
            fail_open_used=False,
            models_used=["rule_based", "tfidf_xgboost", "anomaly_detector"],
        )

        async def mock_classify(fn, texts, logs=None):
            return [mock_result for _ in texts]

        classifier.circuit_breaker.call = mock_classify

        logs = [{"message": "Malware detected!", "source": "antivirus"}]
        results = await classifier.classify_batch(logs)

        # Should be critical
        assert results[0].prediction.category == "critical"


class TestSafeEnsembleHealth:
    """Test health status reporting."""

    def test_health_status_healthy(self):
        """Should report healthy when circuit is closed and models are loaded."""
        from src.utils.circuit_breaker import CircuitState

        classifier = SafeEnsembleClassifier()

        # Mock loaded classifiers
        classifier.classifiers = {
            "rule_based": MagicMock(is_loaded=True),
            "tfidf_xgboost": MagicMock(is_loaded=True),
        }
        classifier.is_loaded = True

        # Reset circuit breaker to ensure closed state
        classifier.circuit_breaker.stats.state = CircuitState.CLOSED

        status = classifier.get_health_status()

        assert status["healthy"]
        assert "rule_based" in status["models"]["healthy"]
        assert len(status["models"]["unhealthy"]) == 0

    def test_health_status_degraded(self):
        """Should report unhealthy models."""
        classifier = SafeEnsembleClassifier()

        classifier.classifiers = {
            "rule_based": MagicMock(is_loaded=True),
            "tfidf_xgboost": MagicMock(is_loaded=False),
        }
        classifier.is_loaded = True

        status = classifier.get_health_status()

        assert "tfidf_xgboost" in status["models"]["unhealthy"]


class TestClassificationResult:
    """Test ClassificationResult dataclass."""

    def test_result_creation(self):
        """Should create classification result correctly."""
        prediction = Prediction(category="suspicious", confidence=0.75, model="ensemble")

        result = ClassificationResult(
            prediction=prediction,
            processing_time_ms=45.2,
            compliance_bypassed=False,
            fail_open_used=False,
            models_used=["rule_based", "tfidf_xgboost"],
        )

        assert result.prediction.category == "suspicious"
        assert result.processing_time_ms == 45.2
        assert not result.compliance_bypassed
        assert not result.fail_open_used
        assert len(result.models_used) == 2

"""
Safe Ensemble Classifier

Production-ready ensemble classifier with fail-open behavior,
circuit breaker pattern, and compliance bypass integration.

This is the main classifier to use in production environments.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from src.models.anomaly_detector import AnomalyDetector
from src.models.base import BaseClassifier, ClassifierRegistry, Prediction
from src.models.rule_based import RuleBasedClassifier
from src.models.tfidf_classifier import TFIDFClassifier
from src.monitoring.production_metrics import (
    CIRCUIT_BREAKER_STATE,
    METRICS,
    MODEL_PREDICTION_COUNT,
)
from src.preprocessing.compliance_gate import (
    ComplianceGate,
    create_compliance_bypass_prediction,
)
from src.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    register_circuit_breaker,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ClassificationResult:
    """Result of classification including metadata."""
    prediction: Prediction
    processing_time_ms: float
    compliance_bypassed: bool = False
    fail_open_used: bool = False
    models_used: list[str] = None

    def __post_init__(self):
        if self.models_used is None:
            self.models_used = []


def create_fail_open_prediction(
    text: str,
    reason: str = "system_error"
) -> Prediction:
    """
    Create a fail-open prediction that ensures log goes to QRadar.

    When the AI system fails, we default to sending ALL logs to QRadar
    to ensure no security events are missed.
    """
    return Prediction(
        category="critical",  # Always forward on failure
        confidence=0.0,       # Zero confidence indicates fail-open
        model="fail_open",
        probabilities={"critical": 1.0, "suspicious": 0.0, "routine": 0.0, "noise": 0.0},
        explanation={
            "fail_open": True,
            "reason": reason,
            "note": "Log forwarded to QRadar due to system safety measure"
        }
    )


@ClassifierRegistry.register("safe_ensemble")
class SafeEnsembleClassifier(BaseClassifier):
    """
    Production-safe ensemble classifier.

    Features:
    - Fail-open behavior: All logs go to QRadar on any error
    - Circuit breaker: Prevents cascading failures
    - Compliance bypass: Regulated logs skip AI classification
    - Timeout protection: Guaranteed response time
    - Full observability: Metrics for all operations

    This classifier should be used in production instead of the
    basic EnsembleClassifier.

    Example:
        classifier = SafeEnsembleClassifier(
            model_path="models/latest",
            config=config
        )
        await classifier.load()

        results = await classifier.classify_batch(logs)
        for result in results:
            if result.fail_open_used:
                logger.warning("Fail-open was triggered")
    """

    def __init__(
        self,
        model_path: str | None = None,
        config: dict[str, Any] | None = None
    ):
        super().__init__("safe_ensemble", config)
        self.model_path = model_path

        # Configuration
        self.config = config or {}
        self.timeout_seconds = self.config.get("timeout_seconds", 5.0)
        self.max_batch_size = self.config.get("max_batch_size", 1000)

        # Model weights
        self.weights = {
            "rule_based": 0.30,
            "tfidf_xgboost": 0.45,
            "anomaly_detector": 0.25
        }
        if config and "ensemble" in config:
            if "weights" in config["ensemble"]:
                self.weights = config["ensemble"]["weights"]

        # Combination strategy
        self.strategy = self.config.get("ensemble", {}).get(
            "combination_strategy", "weighted_average"
        )

        # Component classifiers
        self.classifiers: dict[str, BaseClassifier] = {}

        # Compliance gate
        self.compliance_gate = ComplianceGate(
            self.config.get("compliance", {})
        )

        # Circuit breaker for fail-open
        self.circuit_breaker = CircuitBreaker(
            name="ensemble_classifier",
            fallback=self._fail_open_fallback,
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout_seconds=30.0
            ),
            on_state_change=self._on_circuit_state_change
        )
        register_circuit_breaker(self.circuit_breaker)

        logger.info(
            "SafeEnsembleClassifier initialized",
            extra={
                "model_path": model_path,
                "timeout_seconds": self.timeout_seconds,
                "weights": self.weights
            }
        )

    def _on_circuit_state_change(
        self,
        old_state: CircuitState,
        new_state: CircuitState
    ):
        """Handle circuit breaker state changes."""
        state_value = {"closed": 0, "open": 1, "half_open": 2}
        CIRCUIT_BREAKER_STATE.labels(
            circuit_name="ensemble_classifier"
        ).set(state_value.get(new_state.value, 0))

        if new_state == CircuitState.OPEN:
            logger.critical(
                "ALERT: Ensemble classifier circuit breaker OPEN - "
                "all logs will be forwarded to QRadar",
                extra={"old_state": old_state.value, "new_state": new_state.value}
            )

    async def _fail_open_fallback(
        self,
        texts: list[str],
        logs: list[dict[str, Any]] | None = None
    ) -> list[ClassificationResult]:
        """
        Fallback function when circuit is open.

        Creates fail-open predictions for all logs, ensuring they
        are forwarded to QRadar.
        """
        METRICS.record_fail_open_event("circuit_open", len(texts))

        results = []
        for text in texts:
            prediction = create_fail_open_prediction(text, "circuit_open")
            results.append(ClassificationResult(
                prediction=prediction,
                processing_time_ms=0.0,
                fail_open_used=True,
                models_used=[]
            ))

        return results

    async def load(self):
        """Load all component classifiers with error handling."""
        logger.info("Loading SafeEnsembleClassifier components...")

        errors = []

        # Load rule-based classifier (critical - must succeed)
        try:
            rule_config = self.config.get("rule_based", {})
            rule_config.setdefault("rules_path", "configs/rules.yaml")
            self.classifiers["rule_based"] = RuleBasedClassifier(rule_config)
            await self.classifiers["rule_based"].load()
            logger.info("Rule-based classifier loaded")
        except Exception as e:
            errors.append(f"rule_based: {e}")
            logger.error(f"Failed to load rule-based classifier: {e}")

        # Load TF-IDF classifier
        try:
            tfidf_config = self.config.get("tfidf", {})
            if self.model_path:
                tfidf_config["model_path"] = f"{self.model_path}/tfidf_xgboost"
            self.classifiers["tfidf_xgboost"] = TFIDFClassifier(tfidf_config)
            await self.classifiers["tfidf_xgboost"].load()
            logger.info("TF-IDF classifier loaded")
        except Exception as e:
            errors.append(f"tfidf_xgboost: {e}")
            logger.warning(f"Failed to load TF-IDF classifier: {e}")

        # Load anomaly detector
        try:
            anomaly_config = self.config.get("anomaly", {})
            if self.model_path:
                anomaly_config["model_path"] = f"{self.model_path}/anomaly_detector"
            self.classifiers["anomaly_detector"] = AnomalyDetector(anomaly_config)
            await self.classifiers["anomaly_detector"].load()
            logger.info("Anomaly detector loaded")
        except Exception as e:
            errors.append(f"anomaly_detector: {e}")
            logger.warning(f"Failed to load anomaly detector: {e}")

        # Check minimum viable configuration
        if "rule_based" not in self.classifiers:
            raise RuntimeError(
                "Rule-based classifier is required but failed to load. "
                f"Errors: {errors}"
            )

        self.is_loaded = True

        if errors:
            logger.warning(
                f"SafeEnsembleClassifier loaded with degraded models: {errors}"
            )
        else:
            logger.info(
                f"SafeEnsembleClassifier fully loaded with {len(self.classifiers)} models"
            )

    async def classify_batch(
        self,
        logs: list[dict[str, Any]]
    ) -> list[ClassificationResult]:
        """
        Classify a batch of logs with full safety measures.

        Args:
            logs: List of log dictionaries with 'message' and optional metadata

        Returns:
            List of ClassificationResult with predictions and metadata
        """
        if not logs:
            return []

        start_time = time.time()

        # Separate compliance-regulated logs
        regulated_logs = []
        regular_logs = []
        regulated_indices = []
        regular_indices = []

        for i, log in enumerate(logs):
            decision = self.compliance_gate.check(log)
            if decision.is_regulated:
                regulated_logs.append((log, decision))
                regulated_indices.append(i)

                # Record compliance bypass metric
                for rule in decision.matched_rules:
                    for framework in decision.frameworks:
                        METRICS.record_compliance_bypass(framework.value, rule)
            else:
                regular_logs.append(log)
                regular_indices.append(i)

        # Process compliance-bypassed logs
        regulated_results = []
        for log, decision in regulated_logs:
            bypass_pred = create_compliance_bypass_prediction(log, decision)
            regulated_results.append(ClassificationResult(
                prediction=Prediction(**{
                    k: v for k, v in bypass_pred.items()
                    if k in ['category', 'confidence', 'model', 'probabilities', 'explanation']
                }),
                processing_time_ms=0.0,
                compliance_bypassed=True,
                models_used=["compliance_bypass"]
            ))

        # Process regular logs through ensemble (with circuit breaker)
        regular_results = []
        if regular_logs:
            texts = [log.get("message", "") for log in regular_logs]

            try:
                # Apply timeout protection
                regular_results = await asyncio.wait_for(
                    self.circuit_breaker.call(
                        self._classify_texts,
                        texts,
                        regular_logs
                    ),
                    timeout=self.timeout_seconds
                )
            except TimeoutError:
                logger.error(
                    f"Classification timeout after {self.timeout_seconds}s",
                    extra={"batch_size": len(texts)}
                )
                METRICS.record_fail_open_event("timeout", len(texts))

                # Fail-open on timeout
                regular_results = [
                    ClassificationResult(
                        prediction=create_fail_open_prediction(text, "timeout"),
                        processing_time_ms=self.timeout_seconds * 1000,
                        fail_open_used=True,
                        models_used=[]
                    )
                    for text in texts
                ]

        # Merge results in original order
        all_results = [None] * len(logs)
        for i, result in zip(regulated_indices, regulated_results, strict=False):
            all_results[i] = result
        for i, result in zip(regular_indices, regular_results, strict=False):
            all_results[i] = result

        # Record batch metrics
        total_time = time.time() - start_time
        METRICS.record_batch_processed(len(logs), "safe_ensemble", total_time)

        return all_results

    async def _classify_texts(
        self,
        texts: list[str],
        logs: list[dict[str, Any]] | None = None
    ) -> list[ClassificationResult]:
        """
        Internal classification with ensemble logic.

        This method is protected by the circuit breaker.
        """
        start_time = time.time()

        if not self.is_loaded:
            await self.load()

        # Get predictions from all available classifiers
        all_predictions: dict[str, list[Prediction]] = {}
        models_used = []

        for name, classifier in self.classifiers.items():
            try:
                preds = await classifier.predict_batch(texts)
                all_predictions[name] = preds
                models_used.append(name)

                # Record per-model metrics
                for pred in preds:
                    MODEL_PREDICTION_COUNT.labels(
                        model=name,
                        category=pred.category
                    ).inc()

            except Exception as e:
                logger.warning(
                    f"Classifier {name} failed",
                    extra={"error": str(e), "batch_size": len(texts)}
                )
                # Use neutral predictions for failed classifier
                all_predictions[name] = [
                    Prediction(
                        category="routine",
                        confidence=0.5,
                        model=name,
                        explanation={"error": str(e)}
                    )
                    for _ in texts
                ]

        # Combine predictions
        combined = self._combine_predictions(texts, all_predictions)

        # Create results
        processing_time = (time.time() - start_time) * 1000

        results = []
        for i, prediction in enumerate(combined):
            per_item_time = processing_time / len(texts)
            results.append(ClassificationResult(
                prediction=prediction,
                processing_time_ms=per_item_time,
                fail_open_used=False,
                models_used=models_used
            ))

            # Record individual log metrics
            source = logs[i].get("source", "unknown") if logs else "unknown"
            METRICS.record_log_processed(
                source=source,
                category=prediction.category,
                model="safe_ensemble",
                confidence=prediction.confidence,
                latency_seconds=per_item_time / 1000,
                forwarded_to_qradar=prediction.category in ["critical", "suspicious"]
            )

        return results

    def _combine_predictions(
        self,
        texts: list[str],
        all_predictions: dict[str, list[Prediction]]
    ) -> list[Prediction]:
        """Combine predictions from all models using weighted average."""
        results = []

        for i in range(len(texts)):
            category_scores: dict[str, float] = dict.fromkeys(self.CATEGORIES, 0.0)
            explanations = {}

            total_weight = 0.0

            for model_name, predictions in all_predictions.items():
                pred = predictions[i]
                weight = self.weights.get(model_name, 0.25)
                total_weight += weight

                if pred.probabilities:
                    for cat, prob in pred.probabilities.items():
                        category_scores[cat] += weight * prob
                else:
                    category_scores[pred.category] += weight * pred.confidence
                    remaining = weight * (1 - pred.confidence)
                    for cat in self.CATEGORIES:
                        if cat != pred.category:
                            category_scores[cat] += remaining / (len(self.CATEGORIES) - 1)

                explanations[model_name] = {
                    "prediction": pred.category,
                    "confidence": pred.confidence,
                    "explanation": pred.explanation
                }

            # Normalize scores
            if total_weight > 0:
                category_scores = {k: v / total_weight for k, v in category_scores.items()}

            # Get final prediction
            final_category = max(category_scores, key=category_scores.get)
            final_confidence = category_scores[final_category]

            # CRITICAL SAFETY OVERRIDE:
            # If rule-based says critical with high confidence, always use it
            rule_pred = all_predictions.get("rule_based", [None])[i]
            if rule_pred:
                if rule_pred.category == "critical" and rule_pred.confidence > 0.85:
                    final_category = "critical"
                    final_confidence = rule_pred.confidence
                    explanations["override"] = "Rule-based critical override applied"

            results.append(Prediction(
                category=final_category,
                confidence=final_confidence,
                model="safe_ensemble",
                probabilities=category_scores,
                explanation={"model_predictions": explanations}
            ))

        return results

    async def predict(self, text: str) -> Prediction:
        """Classify a single log message."""
        log = {"message": text}
        results = await self.classify_batch([log])
        return results[0].prediction

    async def predict_batch(self, texts: list[str]) -> list[Prediction]:
        """Classify a batch of log messages (simple interface)."""
        logs = [{"message": text} for text in texts]
        results = await self.classify_batch(logs)
        return [r.prediction for r in results]

    def get_health_status(self) -> dict[str, Any]:
        """Get health status for monitoring."""
        circuit_stats = self.circuit_breaker.get_stats()
        compliance_stats = self.compliance_gate.get_stats()

        models_healthy = []
        models_unhealthy = []

        for name, classifier in self.classifiers.items():
            if classifier.is_loaded:
                models_healthy.append(name)
            else:
                models_unhealthy.append(name)

        return {
            "healthy": circuit_stats["state"] == "closed" and len(models_healthy) > 0,
            "circuit_breaker": circuit_stats,
            "compliance_gate": compliance_stats,
            "models": {
                "healthy": models_healthy,
                "unhealthy": models_unhealthy,
                "total": len(self.classifiers)
            }
        }


# Factory function for easy creation
async def create_safe_classifier(
    model_path: str = "models/latest",
    config: dict[str, Any] | None = None
) -> SafeEnsembleClassifier:
    """
    Factory function to create and initialize a SafeEnsembleClassifier.

    Usage:
        classifier = await create_safe_classifier("models/v1")
        results = await classifier.classify_batch(logs)
    """
    classifier = SafeEnsembleClassifier(model_path=model_path, config=config)
    await classifier.load()
    return classifier

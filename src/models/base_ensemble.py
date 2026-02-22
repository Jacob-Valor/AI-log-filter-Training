"""
Base Ensemble Classifier

Shared logic for SafeEnsembleClassifier and ONNXSafeEnsembleClassifier.
Eliminates code duplication for circuit breaker, compliance gate,
prediction combination, and fail-open behaviour.
"""

from __future__ import annotations

import asyncio
import time
from abc import abstractmethod
from typing import Any

from src.models.base import BaseClassifier, Prediction
from src.models.classification_result import ClassificationResult, create_fail_open_prediction
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


class BaseEnsembleClassifier(BaseClassifier):
    """
    Abstract base for production-safe ensemble classifiers.

    Provides shared infrastructure:
    - Fail-open behaviour via circuit breaker
    - Compliance gate bypass for regulated logs
    - Weighted-average prediction combination with safety overrides
    - Timeout protection
    - Full Prometheus observability
    """

    def __init__(
        self,
        name: str,
        model_path: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        super().__init__(name, config)
        self.model_path = model_path
        self.config = config or {}

        # Configuration
        self.timeout_seconds: float = self.config.get("timeout_seconds", 5.0)
        self.max_batch_size: int = self.config.get("max_batch_size", 1000)

        # Model weights
        self.weights: dict[str, float] = {
            "rule_based": 0.30,
            "tfidf_xgboost": 0.45,
            "anomaly_detector": 0.25,
        }
        if config and "ensemble" in config and "weights" in config["ensemble"]:
            self.weights = config["ensemble"]["weights"]

        # Component classifiers – populated by subclasses in load()
        self.classifiers: dict[str, BaseClassifier] = {}

        # Compliance gate
        self.compliance_gate = ComplianceGate(self.config.get("compliance", {}))

        # Circuit breaker for fail-open
        self.circuit_breaker = CircuitBreaker(
            name=f"{name}_classifier",
            fallback=self._fail_open_fallback,
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout_seconds=30.0,
            ),
            on_state_change=self._on_circuit_state_change,
        )
        register_circuit_breaker(self.circuit_breaker)

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @abstractmethod
    async def load(self) -> None:
        """Load model components. Must set self.is_loaded = True."""

    # ------------------------------------------------------------------
    # Circuit breaker helpers
    # ------------------------------------------------------------------

    def _on_circuit_state_change(self, old_state: CircuitState, new_state: CircuitState) -> None:
        state_value = {"closed": 0, "open": 1, "half_open": 2}
        CIRCUIT_BREAKER_STATE.labels(circuit_name=f"{self.name}_classifier").set(
            state_value.get(new_state.value, 0)
        )
        if new_state == CircuitState.OPEN:
            logger.critical(
                "ALERT: %s circuit breaker OPEN – all logs forwarded to QRadar",
                self.name,
                extra={"old_state": old_state.value, "new_state": new_state.value},
            )

    async def _fail_open_fallback(
        self,
        texts: list[str],
        logs: list[dict[str, Any]] | None = None,
    ) -> list[ClassificationResult]:
        METRICS.record_fail_open_event("circuit_open", len(texts))
        return [
            ClassificationResult(
                prediction=create_fail_open_prediction(text, "circuit_open"),
                processing_time_ms=0.0,
                fail_open_used=True,
                models_used=[],
            )
            for text in texts
        ]

    # ------------------------------------------------------------------
    # Core classification pipeline
    # ------------------------------------------------------------------

    async def classify_batch(self, logs: list[dict[str, Any]]) -> list[ClassificationResult]:
        """Classify a batch of logs with full safety measures."""
        if not logs:
            return []

        start_time = time.time()

        # Separate compliance-regulated logs
        regulated_results: list[ClassificationResult] = []
        regular_logs: list[dict[str, Any]] = []
        regulated_indices: list[int] = []
        regular_indices: list[int] = []

        for i, log in enumerate(logs):
            decision = self.compliance_gate.check(log)
            if decision.is_regulated:
                regulated_indices.append(i)
                bypass_pred = create_compliance_bypass_prediction(log, decision)
                regulated_results.append(
                    ClassificationResult(
                        prediction=Prediction(
                            category=bypass_pred["category"],
                            confidence=bypass_pred["confidence"],
                            model=bypass_pred["model"],
                            explanation=bypass_pred.get("explanation"),
                        ),
                        processing_time_ms=0.0,
                        compliance_bypassed=True,
                        models_used=["compliance_bypass"],
                    )
                )
                for rule in decision.matched_rules:
                    for framework in decision.frameworks:
                        METRICS.record_compliance_bypass(framework.value, rule)
            else:
                regular_logs.append(log)
                regular_indices.append(i)

        # Process regular logs through ensemble (with circuit breaker)
        regular_results: list[ClassificationResult] = []
        if regular_logs:
            texts = [log.get("message", "") for log in regular_logs]
            try:
                regular_results = await asyncio.wait_for(
                    self.circuit_breaker.call(self._classify_texts, texts, regular_logs),
                    timeout=self.timeout_seconds,
                )
            except TimeoutError:
                logger.error(
                    "Classification timeout after %ss",
                    self.timeout_seconds,
                    extra={"batch_size": len(texts)},
                )
                METRICS.record_fail_open_event("timeout", len(texts))
                regular_results = [
                    ClassificationResult(
                        prediction=create_fail_open_prediction(text, "timeout"),
                        processing_time_ms=self.timeout_seconds * 1000,
                        fail_open_used=True,
                        models_used=[],
                    )
                    for text in texts
                ]

        # Merge results in original order
        result_map: dict[int, ClassificationResult] = {}
        for i, result in zip(regulated_indices, regulated_results, strict=True):
            result_map[i] = result
        for i, result in zip(regular_indices, regular_results, strict=True):
            result_map[i] = result
        all_results = [result_map[i] for i in range(len(logs))]

        # Record batch metrics
        total_time = time.time() - start_time
        METRICS.record_batch_processed(len(logs), self.name, total_time)
        return all_results

    async def _classify_texts(
        self,
        texts: list[str],
        logs: list[dict[str, Any]] | None = None,
    ) -> list[ClassificationResult]:
        """Internal classification protected by the circuit breaker."""
        start_time = time.time()

        if not self.is_loaded:
            await self.load()

        # Gather predictions from every available classifier
        all_predictions: dict[str, list[Prediction]] = {}
        models_used: list[str] = []

        for name, classifier in self.classifiers.items():
            try:
                preds = await classifier.predict_batch(texts)
                all_predictions[name] = preds
                models_used.append(name)
                for pred in preds:
                    MODEL_PREDICTION_COUNT.labels(model=name, category=pred.category).inc()
            except Exception as e:
                logger.warning(
                    "Classifier %s failed",
                    name,
                    extra={"error": str(e), "batch_size": len(texts)},
                )
                all_predictions[name] = [
                    Prediction(
                        category="routine",
                        confidence=0.5,
                        model=name,
                        explanation={"error": str(e)},
                    )
                    for _ in texts
                ]

        combined = self._combine_predictions(texts, all_predictions)
        processing_time = (time.time() - start_time) * 1000

        results: list[ClassificationResult] = []
        per_item_time = processing_time / max(len(texts), 1)
        for i, prediction in enumerate(combined):
            results.append(
                ClassificationResult(
                    prediction=prediction,
                    processing_time_ms=per_item_time,
                    fail_open_used=False,
                    models_used=models_used,
                )
            )
            source = logs[i].get("source", "unknown") if logs else "unknown"
            METRICS.record_log_processed(
                source=source,
                category=prediction.category,
                model=self.name,
                confidence=prediction.confidence,
                latency_seconds=per_item_time / 1000,
                forwarded_to_qradar=prediction.category in ("critical", "suspicious"),
            )
        return results

    # ------------------------------------------------------------------
    # Prediction combination
    # ------------------------------------------------------------------

    def _combine_predictions(
        self,
        texts: list[str],
        all_predictions: dict[str, list[Prediction]],
    ) -> list[Prediction]:
        """Combine predictions from all models using weighted average."""
        results: list[Prediction] = []

        for idx, _text in enumerate(texts):
            category_scores: dict[str, float] = dict.fromkeys(self.CATEGORIES, 0.0)
            explanations: dict[str, Any] = {}
            total_weight = 0.0

            for model_name, predictions in all_predictions.items():
                pred = predictions[idx]
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
                    "explanation": pred.explanation,
                }

            # Normalize
            if total_weight > 0:
                category_scores = {k: v / total_weight for k, v in category_scores.items()}

            final_category = max(category_scores, key=lambda k: category_scores[k])
            final_confidence = category_scores[final_category]

            # CRITICAL SAFETY OVERRIDE: rule-based critical wins
            rule_pred = all_predictions.get("rule_based", [None])[idx]
            if rule_pred and rule_pred.category == "critical" and rule_pred.confidence > 0.85:
                final_category = "critical"
                final_confidence = rule_pred.confidence
                explanations["override"] = "Rule-based critical override applied"

            results.append(
                Prediction(
                    category=final_category,
                    confidence=final_confidence,
                    model=self.name,
                    probabilities=category_scores,
                    explanation={"model_predictions": explanations},
                )
            )

        return results

    # ------------------------------------------------------------------
    # Simple interface (delegates to classify_batch)
    # ------------------------------------------------------------------

    async def predict(self, text: str) -> Prediction:
        """Classify a single log message."""
        results = await self.classify_batch([{"message": text}])
        return results[0].prediction

    async def predict_batch(self, texts: list[str]) -> list[Prediction]:
        """Classify a batch of log messages (simple interface)."""
        logs = [{"message": text} for text in texts]
        results = await self.classify_batch(logs)
        return [r.prediction for r in results]

    # ------------------------------------------------------------------
    # Health / monitoring
    # ------------------------------------------------------------------

    def get_health_status(self) -> dict[str, Any]:
        """Get health status for monitoring."""
        circuit_stats = self.circuit_breaker.get_stats()
        compliance_stats = self.compliance_gate.get_stats()

        models_healthy = [n for n, c in self.classifiers.items() if c.is_loaded]
        models_unhealthy = [n for n, c in self.classifiers.items() if not c.is_loaded]

        return {
            "healthy": circuit_stats["state"] == "closed" and len(models_healthy) > 0,
            "circuit_breaker": circuit_stats,
            "compliance_gate": compliance_stats,
            "models": {
                "healthy": models_healthy,
                "unhealthy": models_unhealthy,
                "total": len(self.classifiers),
            },
        }

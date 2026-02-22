"""
Safe Ensemble Classifier

Production-ready ensemble classifier with fail-open behavior,
circuit breaker pattern, and compliance bypass integration.

This is the main classifier to use in production environments.
"""

from typing import Any

from src.models.anomaly_detector import AnomalyDetector
from src.models.base import ClassifierRegistry
from src.models.base_ensemble import BaseEnsembleClassifier
from src.models.rule_based import RuleBasedClassifier
from src.models.tfidf_classifier import TFIDFClassifier
from src.utils.logging import get_logger

logger = get_logger(__name__)


@ClassifierRegistry.register("safe_ensemble")
class SafeEnsembleClassifier(BaseEnsembleClassifier):
    """
    Production-safe ensemble classifier.

    Features:
    - Fail-open behavior: All logs go to QRadar on any error
    - Circuit breaker: Prevents cascading failures
    - Compliance bypass: Regulated logs skip AI classification
    - Timeout protection: Guaranteed response time
    - Full observability: Metrics for all operations

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

    def __init__(self, model_path: str | None = None, config: dict[str, Any] | None = None):
        super().__init__("safe_ensemble", model_path=model_path, config=config)

        logger.info(
            "SafeEnsembleClassifier initialized",
            extra={
                "model_path": model_path,
                "timeout_seconds": self.timeout_seconds,
                "weights": self.weights,
            },
        )

    async def load(self) -> None:
        """Load all component classifiers with error handling."""
        logger.info("Loading SafeEnsembleClassifier components...")
        errors: list[str] = []

        # Load rule-based classifier (critical – must succeed)
        try:
            rule_config = self.config.get("rule_based", {})
            rule_config.setdefault("rules_path", "configs/rules.yaml")
            self.classifiers["rule_based"] = RuleBasedClassifier(rule_config)
            await self.classifiers["rule_based"].load()
            logger.info("Rule-based classifier loaded")
        except Exception as e:
            errors.append(f"rule_based: {e}")
            logger.error("Failed to load rule-based classifier: %s", e)

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
            logger.warning("Failed to load TF-IDF classifier: %s", e)

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
            logger.warning("Failed to load anomaly detector: %s", e)

        # Check minimum viable configuration
        if "rule_based" not in self.classifiers:
            raise RuntimeError(
                f"Rule-based classifier is required but failed to load. Errors: {errors}"
            )

        self.is_loaded = True

        if errors:
            logger.warning("SafeEnsembleClassifier loaded with degraded models: %s", errors)
        else:
            logger.info(
                "SafeEnsembleClassifier fully loaded with %d models",
                len(self.classifiers),
            )


# Factory function for easy creation
async def create_safe_classifier(
    model_path: str = "models/latest", config: dict[str, Any] | None = None
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

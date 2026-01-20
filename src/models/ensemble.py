"""
Ensemble Classifier

Combines multiple classifiers for robust log classification.
Uses weighted averaging or voting for final predictions.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models.rule_based import RuleBasedClassifier
from src.models.tfidf_classifier import TFIDFClassifier
from src.utils.logging import get_logger

from src.models.anomaly_detector import AnomalyDetector
from src.models.base import BaseClassifier, ClassifierRegistry, Prediction

logger = get_logger(__name__)


@ClassifierRegistry.register("ensemble")
class EnsembleClassifier(BaseClassifier):
    """
    Ensemble classifier combining multiple models.

    Combines rule-based, ML, and anomaly detection approaches
    for robust log classification.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__("ensemble", config)
        self.model_path = model_path

        # Default weights
        self.weights = {
            "rule_based": 0.30,
            "tfidf_xgboost": 0.45,
            "anomaly_detector": 0.25
        }

        if config and "ensemble" in config:
            ensemble_config = config["ensemble"]
            if "weights" in ensemble_config:
                self.weights = ensemble_config["weights"]

        # Combination strategy
        self.strategy = config.get("ensemble", {}).get(
            "combination_strategy", "weighted_average"
        ) if config else "weighted_average"

        # Initialize component classifiers
        self.classifiers: Dict[str, BaseClassifier] = {}

    async def load(self):
        """Load all component classifiers."""
        logger.info("Loading ensemble classifier components...")

        # Rule-based classifier
        rule_config = self.config.get("rule_based", {}) if self.config else {}
        rule_config["rules_path"] = rule_config.get("rules_path", "configs/rules.yaml")
        self.classifiers["rule_based"] = RuleBasedClassifier(rule_config)
        await self.classifiers["rule_based"].load()

        # TF-IDF classifier
        tfidf_config = self.config.get("tfidf", {}) if self.config else {}
        if self.model_path:
            tfidf_config["model_path"] = f"{self.model_path}/tfidf_xgboost"
        self.classifiers["tfidf_xgboost"] = TFIDFClassifier(tfidf_config)
        await self.classifiers["tfidf_xgboost"].load()

        # Anomaly detector
        anomaly_config = self.config.get("anomaly", {}) if self.config else {}
        if self.model_path:
            anomaly_config["model_path"] = f"{self.model_path}/anomaly_detector"
        self.classifiers["anomaly_detector"] = AnomalyDetector(anomaly_config)
        await self.classifiers["anomaly_detector"].load()

        self.is_loaded = True
        logger.info(f"Loaded {len(self.classifiers)} classifiers")

    async def predict(self, text: str) -> Prediction:
        """Classify a single log message."""
        predictions = await self.predict_batch([text])
        return predictions[0]

    async def predict_batch(self, texts: List[str]) -> List[Prediction]:
        """Classify a batch of log messages using ensemble."""
        if not self.is_loaded:
            await self.load()

        # Get predictions from all classifiers
        all_predictions: Dict[str, List[Prediction]] = {}

        for name, classifier in self.classifiers.items():
            try:
                preds = await classifier.predict_batch(texts)
                all_predictions[name] = preds
            except Exception as e:
                logger.warning(f"Classifier {name} failed: {e}")
                # Use default predictions
                all_predictions[name] = [
                    Prediction(
                        category="routine",
                        confidence=0.5,
                        model=name
                    )
                    for _ in texts
                ]

        # Combine predictions
        if self.strategy == "weighted_average":
            return self._combine_weighted_average(texts, all_predictions)
        elif self.strategy == "max_voting":
            return self._combine_max_voting(texts, all_predictions)
        else:
            return self._combine_weighted_average(texts, all_predictions)

    def _combine_weighted_average(
        self,
        texts: List[str],
        all_predictions: Dict[str, List[Prediction]]
    ) -> List[Prediction]:
        """Combine predictions using weighted averaging."""
        results = []

        for i in range(len(texts)):
            # Aggregate probabilities across models
            category_scores: Dict[str, float] = {cat: 0.0 for cat in self.CATEGORIES}
            explanations = {}

            for model_name, predictions in all_predictions.items():
                pred = predictions[i]
                weight = self.weights.get(model_name, 0.25)

                if pred.probabilities:
                    # Use full probability distribution
                    for cat, prob in pred.probabilities.items():
                        category_scores[cat] += weight * prob
                else:
                    # Use confidence for predicted category
                    category_scores[pred.category] += weight * pred.confidence
                    # Distribute remaining weight
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
            total = sum(category_scores.values())
            if total > 0:
                category_scores = {k: v / total for k, v in category_scores.items()}

            # Get final prediction
            final_category = max(category_scores, key=category_scores.get)
            final_confidence = category_scores[final_category]

            # Override: If rule-based says critical with high confidence, use it
            rule_pred = all_predictions.get("rule_based", [None])[i]
            if rule_pred and rule_pred.category == "critical" and rule_pred.confidence > 0.9:
                final_category = "critical"
                final_confidence = rule_pred.confidence

            results.append(Prediction(
                category=final_category,
                confidence=final_confidence,
                model="ensemble",
                probabilities=category_scores,
                explanation={"model_predictions": explanations}
            ))

        return results

    def _combine_max_voting(
        self,
        texts: List[str],
        all_predictions: Dict[str, List[Prediction]]
    ) -> List[Prediction]:
        """Combine predictions using max voting."""
        results = []

        for i in range(len(texts)):
            votes: Dict[str, float] = {cat: 0.0 for cat in self.CATEGORIES}
            explanations = {}

            for model_name, predictions in all_predictions.items():
                pred = predictions[i]
                weight = self.weights.get(model_name, 0.25)
                votes[pred.category] += weight

                explanations[model_name] = {
                    "prediction": pred.category,
                    "confidence": pred.confidence
                }

            final_category = max(votes, key=votes.get)
            final_confidence = votes[final_category] / sum(votes.values())

            results.append(Prediction(
                category=final_category,
                confidence=final_confidence,
                model="ensemble",
                explanation={"votes": votes, "model_predictions": explanations}
            ))

        return results

    def save(self, path: str):
        """Save all component models."""
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        for name, classifier in self.classifiers.items():
            try:
                classifier.save(str(save_path / name))
            except NotImplementedError:
                logger.debug(f"Classifier {name} does not support saving")

        logger.info(f"Ensemble saved to {save_path}")

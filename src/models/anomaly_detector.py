"""
Anomaly Detection Model

Uses Isolation Forest for detecting anomalous log patterns.
Complements classification by identifying unusual logs.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from src.models.base import BaseClassifier, ClassifierRegistry, Prediction
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AnomalyFeatures:
    """Features extracted for anomaly detection."""

    message_length: int
    word_count: int
    digit_ratio: float
    special_char_ratio: float
    uppercase_ratio: float
    has_error_keyword: int
    has_ip_address: int
    hour_of_day: int

    def to_array(self) -> np.ndarray:
        return np.array([
            self.message_length,
            self.word_count,
            self.digit_ratio,
            self.special_char_ratio,
            self.uppercase_ratio,
            self.has_error_keyword,
            self.has_ip_address,
            self.hour_of_day
        ])


@ClassifierRegistry.register("anomaly_detector")
class AnomalyDetector(BaseClassifier):
    """
    Anomaly detection for log classification.

    Uses Isolation Forest to detect unusual log patterns that
    may indicate security issues even if not matching known patterns.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("anomaly_detector", config)
        self.model = None
        self.scaler = None

        # Config
        self.contamination = config.get("contamination", 0.1) if config else 0.1
        self.n_estimators = config.get("n_estimators", 200) if config else 200
        self.anomaly_threshold = config.get("threshold", -0.5) if config else -0.5

    async def load(self):
        """Load trained model from disk."""
        model_path = Path(self.config.get("model_path", "models/anomaly_detector"))

        try:
            artifacts = joblib.load(model_path / "model.joblib")
            self.model = artifacts["model"]
            self.scaler = artifacts["scaler"]
            self.is_loaded = True
            logger.info(f"Loaded anomaly detector from {model_path}")

        except FileNotFoundError:
            logger.warning(f"Model not found at {model_path}, initializing empty model")
            self._initialize_empty()
            self.is_loaded = True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def _initialize_empty(self):
        """Initialize empty model."""
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            max_samples="auto",
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()

    def extract_features(self, text: str) -> AnomalyFeatures:
        """Extract numerical features from log text."""
        import re
        from datetime import datetime

        # Basic text features
        message_length = len(text)
        word_count = len(text.split())

        # Character ratios
        digit_count = sum(c.isdigit() for c in text)
        special_count = sum(not c.isalnum() and not c.isspace() for c in text)
        upper_count = sum(c.isupper() for c in text)

        digit_ratio = digit_count / max(message_length, 1)
        special_char_ratio = special_count / max(message_length, 1)
        uppercase_ratio = upper_count / max(message_length, 1)

        # Keyword indicators
        has_error = 1 if re.search(r"\b(error|fail|exception|critical)\b", text, re.I) else 0
        has_ip = 1 if re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text) else 0

        # Time feature (current hour as proxy)
        hour = datetime.now().hour

        return AnomalyFeatures(
            message_length=message_length,
            word_count=word_count,
            digit_ratio=digit_ratio,
            special_char_ratio=special_char_ratio,
            uppercase_ratio=uppercase_ratio,
            has_error_keyword=has_error,
            has_ip_address=has_ip,
            hour_of_day=hour
        )

    async def predict(self, text: str) -> Prediction:
        """Check if a log is anomalous."""
        predictions = await self.predict_batch([text])
        return predictions[0]

    async def predict_batch(self, texts: list[str]) -> list[Prediction]:
        """Check if logs are anomalous."""
        if not self.is_loaded:
            await self.load()

        # Extract features
        features = [self.extract_features(text).to_array() for text in texts]
        X = np.array(features)

        # Check if model is trained
        if not hasattr(self.scaler, "mean_"):
            return [
                Prediction(
                    category="routine",
                    confidence=0.5,
                    model=self.name,
                    explanation={"note": "Model not trained", "is_anomaly": False}
                )
                for _ in texts
            ]

        # Scale and predict
        X_scaled = self.scaler.transform(X)
        scores = self.model.score_samples(X_scaled)
        predictions_raw = self.model.predict(X_scaled)

        results = []
        for score, pred in zip(scores, predictions_raw, strict=False):
            is_anomaly = pred == -1

            # Convert anomaly detection to classification
            if is_anomaly:
                category = "suspicious"
                confidence = min(0.9, 0.5 + abs(score))
            else:
                category = "routine"  # Let other models decide
                confidence = 0.5

            results.append(Prediction(
                category=category,
                confidence=confidence,
                model=self.name,
                explanation={
                    "is_anomaly": is_anomaly,
                    "anomaly_score": float(score)
                }
            ))

        return results

    def train(self, texts: list[str]):
        """Train anomaly detector on normal logs."""
        logger.info(f"Training anomaly detector on {len(texts)} samples")

        # Extract features
        features = [self.extract_features(text).to_array() for text in texts]
        X = np.array(features)

        # Scale and fit
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)

        logger.info("Anomaly detector training complete")

    def save(self, path: str):
        """Save model to disk."""
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        artifacts = {
            "model": self.model,
            "scaler": self.scaler,
            "config": self.config
        }

        joblib.dump(artifacts, save_path / "model.joblib")
        logger.info(f"Anomaly detector saved to {save_path}")

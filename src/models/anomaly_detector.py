"""Isolation Forest anomaly detector with ONNX-first persistence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import numpy as np

from src.models.base import BaseClassifier, ClassifierRegistry, Prediction
from src.models.onnx_converter import convert_sklearn_to_onnx
from src.utils.logging import get_logger

logger = get_logger(__name__)

ONNX_AVAILABLE = find_spec("onnxruntime") is not None


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
        return np.array(
            [
                self.message_length,
                self.word_count,
                self.digit_ratio,
                self.special_char_ratio,
                self.uppercase_ratio,
                self.has_error_keyword,
                self.has_ip_address,
                self.hour_of_day,
            ]
        )


@ClassifierRegistry.register("anomaly_detector")
class AnomalyDetector(BaseClassifier):
    """Anomaly detection for log classification."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("anomaly_detector", config)
        self.model: Any | None = None
        self.scaler: Any | None = None

        self.model_session: Any | None = None
        self.scaler_session: Any | None = None
        self.model_input_name: str | None = None
        self.scaler_input_name: str | None = None

        self.contamination = config.get("contamination", 0.1) if config else 0.1
        self.n_estimators = config.get("n_estimators", 200) if config else 200
        self.anomaly_threshold = config.get("threshold", -0.5) if config else -0.5

    async def load(self):
        """Load trained ONNX model artifacts from disk."""
        model_path = Path(self.config.get("model_path", "models/anomaly_detector"))
        model_file = model_path / "model.onnx"
        scaler_file = model_path / "scaler.onnx"

        try:
            if model_file.exists() and scaler_file.exists():
                if not ONNX_AVAILABLE:
                    raise ImportError("onnxruntime is required for ONNX inference")

                ort = import_module("onnxruntime")
                scaler_session = ort.InferenceSession(str(scaler_file))
                model_session = ort.InferenceSession(str(model_file))

                self.scaler_session = scaler_session
                self.model_session = model_session
                self.scaler_input_name = scaler_session.get_inputs()[0].name
                self.model_input_name = model_session.get_inputs()[0].name
                self.is_loaded = True
                logger.info(f"Loaded anomaly detector ONNX artifacts from {model_path}")
                return

            logger.warning(f"ONNX artifacts not found at {model_path}, initializing empty model")
            self._initialize_empty()
            self.is_loaded = True

        except Exception as e:
            logger.error(f"Failed to load anomaly detector: {e}")
            raise

    def _initialize_empty(self):
        """Initialize empty sklearn model for training."""
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        contamination: Any = self.contamination
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=self.n_estimators,
            max_samples="auto",
            random_state=42,
            n_jobs=-1,
        )
        self.scaler = StandardScaler()
        self.model_session = None
        self.scaler_session = None
        self.model_input_name = None
        self.scaler_input_name = None

    def extract_features(self, text: str) -> AnomalyFeatures:
        """Extract numerical features from log text."""
        message_length = len(text)
        word_count = len(text.split())

        digit_count = sum(c.isdigit() for c in text)
        special_count = sum(not c.isalnum() and not c.isspace() for c in text)
        upper_count = sum(c.isupper() for c in text)

        digit_ratio = digit_count / max(message_length, 1)
        special_char_ratio = special_count / max(message_length, 1)
        uppercase_ratio = upper_count / max(message_length, 1)

        has_error = 1 if re.search(r"\b(error|fail|exception|critical)\b", text, re.I) else 0
        has_ip = 1 if re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text) else 0
        hour = datetime.now().hour

        return AnomalyFeatures(
            message_length=message_length,
            word_count=word_count,
            digit_ratio=digit_ratio,
            special_char_ratio=special_char_ratio,
            uppercase_ratio=uppercase_ratio,
            has_error_keyword=has_error,
            has_ip_address=has_ip,
            hour_of_day=hour,
        )

    async def predict(self, text: str) -> Prediction:
        """Check if a log is anomalous."""
        predictions = await self.predict_batch([text])
        return predictions[0]

    async def predict_batch(self, texts: list[str]) -> list[Prediction]:
        """Check if logs are anomalous."""
        if not self.is_loaded:
            await self.load()

        features = [self.extract_features(text).to_array() for text in texts]
        X = np.array(features, dtype=np.float32)

        if self.scaler_session and self.model_session:
            return self._predict_with_onnx(X)

        if self.scaler is None or self.model is None or not hasattr(self.scaler, "mean_"):
            return [
                Prediction(
                    category="routine",
                    confidence=0.5,
                    model=self.name,
                    probabilities={
                        "critical": 0.0,
                        "suspicious": 0.5,
                        "routine": 0.5,
                        "noise": 0.0,
                    },
                    explanation={"note": "Model not trained", "is_anomaly": False},
                )
                for _ in texts
            ]

        X_scaled = self.scaler.transform(X)
        scores = self.model.score_samples(X_scaled)
        predictions_raw = self.model.predict(X_scaled)
        return self._to_predictions(
            scores=scores, predictions_raw=predictions_raw, batch_size=len(texts)
        )

    def _predict_with_onnx(self, X: np.ndarray) -> list[Prediction]:
        if not self.scaler_session or not self.model_session:
            raise RuntimeError("ONNX sessions are not initialized")
        if not self.scaler_input_name or not self.model_input_name:
            raise RuntimeError("ONNX input names are missing")

        scaler_output = self.scaler_session.run(None, {self.scaler_input_name: X})
        if not scaler_output:
            raise RuntimeError("Scaler ONNX model returned no outputs")

        X_scaled = np.asarray(scaler_output[0], dtype=np.float32)
        model_output = self.model_session.run(None, {self.model_input_name: X_scaled})
        if not model_output:
            raise RuntimeError("Anomaly ONNX model returned no outputs")

        predictions_raw = np.asarray(model_output[0]).reshape(-1)
        if len(model_output) > 1:
            scores = np.asarray(model_output[1]).reshape(-1)
        else:
            scores = np.zeros(len(predictions_raw), dtype=np.float32)

        return self._to_predictions(
            scores=scores,
            predictions_raw=predictions_raw,
            batch_size=len(predictions_raw),
        )

    def _to_predictions(
        self,
        scores: np.ndarray,
        predictions_raw: np.ndarray,
        batch_size: int,
    ) -> list[Prediction]:
        results: list[Prediction] = []

        for score, pred in zip(scores, predictions_raw, strict=True):
            is_anomaly = self._is_anomaly_prediction(pred)

            if is_anomaly:
                category = "suspicious"
                confidence = min(0.9, 0.5 + abs(float(score)))
                probabilities = {
                    "critical": 0.0,
                    "suspicious": confidence,
                    "routine": 1 - confidence,
                    "noise": 0.0,
                }
            else:
                category = "routine"
                confidence = 0.5
                probabilities = {
                    "critical": 0.0,
                    "suspicious": 1 - confidence,
                    "routine": confidence,
                    "noise": 0.0,
                }

            results.append(
                Prediction(
                    category=category,
                    confidence=confidence,
                    model=self.name,
                    probabilities=probabilities,
                    explanation={
                        "is_anomaly": is_anomaly,
                        "anomaly_score": float(score),
                        "batch_size": batch_size,
                    },
                )
            )

        return results

    @staticmethod
    def _is_anomaly_prediction(prediction_value: Any) -> bool:
        if isinstance(prediction_value, bytes):
            prediction_value = prediction_value.decode("utf-8", errors="ignore")
        if isinstance(prediction_value, str):
            normalized = prediction_value.strip().lower()
            return normalized in {"-1", "anomaly", "anomalous", "true"}

        try:
            return int(prediction_value) == -1
        except (TypeError, ValueError):
            return False

    def train(self, texts: list[str]):
        """Train anomaly detector on normal logs."""
        if self.model is None or self.scaler is None:
            self._initialize_empty()

        assert self.model is not None
        assert self.scaler is not None
        logger.info(f"Training anomaly detector on {len(texts)} samples")

        features = [self.extract_features(text).to_array() for text in texts]
        X = np.array(features)

        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)

        self.scaler_session = None
        self.model_session = None
        logger.info("Anomaly detector training complete")

    def save(self, path: str):
        """Save anomaly detector artifacts in ONNX format."""
        if self.model is None or self.scaler is None:
            raise ValueError("Anomaly detector is not initialized for saving")
        if not hasattr(self.scaler, "mean_"):
            raise ValueError("Scaler is not fitted")
        if not hasattr(self.model, "estimators_"):
            raise ValueError("IsolationForest model is not fitted")

        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        convert_sklearn_to_onnx(
            estimator=self.scaler,
            output_path=str(save_path / "scaler.onnx"),
            feature_count=8,
        )
        convert_sklearn_to_onnx(
            estimator=self.model,
            output_path=str(save_path / "model.onnx"),
            feature_count=8,
        )

        with open(save_path / "config.json", "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

        logger.info(f"Anomaly detector ONNX artifacts saved to {save_path}")

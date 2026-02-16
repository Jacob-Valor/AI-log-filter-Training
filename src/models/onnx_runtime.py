"""ONNX Runtime wrappers for production inference."""

from __future__ import annotations

import time
from dataclasses import dataclass
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import numpy as np

from src.models.anomaly_detector import AnomalyFeatures
from src.models.base import BaseClassifier, ClassifierRegistry, Prediction
from src.utils.logging import get_logger

logger = get_logger(__name__)

ONNX_AVAILABLE = find_spec("onnxruntime") is not None


@dataclass
class ONNXModelInfo:
    """Information about a loaded ONNX model."""

    input_name: str
    input_shape: tuple[Any, ...]
    output_names: list[str]
    model_path: str
    load_time_ms: float


@ClassifierRegistry.register("onnx_anomaly_detector")
class ONNXAnomalyDetector(BaseClassifier):
    """ONNX Runtime-based anomaly detector."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("onnx_anomaly_detector", config)

        if not ONNX_AVAILABLE:
            raise ImportError("onnxruntime is not installed")

        self.model_path = (
            config.get("model_path", "models/anomaly_detector/model.onnx")
            if config
            else "models/anomaly_detector/model.onnx"
        )
        self.scaler_path = (
            config.get("scaler_path", "models/anomaly_detector/scaler.onnx")
            if config
            else "models/anomaly_detector/scaler.onnx"
        )

        self.anomaly_threshold = config.get("threshold", -0.5) if config else -0.5

        self.model_session: Any | None = None
        self.scaler_session: Any | None = None
        self.model_info: ONNXModelInfo | None = None
        self.model_input_name: str | None = None
        self.scaler_input_name: str | None = None

        self.inference_count = 0
        self.total_inference_time_ms = 0.0

    async def load(self):
        """Load ONNX model artifacts from disk."""
        start_time = time.perf_counter()
        model_path = Path(self.model_path)
        scaler_path = Path(self.scaler_path)

        try:
            ort = import_module("onnxruntime")

            if not model_path.exists():
                raise FileNotFoundError(f"ONNX model not found at {model_path}")
            if not scaler_path.exists():
                raise FileNotFoundError(f"Scaler ONNX model not found at {scaler_path}")

            model_session: Any = ort.InferenceSession(str(model_path))
            scaler_session: Any = ort.InferenceSession(str(scaler_path))

            input_meta = model_session.get_inputs()[0]
            output_metas = model_session.get_outputs()
            self.model_input_name = input_meta.name
            self.scaler_input_name = scaler_session.get_inputs()[0].name
            self.model_session = model_session
            self.scaler_session = scaler_session

            self.model_info = ONNXModelInfo(
                input_name=input_meta.name,
                input_shape=tuple(input_meta.shape),
                output_names=[output.name for output in output_metas],
                model_path=str(model_path),
                load_time_ms=(time.perf_counter() - start_time) * 1000,
            )

            self.is_loaded = True
            logger.info(
                "Loaded ONNX anomaly detector",
                extra={
                    "model_path": str(model_path),
                    "scaler_path": str(scaler_path),
                    "load_time_ms": round(self.model_info.load_time_ms, 2),
                },
            )

        except Exception as e:
            logger.error(f"Failed to load ONNX anomaly detector: {e}")
            raise

    def extract_features(self, text: str) -> AnomalyFeatures:
        """Extract numerical features from log text."""
        import re
        from datetime import datetime

        message_length = len(text)
        word_count = len(text.split())

        digit_count = sum(char.isdigit() for char in text)
        special_count = sum(not char.isalnum() and not char.isspace() for char in text)
        upper_count = sum(char.isupper() for char in text)

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
        """Predict anomaly status for a single log."""
        predictions = await self.predict_batch([text])
        return predictions[0]

    async def predict_batch(self, texts: list[str]) -> list[Prediction]:
        """Predict anomaly status for multiple logs."""
        if not self.is_loaded:
            await self.load()

        if (
            self.model_session is None
            or self.scaler_session is None
            or self.model_input_name is None
            or self.scaler_input_name is None
        ):
            raise RuntimeError("ONNX anomaly detector is not loaded")

        start_time = time.perf_counter()

        features = [self.extract_features(text).to_array() for text in texts]
        X = np.asarray(features, dtype=np.float32)

        scaler_output = self.scaler_session.run(None, {self.scaler_input_name: X})
        if not scaler_output:
            raise RuntimeError("Scaler ONNX model returned no outputs")
        X_scaled = np.asarray(scaler_output[0], dtype=np.float32)

        outputs = self.model_session.run(None, {self.model_input_name: X_scaled})
        if not outputs:
            raise RuntimeError("Anomaly ONNX model returned no outputs")

        predictions_raw = np.asarray(outputs[0]).reshape(-1)
        if len(outputs) > 1:
            scores = np.asarray(outputs[1]).reshape(-1)
        else:
            scores = np.zeros(len(predictions_raw), dtype=np.float32)

        inference_time = (time.perf_counter() - start_time) * 1000
        self.inference_count += len(texts)
        self.total_inference_time_ms += inference_time

        results: list[Prediction] = []
        for score, pred in zip(scores, predictions_raw, strict=True):
            is_anomaly = self._is_anomaly(pred)
            if is_anomaly:
                confidence = min(0.9, 0.5 + abs(float(score)))
                category = "suspicious"
                probabilities = {
                    "critical": 0.0,
                    "suspicious": confidence,
                    "routine": 1 - confidence,
                    "noise": 0.0,
                }
            else:
                confidence = 0.5
                category = "routine"
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
                        "inference_time_ms": round(inference_time / max(len(texts), 1), 3),
                    },
                )
            )

        return results

    @staticmethod
    def _is_anomaly(value: Any) -> bool:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="ignore")
        if isinstance(value, str):
            return value.strip().lower() in {"-1", "anomaly", "anomalous", "true"}
        try:
            return int(value) == -1
        except (TypeError, ValueError):
            return False

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        if self.inference_count == 0:
            return {"inference_count": 0, "avg_inference_time_ms": 0.0}

        return {
            "inference_count": self.inference_count,
            "avg_inference_time_ms": round(self.total_inference_time_ms / self.inference_count, 3),
            "model_load_time_ms": round(self.model_info.load_time_ms, 2)
            if self.model_info
            else None,
            "model_path": self.model_path,
            "scaler_path": self.scaler_path,
        }


class ONNXEnsembleClassifier(BaseClassifier):
    """Placeholder ensemble for ONNX-only inference."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("onnx_ensemble", config)
        cfg = config or {}
        self.model_paths = cfg.get("model_paths", {})
        self.weights = cfg.get(
            "weights",
            {
                "rule_based": 0.30,
                "tfidf_xgboost": 0.45,
                "anomaly": 0.25,
            },
        )
        self.models: dict[str, BaseClassifier] = {}

    async def load(self):
        if "anomaly" in self.model_paths:
            anomaly_cfg = {"model_path": self.model_paths["anomaly"]}
            anomaly_scaler = self.model_paths.get("anomaly_scaler")
            if anomaly_scaler:
                anomaly_cfg["scaler_path"] = anomaly_scaler
            self.models["anomaly"] = ONNXAnomalyDetector(anomaly_cfg)
            await self.models["anomaly"].load()

        self.is_loaded = True
        logger.info(f"Loaded {len(self.models)} ONNX models")

    async def predict(self, text: str) -> Prediction:
        predictions = await self.predict_batch([text])
        return predictions[0]

    async def predict_batch(self, texts: list[str]) -> list[Prediction]:
        raise NotImplementedError("Full ONNX ensemble implementation required")


def compare_inference_speed(
    baseline_detector: BaseClassifier,
    onnx_detector: ONNXAnomalyDetector,
    test_texts: list[str],
    iterations: int = 100,
) -> dict[str, Any]:
    """Compare baseline detector speed against ONNX detector speed."""
    import asyncio

    async def run_benchmark() -> dict[str, Any]:
        await baseline_detector.predict_batch(test_texts)
        await onnx_detector.predict_batch(test_texts)

        start = time.perf_counter()
        for _ in range(iterations):
            await baseline_detector.predict_batch(test_texts)
        baseline_time = time.perf_counter() - start

        start = time.perf_counter()
        for _ in range(iterations):
            await onnx_detector.predict_batch(test_texts)
        onnx_time = time.perf_counter() - start

        return {
            "baseline_time_ms": baseline_time * 1000 / iterations,
            "onnx_time_ms": onnx_time * 1000 / iterations,
            "speedup": baseline_time / onnx_time if onnx_time > 0 else float("inf"),
            "texts_per_iteration": len(test_texts),
            "iterations": iterations,
        }

    return asyncio.run(run_benchmark())

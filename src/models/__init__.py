"""
Models Module - ML classifiers

This module provides machine learning classifiers for log categorization.
Supports ONNX-based inference for persisted ML artifacts.

ONNX-Only Mode:
    For maximum performance, use ONNX-only mode with ONNXSafeEnsembleClassifier.
    This provides 8x faster inference and 78% smaller model files.

    Example:
        from src.models.onnx_ensemble import create_onnx_classifier
        classifier = await create_onnx_classifier("models/v3")
"""

from src.models.anomaly_detector import AnomalyDetector
from src.models.base import BaseClassifier
from src.models.base_ensemble import BaseEnsembleClassifier
from src.models.classification_result import ClassificationResult, create_fail_open_prediction
from src.models.ensemble import EnsembleClassifier
from src.models.rule_based import RuleBasedClassifier
from src.models.tfidf_classifier import TFIDFClassifier

# Base exports (always available)
__all__ = [
    "BaseClassifier",
    "BaseEnsembleClassifier",
    "ClassificationResult",
    "RuleBasedClassifier",
    "TFIDFClassifier",
    "AnomalyDetector",
    "EnsembleClassifier",
    "create_fail_open_prediction",
]

# ONNX modules are optional – available only when onnxruntime is installed.
try:
    from src.models.onnx_ensemble import (  # noqa: F401
        ONNXSafeEnsembleClassifier,
        create_onnx_classifier,
    )
    from src.models.onnx_runtime import ONNXAnomalyDetector  # noqa: F401

    __all__ += [
        "ONNXAnomalyDetector",
        "ONNXSafeEnsembleClassifier",
        "create_onnx_classifier",
    ]
except ImportError:
    pass

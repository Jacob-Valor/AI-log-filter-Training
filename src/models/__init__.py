"""
Models Module - ML classifiers

This module provides machine learning classifiers for log categorization.
Supports both joblib-based and ONNX-based inference.

ONNX-Only Mode:
    For maximum performance, use ONNX-only mode with ONNXSafeEnsembleClassifier.
    This provides 8x faster inference and 78% smaller model files.

    Example:
        from src.models.onnx_ensemble import create_onnx_classifier
        classifier = await create_onnx_classifier("models/v3/onnx")
"""

from src.models.anomaly_detector import AnomalyDetector
from src.models.base import BaseClassifier
from src.models.ensemble import EnsembleClassifier
from src.models.rule_based import RuleBasedClassifier
from src.models.tfidf_classifier import TFIDFClassifier

# Base exports (always available)
__all__ = [
    "BaseClassifier",
    "RuleBasedClassifier",
    "TFIDFClassifier",
    "AnomalyDetector",
    "EnsembleClassifier",
]

# Try to import ONNX modules (optional - requires onnxruntime)
_ = None  # noqa: F841 - Placeholder to satisfy LSP
try:  # noqa: SIM105 - Try/ExceptPass okay here
    from src.models.onnx_ensemble import (  # noqa: F401
        ONNXSafeEnsembleClassifier,
        create_onnx_classifier,
    )
    from src.models.onnx_runtime import ONNXAnomalyDetector  # noqa: F401

    # Extend exports with ONNX classes
    __all__.extend(
        [
            "ONNXAnomalyDetector",
            "ONNXSafeEnsembleClassifier",
            "create_onnx_classifier",
        ]
    )
except ImportError:
    # ONNX runtime not installed - joblib only mode
    pass

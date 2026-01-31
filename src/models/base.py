"""
Base Classifier - Abstract base class for all classifiers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Prediction:
    """Represents a classification prediction."""

    category: str
    confidence: float
    model: str
    probabilities: dict[str, float] | None = None
    explanation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "model": self.model,
            "probabilities": self.probabilities,
            "explanation": self.explanation,
        }


class BaseClassifier(ABC):
    """
    Abstract base class for log classifiers.

    All classifier implementations should inherit from this class
    and implement the required methods.
    """

    # Standard log categories
    CATEGORIES = ["critical", "suspicious", "routine", "noise"]

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        self.name = name
        self.config = config or {}
        self.is_loaded = False

    @abstractmethod
    async def load(self):
        """Load model weights and resources."""
        pass

    @abstractmethod
    async def predict(self, text: str) -> Prediction:
        """
        Classify a single log message.

        Args:
            text: Log message text

        Returns:
            Prediction object with category and confidence
        """
        pass

    @abstractmethod
    async def predict_batch(self, texts: list[str]) -> list[Prediction]:
        """
        Classify a batch of log messages.

        Args:
            texts: List of log message texts

        Returns:
            List of Prediction objects
        """
        pass

    def save(self, path: str):
        """Save model to disk."""
        raise NotImplementedError(f"{self.name} does not support saving")

    @classmethod
    def load_from_path(cls, path: str) -> "BaseClassifier":
        """Load model from disk."""
        raise NotImplementedError(f"{cls.__name__} does not support loading from path")

    def get_feature_importance(self) -> dict[str, float] | None:
        """Get feature importance scores if available."""
        return None

    def explain(self, text: str) -> dict[str, Any] | None:
        """Generate explanation for a prediction."""
        return None


class ClassifierRegistry:
    """
    Registry for classifier implementations.

    Allows dynamic registration and retrieval of classifier classes.
    """

    _classifiers: dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a classifier class."""

        def decorator(classifier_class: type):
            cls._classifiers[name] = classifier_class
            return classifier_class

        return decorator

    @classmethod
    def get(cls, name: str) -> type:
        """Get a classifier class by name."""
        if name not in cls._classifiers:
            raise ValueError(f"Unknown classifier: {name}")
        return cls._classifiers[name]

    @classmethod
    def list_classifiers(cls) -> list[str]:
        """List all registered classifiers."""
        return list(cls._classifiers.keys())

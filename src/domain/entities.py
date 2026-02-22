"""
Core Domain Entities

Defines the fundamental data structures used across the application.
These entities have no dependencies on infrastructure or external systems.
"""

from dataclasses import dataclass, field
from datetime import datetime
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


@dataclass
class ClassificationResult:
    """Result of classification including metadata."""

    prediction: Prediction
    processing_time_ms: float
    compliance_bypassed: bool = False
    fail_open_used: bool = False
    models_used: list[str] = field(default_factory=list)


@dataclass
class RawLog:
    """Represents a raw log message from Kafka."""

    raw_message: str
    topic: str
    partition: int
    offset: int
    timestamp: datetime
    key: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_message": self.raw_message,
            "topic": self.topic,
            "partition": self.partition,
            "offset": self.offset,
            "timestamp": self.timestamp.isoformat(),
            "key": self.key,
            "headers": self.headers,
        }


@dataclass
class ClassifiedLog:
    """Represents a classified log with prediction."""

    raw_log: RawLog
    parsed_data: dict[str, Any]
    category: str
    confidence: float
    model_used: str
    explanation: dict[str, Any] | None = None
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        message = self.parsed_data.get("message") or self.raw_log.raw_message
        source = self.parsed_data.get("source") or self.raw_log.topic

        return {
            "message": message,
            "source": source,
            "timestamp": self.raw_log.timestamp.isoformat(),
            "category": self.category,
            "confidence": self.confidence,
            "model": self.model_used,
            "explanation": self.explanation,
            "processing_time_ms": self.processing_time_ms,
            "raw_log": self.raw_log.to_dict(),
            "parsed_data": self.parsed_data,
        }

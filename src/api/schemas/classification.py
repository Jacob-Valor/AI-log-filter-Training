from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LogMessage(BaseModel):
    """Single log message for classification."""

    message: str = Field(
        ...,
        description="Log message text to classify",
        examples=[
            "CRITICAL: Multiple failed authentication attempts detected from IP 192.168.1.100",
            "INFO: User admin logged in successfully",
            "DEBUG: Health check endpoint called",
        ],
    )
    source: str | None = Field(
        None,
        description="Log source identifier (e.g., 'firewall', 'ids', 'endpoint')",
        examples=["firewall", "ids", "endpoint", "cloud-app"],
    )
    timestamp: datetime | None = Field(
        None, description="Log timestamp in ISO 8601 format", examples=["2024-01-15T10:30:00Z"]
    )
    metadata: dict[str, Any] | None = Field(
        None,
        description="Additional metadata (source IP, user, etc.)",
        examples=[{"source_ip": "192.168.1.100", "user": "admin"}],
    )


class ClassificationResult(BaseModel):
    """Classification result for a log message."""

    category: str = Field(
        ...,
        description="Predicted category",
        examples=["critical", "suspicious", "routine", "noise"],
    )
    confidence: float = Field(
        ..., description="Prediction confidence (0-1)", examples=[0.95], ge=0, le=1
    )
    model: str = Field(
        ...,
        description="Model used for classification",
        examples=["ensemble", "rule_based", "tfidf_xgboost", "anomaly_detector"],
    )
    probabilities: dict[str, float] | None = Field(
        None,
        description="Per-class probabilities",
        examples=[{"critical": 0.95, "suspicious": 0.03, "routine": 0.01, "noise": 0.01}],
    )
    explanation: dict[str, Any] | None = Field(
        None,
        description="Classification explanation with matched rules/features",
        examples=[{"matched_rules": ["auth_failure_pattern"], "threat_indicators": 2}],
    )


class BatchClassifyRequest(BaseModel):
    """Request for batch classification."""

    logs: list[LogMessage] = Field(
        ...,
        description="List of log messages (max 1000)",
        examples=[
            [
                {"message": "CRITICAL: Malware detected", "source": "endpoint"},
                {"message": "INFO: Backup completed", "source": "system"},
            ]
        ],
    )


class BatchClassifyResponse(BaseModel):
    """Response for batch classification."""

    results: list[ClassificationResult] = Field(..., description="Classification results")
    processing_time_ms: float = Field(..., description="Total processing time in milliseconds")
    total_logs: int = Field(..., description="Number of logs processed")

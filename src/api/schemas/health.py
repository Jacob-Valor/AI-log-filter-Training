from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Overall health status", examples=["healthy", "unhealthy"])
    timestamp: datetime = Field(..., description="Health check timestamp")
    checks: dict[str, Any] = Field(
        ...,
        description="Individual health check results",
        examples=[{"classifier": {"status": "healthy"}, "kafka": {"status": "healthy"}}],
    )


class StatsResponse(BaseModel):
    """Statistics response."""

    total_processed: int = Field(..., description="Total logs processed")
    classification_distribution: dict[str, int] = Field(
        ...,
        description="Distribution across categories",
        examples=[{"critical": 100, "suspicious": 500, "routine": 5000, "noise": 10000}],
    )
    avg_latency_ms: float = Field(..., description="Average classification latency")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")

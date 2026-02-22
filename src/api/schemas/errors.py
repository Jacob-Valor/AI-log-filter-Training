from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error message")
    error_code: str | None = Field(None, description="Error code for programmatic handling")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

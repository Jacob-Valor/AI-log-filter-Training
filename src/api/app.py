"""
FastAPI Application

REST API for log classification and management.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.rate_limiter import (
    RateLimitConfig,
    get_rate_limit_status,
    limiter,
    setup_rate_limiting,
)
from src.models.ensemble import EnsembleClassifier
from src.monitoring.metrics import health_checker
from src.utils.config import get_settings
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

# Global classifier instance
classifier: EnsembleClassifier | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global classifier

    # Startup
    settings = get_settings()
    setup_logging(level=settings.log_level)

    logger.info("Starting AI Log Filter API...")

    # Load classifier
    classifier = EnsembleClassifier(model_path=settings.model_path, config={})
    await classifier.load()

    logger.info("API startup complete")

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down API...")


# Initialize FastAPI app
app = FastAPI(
    title="AI Log Filter API",
    description="AI-Driven Log Classification for SIEM Efficiency",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Setup rate limiting
setup_rate_limiting(app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global classifier instance
classifier: EnsembleClassifier | None = None


# =============================================================================
# Request/Response Models
# =============================================================================


class LogMessage(BaseModel):
    """Single log message for classification."""

    message: str = Field(..., description="Log message text")
    source: str | None = Field(None, description="Log source identifier")
    timestamp: datetime | None = Field(None, description="Log timestamp")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


class ClassificationResult(BaseModel):
    """Classification result for a log message."""

    category: str = Field(..., description="Predicted category")
    confidence: float = Field(..., description="Prediction confidence (0-1)")
    model: str = Field(..., description="Model used for classification")
    probabilities: dict[str, float] | None = Field(
        None, description="Per-class probabilities"
    )
    explanation: dict[str, Any] | None = Field(
        None, description="Classification explanation"
    )


class BatchClassifyRequest(BaseModel):
    """Request for batch classification."""

    logs: list[LogMessage] = Field(..., description="List of log messages")


class BatchClassifyResponse(BaseModel):
    """Response for batch classification."""

    results: list[ClassificationResult]
    processing_time_ms: float
    total_logs: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
    checks: dict[str, Any]


class StatsResponse(BaseModel):
    """Statistics response."""

    total_processed: int
    classification_distribution: dict[str, int]
    avg_latency_ms: float
    uptime_seconds: float


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "AI Log Filter API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Check application health."""
    health = await health_checker.check_health()

    return HealthResponse(
        status=health["status"],
        timestamp=datetime.now(UTC),
        checks=health.get("checks", {}),
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Check if application is ready to serve requests."""
    global classifier

    if classifier is None or not classifier.is_loaded:
        raise HTTPException(status_code=503, detail="Classifier not loaded")

    return {"ready": True}


@app.post("/classify", response_model=ClassificationResult, tags=["Classification"])
@limiter.limit(RateLimitConfig.CLASSIFY_SINGLE_LIMIT)
async def classify_log(request: Request, log: LogMessage):
    """
    Classify a single log message.

    Returns the predicted category, confidence score, and optional explanation.
    """
    global classifier

    if classifier is None:
        raise HTTPException(status_code=503, detail="Classifier not available")

    try:
        import time

        start = time.time()

        prediction = await classifier.predict(log.message)

        processing_time = (time.time() - start) * 1000
        logger.debug(f"Classified log in {processing_time:.2f}ms")

        return ClassificationResult(
            category=prediction.category,
            confidence=prediction.confidence,
            model=prediction.model,
            probabilities=prediction.probabilities,
            explanation=prediction.explanation,
        )

    except Exception as e:
        logger.error(f"Classification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/classify/batch", response_model=BatchClassifyResponse, tags=["Classification"]
)
@limiter.limit(RateLimitConfig.CLASSIFY_BATCH_LIMIT)
async def classify_batch(request: Request, batch_request: BatchClassifyRequest):
    """
    Classify a batch of log messages.

    More efficient than individual requests for processing multiple logs.
    """
    global classifier

    if classifier is None:
        raise HTTPException(status_code=503, detail="Classifier not available")

    if len(batch_request.logs) > 1000:
        raise HTTPException(status_code=400, detail="Batch size exceeds limit (1000)")

    try:
        import time

        start = time.time()

        messages = [log.message for log in batch_request.logs]
        predictions = await classifier.predict_batch(messages)

        processing_time = (time.time() - start) * 1000

        results = [
            ClassificationResult(
                category=pred.category,
                confidence=pred.confidence,
                model=pred.model,
                probabilities=pred.probabilities,
                explanation=pred.explanation,
            )
            for pred in predictions
        ]

        return BatchClassifyResponse(
            results=results,
            processing_time_ms=processing_time,
            total_logs=len(batch_request.logs),
        )

    except Exception as e:
        logger.error(f"Batch classification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", response_model=StatsResponse, tags=["Monitoring"])
async def get_stats():
    """Get classification statistics."""
    # In production, these would come from actual metrics
    return StatsResponse(
        total_processed=0,
        classification_distribution={
            "critical": 0,
            "suspicious": 0,
            "routine": 0,
            "noise": 0,
        },
        avg_latency_ms=0.0,
        uptime_seconds=0.0,
    )


@app.get("/models", tags=["Models"])
async def list_models():
    """List available classification models."""
    return {
        "models": [
            {
                "name": "rule_based",
                "type": "rule_based",
                "description": "Pattern matching classifier",
            },
            {
                "name": "tfidf_xgboost",
                "type": "ml",
                "description": "TF-IDF + XGBoost classifier",
            },
            {
                "name": "anomaly_detector",
                "type": "anomaly",
                "description": "Isolation Forest anomaly detector",
            },
            {
                "name": "ensemble",
                "type": "ensemble",
                "description": "Combined ensemble classifier",
            },
        ]
    }


@app.post("/feedback", tags=["Feedback"])
@limiter.limit(RateLimitConfig.FEEDBACK_LIMIT)
async def submit_feedback(
    request: Request,
    log_id: str,
    correct_category: str,
    background_tasks: BackgroundTasks,
):
    """
    Submit feedback on a classification.

    Used for active learning and model improvement.
    """
    if correct_category not in ["critical", "suspicious", "routine", "noise"]:
        raise HTTPException(status_code=400, detail="Invalid category")

    # In production, this would store feedback for retraining
    background_tasks.add_task(process_feedback, log_id, correct_category)

    return {"status": "feedback_received", "log_id": log_id}


async def process_feedback(log_id: str, correct_category: str):
    """Process feedback in background."""
    logger.info(f"Processing feedback for {log_id}: {correct_category}")
    # Store for retraining


@app.get("/rate-limit-status", tags=["Monitoring"])
async def rate_limit_status(request: Request):
    """
    Get current rate limit status for your client.

    Returns configured limits and how to check remaining quota via headers.
    """
    return await get_rate_limit_status(request)

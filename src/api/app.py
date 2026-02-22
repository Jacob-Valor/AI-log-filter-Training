"""
FastAPI Application

REST API for log classification and management.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.rate_limiter import (
    setup_rate_limiting,
)
from src.api.routers import classification, management, stats
from src.api.schemas.health import HealthResponse
from src.models.ensemble import EnsembleClassifier
from src.monitoring.metrics import health_checker
from src.utils.config import get_settings
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    settings = get_settings()
    setup_logging(level=settings.log_level)

    logger.info("Starting AI Log Filter API...")

    # Load classifier and attach to app.state (avoid module-level global)
    classifier = EnsembleClassifier(model_path=settings.model_path, config={})
    await classifier.load()
    app.state.classifier = classifier

    logger.info("API startup complete")

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down API...")
    app.state.classifier = None


# Initialize FastAPI app
app = FastAPI(
    title="AI Log Filter API",
    description="""
## AI-Driven Log Classification for SIEM Efficiency

An intelligent ML-based log classification system that reduces IBM QRadar SIEM
ingestion volume by 40-60% while maintaining >99.5% critical event recall.

### Classification Categories

| Category | Action | Description |
|----------|--------|-------------|
| **critical** | QRadar (high priority) | Immediate security threats |
| **suspicious** | QRadar (medium priority) | Unusual activity warranting investigation |
| **routine** | Cold storage | Normal operational logs |
| **noise** | Summarized + archived | Low-value logs |

### Features

- **Fail-Open Design**: If AI fails, all logs forward to QRadar (zero data loss)
- **Compliance Bypass**: PCI-DSS, HIPAA, SOX, GDPR logs skip AI entirely
- **Real-time Processing**: <100ms latency for log classification
- **Audit Trail**: Every classification decision is logged

### Rate Limits

- `/classify`: 100 requests/minute
- `/classify/batch`: 30 requests/minute
- `/feedback`: 20 requests/minute
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Info", "description": "API information and metadata"},
        {"name": "Health", "description": "Health check endpoints for monitoring"},
        {"name": "Classification", "description": "Log classification endpoints"},
        {"name": "Models", "description": "Model management and information"},
        {"name": "Monitoring", "description": "Metrics and monitoring endpoints"},
        {"name": "Feedback", "description": "Submit feedback for model improvement"},
    ],
    lifespan=lifespan,
)

# Setup rate limiting
setup_rate_limiting(app)

# CORS middleware — restrict origins in production.
# NOTE: allow_credentials=True requires explicit origins, never "*".
_settings = get_settings()
_is_dev = _settings.app_env == "development"
_cors_origins = (
    ["http://localhost:3000", "http://localhost:8000"]
    if _is_dev
    else [o.strip() for o in _settings.cors_allowed_origins.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=not _is_dev,  # Only send credentials for explicit origins
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Client-ID"],
)




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
async def readiness_check(request: Request):
    """Check if application is ready to serve requests."""
    classifier = getattr(request.app.state, "classifier", None)

    if classifier is None or not classifier.is_loaded:
        raise HTTPException(status_code=503, detail="Classifier not loaded")

    return {"ready": True}




app.include_router(classification.router)
app.include_router(management.router)
app.include_router(stats.router)

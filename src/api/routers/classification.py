import time

from fastapi import APIRouter, HTTPException, Request

from src.api.rate_limiter import RateLimitConfig, limiter
from src.api.schemas.classification import (
    BatchClassifyRequest,
    BatchClassifyResponse,
    ClassificationResult,
    LogMessage,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Classification"])


@router.post(
    "/classify",
    response_model=ClassificationResult,
    responses={
        200: {
            "description": "Successful classification",
            "content": {
                "application/json": {
                    "example": {
                        "category": "critical",
                        "confidence": 0.95,
                        "model": "ensemble",
                        "probabilities": {
                            "critical": 0.95,
                            "suspicious": 0.03,
                            "routine": 0.01,
                            "noise": 0.01,
                        },
                        "explanation": {"matched_rules": ["auth_failure_pattern"]},
                    }
                }
            },
        },
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Classifier not available"},
    },
)
@limiter.limit(RateLimitConfig.CLASSIFY_SINGLE_LIMIT)
async def classify_log(request: Request, log: LogMessage):
    """
    Classify a single log message.

    Returns the predicted category, confidence score, and optional explanation.

    Categories:
    - **critical**: Immediate security threats requiring attention
    - **suspicious**: Unusual activity warranting investigation
    - **routine**: Normal operational logs with forensic value
    - **noise**: Low-value logs that can be filtered
    """
    classifier = getattr(request.app.state, "classifier", None)

    if classifier is None:
        raise HTTPException(status_code=503, detail="Classifier not available")

    try:
        start = time.time()

        prediction = await classifier.predict(log.message)

        processing_time = (time.time() - start) * 1000
        logger.debug("Classified log in %.2fms", processing_time)

        return ClassificationResult(
            category=prediction.category,
            confidence=prediction.confidence,
            model=prediction.model,
            probabilities=prediction.probabilities,
            explanation=prediction.explanation,
        )

    except Exception as e:
        logger.error("Classification error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal classification error")


@router.post(
    "/classify/batch",
    response_model=BatchClassifyResponse,
    responses={
        200: {"description": "Successful batch classification"},
        400: {"description": "Batch size exceeds limit (1000)"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Classifier not available"},
    },
)
@limiter.limit(RateLimitConfig.CLASSIFY_BATCH_LIMIT)
async def classify_batch(request: Request, batch_request: BatchClassifyRequest):
    """
    Classify a batch of log messages.

    More efficient than individual requests for processing multiple logs.
    Maximum batch size is 1000 logs.

    The batch endpoint is optimized for high-throughput scenarios and
    processes logs in parallel when possible.
    """
    classifier = getattr(request.app.state, "classifier", None)

    if classifier is None:
        raise HTTPException(status_code=503, detail="Classifier not available")

    if len(batch_request.logs) > 1000:
        raise HTTPException(status_code=400, detail="Batch size exceeds limit (1000)")

    try:
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
        logger.error("Batch classification error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal classification error")

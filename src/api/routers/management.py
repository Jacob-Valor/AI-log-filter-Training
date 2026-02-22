
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from src.api.rate_limiter import RateLimitConfig, get_rate_limit_status, limiter
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/models", tags=["Models"])
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


@router.post("/feedback", tags=["Feedback"])
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
    logger.info("Processing feedback for %s: %s", log_id, correct_category)
    # Store for retraining


@router.get("/rate-limit-status", tags=["Monitoring"])
async def rate_limit_status(request: Request):
    """
    Get current rate limit status for your client.

    Returns configured limits and how to check remaining quota via headers.
    """
    return await get_rate_limit_status(request)

from fastapi import APIRouter

from src.api.schemas.health import StatsResponse
from src.monitoring.production_metrics import get_metrics_collector

router = APIRouter(tags=["Monitoring"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get classification statistics."""
    collector = get_metrics_collector()
    summary = collector.get_summary()

    return StatsResponse(
        total_processed=(
            summary["detection_quality"]["critical_true_positives"]
            + summary["detection_quality"]["critical_false_negatives"]
            + summary["detection_quality"]["critical_false_positives"]
        ),
        classification_distribution={
            "critical": summary["detection_quality"]["critical_true_positives"],
            "suspicious": 0,
            "routine": 0,
            "noise": 0,
        },
        avg_latency_ms=0.0,
        uptime_seconds=0.0,
    )

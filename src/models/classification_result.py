"""
Shared classification result types.

Provides ClassificationResult and fail-open prediction helpers used
by both SafeEnsembleClassifier and ONNXSafeEnsembleClassifier.
"""


from src.domain.entities import ClassificationResult  # noqa: F401
from src.models.base import Prediction


def create_fail_open_prediction(text: str, reason: str = "system_error") -> Prediction:
    """
    Create a fail-open prediction that ensures log goes to QRadar.

    When the AI system fails, we default to sending ALL logs to QRadar
    to ensure no security events are missed.
    """
    return Prediction(
        category="critical",  # Always forward on failure
        confidence=0.0,  # Zero confidence indicates fail-open
        model="fail_open",
        probabilities={"critical": 1.0, "suspicious": 0.0, "routine": 0.0, "noise": 0.0},
        explanation={
            "fail_open": True,
            "reason": reason,
            "note": "Log forwarded to QRadar due to system safety measure",
        },
    )

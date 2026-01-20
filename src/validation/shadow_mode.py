"""
Shadow Mode Validation Framework

Runs the AI classifier in parallel with existing QRadar ingestion
to validate classification accuracy before enabling production filtering.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.models.base import Prediction
from src.monitoring.production_metrics import METRICS
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationPhase(Enum):
    SHADOW = "shadow"
    PILOT = "pilot"
    GRADUAL = "gradual"
    PRODUCTION = "production"


@dataclass
class ValidationDecision:
    log_id: str
    timestamp: datetime
    log_source: str
    log_message: str
    ai_category: str
    ai_confidence: float
    ai_model: str
    explanation: Dict[str, Any]
    qradar_offense_generated: Optional[bool] = None
    qradar_offense_id: Optional[str] = None
    qradar_offense_type: Optional[str] = None
    qradar_severity: Optional[int] = None
    is_false_negative: Optional[bool] = None
    is_false_positive: Optional[bool] = None
    validation_timestamp: Optional[datetime] = None


@dataclass
class ValidationStats:
    phase: ValidationPhase = ValidationPhase.SHADOW
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_processed: int = 0
    by_category: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    missed_offenses: List[Dict[str, Any]] = field(default_factory=list)
    confidence_buckets: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )


class ShadowModeValidator:
    PHASE_REQUIREMENTS = {
        ValidationPhase.SHADOW: {
            "min_samples": 10000,
            "min_duration_hours": 24,
            "max_false_negative_rate": 0.005,
            "min_critical_recall": 0.995,
        },
        ValidationPhase.PILOT: {
            "min_samples": 50000,
            "min_duration_hours": 72,
            "max_false_negative_rate": 0.002,
            "min_critical_recall": 0.998,
        },
        ValidationPhase.GRADUAL: {
            "min_samples": 100000,
            "min_duration_hours": 168,
            "max_false_negative_rate": 0.001,
            "min_critical_recall": 0.999,
        },
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.stats = ValidationStats()
        self.decisions: Dict[str, ValidationDecision] = {}
        self._lock = asyncio.Lock()
        self.pending_validation: Dict[str, ValidationDecision] = {}
        self.correlation_window_hours = self.config.get("correlation_window_hours", 24)
        logger.info(
            f"ShadowModeValidator initialized in {self.stats.phase.value} phase"
        )

    async def record_decision(
        self, log_id: str, prediction: Prediction, log: Dict[str, Any]
    ) -> ValidationDecision:
        async with self._lock:
            decision = ValidationDecision(
                log_id=log_id,
                timestamp=datetime.now(timezone.utc),
                log_source=log.get("source", "unknown"),
                log_message=log.get("message", "")[:500],
                ai_category=prediction.category,
                ai_confidence=prediction.confidence,
                ai_model=prediction.model,
                explanation=prediction.explanation or {},
            )
            self.decisions[log_id] = decision
            self.pending_validation[log_id] = decision
            self.stats.total_processed += 1
            self.stats.by_category[prediction.category] += 1
            return decision

    async def record_qradar_result(
        self,
        log_id: str,
        offense_generated: bool,
        offense_data: Optional[Dict[str, Any]] = None,
    ):
        async with self._lock:
            if log_id not in self.decisions:
                return
            decision = self.decisions[log_id]
            decision.qradar_offense_generated = offense_generated
            decision.validation_timestamp = datetime.now(timezone.utc)
            if offense_data:
                decision.qradar_offense_id = offense_data.get("offense_id")
                decision.qradar_offense_type = offense_data.get("offense_type")
                decision.qradar_severity = offense_data.get("severity")
            self.pending_validation.pop(log_id, None)
            ai_would_forward = decision.ai_category in ["critical", "suspicious"]
            if offense_generated and ai_would_forward:
                self.stats.true_positives += 1
            elif not offense_generated and not ai_would_forward:
                self.stats.true_negatives += 1
            elif offense_generated and not ai_would_forward:
                self.stats.false_negatives += 1
                decision.is_false_negative = True
                self.stats.missed_offenses.append(
                    {
                        "log_id": log_id,
                        "ai_category": decision.ai_category,
                        "offense_type": decision.qradar_offense_type,
                    }
                )
                METRICS.record_false_negative(
                    decision.ai_category,
                    decision.qradar_offense_type or "unknown",
                    str(decision.qradar_severity or 0),
                )
            elif not offense_generated and ai_would_forward:
                self.stats.false_positives += 1
                decision.is_false_positive = True

    def get_accuracy_metrics(self) -> Dict[str, Any]:
        total = (
            self.stats.true_positives
            + self.stats.true_negatives
            + self.stats.false_positives
            + self.stats.false_negatives
        )
        if total == 0:
            return {"total_validated": 0}
        total_positives = self.stats.true_positives + self.stats.false_negatives
        recall = (
            self.stats.true_positives / total_positives if total_positives > 0 else 1.0
        )
        fnr = self.stats.false_negatives / total_positives if total_positives > 0 else 0
        return {
            "total_processed": self.stats.total_processed,
            "total_validated": total,
            "recall": round(recall, 4),
            "false_negative_rate": round(fnr, 5),
            "false_negatives": self.stats.false_negatives,
            "confusion_matrix": {
                "tp": self.stats.true_positives,
                "tn": self.stats.true_negatives,
                "fp": self.stats.false_positives,
                "fn": self.stats.false_negatives,
            },
        }

    def is_ready_for_next_phase(self) -> Tuple[bool, str]:
        if self.stats.phase == ValidationPhase.PRODUCTION:
            return False, "Already in production"
        reqs = self.PHASE_REQUIREMENTS.get(self.stats.phase, {})
        metrics = self.get_accuracy_metrics()
        if metrics.get("total_validated", 0) < reqs.get("min_samples", 0):
            return False, "Need more samples"
        if metrics.get("false_negative_rate", 1) > reqs.get(
            "max_false_negative_rate", 0.01
        ):
            return False, "False negative rate too high"
        if metrics.get("recall", 0) < reqs.get("min_critical_recall", 0.99):
            return False, "Recall too low"
        return True, "Requirements met"

    def get_validation_report(self) -> Dict[str, Any]:
        ready, reason = self.is_ready_for_next_phase()
        return {
            "phase": self.stats.phase.value,
            "ready_for_next_phase": ready,
            "reason": reason,
            "metrics": self.get_accuracy_metrics(),
        }


def create_shadow_validator(
    config: Optional[Dict[str, Any]] = None,
) -> ShadowModeValidator:
    return ShadowModeValidator(config)

"""
Tests for Shadow Mode Validation Framework

Tests the shadow mode validation for comparing AI decisions
against QRadar offense generation.
"""

import pytest
import pytest_asyncio

from src.models.base import Prediction
from src.validation.shadow_mode import (
    ShadowModeValidator,
    ValidationPhase,
    create_shadow_validator,
)


class TestShadowModeInitialization:
    """Test shadow mode validator initialization."""

    def test_default_initialization(self):
        """Should initialize with default settings."""
        validator = ShadowModeValidator()

        assert validator.stats.phase == ValidationPhase.SHADOW
        assert validator.stats.total_processed == 0
        assert len(validator.decisions) == 0

    def test_initialization_with_config(self):
        """Should respect configuration."""
        config = {"correlation_window_hours": 48}
        validator = ShadowModeValidator(config)

        assert validator.correlation_window_hours == 48


class TestRecordingDecisions:
    """Test decision recording functionality."""

    @pytest.fixture
    def validator(self):
        return ShadowModeValidator()

    @pytest.mark.asyncio
    async def test_record_decision(self, validator):
        """Should record classification decisions."""
        prediction = Prediction(
            category="routine",
            confidence=0.85,
            model="ensemble"
        )
        log = {"message": "User logged in", "source": "auth-server"}

        decision = await validator.record_decision("log-001", prediction, log)

        assert decision.log_id == "log-001"
        assert decision.ai_category == "routine"
        assert decision.ai_confidence == 0.85
        assert validator.stats.total_processed == 1
        assert validator.stats.by_category["routine"] == 1

    @pytest.mark.asyncio
    async def test_record_multiple_decisions(self, validator):
        """Should track multiple decisions."""
        categories = ["critical", "suspicious", "routine", "noise"]

        for i, category in enumerate(categories):
            prediction = Prediction(
                category=category,
                confidence=0.8,
                model="ensemble"
            )
            await validator.record_decision(
                f"log-{i}",
                prediction,
                {"message": f"Log {i}", "source": "test"}
            )

        assert validator.stats.total_processed == 4
        for category in categories:
            assert validator.stats.by_category[category] == 1


class TestQRadarResultRecording:
    """Test QRadar result recording and accuracy calculation."""

    @pytest.fixture
    def validator(self):
        return ShadowModeValidator()

    @pytest.mark.asyncio
    async def test_true_positive(self, validator):
        """AI says critical, QRadar generates offense = True Positive."""
        prediction = Prediction(category="critical", confidence=0.9, model="ensemble")
        await validator.record_decision("log-001", prediction, {"message": "Malware", "source": "av"})

        await validator.record_qradar_result(
            "log-001",
            offense_generated=True,
            offense_data={"offense_id": "123", "offense_type": "Malware"}
        )

        assert validator.stats.true_positives == 1
        assert validator.stats.false_negatives == 0

    @pytest.mark.asyncio
    async def test_true_negative(self, validator):
        """AI says routine, no offense = True Negative."""
        prediction = Prediction(category="routine", confidence=0.8, model="ensemble")
        await validator.record_decision("log-001", prediction, {"message": "Normal", "source": "app"})

        await validator.record_qradar_result("log-001", offense_generated=False)

        assert validator.stats.true_negatives == 1
        assert validator.stats.false_negatives == 0

    @pytest.mark.asyncio
    async def test_false_negative(self, validator):
        """AI says routine, QRadar generates offense = FALSE NEGATIVE (critical!)."""
        prediction = Prediction(category="routine", confidence=0.7, model="ensemble")
        await validator.record_decision("log-001", prediction, {"message": "Sneaky attack", "source": "fw"})

        await validator.record_qradar_result(
            "log-001",
            offense_generated=True,
            offense_data={"offense_id": "999", "offense_type": "Intrusion"}
        )

        assert validator.stats.false_negatives == 1
        assert len(validator.stats.missed_offenses) == 1

        decision = validator.decisions["log-001"]
        assert decision.is_false_negative

    @pytest.mark.asyncio
    async def test_false_positive(self, validator):
        """AI says critical, no offense = False Positive."""
        prediction = Prediction(category="critical", confidence=0.75, model="ensemble")
        await validator.record_decision("log-001", prediction, {"message": "Maybe bad?", "source": "ids"})

        await validator.record_qradar_result("log-001", offense_generated=False)

        assert validator.stats.false_positives == 1

        decision = validator.decisions["log-001"]
        assert decision.is_false_positive


class TestAccuracyMetrics:
    """Test accuracy metric calculations."""

    @pytest_asyncio.fixture
    async def validated_validator(self):
        """Create a validator with various outcomes."""
        validator = ShadowModeValidator()

        # 10 True Positives (critical -> offense)
        for i in range(10):
            pred = Prediction(category="critical", confidence=0.9, model="ensemble")
            await validator.record_decision(f"tp-{i}", pred, {"message": "Attack", "source": "ids"})
            await validator.record_qradar_result(f"tp-{i}", True, {"offense_type": "Attack"})

        # 80 True Negatives (routine -> no offense)
        for i in range(80):
            pred = Prediction(category="routine", confidence=0.8, model="ensemble")
            await validator.record_decision(f"tn-{i}", pred, {"message": "Normal", "source": "app"})
            await validator.record_qradar_result(f"tn-{i}", False)

        # 5 False Positives (critical -> no offense)
        for i in range(5):
            pred = Prediction(category="critical", confidence=0.7, model="ensemble")
            await validator.record_decision(f"fp-{i}", pred, {"message": "Maybe?", "source": "ids"})
            await validator.record_qradar_result(f"fp-{i}", False)

        # 1 False Negative (routine -> offense) - BAD!
        pred = Prediction(category="routine", confidence=0.6, model="ensemble")
        await validator.record_decision("fn-0", pred, {"message": "Missed attack", "source": "fw"})
        await validator.record_qradar_result("fn-0", True, {"offense_type": "Intrusion"})

        return validator

    @pytest.mark.asyncio
    async def test_accuracy_calculation(self, validated_validator):
        """Should calculate accuracy metrics correctly."""
        metrics = validated_validator.get_accuracy_metrics()

        assert metrics["total_validated"] == 96
        assert metrics["confusion_matrix"]["tp"] == 10
        assert metrics["confusion_matrix"]["tn"] == 80
        assert metrics["confusion_matrix"]["fp"] == 5
        assert metrics["confusion_matrix"]["fn"] == 1

    @pytest.mark.asyncio
    async def test_recall_calculation(self, validated_validator):
        """Should calculate recall correctly."""
        metrics = validated_validator.get_accuracy_metrics()

        # Recall = TP / (TP + FN) = 10 / (10 + 1) = 0.909...
        expected_recall = 10 / 11
        assert abs(metrics["recall"] - expected_recall) < 0.01

    @pytest.mark.asyncio
    async def test_false_negative_rate(self, validated_validator):
        """Should calculate false negative rate correctly."""
        metrics = validated_validator.get_accuracy_metrics()

        # FNR = FN / (TP + FN) = 1 / 11 = 0.0909...
        expected_fnr = 1 / 11
        assert abs(metrics["false_negative_rate"] - expected_fnr) < 0.01


class TestPhaseTransitions:
    """Test validation phase transitions."""

    @pytest.fixture
    def validator(self):
        return ShadowModeValidator()

    def test_initial_phase_is_shadow(self, validator):
        """Should start in shadow phase."""
        assert validator.stats.phase == ValidationPhase.SHADOW

    @pytest.mark.asyncio
    async def test_not_ready_with_insufficient_samples(self, validator):
        """Should not be ready without enough samples."""
        ready, reason = validator.is_ready_for_next_phase()

        assert not ready
        assert "samples" in reason.lower()

    @pytest.mark.asyncio
    async def test_not_ready_with_high_fnr(self, validator):
        """Should not be ready if false negative rate too high."""
        # Create many samples with high FNR
        for i in range(10000):
            pred = Prediction(category="routine", confidence=0.8, model="ensemble")
            await validator.record_decision(f"log-{i}", pred, {"message": "Log", "source": "test"})

        # Add lots of false negatives (above 0.5% threshold)
        for i in range(100):
            await validator.record_qradar_result(f"log-{i}", True, {"offense_type": "Attack"})

        # Add some true negatives
        for i in range(100, 10000):
            await validator.record_qradar_result(f"log-{i}", False)

        ready, reason = validator.is_ready_for_next_phase()

        # Should fail on FNR or recall
        assert not ready


class TestValidationReport:
    """Test validation report generation."""

    @pytest.mark.asyncio
    async def test_report_generation(self):
        """Should generate comprehensive report."""
        validator = ShadowModeValidator()

        # Add some data
        pred = Prediction(category="critical", confidence=0.9, model="ensemble")
        await validator.record_decision("log-1", pred, {"message": "Attack", "source": "ids"})
        await validator.record_qradar_result("log-1", True)

        report = validator.get_validation_report()

        assert "phase" in report
        assert "metrics" in report
        assert "ready_for_next_phase" in report
        assert report["phase"] == "shadow"


class TestFactoryFunction:
    """Test factory function."""

    def test_create_shadow_validator(self):
        """Factory should create validator correctly."""
        validator = create_shadow_validator({"correlation_window_hours": 12})

        assert isinstance(validator, ShadowModeValidator)
        assert validator.correlation_window_hours == 12

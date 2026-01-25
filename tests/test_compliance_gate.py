"""
Tests for Compliance Gate

Tests the compliance bypass functionality for regulated logs.
"""

import pytest

from src.preprocessing.compliance_gate import (
    ComplianceDecision,
    ComplianceFramework,
    ComplianceGate,
    ComplianceRule,
    create_compliance_bypass_prediction,
)


class TestComplianceGateBasics:
    """Test basic compliance gate functionality."""

    @pytest.fixture
    def gate(self):
        """Create a compliance gate with default rules."""
        return ComplianceGate({"enabled": True})

    def test_gate_initialization(self, gate):
        """Gate should initialize with default rules."""
        assert gate.enabled
        assert len(gate.rules) > 0

        # Should have rules for major frameworks
        frameworks = {r.framework for r in gate.rules}
        assert ComplianceFramework.PCI_DSS in frameworks
        assert ComplianceFramework.HIPAA in frameworks
        assert ComplianceFramework.SOX in frameworks

    def test_non_regulated_log_passes_through(self, gate):
        """Non-regulated logs should not be bypassed."""
        log = {
            "source": "web-server-01",
            "message": "User logged in successfully"
        }

        decision = gate.check(log)

        assert not decision.is_regulated
        assert not decision.must_forward
        assert len(decision.matched_rules) == 0

    def test_pci_source_is_regulated(self, gate):
        """PCI source patterns should trigger bypass."""
        log = {
            "source": "pci_payment_gateway",
            "message": "Transaction processed"
        }

        decision = gate.check(log)

        assert decision.is_regulated
        assert decision.must_forward
        assert ComplianceFramework.PCI_DSS in decision.frameworks

    def test_hipaa_source_is_regulated(self, gate):
        """HIPAA source patterns should trigger bypass."""
        log = {
            "source": "ehr_patient_records",
            "message": "Patient record accessed"
        }

        decision = gate.check(log)

        assert decision.is_regulated
        assert decision.must_forward
        assert ComplianceFramework.HIPAA in decision.frameworks

    def test_sox_source_is_regulated(self, gate):
        """SOX source patterns should trigger bypass."""
        log = {
            "source": "financial_trading_system",
            "message": "Trade executed"
        }

        decision = gate.check(log)

        assert decision.is_regulated
        assert decision.must_forward
        assert ComplianceFramework.SOX in decision.frameworks

    def test_message_pattern_matching(self, gate):
        """Message patterns should also trigger bypass."""
        log = {
            "source": "generic-app",
            "message": "Accessing cardholder data for customer 12345"
        }

        decision = gate.check(log)

        assert decision.is_regulated
        assert ComplianceFramework.PCI_DSS in decision.frameworks


class TestComplianceGateRetention:
    """Test retention requirements."""

    @pytest.fixture
    def gate(self):
        return ComplianceGate({"enabled": True})

    def test_pci_retention_365_days(self, gate):
        """PCI-DSS should require 365 days retention."""
        log = {"source": "pci_system", "message": "Payment processed"}
        decision = gate.check(log)

        assert decision.minimum_retention_days >= 365

    def test_hipaa_retention_6_years(self, gate):
        """HIPAA should require 6 years (2190 days) retention."""
        log = {"source": "hipaa_records", "message": "PHI accessed"}
        decision = gate.check(log)

        assert decision.minimum_retention_days >= 2190

    def test_sox_retention_7_years(self, gate):
        """SOX should require 7 years (2555 days) retention."""
        log = {"source": "financial_audit", "message": "Audit log entry"}
        decision = gate.check(log)

        assert decision.minimum_retention_days >= 2555


class TestComplianceGateDisabled:
    """Test disabled compliance gate."""

    def test_disabled_gate_allows_all(self):
        """Disabled gate should not bypass any logs."""
        gate = ComplianceGate({"enabled": False})

        log = {"source": "pci_payment_system", "message": "Card transaction"}
        decision = gate.check(log)

        assert not decision.is_regulated
        assert not decision.must_forward


class TestComplianceGateCustomRules:
    """Test custom compliance rules."""

    def test_add_custom_rule(self):
        """Should be able to add custom rules."""
        gate = ComplianceGate({"enabled": True})

        custom_rule = ComplianceRule(
            name="custom_sensitive",
            framework=ComplianceFramework.CUSTOM,
            description="Custom sensitive data",
            source_patterns=[r"^custom_sensitive_"],
            message_patterns=[r"secret_data"],
            minimum_retention_days=730
        )

        gate.add_rule(custom_rule)

        log = {"source": "custom_sensitive_app", "message": "Processing data"}
        decision = gate.check(log)

        assert decision.is_regulated
        assert "custom_sensitive" in decision.matched_rules


class TestComplianceGateStats:
    """Test compliance gate statistics."""

    def test_stats_tracking(self):
        """Should track bypass statistics."""
        gate = ComplianceGate({"enabled": True})

        # Check some logs
        gate.check({"source": "pci_system", "message": "Payment"})
        gate.check({"source": "hipaa_records", "message": "PHI"})
        gate.check({"source": "regular_app", "message": "Normal log"})
        gate.check({"source": "financial_audit", "message": "Audit"})

        stats = gate.get_stats()

        assert stats["total_checked"] == 4
        assert stats["total_bypassed"] == 3
        assert stats["bypass_rate_percent"] == 75.0


class TestComplianceBypassPrediction:
    """Test compliance bypass prediction creation."""

    def test_bypass_prediction_is_critical(self):
        """Bypass predictions should be marked as critical."""
        log = {"source": "pci_system", "message": "Payment processed"}
        decision = ComplianceDecision(
            is_regulated=True,
            matched_rules=["pci_payment_systems"],
            frameworks={ComplianceFramework.PCI_DSS},
            must_forward=True,
            minimum_retention_days=365,
            bypass_reason="Matched PCI-DSS rules"
        )

        prediction = create_compliance_bypass_prediction(log, decision)

        assert prediction["category"] == "critical"
        assert prediction["confidence"] == 1.0
        assert prediction["model"] == "compliance_bypass"
        assert prediction["explanation"]["ai_classification_skipped"]

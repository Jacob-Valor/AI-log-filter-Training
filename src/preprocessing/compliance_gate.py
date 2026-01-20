"""
Compliance Gate

Ensures regulated logs (PCI-DSS, HIPAA, SOX, etc.) bypass AI filtering
and are sent directly to QRadar. This provides a safety mechanism to
guarantee compliance-critical logs are never filtered out.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    SOX = "sox"
    GDPR = "gdpr"
    GLBA = "glba"
    FERPA = "ferpa"
    CUSTOM = "custom"


@dataclass
class ComplianceRule:
    """A single compliance rule definition."""
    name: str
    framework: ComplianceFramework
    description: str
    source_patterns: List[str]
    message_patterns: List[str] = field(default_factory=list)
    minimum_retention_days: int = 365
    must_forward_to_siem: bool = True
    priority: int = 100  # Higher = more important


@dataclass
class ComplianceDecision:
    """Result of compliance check."""
    is_regulated: bool
    matched_rules: List[str]
    frameworks: Set[ComplianceFramework]
    must_forward: bool
    minimum_retention_days: int
    bypass_reason: Optional[str] = None


class ComplianceGate:
    """
    Compliance gate for bypassing AI filtering on regulated logs.

    This component sits before the AI classifier and checks if incoming
    logs should bypass classification entirely and be forwarded directly
    to QRadar. This ensures compliance-critical logs are never filtered.

    Supports multiple compliance frameworks:
    - PCI-DSS: Payment card industry data
    - HIPAA: Healthcare information
    - SOX: Financial/accounting data
    - GDPR: Personal data (EU)
    - Custom: Organization-specific rules

    Example:
        gate = ComplianceGate(config)
        decision = gate.check(log)
        if decision.is_regulated:
            route_directly_to_qradar(log)
        else:
            proceed_to_classification(log)
    """

    # Default compliance rules
    DEFAULT_RULES = [
        # PCI-DSS Rules
        ComplianceRule(
            name="pci_payment_systems",
            framework=ComplianceFramework.PCI_DSS,
            description="Payment processing and cardholder data systems",
            source_patterns=[
                r"^pci[-_]",
                r"^payment[-_]",
                r"^cardholder[-_]",
                r"^pos[-_]",
                r"^card[-_]processing",
            ],
            message_patterns=[
                r"card[-_]?holder",
                r"pan[-_]?data",
                r"payment[-_]?transaction",
                r"credit[-_]?card",
                r"cvv|cvc|cvn",
            ],
            minimum_retention_days=365,
        ),
        ComplianceRule(
            name="pci_network_security",
            framework=ComplianceFramework.PCI_DSS,
            description="PCI network security devices",
            source_patterns=[
                r"^pci[-_]?firewall",
                r"^pci[-_]?ids",
                r"^pci[-_]?waf",
                r"^cde[-_]",  # Cardholder Data Environment
            ],
            minimum_retention_days=365,
        ),

        # HIPAA Rules
        ComplianceRule(
            name="hipaa_phi_systems",
            framework=ComplianceFramework.HIPAA,
            description="Protected Health Information systems",
            source_patterns=[
                r"^hipaa[-_]",
                r"^ehr[-_]",
                r"^emr[-_]",
                r"^patient[-_]",
                r"^phi[-_]",
                r"^medical[-_]",
                r"^healthcare[-_]",
            ],
            message_patterns=[
                r"patient[-_]?id",
                r"medical[-_]?record",
                r"diagnosis",
                r"treatment[-_]?plan",
                r"phi[-_]?access",
                r"hipaa[-_]?audit",
            ],
            minimum_retention_days=2190,  # 6 years for HIPAA
        ),

        # SOX Rules
        ComplianceRule(
            name="sox_financial_systems",
            framework=ComplianceFramework.SOX,
            description="Financial reporting and trading systems",
            source_patterns=[
                r"^financial[-_]",
                r"^accounting[-_]",
                r"^trading[-_]",
                r"^sox[-_]",
                r"^erp[-_]",
                r"^audit[-_]",
                r"^treasury[-_]",
            ],
            message_patterns=[
                r"financial[-_]?transaction",
                r"journal[-_]?entry",
                r"general[-_]?ledger",
                r"audit[-_]?trail",
                r"fiscal[-_]?close",
            ],
            minimum_retention_days=2555,  # 7 years for SOX
        ),

        # GDPR Rules
        ComplianceRule(
            name="gdpr_personal_data",
            framework=ComplianceFramework.GDPR,
            description="EU personal data processing",
            source_patterns=[
                r"^gdpr[-_]",
                r"^eu[-_]?personal",
                r"^pii[-_]",
                r"^customer[-_]?data",
            ],
            message_patterns=[
                r"personal[-_]?data",
                r"data[-_]?subject",
                r"consent[-_]?",
                r"right[-_]?to[-_]?(erasure|forget)",
            ],
            minimum_retention_days=365,
        ),
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize compliance gate.

        Args:
            config: Configuration dictionary with:
                - enabled: bool, whether compliance gate is active
                - rules: list of custom rule definitions
                - additional_source_patterns: dict of framework -> patterns
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.rules: List[ComplianceRule] = []
        self.compiled_patterns: Dict[str, List[Tuple[str, re.Pattern]]] = {}

        self._load_rules()
        self._compile_patterns()

        # Statistics
        self.stats = {
            "total_checked": 0,
            "total_bypassed": 0,
            "bypasses_by_framework": {f.value: 0 for f in ComplianceFramework}
        }

        logger.info(
            f"Compliance gate initialized with {len(self.rules)} rules",
            extra={"enabled": self.enabled, "rule_count": len(self.rules)}
        )

    def _load_rules(self):
        """Load default and custom rules."""
        # Load default rules
        self.rules.extend(self.DEFAULT_RULES)

        # Load custom rules from config
        custom_rules = self.config.get("custom_rules", [])
        for rule_def in custom_rules:
            try:
                framework = ComplianceFramework(
                    rule_def.get("framework", "custom")
                )
                rule = ComplianceRule(
                    name=rule_def["name"],
                    framework=framework,
                    description=rule_def.get("description", ""),
                    source_patterns=rule_def.get("source_patterns", []),
                    message_patterns=rule_def.get("message_patterns", []),
                    minimum_retention_days=rule_def.get("minimum_retention_days", 365),
                    must_forward_to_siem=rule_def.get("must_forward_to_siem", True),
                    priority=rule_def.get("priority", 50),
                )
                self.rules.append(rule)
                logger.debug(f"Loaded custom compliance rule: {rule.name}")
            except Exception as e:
                logger.warning(f"Failed to load custom rule: {e}")

        # Load additional source patterns from config
        additional = self.config.get("additional_source_patterns", {})
        for framework_name, patterns in additional.items():
            try:
                framework = ComplianceFramework(framework_name)
                rule = ComplianceRule(
                    name=f"additional_{framework_name}",
                    framework=framework,
                    description=f"Additional {framework_name} patterns",
                    source_patterns=patterns,
                )
                self.rules.append(rule)
            except Exception as e:
                logger.warning(f"Failed to load additional patterns for {framework_name}: {e}")

    def _compile_patterns(self):
        """Compile regex patterns for performance."""
        self.compiled_patterns = {
            "source": [],
            "message": [],
        }

        for rule in self.rules:
            for pattern in rule.source_patterns:
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    self.compiled_patterns["source"].append((rule.name, compiled))
                except re.error as e:
                    logger.warning(f"Invalid source pattern in {rule.name}: {e}")

            for pattern in rule.message_patterns:
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    self.compiled_patterns["message"].append((rule.name, compiled))
                except re.error as e:
                    logger.warning(f"Invalid message pattern in {rule.name}: {e}")

        logger.debug(
            f"Compiled {len(self.compiled_patterns['source'])} source patterns, "
            f"{len(self.compiled_patterns['message'])} message patterns"
        )

    def check(self, log: Dict[str, Any]) -> ComplianceDecision:
        """
        Check if a log should bypass AI filtering.

        Args:
            log: Log entry with 'source', 'message', and optional metadata

        Returns:
            ComplianceDecision indicating whether to bypass filtering
        """
        if not self.enabled:
            return ComplianceDecision(
                is_regulated=False,
                matched_rules=[],
                frameworks=set(),
                must_forward=False,
                minimum_retention_days=0,
            )

        self.stats["total_checked"] += 1

        source = log.get("source", "")
        message = log.get("message", "")

        matched_rules = set()
        matched_frameworks = set()
        max_retention = 0

        # Check source patterns
        for rule_name, pattern in self.compiled_patterns["source"]:
            if pattern.search(source):
                matched_rules.add(rule_name)

        # Check message patterns
        for rule_name, pattern in self.compiled_patterns["message"]:
            if pattern.search(message):
                matched_rules.add(rule_name)

        # Get framework and retention info for matched rules
        for rule in self.rules:
            if rule.name in matched_rules:
                matched_frameworks.add(rule.framework)
                max_retention = max(max_retention, rule.minimum_retention_days)

        is_regulated = len(matched_rules) > 0

        if is_regulated:
            self.stats["total_bypassed"] += 1
            for framework in matched_frameworks:
                self.stats["bypasses_by_framework"][framework.value] += 1

            bypass_reason = (
                f"Matched compliance rules: {', '.join(matched_rules)}. "
                f"Frameworks: {', '.join(f.value for f in matched_frameworks)}"
            )

            logger.debug(
                "Log bypasses AI filtering due to compliance",
                extra={
                    "source": source[:50],
                    "matched_rules": list(matched_rules),
                    "frameworks": [f.value for f in matched_frameworks],
                }
            )
        else:
            bypass_reason = None

        return ComplianceDecision(
            is_regulated=is_regulated,
            matched_rules=list(matched_rules),
            frameworks=matched_frameworks,
            must_forward=is_regulated,
            minimum_retention_days=max_retention,
            bypass_reason=bypass_reason,
        )

    def check_batch(self, logs: List[Dict[str, Any]]) -> List[ComplianceDecision]:
        """Check a batch of logs for compliance requirements."""
        return [self.check(log) for log in logs]

    def add_rule(self, rule: ComplianceRule):
        """Add a new compliance rule dynamically."""
        self.rules.append(rule)

        # Recompile patterns
        for pattern in rule.source_patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self.compiled_patterns["source"].append((rule.name, compiled))
            except re.error:
                pass

        for pattern in rule.message_patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self.compiled_patterns["message"].append((rule.name, compiled))
            except re.error:
                pass

        logger.info(f"Added compliance rule: {rule.name}")

    def get_stats(self) -> Dict[str, Any]:
        """Get compliance gate statistics."""
        bypass_rate = (
            self.stats["total_bypassed"] / max(self.stats["total_checked"], 1)
        ) * 100

        return {
            **self.stats,
            "bypass_rate_percent": round(bypass_rate, 2),
            "rule_count": len(self.rules),
            "enabled": self.enabled,
        }

    def get_rules_by_framework(
        self, framework: ComplianceFramework
    ) -> List[ComplianceRule]:
        """Get all rules for a specific framework."""
        return [r for r in self.rules if r.framework == framework]


def create_compliance_bypass_prediction(
    log: Dict[str, Any],
    decision: ComplianceDecision
) -> Dict[str, Any]:
    """
    Create a prediction object for compliance-bypassed logs.

    These logs are marked as critical and forwarded to QRadar
    without AI classification.
    """
    return {
        "category": "critical",  # Ensure it goes to QRadar
        "confidence": 1.0,
        "model": "compliance_bypass",
        "explanation": {
            "bypass_reason": decision.bypass_reason,
            "matched_rules": decision.matched_rules,
            "frameworks": [f.value for f in decision.frameworks],
            "minimum_retention_days": decision.minimum_retention_days,
            "ai_classification_skipped": True,
        },
        "metadata": {
            "compliance_regulated": True,
            "retention_days": decision.minimum_retention_days,
        }
    }

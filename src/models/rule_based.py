"""
Rule-Based Classifier

Uses predefined regex patterns and rules for log classification.
Provides high-precision classification for known patterns.
"""

import re
from typing import Any

import yaml

from src.models.base import BaseClassifier, ClassifierRegistry, Prediction
from src.utils.logging import get_logger

logger = get_logger(__name__)


@ClassifierRegistry.register("rule_based")
class RuleBasedClassifier(BaseClassifier):
    """
    Rule-based log classifier using regex patterns.

    Applies predefined rules in priority order to classify logs.
    High confidence for matching rules, provides baseline classification.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("rule_based", config)
        self.rules: dict[str, list[dict[str, Any]]] = {}
        self.compiled_rules: dict[str, list[tuple[str, re.Pattern, float]]] = {}
        self.priority_order = ["critical", "suspicious", "noise", "routine"]
        self.default_category = "routine"
        self.default_confidence = 0.5

    async def load(self):
        """Load rules from configuration file."""
        rules_path = self.config.get("rules_path", "configs/rules.yaml")

        try:
            with open(rules_path) as f:
                rules_config = yaml.safe_load(f)

            self._compile_rules(rules_config)
            self.is_loaded = True
            logger.info(f"Loaded {sum(len(r) for r in self.compiled_rules.values())} rules")

        except FileNotFoundError:
            logger.warning(f"Rules file not found: {rules_path}, using default rules")
            self._load_default_rules()
            self.is_loaded = True
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
            raise

    def _compile_rules(self, rules_config: dict[str, Any]):
        """Compile regex patterns from rules configuration."""
        settings = rules_config.get("settings", {})
        self.priority_order = settings.get("priority_order", self.priority_order)
        self.default_category = settings.get("default_category", self.default_category)
        self.default_confidence = settings.get("default_confidence", self.default_confidence)

        case_insensitive = settings.get("case_insensitive", True)
        flags = re.IGNORECASE if case_insensitive else 0

        for category in self.CATEGORIES:
            self.compiled_rules[category] = []

            if category in rules_config:
                for rule in rules_config[category]:
                    rule_name = rule.get("name", "unnamed")
                    confidence = rule.get("confidence", 0.8)

                    for pattern in rule.get("patterns", []):
                        try:
                            compiled = re.compile(pattern, flags)
                            self.compiled_rules[category].append((rule_name, compiled, confidence))
                        except re.error as e:
                            logger.warning(f"Invalid regex pattern in rule {rule_name}: {e}")

    def _load_default_rules(self):
        """Load minimal default rules."""
        default_rules = {
            "critical": [
                ("malware", re.compile(r"malware|virus|trojan|ransomware", re.I), 0.95),
                ("brute_force", re.compile(r"brute.?force|multiple.*fail.*auth", re.I), 0.90),
            ],
            "suspicious": [
                (
                    "failed_auth",
                    re.compile(r"failed.*(login|auth)|authentication.*fail", re.I),
                    0.75,
                ),
                ("access_denied", re.compile(r"access.*denied|permission.*denied", re.I), 0.70),
            ],
            "noise": [
                ("health_check", re.compile(r"health.?check|heartbeat|keep.?alive", re.I), 0.90),
                ("debug", re.compile(r"^\s*(DEBUG|TRACE)", re.I), 0.85),
            ],
            "routine": [
                ("success", re.compile(r"success|completed|started", re.I), 0.60),
            ],
        }
        self.compiled_rules = default_rules

    async def predict(self, text: str) -> Prediction:
        """Classify a single log message using rules."""
        if not self.is_loaded:
            await self.load()

        # Check rules in priority order
        for category in self.priority_order:
            for rule_name, pattern, confidence in self.compiled_rules.get(category, []):
                if pattern.search(text):
                    return Prediction(
                        category=category,
                        confidence=confidence,
                        model=self.name,
                        explanation={"matched_rule": rule_name},
                    )

        # No rule matched, return default
        return Prediction(
            category=self.default_category,
            confidence=self.default_confidence,
            model=self.name,
            explanation={"matched_rule": None},
        )

    async def predict_batch(self, texts: list[str]) -> list[Prediction]:
        """Classify a batch of log messages."""
        return [await self.predict(text) for text in texts]

    def get_matching_rules(self, text: str) -> list[dict[str, Any]]:
        """Get all rules that match a given text."""
        matches = []

        for category in self.CATEGORIES:
            for rule_name, pattern, confidence in self.compiled_rules.get(category, []):
                match = pattern.search(text)
                if match:
                    matches.append(
                        {
                            "category": category,
                            "rule": rule_name,
                            "confidence": confidence,
                            "match": match.group(0),
                        }
                    )

        return matches

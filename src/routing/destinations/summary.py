import re
from datetime import UTC, datetime
from typing import Any

from src.routing.destinations.base import BaseDestination
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SummaryDestination(BaseDestination):
    """Aggregate and summarize noise logs."""

    def __init__(self, config: dict[str, Any]):
        super().__init__("summary", config)
        self.window_seconds = config.get("aggregation_window_seconds", 3600)
        self.summaries: dict[str, dict[str, Any]] = {}

    async def send(self, logs: list[dict[str, Any]]):
        """Aggregate logs into summaries."""
        for log in logs:
            # Create summary key from log template
            template = self._extract_template(log.get("message", ""))

            if template not in self.summaries:
                self.summaries[template] = {
                    "template": template,
                    "count": 0,
                    "first_seen": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "last_seen": None,
                    "sample": log,
                }

            self.summaries[template]["count"] += 1
            self.summaries[template]["last_seen"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )

        logger.debug("Aggregated %s logs into %s summaries", len(logs), len(self.summaries))

    def _extract_template(self, message: str) -> str:
        """Extract template from message by replacing variables."""
        # Replace IPs
        template = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<IP>", message)
        # Replace numbers
        template = re.sub(r"\b\d+\b", "<NUM>", template)
        # Replace UUIDs
        template = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "<UUID>",
            template,
            flags=re.IGNORECASE,
        )

        return template[:200]  # Limit template length

    async def get_summaries(self) -> list[dict[str, Any]]:
        """Get current summaries."""
        return list(self.summaries.values())

    async def close(self):
        """Export final summaries."""
        if self.summaries:
            logger.info("Final summary: %s unique log patterns", len(self.summaries))
